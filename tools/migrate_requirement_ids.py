"""Move requirements onto lane-scoped ids.

    python -m tools.migrate_requirement_ids --dry-run
    python -m tools.migrate_requirement_ids

A requirement used to be identified by its page and its sentence. It is now
identified by its page, its sentence and its lane, because a page can serve two
lanes and the old identity made them one document. See `requirement_id` and D37.

Rows written under the old id keep it until they are moved, and a row nobody
moves is a row that quietly stops matching anything the code writes next. So
this rewrites each one under its new id and deletes the old, in that order, so a
run that dies half way leaves duplicates rather than a hole.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not un-retire anything. A row retired for a real reason stays retired,
and the ones retired by the identity collision come back the ordinary way, by a
page being read again and still saying what it said. Reviving rows here would
mean guessing which retirements were the collision's fault and which were real,
and that is a guess about what a government page says.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.corpus import REQUIREMENTS, requirement_id  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WRITER, PROJECT))

    rows = [(doc.id, doc.to_dict()) for doc in db.collection(REQUIREMENTS).stream()]
    print(f"{len(rows)} requirements held\n")

    moves: list[tuple[str, str, dict]] = []
    already = 0
    unmovable = 0

    for old_id, row in rows:
        url, quote, lane = row.get("source_url"), row.get("quote"), row.get("lane")
        if not url or not quote or not lane:
            # Nothing to compute an identity from. Left alone and counted rather
            # than deleted, because a row that cannot be moved is a row worth
            # somebody looking at.
            unmovable += 1
            continue
        new_id = requirement_id(url, quote, lane)
        if new_id == old_id:
            already += 1
            continue
        moves.append((old_id, new_id, row))

    print(f"  {already} already on the new id")
    print(f"  {len(moves)} to move")
    print(f"  {unmovable} cannot be moved and were left alone")

    collisions = len(moves) - len({new for _old, new, _row in moves})
    if collisions:
        # Two rows landing on one id means the same sentence, page and lane
        # twice, which is one requirement that was stored twice. Merging them is
        # correct and worth saying out loud.
        print(f"  {collisions} of those land on an id another row also lands on, "
              f"which merges duplicates")

    if dry_run:
        print("\ndry run, nothing written")
        return 0

    written = deleted = 0
    batch = db.batch()
    for old_id, new_id, row in moves:
        batch.set(db.collection(REQUIREMENTS).document(new_id), row)
        written += 1
        if written % 200 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()

    batch = db.batch()
    for old_id, _new_id, _row in moves:
        batch.delete(db.collection(REQUIREMENTS).document(old_id))
        deleted += 1
        if deleted % 200 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()

    remaining = sum(1 for _ in db.collection(REQUIREMENTS).stream())
    live = sum(1 for d in db.collection(REQUIREMENTS).stream()
               if not d.to_dict().get("retired_at"))
    print(f"\nwrote {written}, deleted {deleted}")
    print(f"requirements now: {remaining} held, {live} live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
