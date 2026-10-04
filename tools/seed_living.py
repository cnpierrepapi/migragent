"""Seed the living lane from tools/living_curated.json.

Only rows that tools/verify_urls.py marked "ok" are considered, and each one is
fetched again here before it is written, the same way tools/seed_registry.py
does it, so a page that died since the check is recorded as what it is now.

The curated file holds no language, so it is read off the page's own
<html lang>, falling back to the country's first language.

    python -m tools.seed_living             write to Firestore
    python -m tools.seed_living --dry-run   fetch and report, write nothing
    python -m tools.seed_living --only=ES,SA
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.registry import JURISDICTIONS, Registry, Source, source_id  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")
CURATED = "tools/living_curated.json"


def _language(body: bytes, code: str) -> str:
    m = re.search(rb'<html[^>]*\blang="([a-zA-Z]{2})', body or b"", re.I)
    return m.group(1).decode().lower() if m else JURISDICTIONS[code]["languages"][0]


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    only = next((a.split("=", 1)[1].upper().split(",") for a in sys.argv if a.startswith("--only=")), None)
    data = json.load(open(CURATED, encoding="utf-8"))
    fetcher = Fetcher(delay_seconds=1.0)
    built: list[Source] = []

    for code, rows in data.items():
        if only and code not in only:
            continue
        for row in rows:
            if len(row) < 4 or row[3] != "ok":
                continue
            topic, url, title = row[0], row[1], row[2]
            allowed, why = fetcher.allowed(url)
            result = fetcher.fetch(url) if allowed else None
            if result is None or result.outcome != "fetched":
                print(f"  SKIP  {code} {topic:12} {why if result is None else result.outcome}  {url}")
                continue
            source = Source(
                source_id=source_id(code, "living", url), jurisdiction=code, lane="living",
                kind="government", url=url, title=title,
                language=_language(result.body, code), provenance="official",
                discovered_via="seed", robots_allowed=True, robots_checked_at=result.read_at,
                last_read_at=result.read_at, last_status=result.status,
                stable_sha256=result.sha256, raw_sha256=result.raw_sha256,
            )
            print(f"  ok    {code} {topic:12} {source.language}  {url}")
            built.append(source)

    by_country: dict[str, int] = {}
    for s in built:
        by_country[s.jurisdiction] = by_country.get(s.jurisdiction, 0) + 1
    print(f"\n{len(built)} living pages ready: {by_country}")

    if dry_run:
        print("dry run, nothing written")
        return 0

    db = firestore.Client(project=PROJECT, credentials=identity.credentials_for(identity.WRITER, PROJECT))
    registry = Registry(db)
    fresh = [s for s in built if registry.by_url(s.jurisdiction, "living", s.url) is None]
    written = registry.bulk_put(fresh)
    print(f"wrote {written} new rows ({len(built) - len(fresh)} already there)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
