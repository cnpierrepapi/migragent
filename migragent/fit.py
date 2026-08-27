"""How well a CV fits one job posting, computed from the posting's own words.

WHAT THE NUMBER MEANS, AND WHAT IT DOES NOT
-------------------------------------------
Fit is the share of the things this posting says it wants that the CV can be
shown to evidence. Nothing else goes into it. Not a country's taste in CVs, not
a guess at how many people applied, not a model's overall impression.

**It says fit and it never says you will get the job.** That sentence travels
with the number rather than sitting in a footnote somewhere. What we can support
is that this listing asks for things this CV states. What an employer will do
with an application is not ours to predict and saying otherwise would be selling
somebody a feeling.

THE TWO CHECKS
--------------
A model does the judging, and two things it returns are checked in code before
they count:

1. **The posting's requirement carries a verbatim quote from the posting**, and
   the quote is checked against the fetched page. A requirement that is not on
   the page is dropped, exactly as in extraction. That stops the model deciding
   this welding job wants a driving licence because welding jobs often do.

2. **The evidence carries a claim the CV actually made.** Not a quote match, a
   membership check: the model must name one of the claims already read from the
   CV and verified against it. It cannot credit the person with something they
   did not write down, because the only things it may cite were read out of
   their document before this call was made.

Unverified CV claims, from a scan with no text layer, can still be cited, and a
match resting on one is marked so. A person who photographed their CV should not
silently score lower, and a reader should still know which evidence was checked.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .cv import CV
from .extract import page_text
from .fetcher import Fetched
from .model import call_json
from .clock import now_iso

FITS = "case_fits"

# What the number is allowed to mean, in one sentence, stored with every score
# so it cannot be separated from it by a template somewhere.
CAVEAT = ("This means the listing asks for things your CV states. "
          "It is not a prediction that you will be offered the job.")

MAX_POSTING_CHARS = 20_000


from .fold import fold_ci as _normalise  # noqa: E402


def _claim_for(evidence: str | None, by_value: dict[str, Any]) -> Any:
    """The claim a piece of evidence refers to, or None if it refers to none.

    Exact equality was the first version and it was too brittle to be honest.
    Asked to copy "English, fluent" the model writes "English", and the match is
    thrown away: a welder scored zero against a job asking for English while his
    CV said English. Five of twelve requirements on one posting died that way,
    and the number a person saw was wrong in the direction that hurts.

    So containment either way, on top of exact match. That still requires the
    evidence to correspond to something the person actually wrote, which is the
    whole point of the check, and it stops the check punishing the person for
    the model tidying their wording.

    The bar is a real word, not a stray letter: two characters or fewer match
    nothing, because "a" appearing inside a claim proves nothing about anybody.
    """
    if not evidence:
        return None
    key = _normalise(evidence)
    if key in by_value:
        return by_value[key]
    if len(key) <= 2:
        return None
    for value, claim in by_value.items():
        if key in value or value in key:
            return claim
    return None


@dataclass
class Match:
    """One thing the posting asks for, and whether the CV shows it."""

    asks_for: str
    quote: str
    met: bool
    evidence: str | None = None
    # What the claim said beyond its value: the employer, the dates, the level.
    # Without it a row can read "5 years of experience: Welder", which does not
    # show five years of anything, and the person cannot tell whether the match
    # was fair. The detail is where the dates live.
    evidence_detail: str | None = None
    evidence_verified: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Fit:
    """A CV scored against one listing."""

    listing_id: str
    case_id: str
    posting_url: str
    read_at: str
    matches: list[Match] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None
    caveat: str = CAVEAT

    @property
    def asked(self) -> int:
        return len(self.matches)

    @property
    def met(self) -> int:
        return len([m for m in self.matches if m.met])

    @property
    def score(self) -> int:
        """Whole per cent, or zero where the posting stated nothing to match.

        A posting with no stated requirements scores nothing rather than a
        hundred. "It asks for nothing and you have all of it" is arithmetic
        being clever at a person's expense.
        """
        if not self.matches:
            return 0
        return round(100 * self.met / self.asked)

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "case_id": self.case_id,
            "posting_url": self.posting_url,
            "read_at": self.read_at,
            "score": self.score,
            "asked": self.asked,
            "met": self.met,
            "caveat": self.caveat,
            "matches": [m.to_dict() for m in self.matches],
            "dropped": self.dropped,
            "error": self.error,
        }


PROMPT = """You are comparing one job posting with one person's CV.

THE POSTING is below. THE CV has already been read, and the list of claims it \
makes is below it. Those claims are the only things this person may be credited \
with.

For every requirement the POSTING ITSELF states, return:
  "asks_for": what the posting wants, in plain words, one short sentence
  "quote": a VERBATIM span copied character for character from the posting text \
that states it
  "met": true if one of the CV claims below shows the person has it. Judge the \
substance, not the wording: "read and worked from engineering drawings" shows \
"read and interpret blueprints and drawings". Different words for the same thing \
count.
  "evidence": the claim that shows it, copied EXACTLY as written in the list \
below, or null if met is false
  "note": if met is false, one short line on what is missing, else null

Rules:
- Only requirements the posting states. Do not add what jobs like this usually \
want.
- The quote is checked against the posting automatically. Anything not on the \
page word for word is discarded.
- Judge fairly. A claim in different words still counts, and refusing everything \
that is not phrased identically tells the person nothing useful.
- Do not credit a skill because the job title implies it, and do not credit \
anything with no claim behind it. "evidence" is checked against the list \
automatically, so copy it exactly rather than rewriting it.
- Return the fifteen most important requirements at most. A posting that lists \
thirty duties does not need every one of them scored.
- If the posting states nothing an applicant must have, return an empty list.

Return only JSON: {"matches": [...]}

THE POSTING:
"""


class FitScorer:
    """Scores one CV against one posting."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def score(self, page: Fetched, cv: CV, listing_id: str, case_id: str) -> Fit:
        now = now_iso()
        fit = Fit(listing_id=listing_id, case_id=case_id,
                  posting_url=page.final_url or page.url, read_at=now)

        text = page_text(page)
        if not text:
            fit.error = "the posting could not be read"
            return fit
        if not cv.claims:
            fit.error = "the CV had nothing readable in it to compare"
            return fit

        claims = "\n".join(
            f'- "{c.value}"' + (f" ({c.detail})" if c.detail else "")
            for c in cv.claims
        )
        prompt = (PROMPT + text[:MAX_POSTING_CHARS]
                  + "\n\nTHE CV CLAIMS (the only things this person may be credited with):\n"
                  + claims)

        try:
            parsed = call_json(project=self._project, model=self._model,
                               location=self._location, credentials=self._credentials,
                               parts=[{"text": prompt}],
                               # A posting with twenty requirements, each carrying
                               # its own verbatim quote, does not fit in a default
                               # answer. It came back as half an object.
                               # Thinking tokens are spent from the same budget
                               # as the answer, and this model spends about three
                               # thousand of them before writing anything.
                               max_output_tokens=16384, interactive=True)
        except Exception as exc:  # noqa: BLE001
            fit.error = str(exc)
            return fit

        haystack = _normalise(text)
        by_value = {_normalise(c.value): c for c in cv.claims}

        for item in parsed.get("matches", []):
            asks_for = str(item.get("asks_for") or "").strip()
            quote = str(item.get("quote") or "").strip()
            if not asks_for or not quote:
                continue

            if _normalise(quote) not in haystack:
                fit.dropped.append({"asks_for": asks_for, "quote": quote,
                                    "why": "the quote is not in the posting"})
                continue

            met = bool(item.get("met"))
            evidence = str(item.get("evidence") or "").strip() or None
            claim = _claim_for(evidence, by_value)

            if met and claim is None:
                # It said the person has this and cited something they never
                # claimed. The requirement stays, counted as unmet, because
                # silently dropping it would shrink the denominator and flatter
                # the score.
                fit.matches.append(Match(
                    asks_for=asks_for, quote=quote, met=False,
                    note="no line in the CV was found to show this"))
                fit.dropped.append({"asks_for": asks_for, "quote": evidence or "",
                                    "why": "the evidence is not a claim the CV made"})
                continue

            fit.matches.append(Match(
                asks_for=asks_for, quote=quote, met=met,
                evidence=claim.value if claim else None,
                evidence_detail=claim.detail if claim else None,
                evidence_verified=bool(claim and claim.verified),
                note=str(item.get("note") or "").strip() or None if not met else None,
            ))

        return fit


class Fits:
    """Stores what a CV scored against a listing."""

    def __init__(self, client) -> None:
        self._db = client

    def put(self, fit: Fit) -> None:
        self._db.collection(FITS).document(f"{fit.case_id}-{fit.listing_id}").set(
            fit.to_dict())

    def get(self, case_id: str, listing_id: str) -> dict[str, Any] | None:
        snap = self._db.collection(FITS).document(f"{case_id}-{listing_id}").get()
        return snap.to_dict() if snap.exists else None

    def for_case(self, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        from google.cloud import firestore

        query = (self._db.collection(FITS)
                 .where(filter=firestore.FieldFilter("case_id", "==", case_id))
                 .limit(limit))
        rows = [d.to_dict() for d in query.stream()]
        rows.sort(key=lambda r: r.get("score", 0), reverse=True)
        return rows
