"""Fetch candidate URLs through the product's fetcher (robots honoured) and report.

    python -m tools.verify_urls tools/living_curated.json

Input: {"CC": [["topic", "url", "title"], ...], ...}. Output: the same file with a
verdict on every row, so seeding only takes rows that answered 200 and allowed us.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from migragent.fetcher import Fetcher  # noqa: E402
from migragent.extract import page_text  # noqa: E402


def main() -> int:
    path = sys.argv[1]
    only = next((a.split("=", 1)[1].upper().split(",") for a in sys.argv if a.startswith("--only=")), None)
    data = json.load(open(path, encoding="utf-8"))
    f = Fetcher(delay_seconds=1.0)
    for code, rows in data.items():
        if only and code not in only:
            continue
        for row in rows:
            topic, url = row[0], row[1]
            ok, why = f.allowed(url)
            if not ok:
                row[3:] = ["robots", why[:80]]
            else:
                r = f.fetch(url)
                text = page_text(r) if r.outcome == "fetched" else ""
                row[3:] = ["ok" if r.outcome == "fetched" and len(text) > 400 else r.outcome,
                           f"{r.status} {len(text):,} chars"]
            print(f"{code} {topic:12} {row[3]:10} {row[4]:22} {url}", flush=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
