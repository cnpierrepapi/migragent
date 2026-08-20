"""The people worth speaking to at an employer, found through Google Search.

WHERE THIS CAME FROM AND WHAT CHANGED
-------------------------------------
This is the one feature ported from `dossier`, which did it in TypeScript against
a search API. Two things changed on the way across: it is Python on Gemini, and
the search is Vertex's own Google Search grounding rather than a third party.

That was a decision with a real cost attached and it was made deliberately. The
rest of this product refuses to touch what robots.txt will not let it crawl.
Search grounding does not crawl at all, it reads an index of pages somebody else
fetched, so the gate does not apply to it and cannot. What that means in practice
is written down rather than glossed: **people found this way are labelled as
found through Google Search, with the sources the model was given, and never
presented as something this pipeline read.** The robots gate still governs every
byte we fetch ourselves, which is everything else in the system.

WHAT THE FIRST REAL RUN SHOWED, BEFORE ANY OF THIS WAS BUILT
------------------------------------------------------------
Asked about "Nomad Hauling Inc", a small hauling firm in Merritt, British
Columbia, grounding fired thirty-seven searches and answered confidently about
Nomad Inc, an AI fleet management platform in Toronto. Different company, same
first word.

That is the Chicago Booth failure again: a true answer about the wrong subject,
which no quote check catches because nothing is invented. So the guard comes
first here rather than being added after somebody notices.

  - The model must name the company it actually found, and that name is checked
    against the employer on the listing before a single person is kept.
  - It must say where the company is, and that is checked against the location on
    the listing too, because two real companies share a name more often than two
    share a name and a town.
  - A person with no source is dropped, and the source has to be one the search
    actually returned.

WHY THIS TAKES TWO CALLS
------------------------
Asking for grounding and a JSON answer in one call returns no sources. Measured:
a grounded call answering in prose came back with five `groundingChunks`, each a
real page with a title and a link, and the same call asked for JSON came back
with `webSearchQueries` and nothing else. The model still names sites in the
JSON, from memory, and those names cannot be checked against anything.

Naming a real person at a real company on a source the model made up is not a
feature worth shipping. So: one grounded call that answers in prose and hands
back its sources, then one ordinary call that turns that prose into rows, and
every person's source must be one of the sources the first call actually
returned. Same discipline as everywhere else, applied to the one part of this
product that reaches outside it.

WHAT IS NEVER STORED
--------------------
No contact details. Not an email, not a phone number, not a personal address.
The point of this is "here is who does this job and why they are worth a message
on LinkedIn", not a lead list. Anything that looks like a contact detail is
stripped in code rather than asked for in the prompt.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .model import ModelError, _json_from, call_content

# One shape for "found through search rather than crawled". It travels with the
# rows and appears on the screen.
FOUND_VIA = "google_search_grounding"

_WORDS = re.compile(r"[^a-z0-9]+")

# Words that carry no identity. "Nomad Hauling Inc" and "Nomad Inc" share only
# "nomad" once these go, which is what lets the guard tell them apart.
_NOISE = {"inc", "incorporated", "ltd", "limited", "llc", "llp", "corp",
          "corporation", "company", "co", "group", "holdings", "the", "and",
          "of", "services", "service", "solutions", "international", "canada",
          "enterprises"}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\-\s().]{7,}\d)")


def _significant(name: str) -> set[str]:
    return {w for w in _WORDS.sub(" ", (name or "").lower()).split()
            if w and w not in _NOISE and len(w) > 1}


def same_company(asked: str, found: str) -> bool:
    """Whether the company the model found is the one on the listing.

    Every significant word of the shorter name must appear in the longer one,
    the same rule the institution shares use. It accepts "Nomad Hauling" against
    "Nomad Hauling Inc." and rejects "Nomad Inc" against "Nomad Hauling Inc",
    which is the case that actually happened.
    """
    a, b = _significant(asked), _significant(found)
    if not a or not b:
        return False
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)

    # A subset rule alone lets a one word name swallow a longer one: "Nomad Inc"
    # is a subset of "Nomad Hauling Inc" and would pass, which is the precise
    # failure this function was written for. So a single significant word has to
    # match exactly, and only a name with two or more may be a subset of a
    # longer one.
    if len(smaller) == 1:
        return smaller == larger
    return smaller.issubset(larger)


def same_place(asked: str, found: str) -> bool:
    """Whether the company is where the listing says the job is.

    Loose on purpose: a listing says "Merritt (BC)" and a source says "Merritt,
    British Columbia". One shared significant word is enough, and an empty answer
    from either side is not treated as a contradiction, because plenty of real
    pages simply do not say.
    """
    a, b = _significant(asked), _significant(found)
    if not a or not b:
        return True
    return bool(a & b)


def strip_contacts(text: str) -> str:
    """Take out anything that looks like a way to contact somebody directly."""
    text = _EMAIL.sub("", text or "")
    return _PHONE.sub("", text).strip(" ,;·-")


@dataclass
class Person:
    """One person worth a message, and where they were found."""

    name: str
    role: str
    why: str
    source_title: str | None = None
    source_uri: str | None = None
    found_via: str = FOUND_VIA

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Finding:
    """What one search for an employer produced, including nothing."""

    employer: str
    read_at: str
    people: list[Person] = field(default_factory=list)
    company_found: str | None = None
    where_found: str | None = None
    sources: list[dict[str, str]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    refused_reason: str | None = None
    error: str | None = None

    @property
    def kept(self) -> int:
        return len(self.people)

    def to_dict(self) -> dict[str, Any]:
        row = {k: v for k, v in asdict(self).items() if v is not None}
        row["people"] = [p.to_dict() for p in self.people]
        return row


SEARCH_PROMPT = """Find out who works at one specific employer, in a professional capacity.

EMPLOYER: {employer}
WHERE THE JOB IS: {location}
THE ROLE BEING ADVERTISED: {title}

Search for this employer and read what is published about it.

Say clearly:
1. The full name of the company you found, and the town or city it is based in.
   There are companies with similar names and getting the wrong one is worse than
   finding nobody. If you cannot find this specific employer, say so plainly and
   stop.
2. Up to four people published as working there, with their job titles, and which
   published page each one came from.
3. For each, why they would be worth contacting about this role.

Only people published in a professional capacity. Never give an email address, a
phone number or a home address. If nothing is published about the people at this
company, say so: small employers usually publish nothing and that is a normal
answer."""


STRUCTURE_PROMPT = """Turn the notes below into rows. Add nothing that is not in them.

Return JSON:
{{"company_found": "the full company name in the notes",
  "where_found": "the town or city in the notes",
  "not_found": "a sentence if the notes say the company could not be found, else null",
  "people": [{{"name": "...", "role": "...", "why": "one line", "source_title": "..."}}]}}

"source_title" must be one of these, copied exactly, and a person whose source is
not one of them must be left out entirely:
{sources}

If the notes name no people, return an empty list.

THE NOTES:
{notes}"""


class PeopleFinder:
    """Finds people at an employer, with Google Search grounding."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def find(self, employer: str, location: str = "", title: str = "") -> Finding:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        finding = Finding(employer=employer, read_at=now)

        if not employer.strip():
            finding.refused_reason = "the listing does not name an employer"
            return finding

        # Step one: search, and answer in prose, because that is the only shape
        # that comes back with its sources attached.
        notes, error = self._search(employer, location, title, finding)
        if error:
            finding.error = error
            return finding
        if not finding.sources:
            finding.refused_reason = ("the search returned no sources to check anybody "
                                      "against, so nobody was recorded")
            return finding

        # Step two: turn the notes into rows, with no search and no memory of
        # the wider internet to draw on.
        parsed, why = self._structure(notes, finding)
        if parsed is None:
            finding.error = why
            return finding

        if parsed.get("not_found"):
            finding.refused_reason = str(parsed["not_found"])[:200]
            return finding

        finding.company_found = str(parsed.get("company_found") or "").strip() or None
        finding.where_found = str(parsed.get("where_found") or "").strip() or None

        # The guard, before anybody is kept.
        if not finding.company_found or not same_company(employer, finding.company_found):
            finding.refused_reason = (
                f"the search found {finding.company_found or 'no named company'}, "
                f"which is not {employer}")
            return finding
        if location and finding.where_found and not same_place(location, finding.where_found):
            finding.refused_reason = (
                f"the company found is in {finding.where_found}, and this job is in "
                f"{location}, so it is probably a different business of the same name")
            return finding

        titles = {source["title"].lower(): source for source in finding.sources}

        for item in parsed.get("people", []):
            name = strip_contacts(str(item.get("name") or "").strip())
            role = strip_contacts(str(item.get("role") or "").strip())
            claimed = str(item.get("source_title") or "").strip()

            if not name or not role:
                finding.dropped.append({"name": name, "why": "no name or no role"})
                continue

            source = titles.get(claimed.lower())
            if source is None:
                for key, candidate in titles.items():
                    if key and (key in claimed.lower() or claimed.lower() in key):
                        source = candidate
                        break
            if source is None:
                # Named a page the search did not return. On a feature that names
                # real people that is the difference between a record and a
                # rumour, so the person goes.
                finding.dropped.append({
                    "name": name, "why": f"the source {claimed or 'given'} is not one "
                                         f"the search returned"})
                continue

            finding.people.append(Person(
                name=name, role=role,
                why=strip_contacts(str(item.get("why") or "").strip()),
                source_title=source["title"][:120],
                source_uri=source["uri"] or None,
            ))

        return finding

    def _search(self, employer: str, location: str, title: str,
                finding: Finding) -> tuple[str, str]:
        """The grounded call. Returns its prose, and fills in the sources."""
        body = {
            "contents": [{"role": "user", "parts": [{"text": SEARCH_PROMPT.format(
                employer=employer, location=location or "not stated",
                title=title or "not stated")}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 8192},
        }
        try:
            payload = call_content(project=self._project, model=self._model,
                                   location=self._location,
                                   credentials=self._credentials, body=body,
                                   interactive=True)
        except ModelError as exc:
            return "", str(exc)

        candidate = (payload.get("candidates") or [{}])[0]
        grounding = candidate.get("groundingMetadata") or {}
        finding.queries = list(grounding.get("webSearchQueries") or [])[:12]
        for chunk in (grounding.get("groundingChunks") or [])[:12]:
            web = chunk.get("web") or {}
            if web.get("title"):
                finding.sources.append({"title": web.get("title", ""),
                                        "uri": web.get("uri", "")})

        notes = "".join(part.get("text", "")
                        for part in (candidate.get("content") or {}).get("parts", []))
        return notes, "" if notes.strip() else "the search returned nothing to read"

    def _structure(self, notes: str, finding: Finding):
        """The ordinary call. No search, so nothing new can arrive here."""
        listed = "\n".join(f'- {source["title"]}' for source in finding.sources)
        body = {
            "contents": [{"role": "user", "parts": [{"text": STRUCTURE_PROMPT.format(
                sources=listed, notes=notes[:12000])}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4096,
                                 "responseMimeType": "application/json"},
        }
        try:
            payload = call_content(project=self._project, model=self._model,
                                   location=self._location,
                                   credentials=self._credentials, body=body,
                                   interactive=True)
        except ModelError as exc:
            return None, str(exc)
        return _json_from(payload)
