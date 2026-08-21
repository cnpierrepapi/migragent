"""Prove the watch tells the right person the right thing, once.

    python -m tools.test_alerts

WHAT IS BEING CHECKED, BEYOND "it ran"
--------------------------------------
  - a watch produces alerts only from rows observed after it started, so
    turning it on does not deliver a year of history somebody already lived
  - a change the explainer called immaterial never reaches anybody, because a
    watcher that cries wolf daily teaches people to ignore the day it matters
  - running the digest twice writes the same rows, not twice as many
  - a second run does not mark something unread that has already been read
  - a stopped watch produces nothing at all
  - deleting the case takes the watch and every alert with it

WHY THE FIXTURES ARE REAL ROWS AND NOT FAKES
--------------------------------------------
The alerts are built by reading the `changes` and `occupations` collections the
daily round writes. A fake store would prove the arithmetic and nothing about
the join, and the join is the only part that has ever been wrong. So this writes
real rows into the real collections under a probe id, reads them back through
the real Watcher, and deletes them at the end whether it passed or failed.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import datetime, timedelta, timezone  # noqa: E402

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.alerts import ALERTS, Alerts, Watcher, Watches  # noqa: E402
from migragent.cases import Cases  # noqa: E402
from migragent.cv import CVStore  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402
from migragent.listings import Listings  # noqa: E402
from migragent.occupations import Shortages  # noqa: E402
from migragent.round import CHANGES, ChangeWriter  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
PROBE = "probe-alerts"


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(days=days_ago)).isoformat(timespec="seconds")


def write_fixtures(db) -> list:
    """Three changes and one shortage occupation, dated around the mark.

    Written straight to the collections rather than through a round, because
    what is under test is what the digest makes of rows that are already there.
    """
    written = []

    rows = [
        # After the mark, material: this is the one that should reach somebody.
        (f"{PROBE}-material", {"material": True, "after_read_at": _iso(0.2),
                               "summary": "The salary floor rose to £41,700."}),
        # After the mark, immaterial: a cookie banner moved. Nobody hears.
        (f"{PROBE}-immaterial", {"material": False, "after_read_at": _iso(0.2),
                                 "summary": "no change to what is required"}),
        # Material, but before the watch started. Old news, not news.
        (f"{PROBE}-old", {"material": True, "after_read_at": _iso(30),
                          "summary": "Something that happened last month."}),
    ]
    for doc_id, extra in rows:
        payload = {"change_id": doc_id, "source_id": PROBE, "jurisdiction": "CA",
                   "lane": "work", "source_url": "https://example.gov/probe",
                   "before_read_at": _iso(31), "before_sha256": "a", "after_sha256": "b",
                   "added": 2, "removed": 1, "diff_sample": "probe",
                   "summary_by": "model", **extra}
        db.collection(CHANGES).document(doc_id).set(payload)
        written.append(db.collection(CHANGES).document(doc_id))

    occ_id = f"{PROBE}-occupation"
    db.collection("occupations").document(occ_id).set({
        "title": "Probe welders and related machine operators",
        "quote": "Probe welders and related machine operators",
        "jurisdiction": "CA", "source_url": "https://example.gov/probe-shortages",
        "read_at": _iso(0.2), "first_seen_at": _iso(0.2),
    })
    written.append(db.collection("occupations").document(occ_id))
    return written


def main() -> int:
    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WEB, PROJECT),
    )
    cases = Cases(db)
    case = cases.create("CA", "work")
    fixtures = write_fixtures(db)
    marks, store = Watches(db), Alerts(db)
    failures: list[str] = []

    try:
        watch = marks.start(case.case_id, "CA", "work")
        # Started a day ago, so the fixtures dated 0.2 days ago are after the
        # mark and the one dated 30 days ago is before it.
        db.collection("watches").document(case.case_id).update(
            {"started_at": _iso(1)})
        watch = marks.get(case.case_id)
        print(f"watch on {case.case_id[:12]}..., since {watch.since()[:10]}")

        watcher = Watcher(db, changes=ChangeWriter(db), shortages=Shortages(db),
                          institutions=Institutions(db), listings=Listings(db),
                          cvs=CVStore(db))

        first = watcher.digest([watch], store, marks)
        print(f"first digest: {first}")

        rows = store.for_case(case.case_id)
        headlines = [r.get("headline", "") for r in rows]
        for line in headlines:
            print(f"  {line[:80]}")

        if not any("41,700" in h for h in headlines):
            failures.append("the material change did not reach the person it was for")
        if any("no change to what is required" in h for h in headlines):
            failures.append("an immaterial change was reported as news")
        if any("last month" in h for h in headlines):
            failures.append("a change from before the watch started was delivered")
        if not any("Probe welders" in h for h in headlines):
            failures.append("an occupation added to the shortage list was not announced")

        # Every alert has to be able to say where it came from. An alert with no
        # source is a rumour, and this product does not carry rumours.
        for row in rows:
            if not row.get("evidence_by"):
                failures.append(f"an alert carries no source: {row.get('headline')!r}")

        # Read them, the way a person opening the page does.
        store.mark_seen(case.case_id)

        # Run it again. Same day, same rows: the mark has moved, so nothing new,
        # and nothing duplicated either.
        again = marks.get(case.case_id)
        second = watcher.digest([again], store, marks)
        print(f"second digest: {second}")

        after = store.for_case(case.case_id)
        if len(after) != len(rows):
            failures.append(f"a second digest changed the count from {len(rows)} "
                            f"to {len(after)}; ids are not derived after all")
        unread = [r for r in after if not r.get("seen_at")]
        if unread:
            failures.append(f"{len(unread)} alerts were marked unread again by a re-run")

        # Off means off.
        marks.stop(case.case_id)
        if any(w.case_id == case.case_id for w in marks.active()):
            failures.append("a stopped watch is still being run")

    finally:
        for ref in fixtures:
            ref.delete()
        removed = cases.delete(case.case_id)
        print(f"cleanup: {removed}")
        if removed.get("watch") != 1:
            failures.append("deleting the case did not delete the watch")
        if not removed.get("alerts"):
            failures.append("deleting the case did not delete its alerts")
        left = sum(1 for _ in db.collection(ALERTS).where(
            filter=firestore.FieldFilter("case_id", "==", case.case_id)).stream())
        if left:
            failures.append(f"{left} alerts survived the delete")

    if failures:
        print("\nFAIL")
        for line in failures:
            print(f"  {line}")
        return 1

    print("\nPASS  the right things reached the right person, once, with a source "
          "on each, and all of it went when the case did")
    return 0


if __name__ == "__main__":
    sys.exit(main())
