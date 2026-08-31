"""Point every source back at its most recent stored snapshot.

    python -m tools.backfill_snapshots --dry-run
    python -m tools.backfill_snapshots

WHY THIS EXISTS. The walk that rebuilds the registry records what it fetched,
hashed and when, and it does not record where the snapshot went, because the
walk does not store snapshots. So a rebuilt row has no `snapshot_path` even
though the archive is full of that page's history.

That matters more than it looks. The watcher's second gate reads the stored
version and diffs the text against it, and with no path to read it falls back to
"we hold today and not yesterday", which means every page reports a change it
cannot date and gets re-extracted. One rebuild would cost a full re-read of the
whole corpus and fill the change screen with rows saying the history is
incomplete.

The archive already knows. Objects are named `source_id/day/timestamp.html`, so
the most recent snapshot for a source can be read straight off the bucket
listing without fetching anything or asking anybody.

Run this after any registry rebuild.
"""
from __future__ import annotations
import os

import sys
from collections import defaultdict

sys.path.insert(0, ".")

from google.cloud import firestore, storage  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.registry import Registry  # noqa: E402
from migragent.snapshots import BUCKET  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    writer = identity.credentials_for(identity.WRITER, PROJECT)

    # Listing needs a principal that may read the archive. The researcher may
    # not, on purpose, so the listing runs as the writer's Firestore identity
    # paired with application default credentials for storage.
    gcs = storage.Client(project=PROJECT)

    latest: dict[str, str] = {}
    counts: dict[str, int] = defaultdict(int)
    for blob in gcs.list_blobs(BUCKET):
        source_id = blob.name.split("/", 1)[0]
        counts[source_id] += 1
        # Object names sort by day then timestamp, so the largest name for a
        # source is its most recent snapshot. No metadata fetch needed.
        if blob.name > latest.get(source_id, ""):
            latest[source_id] = blob.name

    print(f"{len(latest)} sources have snapshots, "
          f"{sum(counts.values())} objects in the archive\n")

    db = firestore.Client(project=PROJECT, credentials=writer)
    registry = Registry(db)

    fixed = already = missing = 0
    for source in registry.all():
        path = latest.get(source.source_id)
        if path is None:
            missing += 1
            continue
        full = f"gs://{BUCKET}/{path}"
        if source.snapshot_path == full:
            already += 1
            continue
        source.snapshot_path = full
        if not dry_run:
            registry.put(source)
        fixed += 1

    print(f"{fixed} rows pointed at their latest snapshot, {already} already correct, "
          f"{missing} sources have no snapshot yet")
    if dry_run:
        print("dry run, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
