"""Mark which registered institutions are actually higher education.

    python -m tools.mark_higher_ed

WHY IT IS NEEDED
----------------
The UK's student sponsor register is not a list of universities. It is a list of
everyone licensed to sponsor a student visa, and 541 of its 946 rows are licensed
for the Child Student route: independent secondary schools. Putney High School
and St Paul's Girls' School are on it, correctly, and neither is anywhere a
person applying for a BSc will ever go.

Ranking the deep reading list without this filter put them above universities,
because they are in London and the area proxy scores every London row the same.

The register's own `routes` column only half answers it. 185 rows are Child
Student only and are clearly out, but St Paul's Girls' is licensed for both
Student and Child Student, so the column cannot separate a sixth form from a
university.

WHAT THIS USES INSTEAD
----------------------
Wikidata's class tree. An institution that appears under "higher education
institution" (Q38723), walked through subclasses, is a higher education
institution: that is what the class means, and it is the same query that found
Cambridge when a hand-written list of class ids did not.

Same rule as tools/find_school_sites.py: this is a lookup aid, never a source.
It decides where reading budget goes. Nothing about it is displayed and no claim
rests on it. A school wrongly left unmarked is a school we read later, which
costs us time and costs nobody anything else.
"""
from __future__ import annotations
import os

import sys
import time

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402
from tools.find_school_sites import COUNTRIES, PAUSE, _key, query  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")


def main() -> int:
    dry = "--dry" in sys.argv

    higher: dict[str, set[str]] = {}
    for i, (code, (qid, label)) in enumerate(COUNTRIES.items()):
        if i:
            print(f"  waiting {PAUSE}s", flush=True)
            time.sleep(PAUSE)
        print(f"  asking Wikidata which {label} institutions are higher education ...",
              flush=True)
        rows = query(qid, walk=True)
        higher[code] = {_key(b.get("itemLabel", {}).get("value", "")) for b in rows}
        print(f"    {len(higher[code])} names", flush=True)

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    store = Institutions(db)
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(store.COLLECTION).stream()]

    marked = 0
    batch = db.batch()
    written = 0
    for row in rows:
        code = row.get("jurisdiction", "")
        is_higher = _key(row.get("name", "")) in higher.get(code, set())
        if not is_higher:
            continue
        marked += 1
        if dry:
            continue
        batch.set(db.collection(store.COLLECTION).document(row["id"]),
                  {"higher_ed": True}, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    if written % 400 and not dry:
        batch.commit()

    print(f"\nmarked {marked} of {len(rows)} institutions as higher education")
    if dry:
        print("--dry, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
