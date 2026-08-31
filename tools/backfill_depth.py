"""Set `depth` on rows written before it was recorded, without re-walking.

The walk already stored `lead_url`, the page we were on when we found each one,
so the trail is in the data and the depth can be derived from it. Re-walking a
thousand pages to learn something the rows already imply would spend an hour of
somebody else's bandwidth for nothing.

    python tools/backfill_depth.py
"""
from __future__ import annotations
import os

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.registry import Registry  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")


def main() -> int:
    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WRITER, PROJECT),
    )
    rows = Registry(db).all()

    seeds = {r.url.rstrip("/") for r in rows if r.discovered_via == "seed"}
    depths: dict[str, int] = {u: 0 for u in seeds}

    # Two passes is enough because the walk itself only went two deep.
    for _ in range(3):
        for r in rows:
            url = r.url.rstrip("/")
            if url in depths:
                continue
            lead = (r.lead_url or "").rstrip("/")
            if lead in depths:
                depths[url] = depths[lead] + 1

    batch = db.batch()
    written = 0
    unresolved = 0
    for r in rows:
        url = r.url.rstrip("/")
        depth = depths.get(url)
        if depth is None:
            unresolved += 1
            continue
        if r.depth == depth:
            continue
        batch.update(db.collection("sources").document(r.source_id), {"depth": depth})
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()

    spread: dict[int, int] = {}
    for d in depths.values():
        spread[d] = spread.get(d, 0) + 1
    print(f"set depth on {written} rows, {unresolved} could not be traced to an entry page")
    for d in sorted(spread):
        print(f"  depth {d}: {spread[d]} sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
