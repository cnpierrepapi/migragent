"""Run one round from here, for when you need to watch it happen.

    python -m tools.run_round CA study --limit 5
    python -m tools.run_round ES work --mode extract
    python -m tools.run_round UK study --all

The job in Cloud Run is the real thing. This exists so a round can be watched
line by line while it is being changed, and so a lane can be pushed along by
hand without touching the schedule.

TWO DIFFERENCES FROM THE JOB, BOTH DELIBERATE
---------------------------------------------
The job runs as the **watcher**, which is the only identity allowed to read the
snapshot archive back. Nothing can become the watcher, on purpose, and that
includes a person at a terminal. So this runs the way the older tools did, as
the researcher for reading and the writer for recording.

Which means **watch mode cannot diff from here**: the researcher can add to the
snapshot archive and cannot read it, so there is no yesterday to compare with.
Watch mode belongs to the job. This one extracts.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from google.cloud import firestore, storage  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.changes import Explainer  # noqa: E402
from migragent.corpus import Corpus  # noqa: E402
from migragent.extract import Extractor  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.occupations import ShortageReader, Shortages  # noqa: E402
from migragent.registry import Registry  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402
from migragent.round import ChangeWriter, Round, RunLog  # noqa: E402
from migragent.snapshots import SnapshotStore  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
MODEL = "gemini-3.5-flash"
MODEL_LOCATION = "global"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 64

    jurisdiction, lane = sys.argv[1].upper(), sys.argv[2].lower()
    mode = "extract"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    max_depth = None if "--all" in sys.argv else 1
    if "--depth" in sys.argv:
        # `--depth 0` reads only the pages we deliberately seeded.
        #
        # Needed where a site's sections are not lane shaped. The walk gives a
        # discovered page the lane of the entry that found it, which is right
        # when a government puts student pages under a student section, and
        # wrong when one catalogue serves every route: Italy's visa portal
        # handed its study entry the tourism, business and salaried employment
        # pages, all tagged study. See D29.
        max_depth = int(sys.argv[sys.argv.index("--depth") + 1])
    force = "--force" in sys.argv

    if mode == "watch":
        print("watch mode needs the snapshot archive read back, which only the")
        print("watcher may do. Run the job for that. See the module docstring.")
        return 64

    reader = identity.credentials_for(identity.RESEARCHER, PROJECT)
    writer = identity.credentials_for(identity.WRITER, PROJECT)

    writer_db = firestore.Client(project=PROJECT, credentials=writer)

    fetcher = Fetcher(delay_seconds=0.5)
    with BrowserFetcher(fetcher) as browser:
        round_ = Round(
            registry=Registry(writer_db),
            corpus=Corpus(writer_db),
            snapshots=SnapshotStore(storage.Client(project=PROJECT, credentials=reader)),
            fetcher=fetcher,
            extractor=Extractor(PROJECT, MODEL, MODEL_LOCATION, reader),
            explainer=Explainer(PROJECT, MODEL, MODEL_LOCATION, reader),
            changes_writer=ChangeWriter(writer_db),
            shortage_reader=ShortageReader(PROJECT, MODEL, MODEL_LOCATION, reader),
            shortages=Shortages(writer_db),
            browser=browser,
            on_event=lambda line: print(line, flush=True),
        )
        result = round_.run(jurisdiction, lane, mode=mode, max_depth=max_depth,
                            limit=limit, force=force)

    RunLog(writer_db).record(result)

    print(f"\nconsidered {result.considered}, fetched {result.fetched}, "
          f"extracted {result.extracted}, already read {result.skipped_already_read}, "
          f"unreadable {result.unreadable}, failed {result.failed}")
    print(f"kept {result.kept}, dropped {result.dropped}, retired {result.retired}, "
          f"{result.seconds}s")
    if result.failed or result.unreadable:
        print("\nwhat did not read:")
        for o in result.outcomes:
            if o.outcome in ("failed", "unreadable"):
                print(f"  {o.outcome:<11} {o.url[-62:]}")
                print(f"      {(o.detail or '')[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
