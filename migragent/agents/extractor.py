"""The Extractor as an agent: read one page, and revise what it could not prove.

WHAT THIS ADDS OVER THE ONE-SHOT CALL
------------------------------------
`migragent/extract.py` sends a page to the model once and keeps whatever comes
back that survives the quote check. A requirement the model half-remembered,
with a quote stitched from two sentences, is dropped in silence and never
reconsidered. The page may well state that requirement in a sentence the model
did not quite copy.

This agent gets the refusal back in words and can try again: find the sentence
that actually says it, or leave it out. Same page, same budget of page text,
same quote check. The difference is the loop.

WHAT DOES NOT CHANGE, BY CONSTRUCTION
-----------------------------------
The rule `extract.py` exists for holds here exactly. The citation is the URL
that was fetched and the timestamp the bytes arrived, assembled from the
`Fetched` object and never put in a prompt or read out of a response. Every
requirement carries a span checked against the page text before it may exist.
The agent cannot reach either mechanism: it offers a requirement to a tool, and
the tool decides.

It returns the same `Extraction` the one-shot extractor returns, so the round
does not know or care which produced it.
"""
from __future__ import annotations

import os
from typing import Any

from ..fetcher import Fetched
from .base import Outcome, build_llm, function_tools, run_to_completion
from ..extract import MAX_CHARS, Extraction, Requirement, _normalise, page_text


def enabled() -> bool:
    return os.environ.get("MIGRAGENT_AGENT_EXTRACT", "").strip().lower() in {
        "1", "true", "on", "yes"}


INSTRUCTION = """You are reading one page from an official government website about immigration, study or work permits, for the {lane} route into {place}.

List only the requirements this page itself states. A requirement is something an applicant must do, have, pay or prove.

For each one, call record_requirement with:
  text: the requirement in plain words, one sentence, addressed to the applicant, in the same language as the page.
  quote: a span copied from the page below, character for character, that states this requirement. Do not paraphrase, do not join two sentences, do not fix spelling.
  category: one of requirement, cost, timing, eligibility, document.
  cost, duration, depends_on: fill these only if the page states them.

The quote is checked against the page. If it is refused, the page did not state it in those words: find the sentence that actually says it and copy it exactly, or do not record the requirement. Do not reword a refused quote to slip it past the check.

Only what is on this page. You have read many immigration pages. What you remember is not evidence.

If this page states no requirements, record none. That is a correct answer. For anything the page refers to but does not state, call note_open_question.

When you have recorded what this page states and retried what was refused, call finish."""


class ExtractDesk:
    """One page, and the quote check. The only surface the agent can reach."""

    def __init__(self, *, page: Fetched, jurisdiction: str, lane: str,
                 language: str, provenance: str) -> None:
        self._text = page_text(page)[:MAX_CHARS]
        self._haystack = _normalise(self._text)
        self._jurisdiction = jurisdiction
        self._lane = lane
        self._language = language
        self._provenance = provenance
        self._source_url = page.final_url or page.url
        self._read_at = page.read_at
        self.result = Extraction(source_url=self._source_url, read_at=self._read_at)
        self.stopped = False

    @property
    def page_is_empty(self) -> bool:
        return not self._text

    def record_requirement(self, text: str, quote: str, category: str = "requirement",
                           cost: str = "", duration: str = "", depends_on: str = "") -> str:
        """Record one thing the applicant must do, have, pay or prove.

        Args:
            text: the requirement in plain words, one sentence, second person.
            quote: a span copied from the page, character for character, that states it.
            category: one of requirement, cost, timing, eligibility, document.
            cost: the amount if the page states one, otherwise empty.
            duration: how long it takes if the page states one, otherwise empty.
            depends_on: what must happen first if the page says so, otherwise empty.
        """
        text, quote = (text or "").strip(), (quote or "").strip()
        if not text or not quote:
            self.result.dropped.append({"text": text, "quote": quote,
                                        "why": "no quote given"})
            return "Refused. A requirement needs both a plain sentence and a quote."
        if _normalise(quote) not in self._haystack:
            self.result.dropped.append({"text": text, "quote": quote,
                                        "why": "the quote is not on the page"})
            return ("Refused. That quote is not on the page word for word. Find the "
                    "sentence that actually states this and copy it exactly, or leave "
                    "the requirement out.")
        self.result.requirements.append(Requirement(
            text=text, quote=quote, category=category or "requirement",
            cost=cost or None, duration=duration or None, depends_on=depends_on or None,
            source_url=self._source_url, read_at=self._read_at,
            source_language=self._language, provenance=self._provenance,
            jurisdiction=self._jurisdiction, lane=self._lane,
        ))
        return "Recorded."

    def note_open_question(self, question: str) -> str:
        """Note something the page refers to but does not state.

        Args:
            question: what a reader would still need to know.
        """
        question = (question or "").strip()
        if question:
            self.result.open_questions.append(question)
        return "Noted."

    def finish(self, why: str = "") -> str:
        """Stop, once the page's requirements are recorded and refusals retried.

        Args:
            why: one line, optional.
        """
        self.stopped = True
        return "Finished."


class AgentExtractor:
    """Reads one page with an ADK agent. Signature-compatible with Extractor."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _agent(self, desk: ExtractDesk, place: str, lane: str, page_body: str):
        from google.adk.agents import LlmAgent

        return LlmAgent(
            name="extractor",
            description="Reads one government page and records what it requires.",
            model=build_llm(project=self._project, model=self._model,
                            location=self._location, credentials=self._credentials),
            instruction=INSTRUCTION.format(lane=lane, place=place) + "\n\nPAGE TEXT:\n"
            + page_body,
            tools=function_tools([desk.record_requirement, desk.note_open_question,
                                  desk.finish]),
        )

    def extract(self, page: Fetched, jurisdiction: str, lane: str, language: str,
                provenance: str = "official") -> Extraction:
        desk = ExtractDesk(page=page, jurisdiction=jurisdiction, lane=lane,
                           language=language, provenance=provenance)
        if desk.page_is_empty:
            desk.result.model_error = "no readable text on the page"
            return desk.result

        from ..registry import JURISDICTIONS
        place = JURISDICTIONS.get(jurisdiction, {}).get("name", jurisdiction)

        outcome: Outcome = run_to_completion(
            agent=self._agent(desk, place, lane, desk._text),
            message=(f"Read this {lane} page for {place} and record the requirements it "
                     "states. Retry anything the quote check refuses, then finish."),
            stop_when=lambda: desk.stopped,
            user_id="ingestion",
        )
        # A run that fell over keeps what it had already recorded. Those passed
        # the quote check when they were accepted; a later failure does not
        # unmake that. model_error is set only when nothing was recorded, so the
        # round's existing "if extraction.model_error" branch still means "this
        # page produced nothing and here is why".
        if outcome.error and not desk.result.requirements:
            desk.result.model_error = outcome.error
        return desk.result
