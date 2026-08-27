"""The Lane Classifier: which route a page is actually about.

THE DEFECT THIS CLOSES
----------------------
A discovered page inherits the lane of the entry that found it. Government sites
link the work route from the study route and back again, and a catalogue page
serves every route at once. So a page about salaried employment gets tagged
`lane=study` because the study index linked it, and one command from being
extracted into a study guide. Every other mechanism works: the quote is real,
the link is real, the date is real, and the requirement has nothing to do with
studying. D29 recorded it as a near miss in Italy while D32 had already shipped
it into the UK lead lanes. Per-page lane detection did not exist. This is it.

WHAT THE AGENT DECIDES, AND WHAT IT CANNOT DO
--------------------------------------------
It is shown one page and decides which of study and work it is about: one, both
or neither. It is not told which lane the walk assigned, because that would ask
it to confirm rather than to read.

Every route it names has to carry a sentence from the page, checked against the
page the same way `migragent/extract.py` checks a requirement's quote. A page it
says is about neither route carries a sentence too, showing what it is about
instead. The check is in the tool, not the prompt.

The page is handed over already fetched. This agent does not fetch, so the
robots gate does not arise here: it was passed before the page reached it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..extract import MAX_CHARS, _normalise
from .base import Outcome, build_llm, function_tools, run_to_completion

LANES = ("study", "work")


def enabled() -> bool:
    """Off unless switched on. A new classifier does not get to be a default."""
    return os.environ.get("MIGRAGENT_AGENT_LANE", "").strip().lower() in {
        "1", "true", "on", "yes"}


@dataclass
class LaneVerdict:
    """Which routes a page serves, each with the sentence that shows it."""

    lanes: set[str] = field(default_factory=set)
    evidence: dict[str, str] = field(default_factory=dict)
    off_topic_quote: str = ""
    refused: list[dict[str, str]] = field(default_factory=list)
    stopped_because: str = ""
    error: str = ""
    turns: int = 0

    def serves(self, lane: str) -> bool:
        return lane in self.lanes

    @property
    def about_a_route(self) -> bool:
        return bool(self.lanes)

    @property
    def answered(self) -> bool:
        """Did the agent actually reach a verdict, rather than fall over."""
        return not self.error and (bool(self.lanes) or bool(self.off_topic_quote))

    def agrees_with(self, assigned_lane: str) -> bool:
        """Does the page serve the lane the walk filed it under."""
        return assigned_lane in self.lanes


INSTRUCTION = """You are shown one page from an official government immigration website. Decide which application routes it is about.

The routes are:
  study - a visa or permit to study
  work  - a visa or permit to work

A page can be about one route, both, or neither. A page linked from a study section is not necessarily about studying: governments link the work route from the study route and the other way round, and a single index page can list every route at once.

For each route this page is actually about, call mark_lane with the route and one sentence copied from the page, character for character, that shows the page is about that route. The sentence is checked against the page. Anything that is not on the page word for word is refused and told back to you.

If the page is about neither route, for example tourism, a family or partner visa, business travel, citizenship or a general information page, call mark_none with one sentence from the page that shows what it is about instead.

Do not use what you remember about this country's immigration system. Decide from this page only.

When you have marked what this page is about, call finish."""


class LaneDesk:
    """The only surface the agent can reach. The quote check lives here."""

    def __init__(self, page_text: str) -> None:
        self._text = page_text[:MAX_CHARS]
        self._haystack = _normalise(self._text)
        self.verdict = LaneVerdict()

    def _on_page(self, quote: str) -> bool:
        return bool(quote) and _normalise(quote) in self._haystack

    def mark_lane(self, lane: str, quote: str) -> str:
        """Mark that this page is about one application route.

        Args:
            lane: one of study, work.
            quote: a sentence copied from the page that shows it is about this route.
        """
        lane = (lane or "").strip().lower()
        quote = (quote or "").strip()
        if lane not in LANES:
            return f"Refused. The route must be one of: {', '.join(LANES)}."
        if not self._on_page(quote):
            self.verdict.refused.append(
                {"lane": lane, "quote": quote, "why": "the quote is not on the page"})
            return ("Refused. That sentence is not on the page word for word. Copy the "
                    "sentence that actually shows this page is about the route, or do "
                    "not mark it.")
        self.verdict.lanes.add(lane)
        self.verdict.evidence[lane] = quote
        return "Marked."

    def mark_none(self, quote: str) -> str:
        """Mark that this page is about neither the study route nor the work route.

        Args:
            quote: a sentence copied from the page that shows what it is about instead.
        """
        quote = (quote or "").strip()
        if not self._on_page(quote):
            self.verdict.refused.append(
                {"lane": "none", "quote": quote, "why": "the quote is not on the page"})
            return ("Refused. That sentence is not on the page word for word. Copy one "
                    "that is.")
        self.verdict.off_topic_quote = quote
        return "Marked."

    def finish(self) -> str:
        """Stop, once this page's routes have been marked."""
        self.verdict.stopped_because = "the agent marked the page and finished"
        return "Finished."


class LaneClassifier:
    """Runs one classification with ADK and returns the verdict.

    Built fresh per page: the tools are bound to a desk that holds one page's
    text, and the quote check has to be against that page and no other.
    """

    def __init__(self, *, project: str, model: str, location: str, credentials) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _agent(self, desk: LaneDesk):
        from google.adk.agents import LlmAgent

        return LlmAgent(
            name="lane_classifier",
            description="Decides which immigration route a government page is about.",
            model=build_llm(project=self._project, model=self._model,
                            location=self._location, credentials=self._credentials),
            instruction=INSTRUCTION,
            tools=function_tools([desk.mark_lane, desk.mark_none, desk.finish]),
        )

    def classify(self, url: str, page_text: str) -> LaneVerdict:
        """Which routes this page serves. `url` is for the message only."""
        if not (page_text or "").strip():
            v = LaneVerdict()
            v.error = "the page had no readable text"
            return v

        desk = LaneDesk(page_text)
        outcome: Outcome = run_to_completion(
            agent=self._agent(desk),
            message=(f"Here is the page at {url}. Decide which routes it is about, "
                     "mark each one with a sentence from the page, then finish."),
            stop_when=lambda: bool(desk.verdict.stopped_because),
            user_id="ingestion",
        )
        desk.verdict.turns = outcome.turns
        desk.verdict.error = outcome.error
        if not desk.verdict.stopped_because:
            desk.verdict.stopped_because = outcome.stopped_because
        return desk.verdict
