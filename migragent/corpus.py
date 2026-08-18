"""The corpus: every requirement we have read, and what could not be sourced.

The registry says which pages exist and when they were last read. This is what
those pages turned out to say.

It is written only by the writer identity, which is the one principal allowed to
publish. The researcher extracts and cannot write here, and that is enforced by
Google rather than by this file being careful, which `tools/test_isolation.py`
checks and D1 records.

Requirements are keyed on the source URL plus a digest of the quote, so
re-reading an unchanged page updates rows in place rather than piling up copies
of the same requirement. That also means a requirement whose quote changes is a
new row, which is what the watcher wants: the old one stops being confirmed and
the change is visible rather than overwritten.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from .extract import Extraction, Requirement

REQUIREMENTS = "requirements"
OPEN_QUESTIONS = "open_questions"
READS = "reads"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def requirement_id(source_url: str, quote: str) -> str:
    """Stable across re-reads of the same page saying the same thing."""
    digest = hashlib.sha256(f"{source_url}\n{quote}".encode()).hexdigest()[:24]
    return digest


@dataclass
class PageRead:
    """One page, read once, and what came of it.

    Kept even when a page yields nothing. A page that produced no requirements
    is a real result and the difference between "we have not looked" and "we
    looked and it says nothing" is exactly the difference this product sells.
    """

    source_id: str
    source_url: str
    read_at: str
    jurisdiction: str
    lane: str
    kept: int
    dropped: int
    open_questions: int
    model_error: str | None = None
    dropped_detail: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class Corpus:
    """Reads and writes what the pages said."""

    def __init__(self, client: firestore.Client) -> None:
        self._db = client

    def record(self, source_id: str, extraction: Extraction,
               jurisdiction: str, lane: str) -> PageRead:
        batch = self._db.batch()
        written = 0

        for req in extraction.requirements:
            doc = self._db.collection(REQUIREMENTS).document(
                requirement_id(req.source_url, req.quote)
            )
            payload = req.to_dict()
            payload["source_id"] = source_id
            payload["last_confirmed_at"] = extraction.read_at
            batch.set(doc, payload, merge=True)
            written += 1
            if written % 400 == 0:
                batch.commit()
                batch = self._db.batch()

        # Open questions are stored, not discarded. They are the honest back of
        # the guide, and they are also the best list of what to go and read next.
        for question in extraction.open_questions:
            qid = hashlib.sha256(
                f"{extraction.source_url}\n{question}".encode()
            ).hexdigest()[:24]
            batch.set(self._db.collection(OPEN_QUESTIONS).document(qid), {
                "question": question,
                "source_url": extraction.source_url,
                "source_id": source_id,
                "jurisdiction": jurisdiction,
                "lane": lane,
                "raised_at": extraction.read_at,
            }, merge=True)

        read = PageRead(
            source_id=source_id,
            source_url=extraction.source_url,
            read_at=extraction.read_at,
            jurisdiction=jurisdiction,
            lane=lane,
            kept=len(extraction.requirements),
            dropped=len(extraction.dropped),
            open_questions=len(extraction.open_questions),
            model_error=extraction.model_error,
            dropped_detail=extraction.dropped[:20],
        )
        batch.set(
            self._db.collection(READS).document(f"{source_id}-{extraction.read_at}"),
            read.to_dict(),
        )
        batch.commit()
        return read

    def requirements_for(self, jurisdiction: str, lane: str) -> list[dict[str, Any]]:
        """Everything read for one lane.

        Two equality filters and then sorting in Python, because a where plus an
        order_by needs a composite index and a fresh clone would 400 on an index
        nobody created. Rule 30.
        """
        query = (
            self._db.collection(REQUIREMENTS)
            .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
            .where(filter=firestore.FieldFilter("lane", "==", lane))
        )
        rows = [d.to_dict() for d in query.stream()]
        order = {"eligibility": 0, "document": 1, "requirement": 2, "cost": 3, "timing": 4}
        return sorted(rows, key=lambda r: (order.get(r.get("category", ""), 5),
                                           r.get("source_url", "")))

    def open_questions_for(self, jurisdiction: str, lane: str) -> list[dict[str, Any]]:
        query = (
            self._db.collection(OPEN_QUESTIONS)
            .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
            .where(filter=firestore.FieldFilter("lane", "==", lane))
        )
        return sorted((d.to_dict() for d in query.stream()),
                      key=lambda r: r.get("question", ""))

    def _count(self, query) -> int:
        return int(query.count().get()[0][0].value)

    def _sum(self, field: str) -> int:
        """Server-side sum, so the totals do not get slower as the corpus grows."""
        result = self._db.collection(READS).sum(field, alias="total").get()
        return int(result[0][0].value or 0)

    def totals(self) -> dict[str, int]:
        """Counted on the server. Rule 5 says the number is real, not that it is
        expensive: dragging every read row back to add up two integers costs a
        document read per page ever read."""
        return {
            "requirements": self._count(self._db.collection(REQUIREMENTS)),
            "open_questions": self._count(self._db.collection(OPEN_QUESTIONS)),
            "pages_read": self._count(self._db.collection(READS)),
            "kept": self._sum("kept"),
            "dropped": self._sum("dropped"),
        }
