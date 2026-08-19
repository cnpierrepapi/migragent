"""Routes: what to do about the things you do not have.

A gap is not an answer. "You need proof of English" tells somebody nothing they
did not already know from the requirement itself. What they need is which tests
this particular regulator accepts, what each costs, how long each takes to book,
and which one is realistic from where they are.

WHERE A ROUTE IS ALLOWED TO COME FROM
-------------------------------------
The same place everything else comes from: pages we have read.

A model asked to name accepted English tests will produce a confident, mostly
correct, occasionally outdated list, and the wrong entry will be indistinguishable
from the right ones. So a route may only cite requirements already in the corpus,
each of which already carries its source page and the date it was read. A route
that cites a requirement id we do not hold is dropped and counted.

WHAT HAPPENS WHEN THERE IS NO ROUTE
-----------------------------------
It says so. "We have not read a page that says what the alternatives are" is a
useful sentence and an honest one, and it goes to open questions where somebody
can see it is a hole rather than an absence of options.

A missing route is still an answer, which is the line from HOW_IT_WORKS.md. It is
just not the answer we would like.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .model import call_json


@dataclass
class Option:
    """One way through a gap, and where we read about it."""

    name: str
    what_it_is: str
    cost: str | None = None
    lead_time: str | None = None
    accepted_by: str | None = None
    source_url: str = ""
    read_at: str = ""
    quote: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Route:
    """A gap, and the ways through it we can actually evidence."""

    requirement_id: str
    requirement_text: str
    options: list[Option] = field(default_factory=list)
    no_route_reason: str | None = None

    @property
    def has_options(self) -> bool:
        return bool(self.options)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_text": self.requirement_text,
            "options": [o.to_dict() for o in self.options],
            "no_route_reason": self.no_route_reason,
        }


PROMPT = """A person is missing something an application requires. Below is what \
they are missing, and every requirement we have read for this application.

MISSING:
{gap}

REQUIREMENTS WE HAVE READ (id, then text, then the quote from the source page):
{corpus}

Find the requirements in that list which describe ways to satisfy the missing \
thing: accepted alternatives, named tests, accepted documents, thresholds, costs \
or timings that apply to it.

Return JSON:
{{"options": [
  {{"cites": "<requirement id from the list>",
    "name": "short name for this option",
    "what_it_is": "one sentence in plain words",
    "cost": "only if the cited requirement states one, else null",
    "lead_time": "only if the cited requirement states one, else null",
    "accepted_by": "who accepts it, only if stated, else null"}}
]}}

Rules:
- "cites" MUST be an id from the list. Anything else is discarded automatically.
- Never name a test, body, fee or timeframe that is not in the cited requirement. \
Do not use what you know from elsewhere.
- If the list contains nothing that describes a way through, return an empty \
options list. That is a correct answer and it is more useful than a guess."""


class RouteFinder:
    """Finds ways through a gap, using only what the corpus already holds."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _call(self, prompt: str):
        """Delegates to migragent.model, which retries and reports properly.

        Every caller used to carry its own copy of this and none of them
        retried, so one run hitting the quota produced three unrelated
        looking symptoms. See D20.
        """
        return call_json(
            project=self._project, model=self._model,
            location=self._location, credentials=self._credentials,
            parts=[{"text": prompt}],
        )

    def find(self, gap: dict[str, Any],
             corpus: list[dict[str, Any]]) -> tuple[Route, list[dict[str, str]]]:
        route = Route(requirement_id=gap.get("requirement_id", ""),
                      requirement_text=gap.get("text", ""))
        dropped: list[dict[str, str]] = []

        by_id = {r.get("id", ""): r for r in corpus}
        if not by_id:
            route.no_route_reason = "nothing has been read for this lane yet"
            return route, dropped

        listing = "\n".join(
            f'- {r.get("id","")}: {r.get("text","")}\n    quote: {r.get("quote","")[:200]}'
            for r in corpus[:120]
        )

        try:
            parsed = self._call(PROMPT.format(gap=gap.get("text", ""), corpus=listing))
        except Exception as exc:  # noqa: BLE001
            route.no_route_reason = f"the route search failed: {exc}"
            return route, dropped

        for item in parsed.get("options", []):
            cited = str(item.get("cites") or "")
            source = by_id.get(cited)
            if source is None:
                # A route resting on a requirement we do not hold is exactly the
                # confident invention this whole build guards against, and in
                # this feature it would be the most damaging kind: a named test
                # that is not accepted, with a price on it.
                dropped.append({"cites": cited, "why": "cites a requirement we do not hold"})
                continue

            route.options.append(Option(
                name=str(item.get("name") or "")[:80],
                what_it_is=str(item.get("what_it_is") or ""),
                cost=item.get("cost") or None,
                lead_time=item.get("lead_time") or None,
                accepted_by=item.get("accepted_by") or None,
                source_url=source.get("source_url", ""),
                read_at=source.get("read_at", ""),
                quote=source.get("quote", ""),
            ))

        if not route.options and route.no_route_reason is None:
            route.no_route_reason = (
                "we have not read a page that says what the alternatives are"
            )
        return route, dropped
