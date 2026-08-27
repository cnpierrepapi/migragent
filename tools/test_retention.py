"""Prove the retention sweeper deletes what is expired and nothing else.

A sweeper that deletes everything passes a test that only checks expired cases
are gone. So this writes both an expired case and a live one, and it fails if
the live one is touched. The second half is the half that matters.

    python tools/test_retention.py
"""
from __future__ import annotations
import os

import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.cases import CASES, Cases  # noqa: E402
from migragent.documents import Field, ReadDocument  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")


def main() -> int:
    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WEB, PROJECT),
    )
    cases = Cases(db)

    expired = cases.create("CA", "study")
    live = cases.create("UK", "study")
    for case in (expired, live):
        cases.add_document(case.case_id, ReadDocument(
            kind="passport", filename="probe.pdf", read_at=case.created_at,
            text_layer=True,
            fields=[Field(name="date_of_expiry", value="2029-01-01",
                          quote="probe", verified=True)]))
        cases.save_coverage(case.case_id, {"score": 10, "covered": 1,
                                           "document_requirements": 10})

    # Push one case's expiry into the past. Touching a case resets it, so this
    # is written after the documents rather than before.
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    db.collection(CASES).document(expired.case_id).update({"expires_at": past})

    print(f"expired case {expired.case_id[:10]}... expires_at {past}")
    print(f"live case    {live.case_id[:10]}... expires_at {live.expires_at}")

    listed = cases.expired()
    if expired.case_id not in listed:
        print("FAIL  the expired case was not listed as expired")
        return 1
    if live.case_id in listed:
        print("FAIL  the live case was listed as expired")
        return 1
    print(f"\nexpired() found {len(listed)} case(s), including ours, excluding the live one")

    swept = cases.sweep()
    print(f"sweep reported: {swept}")

    gone = cases.get(expired.case_id) is None
    survived = cases.get(live.case_id) is not None
    print(f"\n  expired case deleted:  {gone}")
    print(f"  live case untouched:   {survived}")

    if not gone:
        print("\nFAIL  the expired case survived the sweep")
        return 1
    if not survived:
        print("\nFAIL  the sweep deleted a case that had not expired")
        return 1
    if len(cases.documents(expired.case_id)) != 0:
        print("\nFAIL  the swept case left document rows behind")
        return 1
    if len(cases.documents(live.case_id)) != 1:
        print("\nFAIL  the live case lost its documents")
        return 1

    cases.delete(live.case_id)
    print("\nPASS  expired cases are removed, live cases are left alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
