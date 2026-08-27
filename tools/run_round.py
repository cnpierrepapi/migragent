"""Run one round from here, for when you need to watch it happen.

    python -m tools.run_round CA study --limit 5
    python -m tools.run_round ES work --mode extract
    python -m tools.run_round UK study --all
    python -m tools.run_round UK work --agent --limit 1

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
import os

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
from migragent.researcher import Researcher  # noqa: E402
from migragent.lanes import LaneCheck, enabled as lane_check_enabled  # noqa: E402
from migragent.agents.extractor import AgentExtractor, enabled as agent_extract_enabled  # noqa: E402
from migragent.meaning import Embedder  # noqa: E402
from migragent.verify import SecondReader, enabled as second_read_enabled  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402
from migragent.round import ChangeWriter, Round, RunLog  # noqa: E402
from migragent.snapshots import SnapshotStore  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")
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
    # The agent reads entry pages and chooses what to open from there. Off by
    # default so a round reads the way it has been reading unless somebody says
    # otherwise, and comparable against it when they do.
    with_agent = "--agent" in sys.argv
    # Either the flag on the command line or the environment switch, so a local
    # run can try it without exporting anything and the job needs no new flag.
    with_second = "--second-read" in sys.argv or second_read_enabled()
    # The Lane Classifier reads a discovered page and says which routes it is
    # about, so a work page linked from a study index does not get extracted
    # into the study guide. D29 and D32. Off unless asked for.
    with_lane_check = "--lane-check" in sys.argv or lane_check_enabled()
    # One model call per page that says which routes it serves, quote-checked in
    # code. Built as an agent first; a full session per page made a watch round
    # take hours, and classifying a page is one judgment, not multi-step work.
    # The Extractor as an agent reads one page and retries what the quote check
    # refuses, instead of dropping it in silence. Same page, same quote check.
    with_agent_extract = "--agent-extract" in sys.argv or agent_extract_enabled()
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
            extractor=(AgentExtractor(PROJECT, MODEL, MODEL_LOCATION, reader)
                       if with_agent_extract
                       else Extractor(PROJECT, MODEL, MODEL_LOCATION, reader)),
            explainer=Explainer(PROJECT, MODEL, MODEL_LOCATION, reader),
            changes_writer=ChangeWriter(writer_db),
            shortage_reader=ShortageReader(PROJECT, MODEL, MODEL_LOCATION, reader),
            shortages=Shortages(writer_db),
            researcher=Researcher(project=PROJECT, model=MODEL, location=MODEL_LOCATION,
                                  credentials=reader, fetcher=fetcher,
                                  on_event=lambda line: print(line, flush=True))
            if with_agent else None,
            second_reader=SecondReader(PROJECT, reader) if with_second else None,
            embedder=Embedder(PROJECT, reader),
            lane_classifier=LaneCheck(PROJECT, MODEL, MODEL_LOCATION, reader)
            if with_lane_check else None,
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
    if result.reworded:
        print(f"reworded: {result.reworded} page(s) moved their words and not their meaning")
    if with_lane_check:
        print(f"off-lane: {result.off_lane} page(s) were about another route and not "
              f"extracted into {lane}")
    if with_second and result.second_read.startswith("skipped"):
        print(f"second read: {result.second_read}")
    if with_second and result.second_read == "on":
        seen = result.agreed + result.disputed + result.unverified
        rate = (result.disputed / seen * 100) if seen else 0.0
        print(f"second read: agreed {result.agreed}, disputed {result.disputed}, "
              f"unverified {result.unverified}, disagreement {rate:.1f}%")

    # What the agent chose, and why it stopped. Without this a researched row
    # prints as one line with a count on it, and a session that fell over looks
    # exactly like a session that found nothing.
    for o in result.outcomes:
        if o.outcome == "researched":
            print(f"  chose from {o.url[-70:]}")
            print(f"      {o.detail}")
    if result.off_lane:
        print("\nread as another route, not extracted:")
        for o in result.outcomes:
            if o.outcome == "off-lane":
                print(f"  {o.url[-66:]}")
                print(f"      {(o.detail or '')[:110]}")
    if result.failed or result.unreadable:
        print("\nwhat did not read:")
        for o in result.outcomes:
            if o.outcome in ("failed", "unreadable"):
                print(f"  {o.outcome:<11} {o.url[-62:]}")
                print(f"      {(o.detail or '')[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
