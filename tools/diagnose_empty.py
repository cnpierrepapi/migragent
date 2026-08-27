"""Why did a school produce no courses? Categorise before guessing.

    python -m tools.diagnose_empty --limit 40

No model calls. It fetches each candidate index and records what happened, so a
fix is aimed at the actual failure rather than at the first one somebody thought
of. 135 schools produced nothing and they did not all fail the same way.
"""
from __future__ import annotations
import os

import collections
import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.extract import page_text  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402
from migragent.schools import course_links  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")


def main() -> int:
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 40
    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(Institutions.COLLECTION).stream()
            if d.to_dict().get("site_state") == "reachable"
            and not d.to_dict().get("courses_found")]
    print(f"{len(rows)} schools reachable but empty; checking {min(limit, len(rows))}\n")

    fetcher = Fetcher(delay_seconds=1.0)
    verdicts = collections.Counter()

    with BrowserFetcher(fetcher=fetcher) as browser:
        for row in rows[:limit]:
            name = (row.get("name") or "").encode("ascii", "replace").decode()
            urls = [u for u in (row.get("courses_url_options") or []) if u] or \
                   [u for u in (row.get("courses_url"), row.get("website")) if u]

            verdict, detail = "no candidate url", ""
            for url in urls[:4]:
                page = fetcher.fetch(url)
                if not page.ok:
                    verdict, detail = f"static {page.outcome}", url
                    rendered = browser.fetch(url)
                    if not rendered.ok:
                        verdict = f"refused both ({rendered.outcome})"
                        continue
                    page = rendered

                text = page_text(page)
                links = course_links(page.body.decode("utf-8", "replace"), url)
                if len(text) < 400:
                    verdict, detail = "page nearly empty", url
                    continue
                # It fetched and has text. So the reader saw it and found no
                # courses, which means the page is a prospectus landing page or
                # a search box rather than a list.
                verdict = f"readable, {len(links)} onward links"
                detail = url
                break

            verdicts[verdict.split(" (")[0]] += 1
            print(f"  {name[:38]:40} {verdict[:34]:36} {detail[:44]}", flush=True)

    print("\n--- verdicts ---")
    for v, n in verdicts.most_common():
        print(f"  {n:>4}  {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
