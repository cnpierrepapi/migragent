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



def requirement_id(source_url: str, quote: str, lane: str = "") -> str:
    """Stable across re-reads of the same page saying the same thing, per lane.

    THE LANE USED TO BE MISSING AND IT COST A GUIDE ITS FRONT PAGE.

    A government page can belong to two lanes. `gov.uk/skilled-worker-visa` is
    the work lane's entry page, and the study walk reaches it as well. With
    identity as url plus quote, both lanes shared one document, so whichever
    round ran last owned it and anything done to it in one lane happened in the
    other.

    That turned a correct fix into a regression. D32 retired the Skilled Worker
    requirements from the study guide, where they did not belong, and because
    they were the same documents it retired them from the work guide, where they
    are the whole point. The UK work guide lost its own front page, and no count
    on any screen so much as flinched.

    So a requirement is identified by the page, the sentence, and the question it
    answers. Rows written before this carry the old id and are moved by
    tools/migrate_requirement_ids.py rather than left to drift.
    """
    digest = hashlib.sha256(f"{source_url}\n{quote}\n{lane}".encode()).hexdigest()[:24]
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
                requirement_id(req.source_url, req.quote, lane)
            )
            payload = req.to_dict()
            payload["source_id"] = source_id
            payload["last_confirmed_at"] = extraction.read_at

            # A page that still says it un-retires it. Without this a retirement
            # is permanent whatever the page goes on to say: `merge=True` leaves
            # alone the fields it is not given, so re-reading a page updated the
            # date on a row that stayed invisible for good. That is D25b's shape
            # again, a field that can be set and never cleared.
            payload["retired_at"] = firestore.DELETE_FIELD
            payload["retired_reason"] = firestore.DELETE_FIELD

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

    def requirements_for(self, jurisdiction: str, lane: str,
                         allowed_urls: set[str] | None = None) -> list[dict[str, Any]]:
        """Everything read for one lane, optionally narrowed to nearby pages.

        `allowed_urls` is how the guide stays about the thing you asked for. The
        walk reaches other visa types two hops out, so a UK study walk holds the
        Ancestry visa and airport transit pages. They are real pages that really
        change and they belong in the corpus, and a study guide that quoted them
        would be padding. The corpus stays wide, the guide stays close.

        Two equality filters and then sorting in Python, because a where plus an
        order_by needs a composite index and a fresh clone would 400 on an index
        nobody created. Rule 30.
        """
        query = (
            self._db.collection(REQUIREMENTS)
            .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
            .where(filter=firestore.FieldFilter("lane", "==", lane))
        )
        # The document id is the requirement's identity and the matcher needs
        # it, so it travels with the row rather than being left behind in the
        # key.
        rows = [{**d.to_dict(), "id": d.id} for d in query.stream()]
        # A requirement the page has stopped making never reaches a guide again.
        # It stays in the collection with the date it was retired, because the
        # record of what a government used to ask for is worth keeping and is
        # what the change screen is built from. It is simply no longer something
        # we tell somebody to go and do.
        rows = [r for r in rows if not r.get("retired_at")]
        if allowed_urls is not None:
            rows = [r for r in rows if r.get("source_url", "").rstrip("/") in allowed_urls]
        order = {"eligibility": 0, "document": 1, "requirement": 2, "cost": 3, "timing": 4}
        return sorted(rows, key=lambda r: (order.get(r.get("category", ""), 5),
                                           r.get("source_url", "")))

    def open_questions_for(self, jurisdiction: str, lane: str,
                           allowed_urls: set[str] | None = None) -> list[dict[str, Any]]:
        query = (
            self._db.collection(OPEN_QUESTIONS)
            .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
            .where(filter=firestore.FieldFilter("lane", "==", lane))
        )
        # The document id is the requirement's identity and the matcher needs
        # it, so it travels with the row rather than being left behind in the
        # key.
        rows = [{**d.to_dict(), "id": d.id} for d in query.stream()]
        if allowed_urls is not None:
            rows = [r for r in rows if r.get("source_url", "").rstrip("/") in allowed_urls]
        return sorted(rows, key=lambda r: r.get("question", ""))

    def live_ids_for_source(self, source_id: str) -> set[str]:
        """Requirement ids currently standing from one page.

        The watcher needs this before it re-extracts, so it can tell the
        difference between a requirement the page still makes and one it has
        stopped making.
        """
        query = self._db.collection(REQUIREMENTS).where(
            filter=firestore.FieldFilter("source_id", "==", source_id)
        )
        return {d.id for d in query.stream() if not d.to_dict().get("retired_at")}

    def retire(self, requirement_ids: set[str], at: str, reason: str) -> int:
        """Stop a requirement being told to anybody, without deleting it.

        Deleting would destroy the only evidence that the page used to say it,
        which is exactly what the change screen is for. So the row stays, gains
        the date we noticed and the reason, and drops out of every guide from
        that moment.
        """
        if not requirement_ids:
            return 0
        batch = self._db.batch()
        for i, rid in enumerate(sorted(requirement_ids), 1):
            batch.set(self._db.collection(REQUIREMENTS).document(rid), {
                "retired_at": at,
                "retired_reason": reason,
            }, merge=True)
            if i % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return len(requirement_ids)

    def has_been_read(self, source_id: str) -> bool:
        """Whether this page has ever produced a read row.

        A backfill uses this to skip pages already done, so a run that dies two
        thirds through resumes rather than starting again and paying for every
        page a second time.
        """
        query = self._db.collection(READS).where(
            filter=firestore.FieldFilter("source_id", "==", source_id)
        ).limit(1)
        return any(True for _ in query.stream())

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
