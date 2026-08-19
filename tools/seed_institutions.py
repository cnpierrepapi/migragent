"""Read the official registers of institutions that may take foreign students.

    python -m tools.seed_institutions --dry-run
    python -m tools.seed_institutions

WHAT THIS IS FOR. For a study case the question is not which school is best, it
is whether the school is on the list. An offer from an institution that is not
licensed to sponsor is not a route, however good the institution.

WHAT IT IS NOT. It is not a ranking by international share. No government here
publishes that per institution, so the fields for it exist, stay empty, and the
product says the share is unknown rather than ranking on a number bought from
somebody else and shown next to a government link. See migragent/institutions.py.

THE UK REGISTER MOVES. Its CSV lives at a dated asset URL that changes with every
revision, so the URL is discovered from the publication page each run rather than
written down here. A register whose address is copied into code is a register
that silently goes stale.
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")

from google.cloud import firestore, storage  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.institutions import Institutions, from_csv, from_html_table  # noqa: E402
from migragent.snapshots import SnapshotStore  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"

UK_PUBLICATION = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-students"
CA_REGISTER = ("https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/"
               "study-permit/prepare/designated-learning-institutions-list.html")

_UK_ASSET = re.compile(r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]+\.csv)"')


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    fetcher = Fetcher(delay_seconds=1.5)
    reader_creds = identity.credentials_for(identity.RESEARCHER, PROJECT)
    writer_creds = identity.credentials_for(identity.WRITER, PROJECT)
    store = Institutions(firestore.Client(project=PROJECT, credentials=writer_creds))
    snapshots = SnapshotStore(storage.Client(project=PROJECT, credentials=reader_creds))

    parsed = []

    # ---- United Kingdom, a CSV linked from a publication page ----------------
    page = fetcher.fetch(UK_PUBLICATION)
    if not page.ok:
        print(f"UK  publication page unreadable: {page.outcome} {page.status}")
    else:
        assets = sorted(set(_UK_ASSET.findall(page.body.decode("utf-8", "ignore"))))
        if not assets:
            print("UK  no CSV linked from the publication page, register not read")
        else:
            csv_url = assets[0]
            data = fetcher.fetch(csv_url, expect="data")
            print(f"UK  {csv_url.rsplit('/', 1)[-1]}")
            if not data.ok:
                print(f"UK  register unreadable: {data.outcome} {data.status}")
            else:
                items = from_csv(data.body, "UK", name_column="Sponsor Name",
                                 status_column="Status", location_column="Town/City",
                                 route_column="Route")
                for item in items:
                    item.source_url = csv_url
                    item.read_at = data.read_at
                    item.register_name = "Register of licensed sponsors: students"
                print(f"UK  {len(items)} institutions parsed")
                if not dry_run:
                    snapshots.store("uk-register-student-sponsors", data)
                parsed.extend(items)

    # ---- Canada, an HTML table -----------------------------------------------
    ca = fetcher.fetch(CA_REGISTER)
    if not ca.ok:
        print(f"CA  register unreadable: {ca.outcome} {ca.status}")
    else:
        items = from_html_table(ca.body, "CA", name_index=1, location_index=0, min_cells=3)
        for item in items:
            item.source_url = ca.final_url or CA_REGISTER
            item.read_at = ca.read_at
            item.register_name = "Designated learning institutions list"
        print(f"CA  {len(items)} institutions parsed")
        if not dry_run:
            snapshots.store("ca-register-designated-learning-institutions", ca)
        parsed.extend(items)

    if not parsed:
        print("\nnothing parsed, nothing written")
        return 1

    print(f"\nsample of what was parsed:")
    for item in parsed[:3] + parsed[-3:]:
        print(f"  {item.jurisdiction}  {item.name[:52]:<52} {(item.location or '')[:22]}")

    if dry_run:
        print("\ndry run, nothing written")
        return 0

    written = store.record(parsed)
    print(f"\nwrote {written} institutions")
    print(f"institutions now: {store.counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
