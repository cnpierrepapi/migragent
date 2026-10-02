"""Articles: what moved on an official page, and exactly who it moves for.

WHAT THIS IS
------------
The watch round already finds when a government or school page changes, and the
change writer already asks whether the change alters what is required. This
turns each such change into an article a person can read without opening the
page, and attaches the report that shows how every line in it was got.

It runs on its own, as the `articles` mode of the worker, after the morning
watch round and digest. Nobody starts it and nobody edits what it writes.

THE RULE THIS FILE EXISTS TO ENFORCE
------------------------------------
The model proposes; the page decides. Every claim in an article, including
every line of who it is for, has to carry a verbatim quote from the page as it
reads today, and the quote is checked here, in code, against that page's own
text. A claim whose quote is not on the page is dropped, and the drop is listed
in the report with the reason. The article itself is assembled in code from the
claims that survived, so there is no free prose for an invention to hide in.

"Who it is for" gets the most room because it is the point. A rule change is
only news to the people it touches: the occupation, the level of study, the
route, where they are applying from, what they earn, who comes with them. The
model is asked to be as specific as the page is and no more. Where the page sets
no condition on something a reader would want to know, that goes under "what
the page does not say", not into a guess.

WHAT AN ARTICLE IS NOT
----------------------
Advice. It reports what official pages say and when they said it. The report
names both stored reads of every page. The store is private, so a reader checks
the article against the live page through its link, and anybody with access to
the bucket can check it against the exact bytes that were read.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .fetcher import Fetched
from .fold import fold as _normalise
from .voice import RULES as VOICE_RULES
from .voice import hits as voice_hits
from .voice import tidy

ARTICLES = "articles"
SKIPPED = "article_skips"
MAX_CHARS = 60_000

PROMPT = """You are writing for MIGRAGENT, an immigration wire. An official page changed.
You are given what changed (a diff sample) and the full text of the page as it reads now.

Return JSON only, in this shape:
{
  "headline": "plain, factual, under 90 characters, no hype, names the country and route",
  "dek": "one sentence: what changed and for whom",
  "what_changed": [{"text": "...", "quote": "..."}],
  "who_for": [{"group": "...", "why": "...", "quote": "...",
               "conditions": [{"text": "...", "quote": "..."}]}],
  "who_not_for": [{"group": "...", "why": "...", "quote": "..."}],
  "dates": [{"what": "...", "date": "...", "quote": "..."}],
  "what_to_do": [{"text": "...", "quote": "..."}],
  "not_said": ["..."]
}

Rules:
- The article is about WHAT CHANGED and nothing else. Pages carry many unrelated
  topics. If a sentence on the page is not about the change in the diff, it must not
  appear anywhere in your answer, not even in "who_not_for".
- Every "quote" must be copied character for character from PAGE TEXT below. Never
  from the diff alone, never paraphrased, never stitched from two places. Keep quotes
  short: the smallest span that proves the claim.
- "who_for" is the most important part. List the people THIS CHANGE affects, as
  specifically as the page states them: route or visa name, occupation or field,
  level of study, nationality, age, where they apply from (inside or outside the
  country), salary or funds thresholds, family members, people already holding a
  visa, deadlines that apply to them. One group per item. The quote must show that
  this group is touched by the change; a quote that only shows the group exists
  somewhere on the page is not enough.
- Give each "who_for" group every condition the page sets on it, one per item in
  "conditions": salary or income floor, qualification or level of study, occupation
  code or skill level, age, language test, funds to show, contract or sponsor, length
  of stay, where to apply from, fees, family it may bring. Each condition carries its
  own quote. List as many as the page states. This is the detail readers come for.
- "why" restates what its own quote says, in plain words, and adds nothing the quote
  does not say.
- If the page does not say who the change applies to, give the narrowest group it
  does name for this change, and put every unanswered question (which nationalities,
  who is exempt, when it takes effect, whether current holders are affected) in
  "not_said". Never fill a gap with a guess.
- "date" is written exactly as the page writes it.
- Write everything in English, whatever language the page is in. Quotes stay in the
  page's own language, copied exactly, because they are checked against the page.
- "headline" and "dek" state only what your quoted claims state. No adjectives the
  page does not use, and no selling words: comprehensive, streamlined, major, key,
  landmark, significant. A reader should be able to check every word of them
  against the quotes below.
- No advice beyond what the page itself says to do.

DIFF SAMPLE:
"""

# The house voice goes in just before the material, so it is the last instruction
# the model reads before writing. See migragent/voice.py.
PROMPT = PROMPT.replace("\nDIFF SAMPLE:\n", VOICE_RULES + "\nDIFF SAMPLE:\n")

# What stands in for the diff when the desk submits a filing by hand.
DESK_DIFF = ("No diff: this is a filing submitted by the MIGRAGENT desk because the page could not be "
             "crawled. Treat the whole PAGE TEXT as what is new, and write it up the same way.")

REWRITE = """Rewrite this headline and dek so they follow the voice rules below. Keep every
fact and add none: use only the facts listed. Return JSON only: {"headline": "...", "dek": "..."}
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:70].rstrip("-") or "article"


def article_id(change_ids: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(change_ids)).encode()).hexdigest()[:16]


@dataclass
class Source:
    """One page the article rests on, with both reads of it."""

    url: str
    before_read_at: str
    after_read_at: str
    before_snapshot: str | None
    after_snapshot: str | None
    lines_added: int
    lines_removed: int
    change_summary: str | None
    chars: int = 0


@dataclass
class Report:
    """How the article was got. Shown in full under every article."""

    change_ids: list[str]
    jurisdiction: str
    lane: str
    sources: list[Source]
    model: str
    served_by: str = ""
    cost_usd: float = 0.0
    quotes_checked: int = 0
    quotes_kept: int = 0
    dropped: list[dict[str, str]] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)
    voice: dict[str, Any] = field(default_factory=dict)
    # "crawl" when the watch round found the change; "desk" when a person submitted it.
    origin: str = "crawl"
    desk: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""


def check(parsed: dict[str, Any], pages: list[str]) -> tuple[dict[str, list], list[dict[str, str]], int]:
    """Keep only claims whose quote is on one of the pages. Returns (kept, dropped, checked).

    A kept claim records which page its quote was found on (`source`, 1-based),
    so the article can link each line to the page that says it.
    """
    haystacks = [_normalise(p) for p in pages]
    kept: dict[str, list] = {}
    dropped: list[dict[str, str]] = []
    checked = 0
    for section in ("what_changed", "who_for", "who_not_for", "dates", "what_to_do"):
        kept[section] = []
        for item in parsed.get(section) or []:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("group") or item.get("text") or item.get("what") or "").strip()
            quote = str(item.get("quote") or "").strip()
            checked += 1
            if not claim:
                dropped.append({"section": section, "claim": "", "why": "empty claim"})
                continue
            if not quote:
                dropped.append({"section": section, "claim": claim, "why": "no quote given"})
                continue
            needle = _normalise(quote)
            found = next((i for i, h in enumerate(haystacks) if needle in h), None)
            if found is None:
                dropped.append({"section": section, "claim": claim, "quote": quote,
                                "why": "the quote is not on the page"})
                continue
            row: dict[str, Any] = {k: str(v).strip() for k, v in item.items()
                                   if v and k not in ("source", "conditions")}
            row["source"] = found + 1
            # Each condition on a group is a claim of its own, checked the same way.
            conditions = []
            for cond in item.get("conditions") or []:
                if not isinstance(cond, dict):
                    continue
                ctext = str(cond.get("text") or "").strip()
                cquote = str(cond.get("quote") or "").strip()
                checked += 1
                cfound = (next((i for i, h in enumerate(haystacks) if _normalise(cquote) in h), None)
                          if ctext and cquote else None)
                if cfound is None:
                    dropped.append({"section": f"{section} condition", "claim": f"{claim}: {ctext}",
                                    "quote": cquote,
                                    "why": "no quote given" if not cquote else "the quote is not on the page"})
                    continue
                conditions.append({"text": ctext, "quote": cquote, "source": cfound + 1})
            if conditions:
                row["conditions"] = conditions
            kept[section].append(row)
    kept["not_said"] = [str(x).strip() for x in parsed.get("not_said") or [] if str(x).strip()]
    return kept, dropped, checked


def publishable(kept: dict[str, list]) -> str:
    """Empty when the article may go out, otherwise why not."""
    if not kept["who_for"]:
        return "no line of who it is for survived the quote check"
    if not (kept["what_changed"] or kept["dates"]):
        return "nothing about what changed survived the quote check"
    return ""


_STOP = set("the a an of to for in on and or has have been is are was were with from by its it this that "
            "new page official information".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def cluster(rows: list[dict[str, Any]], threshold: float = 0.6) -> list[list[dict[str, Any]]]:
    """Same country, same day, same meaning: one article, however many pages carry it.

    One extension posted on four pages is one piece of news. Meaning is judged by
    the overlap of the change summaries' words, which is crude and is enough:
    governments copy their own sentences between pages.
    """
    groups: list[tuple[tuple[str, str], set[str], list[dict[str, Any]]]] = []
    for r in sorted(rows, key=lambda c: c.get("after_read_at", "")):
        key = (r.get("jurisdiction", ""), (r.get("after_read_at") or "")[:10])
        words = _words(r.get("summary") or "")
        for gkey, gwords, members in groups:
            if gkey != key:
                continue
            same_page = any(m.get("source_url") == r.get("source_url") for m in members)
            union = gwords | words
            if same_page or (union and len(gwords & words) / len(union) >= threshold):
                members.append(r)
                gwords |= words
                break
        else:
            groups.append((key, set(words), [r]))
    return [members for _, _, members in groups]


class Writer:
    """Finds material changes with no article yet, and writes one per piece of news."""

    def __init__(self, db, snapshots, project: str, model: str, location: str,
                 credentials, days: int = 2, pause: float = 3.0) -> None:
        self._db = db
        self._snapshots = snapshots
        self._project, self._model, self._location = project, model, location
        self._credentials = credentials
        self._days = days
        self._pause = pause

    def pending(self) -> list[list[dict[str, Any]]]:
        from google.cloud import firestore

        since = (_now() - timedelta(days=self._days)).isoformat()
        rows = [{**d.to_dict(), "id": d.id} for d in self._db.collection("changes")
                .where(filter=firestore.FieldFilter("after_read_at", ">=", since)).stream()]
        out = []
        for group in cluster([r for r in rows if r.get("material")]):
            aid = article_id([c["id"] for c in group])
            if self._db.collection(ARTICLES).document(aid).get().exists:
                continue
            if self._db.collection(SKIPPED).document(aid).get().exists:
                continue
            out.append(group)
        return out

    def _page_text(self, change: dict[str, Any]) -> str:
        from .extract import page_text

        path = change.get("after_snapshot")
        body = self._snapshots.read(path) if path else None
        if not body:
            return ""
        page = Fetched(url=change.get("source_url", ""), outcome="fetched",
                       read_at=change.get("after_read_at", ""), status=200, body=body,
                       content_type="text/html")
        return page_text(page)

    def write(self, group: list[dict[str, Any]]) -> dict[str, Any]:
        import time

        from . import orbio
        from .model import call_json

        aid = article_id([c["id"] for c in group])
        latest: dict[str, dict[str, Any]] = {}
        for c in group:
            latest[c.get("source_url", "")] = c
        sources: list[Source] = []
        texts: list[str] = []
        diffs: list[str] = []
        report = Report(change_ids=[c["id"] for c in group], jurisdiction=group[-1].get("jurisdiction", ""),
                        lane=group[-1].get("lane", ""), sources=[], model=self._model,
                        generated_at=_now().isoformat(timespec="seconds"))
        for url, c in latest.items():
            text = self._page_text(c)
            if not text:
                report.unreadable.append(url)
                continue
            sources.append(Source(url=url, before_read_at=c.get("before_read_at", ""),
                                  after_read_at=c.get("after_read_at", ""),
                                  before_snapshot=c.get("before_snapshot"),
                                  after_snapshot=c.get("after_snapshot"),
                                  lines_added=int(c.get("added") or 0),
                                  lines_removed=int(c.get("removed") or 0),
                                  change_summary=c.get("summary"), chars=len(text)))
            texts.append(text)
            diffs.append(c.get("diff_sample") or "")
        report.sources = sources
        if not texts:
            return self._skip(aid, report, "no page snapshot could be read back; a page that was "
                                           "taken down leaves nothing to quote")
        return self._compose(aid, report, sources, texts, "\n".join(diffs)[:8000])

    def write_desk(self, sub: dict[str, Any]) -> dict[str, Any]:
        """A filing the desk submitted by hand: a page that cannot be crawled, a PDF,
        an announcement. Same quote check, same voice, same report, and the report
        says plainly that a person submitted it rather than the crawl finding it.
        """
        text = (sub.get("text") or "").strip()
        aid = f"desk-{sub['id']}"
        observed = (sub.get("observed_on") or _now().date().isoformat())[:10]
        source = Source(url=sub.get("url", ""), before_read_at="", after_read_at=observed,
                        before_snapshot=None, after_snapshot=None, lines_added=0, lines_removed=0,
                        change_summary=sub.get("title") or "Submitted by the desk", chars=len(text))
        report = Report(change_ids=[], jurisdiction=sub.get("jurisdiction", ""), lane=sub.get("lane", ""),
                        sources=[source], model=self._model,
                        generated_at=_now().isoformat(timespec="seconds"))
        report.origin = "desk"
        report.desk = {"submission": sub["id"], "submitted_at": sub.get("submitted_at", ""),
                       "how": sub.get("how", "pasted text"), "note": sub.get("note", "")}
        if len(text) < 120:
            return self._skip(aid, report, "the submitted text is too short to quote from")
        return self._compose(aid, report, [source], [text], DESK_DIFF)

    def _compose(self, aid: str, report: Report, sources: list[Source], texts: list[str],
                 diff: str) -> dict[str, Any]:
        """The shared core: one model call, the quote check, the voice, and the article."""
        import time

        from . import orbio
        from .model import call_json

        budget = MAX_CHARS // len(texts)
        page_block = "\n\n".join(f"PAGE {i + 1} ({s.url}):\n{t[:budget]}"
                                 for i, (s, t) in enumerate(zip(sources, texts)))
        before = dict(orbio.served)
        time.sleep(self._pause)
        parsed = call_json(project=self._project, model=self._model, location=self._location,
                           credentials=self._credentials, max_output_tokens=8192,
                           public=True,  # official pages' own text and their diffs, nothing else
                           parts=[{"text": PROMPT + diff + "\n\nPAGE TEXT:\n" + page_block}])
        report.served_by = "orbio" if orbio.served["orbio"] > before["orbio"] else "vertex"
        report.cost_usd = round(orbio.served["usd"] - before["usd"], 6)

        kept, dropped, checked = check(parsed, texts)
        report.quotes_checked, report.dropped = checked, dropped
        report.quotes_kept = checked - len(dropped)
        why = publishable(kept)
        if why:
            return self._skip(aid, report, why)

        headline = (str(parsed.get("headline") or "").strip()[:120]
                    or sources[0].change_summary or "An official page changed")
        headline, dek = self._voice(kept, headline, str(parsed.get("dek") or "").strip()[:300], report)
        observed = max(s.after_read_at for s in sources)[:10]
        doc = {"id": aid, "slug": f"{observed}-{slugify(headline)}", "headline": headline,
               "dek": dek, "published_at": report.generated_at,
               "observed_on": observed, "jurisdiction": report.jurisdiction, "lane": report.lane,
               "origin": report.origin, "hidden": False, **kept, "report": asdict(report)}
        self._db.collection(ARTICLES).document(aid).set(doc)
        return {"written": doc["slug"]}

    def _voice(self, kept: dict[str, list], headline: str, dek: str, report: Report) -> tuple[str, str]:
        """The house voice, enforced on every field the agent wrote. Quotes are never touched."""
        from .model import call_json

        fields = 0
        for section in ("what_changed", "who_for", "who_not_for", "dates", "what_to_do"):
            for item in kept[section]:
                for key in ("group", "why", "text", "what"):
                    if item.get(key):
                        item[key] = tidy(item[key])
                        fields += 1
                for cond in item.get("conditions") or []:
                    cond["text"] = tidy(cond["text"])
                    fields += 1
        kept["not_said"] = [tidy(g) for g in kept["not_said"]]
        headline, dek = tidy(headline), tidy(dek)
        fields += len(kept["not_said"]) + 2

        rewritten = False
        if voice_hits(headline) or voice_hits(dek):
            facts = [i.get("text") or i.get("group") or i.get("what") or ""
                     for sec in ("what_changed", "who_for", "dates") for i in kept[sec]]
            try:
                fixed = call_json(project=self._project, model=self._model, location=self._location,
                                  credentials=self._credentials, max_output_tokens=2048,
                                  public=True,  # the article's own headline and kept facts
                                  parts=[{"text": REWRITE + VOICE_RULES + "\nHEADLINE: " + headline
                                          + "\nDEK: " + dek + "\nFACTS:\n- " + "\n- ".join(facts)}])
                new_h, new_d = tidy(str(fixed.get("headline") or "")), tidy(str(fixed.get("dek") or ""))
                if new_h and len(voice_hits(new_h)) <= len(voice_hits(headline)):
                    headline, rewritten = new_h[:120], True
                if new_d and len(voice_hits(new_d)) <= len(voice_hits(dek)):
                    dek, rewritten = new_d[:300], True
            except Exception:  # noqa: BLE001
                pass  # the original stands, and the report below names what it breaks

        dropped_why = 0
        for section in ("who_for", "who_not_for"):
            for item in kept[section]:
                if item.get("why") and voice_hits(item["why"]):
                    item.pop("why")  # its quote already says it, in the government's own words
                    dropped_why += 1

        remaining = []
        for label, text in [("headline", headline), ("dek", dek)] + [
                (sec, i.get(k, "")) for sec in ("what_changed", "who_for", "who_not_for", "dates", "what_to_do")
                for i in kept[sec] for k in ("group", "why", "text", "what")] + [
                ("condition", c.get("text", "")) for sec in ("who_for",) for i in kept[sec]
                for c in i.get("conditions") or []] + [("not said", g) for g in kept["not_said"]]:
            for h in voice_hits(text):
                remaining.append(f"{label}: {h}")
        report.voice = {"fields": fields, "rewritten": rewritten, "dropped_why": dropped_why,
                        "remaining": sorted(set(remaining))}
        return headline, dek

    def _skip(self, aid: str, report: Report, why: str) -> dict[str, Any]:
        """Not published, and written down as not published, with the reason."""
        self._db.collection(SKIPPED).document(aid).set({"why": why, "report": asdict(report),
                                                        "at": _now().isoformat(timespec="seconds")})
        return {"skipped": why}


def recent(db, limit: int = 30) -> list[dict[str, Any]]:
    from google.cloud import firestore

    # By the day the page changed, not the day the article was written, so an
    # article backfilled today about a change in August files under August.
    rows = [d.to_dict() for d in db.collection(ARTICLES)
            .order_by("observed_on", direction=firestore.Query.DESCENDING).limit(limit + 20).stream()]
    # Hidden by the desk: kept, with its report, but off the wire.
    return [r for r in rows if not r.get("hidden")][:limit]


def by_slug(db, slug: str) -> dict[str, Any] | None:
    from google.cloud import firestore

    for d in db.collection(ARTICLES).where(filter=firestore.FieldFilter("slug", "==", slug)).limit(1).stream():
        return d.to_dict()
    return None
