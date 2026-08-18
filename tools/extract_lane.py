"""Read the pages of one lane and record what they say.

    python tools/extract_lane.py CA study --limit 25
    python tools/extract_lane.py UK study

The researcher extracts. The writer records. Those are two identities on purpose
and the second cannot be reached from a web request.

Pages are fetched fresh here rather than read from the snapshot, so the citation
date on every requirement is the moment this run actually read the page. A date
copied from an earlier fetch would be a small lie of exactly the kind this
product exists to avoid.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402
from google.cloud import storage  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.corpus import Corpus  # noqa: E402
from migragent.extract import Extractor  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.registry import Registry  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402
from migragent.snapshots import SnapshotStore  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
MODEL = "gemini-3.5-flash"
MODEL_LOCATION = "global"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 64
    jurisdiction, lane = sys.argv[1].upper(), sys.argv[2].lower()
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    reader_creds = identity.credentials_for(identity.RESEARCHER, PROJECT)
    writer_creds = identity.credentials_for(identity.WRITER, PROJECT)

    registry = Registry(firestore.Client(project=PROJECT, credentials=reader_creds))
    corpus = Corpus(firestore.Client(project=PROJECT, credentials=writer_creds))
    snapshots = SnapshotStore(storage.Client(project=PROJECT, credentials=reader_creds))
    extractor = Extractor(PROJECT, MODEL, MODEL_LOCATION, reader_creds)

    sources = [s for s in registry.for_lane(jurisdiction, lane) if s.readable]
    if limit:
        sources = sources[:limit]
    print(f"{len(sources)} readable sources for {jurisdiction} {lane}\n")

    fetcher = Fetcher(delay_seconds=0.5)
    kept = dropped = questions = errors = 0

    with BrowserFetcher(fetcher) as browser:
        for i, source in enumerate(sources, 1):
            page = fetcher.fetch(source.url)
            # Some hosts hand a plain client almost nothing. If the text is thin,
            # try the browser before concluding the page says nothing.
            if page.ok and len(page.body or b"") < 4000:
                rendered = browser.fetch(source.url)
                if rendered.ok and len(rendered.body or b"") > len(page.body or b""):
                    page = rendered

            if not page.ok:
                print(f"  {i:>3}/{len(sources)}  unreadable  {page.outcome}  {source.url[:64]}")
                errors += 1
                continue

            snapshots.store(source.source_id, page)
            result = extractor.extract(
                page, jurisdiction=jurisdiction, lane=lane,
                language=source.language, provenance=source.provenance,
            )
            if result.model_error:
                print(f"  {i:>3}/{len(sources)}  model error: {result.model_error[:60]}")
                errors += 1
                continue

            corpus.record(source.source_id, result, jurisdiction, lane)
            kept += result.kept
            dropped += len(result.dropped)
            questions += len(result.open_questions)
            flag = "  <- dropped" if result.dropped else ""
            print(f"  {i:>3}/{len(sources)}  kept {result.kept:>2}  dropped "
                  f"{len(result.dropped):>2}  {source.url[-58:]}{flag}")

    print(f"\n{kept} requirements kept, {dropped} dropped, {questions} open questions, "
          f"{errors} pages unreadable")
    if kept + dropped:
        print(f"drop rate {dropped / (kept + dropped) * 100:.1f}%")
    print(f"corpus now: {corpus.totals()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
