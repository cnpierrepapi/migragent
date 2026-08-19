"""Mark the same page in a language we do not read from.

    python -m tools.dedupe_languages --dry-run
    python -m tools.dedupe_languages

Spain's consular site serves one procedure page six times, once per interface
language, at URLs that differ only by a `/language/` segment. The walk found all
six, the registry counted all six as sources, and the extractor read all six and
produced six near identical copies of the same requirement.

That is three separate costs. It inflates the source count on the front of the
product, which is the one number that has to be true. It pays for the same page
six times. And it puts six copies of one requirement into a guide.

**Nothing is deleted.** The row stays with `blocked = duplicate_language` and a
reason in words, because a source that vanishes from a count is how a count
starts lying, and because the rows are evidence that the walk found them.

Requirements already extracted from those pages are retired with the same
reason, so they stop reaching guides while the record of having read them stays.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.corpus import Corpus  # noqa: E402
from migragent.registry import Registry  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WRITER, PROJECT),
    )
    registry = Registry(db)
    corpus = Corpus(db)

    redundant = []
    for source in registry.all():
        if source.blocked is not None:
            continue
        reason = Registry.redundant_language(source.url, source.jurisdiction)
        if reason:
            redundant.append((source, reason))

    print(f"{len(redundant)} sources are the same page in a language we do not read from\n")
    for source, reason in redundant:
        print(f"  {source.jurisdiction} {source.lane:<6} {reason}")
        print(f"      {source.url[-88:]}")

    if not redundant:
        return 0
    if dry_run:
        print("\ndry run, nothing written")
        return 0

    retired_total = 0
    for source, reason in redundant:
        source.blocked = "duplicate_language"
        source.blocked_reason = reason
        registry.put(source)
        ids = corpus.live_ids_for_source(source.source_id)
        retired_total += corpus.retire(ids, now, f"duplicate source: {reason}")

    print(f"\nmarked {len(redundant)} sources, retired {retired_total} requirements")
    print(f"registry now: {registry.counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
