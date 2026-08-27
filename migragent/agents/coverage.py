"""The Coverage Matcher as an agent: which requirements the uploads address.

WHY THIS ONE IS WORTH MAKING AN AGENT
------------------------------------
Most of the single model calls in this product are single calls for a reason,
and wrapping them in an agent would be ceremony. This one is different, because
what it produces is the readiness score, and the score is the number in the
build most likely to become a lie.

The one-shot matcher in `migragent/coverage.py` proposes matches, and a match
that cites a document field nobody uploaded is dropped in silence. Sometimes
that is right: the field is not there. Sometimes the person uploaded a bank
statement and the requirement says "proof of funds" and the match was dropped
on a wording miss, and the score a person sees is lower than the truth, in the
direction that discourages them.

The agent gets the drop back in words and can look again: is there another
document, another field, that addresses this requirement. Same validation, in
the tool, against the same uploaded fields. The difference is the second look.

WHAT DOES NOT CHANGE
-------------------
A match still has to name a document kind and a field that were actually
uploaded. The tool checks both against the fields read from the documents before
this call, and a match that cites anything else is refused and counted. The
agent cannot credit the person with a document they did not provide.

It returns the same `Coverage` the one-shot matcher returns.
"""
from __future__ import annotations

import os
from typing import Any

from ..coverage import ACTION_CATEGORIES, Coverage, Match
from ..documents import ReadDocument
from .base import Outcome, build_llm, function_tools, run_to_completion


def enabled() -> bool:
    return os.environ.get("MIGRAGENT_AGENT_COVERAGE", "").strip().lower() in {
        "1", "true", "on", "yes"}


INSTRUCTION = """You are checking which of an application's requirements a person's uploaded documents already address, for the {lane} route into {place}.

The documents and the fields read from each one are below, and so are the requirements. Those documents and fields are the only things this person may be credited with.

For every requirement one of the documents genuinely addresses, call record_match with the requirement's id, the document kind, the field on that document that addresses it, and one short sentence on why. The kind and field are checked against what was actually uploaded. A match citing a document or field that is not there is refused and told back to you: look for another document that addresses the requirement, or leave it unmatched.

Leaving a requirement unmatched is a correct answer and is more useful than a generous one. Do not match a requirement to a document because the requirement sounds like something a document should cover. Match it only where a named field on an uploaded document shows it.

When you have matched what the documents address and retried what was refused, call finish."""


class CoverageDesk:
    """Requirements, uploaded fields, and the check. The agent's only surface."""

    def __init__(self, *, jurisdiction: str, lane: str,
                 requirements: list[dict[str, Any]],
                 documents: list[ReadDocument]) -> None:
        self.coverage = Coverage(jurisdiction=jurisdiction, lane=lane,
                                 total_requirements=len(requirements))
        satisfiable = [r for r in requirements
                       if r.get("category") not in ACTION_CATEGORIES]
        self.coverage.document_requirements = len(satisfiable)
        self.coverage.action_only = len(requirements) - len(satisfiable)

        self._by_id = {r.get("id", ""): r for r in satisfiable}
        self._available: dict[str, dict[str, tuple[str, bool]]] = {}
        for doc in documents:
            fields = {f.name: (f.value, f.verified) for f in doc.fields}
            self._available[doc.kind] = {**self._available.get(doc.kind, {}), **fields}
        self._matched_ids: set[str] = set()
        self.stopped = False

    @property
    def nothing_to_do(self) -> bool:
        return not self._by_id or not self._available

    def requirements_block(self) -> str:
        return "\n".join(f'- id={rid}: {r.get("text","")}'
                         for rid, r in self._by_id.items()) or "none"

    def documents_block(self) -> str:
        lines = []
        for kind, fields in self._available.items():
            listing = ", ".join(sorted(fields)) or "no readable fields"
            lines.append(f"- {kind}: {listing}")
        return "\n".join(lines) or "none"

    def record_match(self, requirement_id: str, document_kind: str,
                     document_field: str, note: str = "") -> str:
        """Record that one uploaded document addresses one requirement.

        Args:
            requirement_id: the id of the requirement, from the list.
            document_kind: the kind of document that addresses it. Must be one uploaded.
            document_field: the field on that document. Must be one that was read.
            note: one short sentence on why this document addresses the requirement.
        """
        rid = (requirement_id or "").strip()
        kind = (document_kind or "").strip()
        fname = (document_field or "").strip()

        if rid not in self._by_id:
            self.coverage.dropped_matches.append(
                {"requirement_id": rid, "why": "no such requirement in this lane"})
            return "Refused. That id is not in the requirement list."
        if kind not in self._available or fname not in self._available[kind]:
            self.coverage.dropped_matches.append(
                {"requirement_id": rid,
                 "why": f"cites {kind}.{fname}, which was not uploaded"})
            return (f"Refused. {kind}.{fname} was not uploaded. Try another document "
                    "that addresses this requirement, or leave it unmatched.")

        if rid in self._matched_ids:
            return "Already matched. Move on."

        value, verified = self._available[kind][fname]
        self.coverage.matched.append(Match(
            requirement_id=rid, requirement_text=self._by_id[rid].get("text", ""),
            document_kind=kind, document_field=fname, field_value=value,
            verified=verified, note=(note or "").strip(),
        ))
        self._matched_ids.add(rid)
        return "Matched."

    def finish(self, why: str = "") -> str:
        """Stop, once matches are recorded and refusals retried."""
        self.stopped = True
        return "Finished."

    def settle(self) -> Coverage:
        self.coverage.unmatched = [
            {"requirement_id": rid, "text": r.get("text", "")}
            for rid, r in self._by_id.items() if rid not in self._matched_ids
        ]
        return self.coverage


class AgentMatcher:
    """Works out what the uploads cover, with a second look. Matcher-compatible."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _agent(self, desk: CoverageDesk, place: str, lane: str):
        from google.adk.agents import LlmAgent

        return LlmAgent(
            name="coverage_matcher",
            description="Matches uploaded documents to the requirements they address.",
            model=build_llm(project=self._project, model=self._model,
                            location=self._location, credentials=self._credentials),
            instruction=INSTRUCTION.format(lane=lane, place=place)
            + "\n\nDOCUMENTS THEY UPLOADED:\n" + desk.documents_block()
            + "\n\nREQUIREMENTS:\n" + desk.requirements_block(),
            tools=function_tools([desk.record_match, desk.finish]),
        )

    def match(self, jurisdiction: str, lane: str,
              requirements: list[dict[str, Any]],
              documents: list[ReadDocument]) -> Coverage:
        desk = CoverageDesk(jurisdiction=jurisdiction, lane=lane,
                            requirements=requirements, documents=documents)
        if desk.nothing_to_do:
            return desk.settle()

        try:
            from ..registry import JURISDICTIONS
            place = JURISDICTIONS.get(jurisdiction, {}).get("name", jurisdiction)
        except Exception:  # noqa: BLE001
            place = jurisdiction

        outcome: Outcome = run_to_completion(
            agent=self._agent(desk, place, lane),
            message=("Match the uploaded documents to the requirements they address. "
                     "Retry anything the check refuses, then finish."),
            stop_when=lambda: desk.stopped,
            user_id="web",
        )
        if outcome.error and not desk.coverage.matched:
            desk.coverage.dropped_matches.append({"why": outcome.error})
        return desk.settle()
