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
from migragent.board import Board  # noqa: E402
from migragent.alerts import Alert, Alerts, Watches, alert_id  # noqa: E402
from migragent.board import Piece  # noqa: E402
from migragent.cases import (ALERTS, BOARD_ITEMS, CASE_DOCUMENTS, CASES, COVERAGE,
                             CV_CLONES, CV_FIELDS, FITS, PROFILES, RESULTS,
                             WATCHES, Cases)  # noqa: E402
from migragent.cv import CVClones  # noqa: E402
from migragent.profile import Profiles  # noqa: E402
from migragent.cv import CV, Claim, CVStore  # noqa: E402
from migragent.fit import Fit, Fits, Match  # noqa: E402
from migragent.documents import Field, ReadDocument  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"

# A real one-pixel PNG. It has to survive migragent.profile's signature check,
# so a string of the right length would not do.
_PROBE_PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
              "IQAAAABJRU5ErkJggg==")


def count(db, collection: str, case_id: str) -> int:
    if collection == CASES:
        return 1 if db.collection(CASES).document(case_id).get().exists else 0
    if collection in (COVERAGE, RESULTS, CV_FIELDS, WATCHES, PROFILES):
        return 1 if db.collection(collection).document(case_id).get().exists else 0
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
    cases.save_result(case.case_id, {"routes": [], "form": {"questions": []}})

    # Build 5 put a person's CV, their fit scores and their board on the same
    # case. A delete that missed any of them would be the most sensitive miss of
    # the lot, so the fixture writes all three.
    CVStore(db).put(case.case_id, CV(
        filename="probe-cv.pdf", read_at=case.created_at, text_layer=True,
        claims=[Claim(kind="role", value="welder", quote="welder", verified=True)]))
    for i in range(2):
        Fits(db).put(Fit(listing_id=f"probe-listing-{i}", case_id=case.case_id,
                         posting_url="https://example.gov/probe", read_at=case.created_at,
                         matches=[Match(asks_for="weld", quote="weld", met=True)]))
        Board(db).add(case.case_id, {"listing_id": f"probe-listing-{i}",
                                     "title": "probe", "url": "https://example.gov/probe"})

    # Build 6 put the watch and its alerts on the case too. The alerts are the
    # most sensitive rows of the lot: each one says what somebody is applying
    # for, in which country, and when they were told about it.
    Watches(db).start(case.case_id, case.jurisdiction, case.lane)
    Alerts(db).record([Alert(
        alert_id=alert_id(case.case_id, "rule", f"probe-{i}"),
        case_id=case.case_id, kind="rule", headline="probe",
        observed_at=case.created_at, created_at=case.created_at) for i in range(2)])

    # Build 7 clones the CV into each country's shape. Three more documents
    # holding what somebody's CV says, and they go with everything else.
    for code in ("CA", "UK", "EU"):
        CVClones(db).put(case.case_id, code, Piece(
            kind="cv_clone", title=f"CV shaped for {code}", body="probe", note="draft"))

    # A name and a picture: the one thing here that is deliberately kept, which
    # makes proving it is deleted more important rather than less.
    Profiles(db).save(case.case_id, name="Probe Person",
                      avatar="data:image/png;base64," + _PROBE_PNG)

    watched = (CASES, CASE_DOCUMENTS, COVERAGE, RESULTS, CV_FIELDS, FITS,
               BOARD_ITEMS, CV_CLONES, PROFILES, WATCHES, ALERTS)
    before = {c: count(db, c, case.case_id) for c in watched}
    print(f"before delete: {before}")
    if (before[CASE_DOCUMENTS] != 3 or before[CASES] != 1 or before[COVERAGE] != 1
            or before[CV_FIELDS] != 1 or before[FITS] != 2 or before[BOARD_ITEMS] != 2
            or before[WATCHES] != 1 or before[ALERTS] != 2
            or before[CV_CLONES] != 3 or before[PROFILES] != 1):
        print("FAIL  the fixture did not write what it meant to, so a clean")
        print("      delete afterwards would prove nothing")
        return 1

    removed = cases.delete(case.case_id)
    print(f"delete reported: {removed}")

    after = {c: count(db, c, case.case_id) for c in watched}
    print(f"after delete:  {after}")

    survivors = {c: n for c, n in after.items() if n}
    if survivors:
        print(f"\nFAIL  rows survived the delete: {survivors}")
        return 1
    if removed != {"documents": 3, "coverage": 1, "result": 1, "cv": 1,
                   "fits": 2, "board_items": 2, "cv_clones": 3, "profile": 1,
                   "watch": 1, "alerts": 2, "case": 1}:
        print(f"\nFAIL  delete reported {removed}, which does not match what was written")
        return 1

    print("\nPASS  every row a case touched was removed, and the reported counts match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
