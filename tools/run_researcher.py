"""Run the agent on one real entry page, and see what it decided.

    python -m tools.run_researcher UK work
    python -m tools.run_researcher CA study --url https://...
    python -m tools.run_researcher UK work --compare

Nothing is written to the corpus. This prints what the agent read, what it
recorded, what it was refused and why it stopped, because the question Build 4
has to answer is whether handing the choice of pages to an agent produces better
reading than following every link, and that is answered by looking at the pages
it chose rather than by the count of requirements.

`--compare` also runs the existing one shot extractor over the entry page alone,
which is what the walker would have done, so the two can be read side by side.
"""
from __future__ import annotations
import os

import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.extract import Extractor  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.registry import JURISDICTIONS, Registry  # noqa: E402
from migragent.researcher import Researcher  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")
MODEL = "gemini-3.5-flash"
MODEL_LOCATION = "global"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 64

    jurisdiction, lane = sys.argv[1].upper(), sys.argv[2].lower()
    compare = "--compare" in sys.argv
    url = None
    if "--url" in sys.argv:
        url = sys.argv[sys.argv.index("--url") + 1]

    reader = identity.credentials_for(identity.RESEARCHER, PROJECT)
    place = JURISDICTIONS.get(jurisdiction, {}).get("name", jurisdiction)

    language, provenance = "en", "official"
    if url is None:
        db = firestore.Client(project=PROJECT, credentials=reader)
        sources = [s for s in Registry(db).for_lane(jurisdiction, lane)
                   if s.blocked is None and (s.depth or 0) == 0]
        if not sources:
            print(f"no entry page in the registry for {jurisdiction} {lane}")
            return 1
        entry = sources[0]
        url, language, provenance = entry.url, entry.language, entry.provenance

    print(f"{jurisdiction} {lane}: starting at {url}\n")

    fetcher = Fetcher(delay_seconds=0.5)
    researcher = Researcher(project=PROJECT, model=MODEL, location=MODEL_LOCATION,
                            credentials=reader, fetcher=fetcher,
                            on_event=lambda line: print(line, flush=True))
    session = researcher.research(url, jurisdiction=jurisdiction, lane=lane, place=place,
                                  language=language, provenance=provenance)

    print(f"\nturns {session.turns}, pages read {len(session.pages_read)}, "
          f"kept {session.kept}, refused {len(session.refused)}")
    print(f"stopped because: {session.stopped_because}")
    if session.error:
        print(f"error: {session.error}")

    print("\npages it chose:")
    for page in session.pages_read:
        print(f"  {page}")
    for refused in session.pages_refused:
        print(f"  NOT READ  {refused['url']}  {refused['why'][:60]}")

    print(f"\nwhat it recorded ({session.kept}):")
    for req in session.requirements:
        print(f"  [{req.category}] {req.text}")
        print(f"        quote: {req.quote[:100]}")
        print(f"        from:  {req.source_url[-70:]}")

    if session.refused:
        print(f"\nwhat it was refused ({len(session.refused)}):")
        for bad in session.refused:
            print(f"  {bad['why']}: {bad.get('text', '')[:70]}")
            if bad.get("quote"):
                print(f"        it offered: {bad['quote'][:90]}")

    if session.open_questions:
        print("\nopen questions:")
        for q in session.open_questions:
            print(f"  {q}")

    if compare:
        print("\n--- the one shot extractor, on the entry page alone ---")
        page = fetcher.fetch(url)
        extraction = Extractor(PROJECT, MODEL, MODEL_LOCATION, reader).extract(
            page, jurisdiction=jurisdiction, lane=lane, language=language,
            provenance=provenance)
        print(f"kept {extraction.kept}, dropped {len(extraction.dropped)}"
              f"{', error: ' + extraction.model_error if extraction.model_error else ''}")
        for req in extraction.requirements:
            print(f"  [{req.category}] {req.text}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
