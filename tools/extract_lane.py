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
import os

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

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")
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

    # By default, read only the pages the guide is allowed to cite: the entry
    # page and what it links to directly. The walk reaches other visa types two
    # hops out, so reading everything spends model calls on pages about bringing
    # food into the country, which no study guide will ever quote. Those pages
    # stay in the registry and stay watched.
    #
    # --all reads them too, for when the corpus is the point rather than the
    # guide.
    if "--all" in sys.argv:
        sources = [s for s in registry.for_lane(jurisdiction, lane) if s.readable]
        scope = "readable sources, every depth"
    else:
        sources = [s for s in registry.near_lane(jurisdiction, lane) if s.readable]
        scope = "sources at depth 0 and 1, which is what the guide may cite"
    if limit:
        sources = sources[:limit]
    print(f"{len(sources)} {scope} for {jurisdiction} {lane}\n")

    fetcher = Fetcher(delay_seconds=0.5)
    kept = dropped = questions = errors = 0
    failed: list[tuple[str, str]] = []

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

            # One page's bad luck must not end the run. A UK extraction over 60
            # pages died two thirds through on a transient
            # "Network is unreachable" from Firestore, and took every page after
            # it with it. The same flakiness is already D8. A long run over
            # somebody else's network will meet it, so the loop survives it and
            # reports what it lost. See D18.
            try:
                snapshots.store(source.source_id, page)
                result = extractor.extract(
                    page, jurisdiction=jurisdiction, lane=lane,
                    language=source.language, provenance=source.provenance,
                )
                if result.model_error:
                    print(f"  {i:>3}/{len(sources)}  model error: {result.model_error[:60]}")
                    errors += 1
                    failed.append((source.url, result.model_error))
                    continue

                corpus.record(source.source_id, result, jurisdiction, lane)
            except Exception as exc:  # noqa: BLE001
                print(f"  {i:>3}/{len(sources)}  FAILED  {type(exc).__name__}  {source.url[-46:]}")
                errors += 1
                failed.append((source.url, f"{type(exc).__name__}: {exc}"))
                continue
            kept += result.kept
            dropped += len(result.dropped)
            questions += len(result.open_questions)
            flag = "  <- dropped" if result.dropped else ""
            print(f"  {i:>3}/{len(sources)}  kept {result.kept:>2}  dropped "
                  f"{len(result.dropped):>2}  {source.url[-58:]}{flag}")

    print(f"\n{kept} requirements kept, {dropped} dropped, {questions} open questions, "
          f"{errors} pages not read")
    if failed:
        print(f"\n{len(failed)} pages failed and were skipped rather than ending the run:")
        for url, why in failed[:15]:
            print(f"  {url[-64:]}")
            print(f"      {why[:110]}")
    if kept + dropped:
        print(f"drop rate {dropped / (kept + dropped) * 100:.1f}%")
    print(f"corpus now: {corpus.totals()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
