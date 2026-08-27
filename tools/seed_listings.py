"""Read job postings from a government board, for occupations we already hold.

    python -m tools.seed_listings CA --limit 5 --dry-run
    python -m tools.seed_listings CA

The occupations come from the shortage lists this pipeline already read, so
nothing here decides what is worth looking for. If an occupation is not on a
government's own list of what it is short of, this does not go looking for it.

Only Canada is wired up. Job Bank is allowed by robots, answers a plain client
and carries what a listing needs in its markup. The other boards checked on
19 August 2026 are in migragent/listings.py, with which ones refused and how.

A posting is an opportunity, never a source for a requirement. Every row stores
`provenance: employer`, and the board and the site the board gathered it from
stay two separate fields so an advert cannot inherit a government's authority.
"""
from __future__ import annotations
import os

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.listings import JobBank, Listings  # noqa: E402
from migragent.occupations import Shortages  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")

BOARDS = {"CA": JobBank}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 64

    jurisdiction = sys.argv[1].upper()
    dry_run = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    board_class = BOARDS.get(jurisdiction)
    if board_class is None:
        print(f"no readable government board wired up for {jurisdiction}. "
              f"See migragent/listings.py for what was checked and what refused.")
        return 1
    board = board_class()

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WRITER, PROJECT))
    occupations = Shortages(db).for_jurisdiction(jurisdiction)
    if not occupations:
        print(f"no occupations held for {jurisdiction}, so there is nothing to ask about")
        return 1

    # Deduplicated because a government can name the same job in two categories,
    # and asking a board the same question twice is rude rather than thorough.
    seen: set[str] = set()
    wanted = []
    for occupation in occupations:
        title = (occupation.get("title") or "").strip()
        key = title.lower()
        if title and key not in seen:
            seen.add(key)
            wanted.append(occupation)
    if limit:
        wanted = wanted[:limit]

    print(f"{len(wanted)} occupation(s) to ask {board.BOARD} about\n")

    # One request at a time with a real pause. This is somebody's employment
    # service, not a target.
    fetcher = Fetcher(delay_seconds=2.0)
    store = Listings(db)

    total = 0
    empty: list[str] = []
    for i, occupation in enumerate(wanted, 1):
        title = occupation["title"]
        found: list = []
        why = None
        used = title
        for query in board.queries_for(title):
            page = fetcher.fetch(board.search_url(query))
            found, why = board.parse(page, title, occupation.get("occupation_id"), query)
            used = query
            if found:
                break

        if not found:
            empty.append(f"{title}: {why}")
            print(f"  {i:>3}/{len(wanted)}  {0:>3}  {title[:52]:<52} {why or ''}")
            continue

        if not dry_run:
            store.record(found)
        total += len(found)
        note = "" if used == title else f"(asked for '{used}')"
        print(f"  {i:>3}/{len(wanted)}  {len(found):>3}  {title[:52]:<52} {note}")

    print(f"\n{total} listing(s) from {len(wanted) - len(empty)} of {len(wanted)} occupations")
    if empty:
        print(f"\n{len(empty)} occupation(s) returned nothing:")
        for line in empty[:25]:
            print(f"  {line[:110]}")
    if dry_run:
        print("\ndry run, nothing written")
    else:
        print(f"\nlistings now: {store.counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
