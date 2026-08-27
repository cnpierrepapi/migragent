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
import os

import sys
from collections import defaultdict

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.expand import Expander  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402
from migragent.registry import JURISDICTIONS, Registry, Source, source_id  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")
MAX_DEPTH = 2

# The first run used 45 and six of the eight lanes came back with exactly 44,
# which is the cap and not a result. A number that is really the ceiling is a
# number that says nothing, and reporting it as coverage would have been the
# same class of mistake as counting front doors. See D13.
MAX_PAGES = 600


def id_for(existing: dict[tuple[str, str, str], str],
           jurisdiction: str, lane: str, url: str) -> str:
    """The id this page already has, or a new one in the canonical scheme.

    This file used to mint its own ids with its own rule, which did not match
    the one the seeder used, so a page seeded by hand and then reached by the
    walk was filed twice under two names and read twice every round. That is
    D31. The rule now lives in migragent/registry.py and there is one of it.

    Looking the URL up first matters as much as sharing the rule: rows written
    under the old scheme keep the name they already have, so fixing the rule
    does not create a second copy of every page in the registry.
    """
    return existing.get((jurisdiction, lane, url)) or source_id(jurisdiction, lane, url)


def _only() -> set[str]:
    """Jurisdictions this run is limited to, empty meaning all of them.

    An unknown flag used to be ignored in silence, which is how `--only ES`
    became a full purge of every jurisdiction. Anything that looks like a
    jurisdiction code and is not one now stops the run.
    """
    if "--only" not in sys.argv:
        return set()
    raw = sys.argv[sys.argv.index("--only") + 1]
    codes = {c.strip().upper() for c in raw.split(",") if c.strip()}
    unknown = codes - set(JURISDICTIONS)
    if unknown:
        raise SystemExit(f"--only got {', '.join(sorted(unknown))}, which is not "
                         f"a jurisdiction. Known: {', '.join(sorted(JURISDICTIONS))}")
    return codes


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
        # Rows from an earlier walk, plus seed rows whose URL is no longer in
        # the seed list. Spain left an orphan behind when its work entry moved
        # to a different page, and that orphan walked as an eleventh entry point
        # and reported its own zero.
        current_seed_ids = set()
        try:
            from tools.seed_registry import CANDIDATES, source_id as seed_id
            current_seed_ids = {seed_id(j, lane, url) for j, lane, url, _t, _l in CANDIDATES}
        except Exception:  # noqa: BLE001
            pass
        # The purge respects --only as well. It did not once, and a run meant to
        # rebuild one country deleted every walked row in the registry, 1,048
        # down to 14 seeds. It rebuilt, because walked rows are derived and
        # source ids come from URLs, but it cost a full re-walk and every row
        # lost its snapshot path. See D25.
        only = _only()
        stale = [
            s for s in Registry(writer_db).all()
            if (not only or s.jurisdiction in only)
            and (s.discovered_via.startswith("walked from")
                 or (s.discovered_via == "seed" and current_seed_ids
                     and s.source_id not in current_seed_ids))
        ]
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

    # Walking every entry point re-reads a thousand pages to add one country.
    # `--only IT,DE` walks just those, which is what adding a jurisdiction or
    # fixing a seed actually needs.
    only = _only()
    if only:
        entries = [s for s in entries if s.jurisdiction in only]

    print(f"{len(entries)} readable entry points"
          + (f", limited to {', '.join(sorted(only))}" if only else "") + "\n")

    fetcher = Fetcher(delay_seconds=0.6)

    # Navigation has to be learned per host before anything can be told apart,
    # and it needs two pages of a host to learn from. Hosts with only one entry
    # get nothing walked, and the run says so rather than quietly returning
    # everything or nothing.
    with BrowserFetcher(fetcher) as browser:
        expander = Expander(fetcher, max_depth=MAX_DEPTH, max_pages=MAX_PAGES,
                            browser=browser)
        learned = expander.learn_chrome([s.url for s in entries])
        print("navigation links learned per host:")
        for host, n in sorted(learned.items()):
            note = "" if n else "   ONLY ONE PAGE ON THIS HOST, nothing can be told apart"
            print(f"  {n:>4}  {host}{note}")
        print()

        # Every row already in the registry, by what it is a page of, so a
        # page that already has a name keeps it. See id_for.
        existing_ids = {(s.jurisdiction, s.lane, s.url): s.source_id
                        for s in registry.all()}

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
                    source_id=id_for(existing_ids, entry.jurisdiction,
                                     entry.lane, d.url),
                    jurisdiction=entry.jurisdiction,
                    lane=entry.lane,
                    kind="government",
                    url=d.url,
                    title=d.url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace(".html", ""),
                    language=entry.language,
                    provenance="official",
                    discovered_via=f"walked from {entry.source_id}",
                    lead_url=d.lead_url,
                depth=d.depth,
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
