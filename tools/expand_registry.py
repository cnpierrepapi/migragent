"""Walk out from every readable entry page and register what is found.

Fourteen entry points was never a source registry. This is the step that turns
front doors into the pages the requirements actually live on.

Every discovered page is fetched, hashed and recorded with the page we found it
on. A page that turns out to contain no requirement still counts as a page we
read; it simply contributes no citations. The registry counts sources read, and
the guide cites only what actually yielded something, so a wide walk cannot
inflate the number of claims.

    python tools/expand_registry.py --dry-run
    python tools/expand_registry.py
"""
from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.expand import Expander  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.registry import Registry, Source  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
MAX_DEPTH = 2

# The first run used 45 and six of the eight lanes came back with exactly 44,
# which is the cap and not a result. A number that is really the ceiling is a
# number that says nothing, and reporting it as coverage would have been the
# same class of mistake as counting front doors. See D13.
MAX_PAGES = 150


def source_id(jurisdiction: str, lane: str, url: str) -> str:
    parts = url.split("//", 1)[-1].split("/")
    host = parts[0].replace(".", "-")
    tail = "-".join(p for p in parts[1:] if p)[-70:].replace(".", "-") or "root"
    return f"{jurisdiction.lower()}-{lane}-{host}-{tail}"[:180]


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    purge = "--purge" in sys.argv

    writer_db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WRITER, PROJECT),
    )
    if purge:
        # Rows written by an earlier walk are re-derivable, and leaving results
        # from code that has since been fixed would mean the count describes two
        # different methods at once.
        stale = [s for s in Registry(writer_db).all()
                 if s.discovered_via.startswith("walked from")]
        batch = writer_db.batch()
        for i, s in enumerate(stale, 1):
            batch.delete(writer_db.collection("sources").document(s.source_id))
            if i % 400 == 0:
                batch.commit()
                batch = writer_db.batch()
        batch.commit()
        print(f"purged {len(stale)} rows from earlier walks\n")

    reader = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.RESEARCHER, PROJECT),
    )
    registry = Registry(reader)
    entries = [s for s in registry.all() if s.kind == "government" and s.readable]
    print(f"{len(entries)} readable entry points\n")

    fetcher = Fetcher(delay_seconds=0.6)
    expander = Expander(fetcher, max_depth=MAX_DEPTH, max_pages=MAX_PAGES)

    # Navigation has to be learned per host before anything can be told apart,
    # and it needs two pages of a host to learn from. Hosts with only one entry
    # get nothing walked, and the run says so rather than quietly returning
    # everything or nothing.
    learned = expander.learn_chrome([s.url for s in entries])
    print("navigation links learned per host:")
    for host, n in sorted(learned.items()):
        note = "" if n else "   ONLY ONE PAGE ON THIS HOST, nothing can be told apart"
        print(f"  {n:>4}  {host}{note}")
    print()

    discovered: list[Source] = []
    per_lane: dict[tuple[str, str], int] = defaultdict(int)
    skipped_hosts = set()

    for entry in entries:
        host = entry.url.split("//", 1)[-1].split("/", 1)[0]
        if not learned.get(host):
            skipped_hosts.add(host)
            print(f"  skipped  {entry.jurisdiction} {entry.lane}  ({host}, no navigation learned)")
            continue

        found, pages = expander.walk(entry.url, jurisdiction=entry.jurisdiction)
        kept = 0
        for d in found:
            page = pages.get(d.url)
            if page is None or not page.ok:
                continue
            discovered.append(Source(
                source_id=source_id(entry.jurisdiction, entry.lane, d.url),
                jurisdiction=entry.jurisdiction,
                lane=entry.lane,
                kind="government",
                url=d.url,
                title=d.url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace(".html", ""),
                language=entry.language,
                provenance="official",
                discovered_via=f"walked from {entry.source_id}",
                lead_url=d.lead_url,
                robots_allowed=True,
                robots_checked_at=page.read_at,
                last_read_at=page.read_at,
                last_status=page.status,
                stable_sha256=page.sha256,
                raw_sha256=page.raw_sha256,
            ))
            kept += 1
            per_lane[(entry.jurisdiction, entry.lane)] += 1
        print(f"  {kept:>3} new  {entry.jurisdiction} {entry.lane}  from {entry.url[:70]}")

    print(f"\n{len(discovered)} pages discovered and read")
    print("\nper lane:")
    for (j, lane), n in sorted(per_lane.items()):
        print(f"  {j} {lane:<5} {n:>4}")

    if skipped_hosts:
        print("\nHosts with a single entry page, so nothing could be walked:")
        for h in sorted(skipped_hosts):
            print(f"  {h}")

    if dry_run:
        print("\ndry run, nothing written")
        return 0

    written = Registry(writer_db).bulk_put(discovered)
    print(f"\nwrote {written} rows")
    print(f"registry now: {Registry(writer_db).counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
