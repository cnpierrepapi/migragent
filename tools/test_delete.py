"""Prove that deleting a case deletes everything about it.

A delete that returns "done" is not evidence. This one counts rows in every
collection a case touches, before and after, and fails if anything survives.
The claim in docs/DATA_PROTECTION.md is allowed to stand only while this passes.

    python tools/test_delete.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.cases import CASE_DOCUMENTS, CASES, COVERAGE, Cases  # noqa: E402
from migragent.documents import Field, ReadDocument  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"


def count(db, collection: str, case_id: str) -> int:
    if collection == CASES:
        return 1 if db.collection(CASES).document(case_id).get().exists else 0
    if collection == COVERAGE:
        return 1 if db.collection(COVERAGE).document(case_id).get().exists else 0
    q = db.collection(collection).where(
        filter=firestore.FieldFilter("case_id", "==", case_id))
    return sum(1 for _ in q.stream())


def main() -> int:
    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WEB, PROJECT),
    )
    cases = Cases(db)

    case = cases.create("CA", "study")
    print(f"created case {case.case_id[:12]}...")

    for i in range(3):
        cases.add_document(case.case_id, ReadDocument(
            kind="passport", filename=f"probe-{i}.pdf", read_at=case.created_at,
            text_layer=True,
            fields=[Field(name="date_of_expiry", value="2029-01-01",
                          quote="probe", verified=True)],
        ))
    cases.save_coverage(case.case_id, {"score": 42, "covered": 4,
                                       "document_requirements": 10})

    before = {c: count(db, c, case.case_id) for c in (CASES, CASE_DOCUMENTS, COVERAGE)}
    print(f"before delete: {before}")
    if before[CASE_DOCUMENTS] != 3 or before[CASES] != 1 or before[COVERAGE] != 1:
        print("FAIL  the fixture did not write what it meant to, so a clean")
        print("      delete afterwards would prove nothing")
        return 1

    removed = cases.delete(case.case_id)
    print(f"delete reported: {removed}")

    after = {c: count(db, c, case.case_id) for c in (CASES, CASE_DOCUMENTS, COVERAGE)}
    print(f"after delete:  {after}")

    survivors = {c: n for c, n in after.items() if n}
    if survivors:
        print(f"\nFAIL  rows survived the delete: {survivors}")
        return 1
    if removed != {"documents": 3, "coverage": 1, "case": 1}:
        print(f"\nFAIL  delete reported {removed}, which does not match what was written")
        return 1

    print("\nPASS  every row a case touched was removed, and the reported counts match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
