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
RESULTS = "case_results"

# Build 5 added three more places a person's data lives. They are named here
# rather than in the delete function, because a collection that is written
# somewhere and not listed here is a delete that quietly stopped being true.
CV_FIELDS = "case_cv"
FITS = "case_fits"
BOARD_ITEMS = "board_items"

# Build 6 added two more: the watch, and what it has told this person. Same rule
# as above. A collection written somewhere and not deleted here is a delete that
# quietly stopped being true, and an alerts row carries what somebody is applying
# for as surely as a case row does.
WATCHES = "watches"
ALERTS = "alerts"

# Build 7 clones the CV into each country's shape on upload. Same rule again:
# listed here or the delete quietly stopped being true.
CV_CLONES = "case_cv_clones"

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
                detected_kind=d.get("detected_kind"),
                detected_reason=d.get("detected_reason", ""),
                agreement_state=d.get("agreement_state", "unchecked"),
                agreement_note=d.get("agreement_note", ""),
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

    def save_result(self, case_id: str, result: dict[str, Any]) -> None:
        """The routes and the generated form, from one run."""
        self._db.collection(RESULTS).document(case_id).set(result)
        self.touch(case_id)

    def result(self, case_id: str) -> dict[str, Any] | None:
        snap = self._db.collection(RESULTS).document(case_id).get()
        return snap.to_dict() if snap.exists else None

    def delete(self, case_id: str) -> dict[str, int]:
        """Delete everything about a case, and report what went.

        Returns counts rather than a reassurance, because a delete that says
        "done" is not evidence of anything. A delete that leaves an orphan is a
        broken delete, so the numbers are the point and the test asserts on them.
        """
        removed = {"documents": 0, "coverage": 0, "result": 0, "cv": 0,
                   "fits": 0, "board_items": 0, "cv_clones": 0, "watch": 0,
                   "alerts": 0, "case": 0}

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

        res = self._db.collection(RESULTS).document(case_id)
        if res.get().exists:
            res.delete()
            removed["result"] = 1

        cv = self._db.collection(CV_FIELDS).document(case_id)
        if cv.get().exists:
            cv.delete()
            removed["cv"] = 1

        # Fits and board items are per case and there can be many of each.
        for collection, key in ((FITS, "fits"), (BOARD_ITEMS, "board_items"),
                                (CV_CLONES, "cv_clones")):
            rows = self._db.collection(collection).where(
                filter=firestore.FieldFilter("case_id", "==", case_id))
            batch = self._db.batch()
            n = 0
            for snap in rows.stream():
                batch.delete(snap.reference)
                removed[key] += 1
                n += 1
                if n % 400 == 0:
                    batch.commit()
                    batch = self._db.batch()
            batch.commit()

        watch = self._db.collection(WATCHES).document(case_id)
        if watch.get().exists:
            watch.delete()
            removed["watch"] = 1

        alerts = self._db.collection(ALERTS).where(
            filter=firestore.FieldFilter("case_id", "==", case_id))
        batch = self._db.batch()
        n = 0
        for snap in alerts.stream():
            batch.delete(snap.reference)
            removed["alerts"] += 1
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        if n:
            batch.commit()

        case = self._db.collection(CASES).document(case_id)
        if case.get().exists:
            case.delete()
            removed["case"] = 1

        return removed

    def expired(self, limit: int = 500) -> list[str]:
        """Cases past their retention date."""
        now = _now().isoformat(timespec="seconds")
        query = self._db.collection(CASES).where(
            filter=firestore.FieldFilter("expires_at", "<", now)).limit(limit)
        return [s.id for s in query.stream()]

    def sweep(self, limit: int = 500) -> dict[str, int]:
        """Delete every case past its retention date, and report the numbers.

        This is what turns the retention window from a date written on a row
        into something that happens. Before it existed, docs/DATA_PROTECTION.md
        said so in as many words rather than letting a promise stand on nothing.

        It reuses `delete`, so a swept case goes the same way a person's own
        delete goes and cannot leave a different set of orphans.
        """
        swept = {"cases": 0, "documents": 0, "coverage": 0, "results": 0}
        for case_id in self.expired(limit):
            removed = self.delete(case_id)
            swept["cases"] += removed["case"]
            swept["documents"] += removed["documents"]
            swept["coverage"] += removed["coverage"]
            swept["results"] += removed["result"]
        return swept
