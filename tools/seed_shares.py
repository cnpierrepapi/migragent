"""Read the international student percentage for institutions we already hold.

    python -m tools.seed_shares UK --limit 25 --dry-run
    python -m tools.seed_shares UK

Only institutions already in the register are looked up, so this can never
introduce a school that no government lists. It adds one fact to a row that
already exists.

Every figure lands with its publisher, its edition and the span it was read from,
and the provenance is `portal` rather than `official`, because Times Higher
Education is a publisher and not a government. See migragent/shares.py for why
this is not a government source and what was tried first.

A page is skipped rather than guessed at whenever it does not prove it is about
the institution we asked for, and the run prints every skip with its reason.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.institutions import Institutions, institution_id  # noqa: E402
from migragent.shares import BASE, read_share, slug_for  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 64

    jurisdiction = sys.argv[1].upper()
    dry_run = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WRITER, PROJECT))
    store = Institutions(db)

    rows = [d.to_dict() for d in db.collection(Institutions.COLLECTION)
            .where(field_path="jurisdiction", op_string="==", value=jurisdiction).stream()]
    rows.sort(key=lambda r: r.get("name", ""))
    if limit:
        rows = rows[:limit]

    print(f"{len(rows)} institutions in {jurisdiction}\n")

    fetcher = Fetcher(delay_seconds=1.2)
    read = 0
    reasons: dict[str, int] = {}

    for row in rows:
        name = row.get("name", "")
        url = BASE + slug_for(name)
        page = fetcher.fetch(url)
        share, why = read_share(page, name, jurisdiction)

        if share is None:
            key = why.split(":")[0][:52]
            reasons[key] = reasons.get(key, 0) + 1
            print(f"  skip  {name[:44]:<44} {why[:58]}")
            continue

        read += 1
        print(f"  ok    {name[:44]:<44} {share.international_share:>5.0f}%  "
              f"{share.edition or 'edition unstated'}")

        if not dry_run:
            db.collection(Institutions.COLLECTION).document(
                institution_id(jurisdiction, name)).set({
                    "international_share": share.international_share,
                    "share_publisher": share.publisher,
                    "share_edition": share.edition,
                    "share_quote": share.quote,
                    "share_source_url": share.source_url,
                    "share_read_at": share.read_at,
                    "share_provenance": share.provenance,
                }, merge=True)

    print(f"\n{read} of {len(rows)} institutions have a published share")
    if reasons:
        print("\nwhy the rest do not:")
        for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>4}  {why}")
    if dry_run:
        print("\ndry run, nothing written")
    else:
        print(f"\ninstitutions now: {store.counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
