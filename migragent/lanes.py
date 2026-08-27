"""Which route a page is actually about: study, work, both, or neither.

WHY THIS IS A PLAIN CALL AND NOT AN AGENT
---------------------------------------
It was built as an ADK agent first. On a real run it cost a full agent session
per page, and a watch round over 143 pages would have taken hours. That was the
tell: deciding which question a page answers is one judgment, not multi-step
work. An agent that navigated or revised over real text earns its session cost;
this does not.

So it is one `call_json`, and the quote check that keeps it honest is in code
right here, the same place it is for extraction. The judgment is unchanged from
the agent version; only the ceremony is gone.

THE DEFECT THIS CLOSES
----------------------
A discovered page inherits the lane of the entry that found it. Government sites
link the work route from the study route and back, and one catalogue can serve
every route, so a page about salaried employment gets tagged `lane=study` and is
one command from being extracted into a study guide. Every mechanism works: the
quote is real, the link is real, the date is real, and the requirement has
nothing to do with studying. D29 and D32.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .extract import MAX_CHARS, _normalise
from .model import call_json

LANES = ("study", "work")


def enabled() -> bool:
    """Off unless switched on. Reads MIGRAGENT_LANE_CHECK."""
    return os.environ.get("MIGRAGENT_LANE_CHECK", "").strip().lower() in {
        "1", "true", "on", "yes"}


@dataclass
class LaneVerdict:
    """Which routes a page serves, each with the sentence that shows it."""

    lanes: set[str] = field(default_factory=set)
    evidence: dict[str, str] = field(default_factory=dict)
    off_topic_quote: str = ""
    dropped: list[dict[str, str]] = field(default_factory=list)
    error: str = ""
    stopped_because: str = ""

    def serves(self, lane: str) -> bool:
        return lane in self.lanes

    @property
    def about_a_route(self) -> bool:
        return bool(self.lanes)

    @property
    def answered(self) -> bool:
        """Did the call produce a verdict, rather than fail."""
        return not self.error and (bool(self.lanes) or bool(self.off_topic_quote))

    def agrees_with(self, assigned_lane: str) -> bool:
        return assigned_lane in self.lanes


PROMPT = """Below is the text of one page from an official government immigration website.

Decide which application routes it is about. The routes are:
  study - a visa or permit to study
  work  - a visa or permit to work

A page can be about one route, both, or neither. A page linked from a study \
section is not necessarily about studying: governments link the work route from \
the study route and the other way round, and a single index page can list every \
route at once.

Return JSON:
{"lanes": [{"lane": "study" or "work",
            "quote": "a sentence copied from the page, character for character, \
that shows the page is about this route"}],
 "off_topic_quote": "if the page is about neither route (tourism, a family or \
partner visa, business travel, citizenship, a general information page), a \
sentence copied from the page that shows what it is about instead; otherwise \
an empty string"}

Rules:
- Every quote is checked against the page automatically. Anything not on the \
page word for word is discarded.
- Decide from this page only. Do not use what you know about this country's \
immigration system.
- If the page is about a route, list it. Do not also fill in off_topic_quote.

PAGE TEXT:
"""


class LaneCheck:
    """One model call that says which routes a page serves. Quote-checked in code."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def classify(self, url: str, page_text: str) -> LaneVerdict:
        """Which routes this page serves. `url` is unused; kept for a stable call site."""
        verdict = LaneVerdict()
        text = (page_text or "")[:MAX_CHARS]
        if not text.strip():
            verdict.error = "the page had no readable text"
            return verdict

        try:
            parsed = call_json(
                project=self._project, model=self._model, location=self._location,
                credentials=self._credentials, parts=[{"text": PROMPT + text}],
            )
        except Exception as exc:  # noqa: BLE001
            verdict.error = f"{type(exc).__name__}: {exc}"[:200]
            return verdict

        haystack = _normalise(text)

        for item in parsed.get("lanes", []) or []:
            lane = str(item.get("lane") or "").strip().lower()
            quote = str(item.get("quote") or "").strip()
            if lane not in LANES:
                continue
            if not quote or _normalise(quote) not in haystack:
                verdict.dropped.append(
                    {"lane": lane, "quote": quote, "why": "the quote is not on the page"})
                continue
            verdict.lanes.add(lane)
            verdict.evidence[lane] = quote

        off = str(parsed.get("off_topic_quote") or "").strip()
        # Only trust an off-topic quote when no route was found. A page that is
        # about a route is about that route even if it also mentions tourism.
        if off and not verdict.lanes:
            if _normalise(off) in haystack:
                verdict.off_topic_quote = off
            else:
                verdict.dropped.append(
                    {"lane": "none", "quote": off, "why": "the quote is not on the page"})

        verdict.stopped_because = "classified"
        return verdict
