"""Shortage lists: the jobs a country says out loud that it cannot fill.

WHY THIS AND NOT A LIST OF COMPANIES
------------------------------------
The obvious way to help somebody find work abroad is to tell them which
employers hire foreigners. Nobody publishes that, so building on it means
inferring a list and then citing ourselves for it.

Every country here publishes something better and publishes it officially: a
list of occupations it cannot fill from its own labour market. The UK has an
immigration salary list, Spain publishes a catalogue of hard to fill occupations
in its official gazette every quarter, Germany's employment agency publishes a
bottleneck analysis, Canada names the categories it selects for.

They are government pages with a publisher and a date, so they arrive through the
same door as everything else and get the same treatment.

WHAT AN OCCUPATION IS AND IS NOT
--------------------------------
It is evidence that a government has said this work is short. That is a fair
reason to think an employer is more likely to sponsor somebody.

It is NOT a requirement. Nothing on a shortage list tells you what you must have
or do, and an occupation must never reach a guide dressed as a requirement. They
are separate collections on purpose.

It is also not a promise. "This is on the shortage list" is a true sentence about
a published list. "You will get a job" is not a sentence this product says.

THE SAME QUOTE RULE
-------------------
An occupation exists only if a verbatim span from the page names it. A list of
jobs is exactly the kind of content a model will happily continue past the end
of, and a plausible occupation that was never on the list is the same defect as
an invented requirement, with the same official link beside it.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .extract import MAX_CHARS, _normalise, page_text
from .fetcher import Fetched
from .model import call_json

PROMPT = """You are reading one page published by a government or a public \
employment service. It concerns occupations that are hard to fill, in shortage, \
in demand, or otherwise prioritised for immigration.

List only the occupations this page ITSELF names.

For each one, return:
  "title": the occupation as the page names it
  "quote": a VERBATIM span copied exactly from the page text below, containing \
that occupation. Copy it character for character. Do not paraphrase, do not join \
two separate lines, do not tidy spelling or capitalisation.
  "code": the occupation code if the page gives one, else null
  "note": any condition the page attaches, such as a region, a salary floor or a \
qualification, else null

Also return:
  "publisher": who the page says publishes this list, else null
  "period": the period or edition the page says the list covers, such as a \
quarter or a year, else null

Rules you must follow:
- If this page names no occupations, return an empty list. An empty list is a \
correct and useful answer, and this page may simply be an index.
- Never add an occupation you know is usually on such lists. Only what is here.
- The "quote" must appear word for word in the page text. It is checked \
automatically and anything that does not match is discarded.
- Do not translate. Give the title in the language of the page.

Return only JSON: \
{"occupations": [...], "publisher": ..., "period": ...}

PAGE TEXT:
"""


def occupation_id(source_url: str, title: str) -> str:
    return hashlib.sha256(f"{source_url}\n{title}".encode()).hexdigest()[:24]


@dataclass
class Occupation:
    """One job a country says it cannot fill, with the line that proves it."""

    title: str
    quote: str
    code: str | None = None
    note: str | None = None

    # Assembled from the fetch. Never from the model.
    source_url: str = ""
    read_at: str = ""
    jurisdiction: str = ""
    source_language: str = ""

    # What the page says about itself. From the model, so labelled as claimed
    # rather than as fact, and both are shown next to a link anybody can open.
    publisher_claimed: str | None = None
    period_claimed: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ShortageReading:
    """What one shortage list page produced, including what it failed to produce."""

    source_url: str
    read_at: str
    occupations: list[Occupation] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    publisher: str | None = None
    period: str | None = None
    model_error: str | None = None

    @property
    def kept(self) -> int:
        return len(self.occupations)


class ShortageReader:
    """Reads a shortage list and keeps only the jobs the page can be shown to name."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def read(self, page: Fetched, jurisdiction: str, language: str) -> ShortageReading:
        result = ShortageReading(source_url=page.final_url or page.url,
                                 read_at=page.read_at)

        text = page_text(page)
        if not text:
            result.model_error = "no readable text on the page"
            return result

        try:
            parsed = call_json(
                project=self._project, model=self._model, location=self._location,
                credentials=self._credentials,
                parts=[{"text": PROMPT + text[:MAX_CHARS]}],
            )
        except Exception as exc:  # noqa: BLE001
            result.model_error = str(exc)
            return result

        haystack = _normalise(text)
        result.publisher = (parsed.get("publisher") or None)
        result.period = (parsed.get("period") or None)

        for item in parsed.get("occupations", []):
            title = str(item.get("title") or "").strip()
            quote = str(item.get("quote") or "").strip()

            if not title or not quote:
                result.dropped.append({"title": title, "why": "no quote given"})
                continue

            if _normalise(quote) not in haystack:
                result.dropped.append({
                    "title": title, "quote": quote,
                    "why": "the quote is not on the page",
                })
                continue

            # A quote that does not contain the occupation it is offered as
            # evidence for proves nothing. This is the shortage list version of
            # a real sentence with one number changed: the span is genuinely on
            # the page and has nothing to do with the job named beside it.
            if _normalise(title) not in _normalise(quote):
                result.dropped.append({
                    "title": title, "quote": quote,
                    "why": "the quote does not contain this occupation",
                })
                continue

            result.occupations.append(Occupation(
                title=title,
                quote=quote,
                code=item.get("code") or None,
                note=item.get("note") or None,
                source_url=result.source_url,
                read_at=result.read_at,
                jurisdiction=jurisdiction,
                source_language=language,
                publisher_claimed=result.publisher,
                period_claimed=result.period,
            ))

        return result


class Shortages:
    """Stores occupations. Never mixed with requirements, per the module docstring."""

    COLLECTION = "occupations"

    def __init__(self, client) -> None:
        self._db = client

    def record(self, reading: ShortageReading, source_id: str) -> int:
        batch = self._db.batch()
        for i, occ in enumerate(reading.occupations, 1):
            payload = occ.to_dict()
            payload["source_id"] = source_id
            batch.set(
                self._db.collection(self.COLLECTION).document(
                    occupation_id(occ.source_url, occ.title)),
                payload, merge=True,
            )
            if i % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return len(reading.occupations)

    def for_jurisdiction(self, jurisdiction: str) -> list[dict[str, Any]]:
        from google.cloud import firestore

        query = self._db.collection(self.COLLECTION).where(
            filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
        rows = [{**d.to_dict(), "id": d.id} for d in query.stream()]
        return sorted(rows, key=lambda r: r.get("title", ""))

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self._db.collection(self.COLLECTION).select(["jurisdiction"]).stream():
            j = d.to_dict().get("jurisdiction", "")
            out[j] = out.get(j, 0) + 1
        return out
