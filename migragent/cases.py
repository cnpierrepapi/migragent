"""A person's case: what they are applying for, and what they have.

Stores the fields read from uploaded documents. Never the documents.
See docs/DATA_PROTECTION.md.

A case is identified by an opaque id held in a cookie. There is no account in
Build 2, so this is deliberately the weakest possible link between a person and
their data: guessable by nobody, recoverable by nobody, and gone when the
retention window closes.
"""
from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore

from .documents import ReadDocument

CASES = "cases"
CASE_DOCUMENTS = "case_documents"
COVERAGE = "case_coverage"

# Long enough to come back and finish, short enough that nothing sits around for
# a reason nobody could defend. docs/DATA_PROTECTION.md explains the choice.
RETENTION_DAYS = 30


def new_case_id() -> str:
    return secrets.token_urlsafe(24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Case:
    case_id: str
    jurisdiction: str
    lane: str
    created_at: str
    last_touched_at: str
    expires_at: str
    document_count: int = 0
    score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Cases:
    """Reads and writes cases, and deletes them properly."""

    def __init__(self, client: firestore.Client) -> None:
        self._db = client

    def create(self, jurisdiction: str, lane: str) -> Case:
        now = _now()
        case = Case(
            case_id=new_case_id(),
            jurisdiction=jurisdiction,
            lane=lane,
            created_at=now.isoformat(timespec="seconds"),
            last_touched_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds"),
        )
        self._db.collection(CASES).document(case.case_id).set(case.to_dict())
        return case

    def get(self, case_id: str) -> Case | None:
        snap = self._db.collection(CASES).document(case_id).get()
        if not snap.exists:
            return None
        return Case(**snap.to_dict())

    def touch(self, case_id: str) -> None:
        """Restart the retention countdown. Using a case keeps it alive."""
        now = _now()
        self._db.collection(CASES).document(case_id).update({
            "last_touched_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds"),
        })

    def add_document(self, case_id: str, doc: ReadDocument) -> str:
        """Store what the document said. Not the document."""
        ref = self._db.collection(CASE_DOCUMENTS).document()
        payload = doc.to_dict()
        payload["case_id"] = case_id
        ref.set(payload)
        self.touch(case_id)
        return ref.id

    def documents(self, case_id: str) -> list[ReadDocument]:
        from .documents import Field

        out: list[ReadDocument] = []
        query = self._db.collection(CASE_DOCUMENTS).where(
            filter=firestore.FieldFilter("case_id", "==", case_id))
        for snap in query.stream():
            d = snap.to_dict()
            out.append(ReadDocument(
                kind=d.get("kind", "other"),
                filename=d.get("filename", ""),
                read_at=d.get("read_at", ""),
                text_layer=d.get("text_layer", False),
                fields=[Field(**f) for f in d.get("fields", [])],
                dropped=d.get("dropped", []),
                error=d.get("error"),
            ))
        return out

    def save_coverage(self, case_id: str, coverage: dict[str, Any]) -> None:
        self._db.collection(COVERAGE).document(case_id).set(coverage)
        self._db.collection(CASES).document(case_id).update(
            {"score": coverage.get("score", 0)})
        self.touch(case_id)

    def coverage(self, case_id: str) -> dict[str, Any] | None:
        snap = self._db.collection(COVERAGE).document(case_id).get()
        return snap.to_dict() if snap.exists else None

    def delete(self, case_id: str) -> dict[str, int]:
        """Delete everything about a case, and report what went.

        Returns counts rather than a reassurance, because a delete that says
        "done" is not evidence of anything. A delete that leaves an orphan is a
        broken delete, so the numbers are the point and the test asserts on them.
        """
        removed = {"documents": 0, "coverage": 0, "case": 0}

        query = self._db.collection(CASE_DOCUMENTS).where(
            filter=firestore.FieldFilter("case_id", "==", case_id))
        batch = self._db.batch()
        n = 0
        for snap in query.stream():
            batch.delete(snap.reference)
            removed["documents"] += 1
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()

        cov = self._db.collection(COVERAGE).document(case_id)
        if cov.get().exists:
            cov.delete()
            removed["coverage"] = 1

        case = self._db.collection(CASES).document(case_id)
        if case.get().exists:
            case.delete()
            removed["case"] = 1

        return removed

    def expired(self, limit: int = 500) -> list[str]:
        """Cases past their retention date.

        The sweeper that acts on this is not built yet, which
        docs/DATA_PROTECTION.md says plainly rather than implying the window
        enforces itself.
        """
        now = _now().isoformat(timespec="seconds")
        query = self._db.collection(CASES).where(
            filter=firestore.FieldFilter("expires_at", "<", now)).limit(limit)
        return [s.id for s in query.stream()]
