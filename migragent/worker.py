"""The ingestion job. One task per lane, run by Cloud Run.

    MIGRAGENT_MODE=extract  python -m migragent.worker
    MIGRAGENT_MODE=watch    python -m migragent.worker
    MIGRAGENT_MODE=digest   python -m migragent.worker
    MIGRAGENT_LANE="CA study" python -m migragent.worker     # one lane, locally

HOW THE WORK IS SPLIT
---------------------
Cloud Run runs this job as several tasks at once and hands each one
`CLOUD_RUN_TASK_INDEX`. The index picks a lane out of a fixed list, so ten lanes
means ten tasks and each task reads one country and one lane. Lanes are
different websites, so running them together is parallel across hosts rather
than pressure on any one host. Inside a lane the fetcher still takes one host at
a time and waits its turn.

WHY NOT PUB/SUB
---------------
The plan said Cloud Scheduler to Pub/Sub to a job, and the topic turned out to
be a delivery mechanism with nothing to deliver. Cloud Run already numbers its
own tasks, retries the ones that fail, and reports which of them died. Adding a
topic would have meant a second thing to configure, a second thing to grant, and
a second place for a message to go missing, all to carry an integer that the
runtime already provides.

So Pub/Sub is not used, and the reason is written in docs/DECISIONS.md rather
than left as an absence somebody has to guess at. Rule: every service earns its
place or stays out.

WHO THIS RUNS AS
----------------
The watcher. It is the only identity that can read the snapshot archive back,
because comparing today with yesterday is the one job that genuinely needs
yesterday. Nothing anywhere can become the watcher: it holds no token creator
binding from any other principal, so a web request cannot start a round no
matter what it does.
"""
from __future__ import annotations

import os
import sys

from google.cloud import firestore, storage

from . import identity
from .changes import Explainer
from .occupations import ShortageReader, Shortages
from .corpus import Corpus
from .extract import Extractor
from .fetcher import Fetcher
from .registry import Registry
from .researcher import Researcher
from .round import ChangeWriter, Round, RunLog, lanes
from .snapshots import SnapshotStore

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
MODEL = os.environ.get("MIGRAGENT_MODEL", "gemini-3.5-flash")
MODEL_LOCATION = os.environ.get("MIGRAGENT_MODEL_LOCATION", "global")
MODE = os.environ.get("MIGRAGENT_MODE", "extract")

# Who reads an entry page: the agent that chooses what to open next, or the flat
# extractor that reads whatever the walk queued. Off unless asked for, so the
# daily round does not change what it does because a dependency was installed.
USE_AGENT = os.environ.get("MIGRAGENT_RESEARCHER", "") == "agent"

# Depth 0 and 1 is the entry page and what the government links directly, which
# is all the guide may cite. Depth 2 stays in the registry and stays watched.
MAX_DEPTH = os.environ.get("MIGRAGENT_MAX_DEPTH", "1")


def _lane_for_task() -> tuple[str, str] | None:
    """Which lane this task reads.

    `MIGRAGENT_LANE` wins, so one lane can be run by hand without touching the
    job. Otherwise the Cloud Run task index picks one out of the fixed list, and
    an index past the end of the list is not an error: a job asked for more
    tasks than there are lanes, and the extra tasks have nothing to do and
    should exit cleanly rather than fail the run.
    """
    explicit = os.environ.get("MIGRAGENT_LANE")
    if explicit:
        parts = explicit.split()
        if len(parts) != 2:
            raise SystemExit(f"MIGRAGENT_LANE should be like 'CA study', got {explicit!r}")
        return parts[0].upper(), parts[1].lower()

    index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    all_lanes = lanes()
    if index >= len(all_lanes):
        return None
    return all_lanes[index]


def selftest() -> int:
    """Prove the watcher's boundary from inside the watcher.

    Decision 5 claims the watcher can read the snapshot archive and cannot
    overwrite or delete anything in it. Rule 3 says a claim gets a test before it
    gets a sentence, and this claim has an awkward property: nothing can become
    the watcher, deliberately, so no test on anybody's laptop can ever run as it.

    So the test runs where the watcher actually lives. `MIGRAGENT_MODE=selftest`
    on the job, and the evidence is in the job's own logs.
    """
    from google.api_core import exceptions as gexc

    credentials = identity.credentials_for(identity.WATCHER, PROJECT)
    gcs = storage.Client(project=PROJECT, credentials=credentials)
    bucket = gcs.bucket("migragent-snapshots")

    results: list[tuple[bool, str, str]] = []

    def check(name: str, probe, expect_forbidden: bool) -> None:
        try:
            probe()
            results.append((not expect_forbidden, name, "it succeeded"))
        except gexc.Forbidden as exc:
            results.append((expect_forbidden, name, f"Forbidden 403: {str(exc)[:60]}"))
        except gexc.NotFound:
            # A principal allowed to read a missing object gets 404. For a read
            # probe that is the answer we want; for a write probe it would mean
            # the write was permitted and simply had nowhere to go.
            results.append((not expect_forbidden, name, "NotFound, so access was permitted"))
        except Exception as exc:  # noqa: BLE001
            results.append((False, name, f"{type(exc).__name__}: {exc}"))

    existing = next(iter(gcs.list_blobs("migragent-snapshots", max_results=1)), None)

    check("watcher CAN list the archive",
          lambda: list(gcs.list_blobs("migragent-snapshots", max_results=1)), False)
    check("watcher CAN read a snapshot back",
          lambda: bucket.blob(existing.name if existing else "_none").download_as_bytes(),
          False)
    check("watcher CAN add a snapshot",
          lambda: bucket.blob("_selftest/probe.html").upload_from_string(b"probe"), False)
    if existing is not None:
        check("watcher CANNOT overwrite an existing snapshot",
              lambda: bucket.blob(existing.name).upload_from_string(b"tampered"), True)
        check("watcher CANNOT delete a snapshot",
              lambda: bucket.blob(existing.name).delete(), True)

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed", flush=True)
    return 1 if failed else 0


def robots_probe() -> int:
    """Print robots.txt exactly as this job sees it.

    On 20 August the daily round marked every Spanish source `robots_disallowed`
    and fetched nothing, and a minute later the same check from a laptop said
    Spain allows us: its robots.txt disallows `/buscar` and nothing else.

    Both readings cannot be wrong, and neither can be argued with from the other
    end. A host can serve different rules to different clients, and a government
    site behind a bot filter can serve a challenge to an unfamiliar address while
    serving the real file to a home connection. So this asks from here, prints
    what came back, and leaves no room for either of us to guess.

    `MIGRAGENT_MODE=robots`, optionally `MIGRAGENT_HOSTS` as a comma separated
    list. The evidence lands in the job's own logs.
    """
    import urllib.error
    import urllib.request

    from .fetcher import TLS, Fetcher

    hosts = [h.strip() for h in os.environ.get(
        "MIGRAGENT_HOSTS",
        "https://www.inclusion.gob.es,https://sede.inclusion.gob.es,"
        "https://www.gov.uk,https://www.canada.ca").split(",") if h.strip()]

    fetcher = Fetcher(delay_seconds=0.5)

    for host in hosts:
        print(f"\n=== {host} ===", flush=True)
        request = urllib.request.Request(f"{host}/robots.txt",
                                         headers={"User-Agent": fetcher.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=30, context=TLS) as response:
                body = response.read().decode("utf-8", "replace")
                print(f"HTTP {response.status}, {len(body)} bytes, "
                      f"content-type {response.headers.get('Content-Type')}", flush=True)
                print("--- first 800 characters as this job received them ---", flush=True)
                print(body[:800], flush=True)
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.reason}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"{type(exc).__name__}: {exc}", flush=True)

    print("\n=== what the gate concludes ===", flush=True)
    for url in [h.strip() for h in os.environ.get(
            "MIGRAGENT_URLS",
            "https://www.inclusion.gob.es/web/migraciones/estudiar,"
            "https://www.gov.uk/skilled-worker-visa").split(",") if h.strip()]:
        state, why = fetcher.permission(url)
        print(f"  {state:<11} {url}", flush=True)
        print(f"              {why}", flush=True)
    return 0


def digest() -> int:
    """Turn what the watch round observed into what particular people are told.

        MIGRAGENT_MODE=digest  python -m migragent.worker

    Runs after the watch round, as one task rather than one per lane, because it
    reads rows the round has already written and the work is grouped by lane
    inside it. Ten tasks would each need the whole set of watches to know which
    of them were theirs.

    It makes no model calls and fetches nothing. Every sentence in every alert
    was written by the round, by a government, or by this file; nothing new is
    generated at the moment of telling somebody, which is what keeps an alert as
    checkable as the requirement it came from.
    """
    from .alerts import Alerts, Watcher, Watches
    from .cv import CVStore
    from .institutions import Institutions
    from .listings import Listings

    credentials = identity.credentials_for(identity.WATCHER, PROJECT)
    db = firestore.Client(project=PROJECT, credentials=credentials)

    marks = Watches(db)
    watches = marks.active()
    if not watches:
        print("no active watches, nothing to tell anybody", flush=True)
        return 0

    watcher = Watcher(
        db,
        changes=ChangeWriter(db),
        shortages=Shortages(db),
        institutions=Institutions(db),
        listings=Listings(db),
        cvs=CVStore(db),
    )
    counted = watcher.digest(watches, Alerts(db), marks)

    print(f"{counted['watches']} watches checked, {counted['alerts']} alerts written: "
          f"{counted.get('rule', 0)} rule, {counted.get('opening', 0)} opening, "
          f"{counted.get('job', 0)} job", flush=True)
    return 0


def main() -> int:
    if not PROJECT:
        raise SystemExit("GOOGLE_CLOUD_PROJECT is not set")

    if MODE == "selftest":
        return selftest()

    if MODE == "digest":
        return digest()

    if MODE == "robots":
        return robots_probe()

    lane_pair = _lane_for_task()
    if lane_pair is None:
        print(f"task {os.environ.get('CLOUD_RUN_TASK_INDEX')} has no lane to read, exiting")
        return 0
    jurisdiction, lane = lane_pair

    credentials = identity.credentials_for(identity.WATCHER, PROJECT)
    db = firestore.Client(project=PROJECT, credentials=credentials)
    gcs = storage.Client(project=PROJECT, credentials=credentials)

    max_depth = None if MAX_DEPTH == "all" else int(MAX_DEPTH)

    # The browser is optional and the job does not carry one. Rendering needs
    # Chromium, which would roughly quadruple the image, and the hosts that need
    # it were already rendered when the registry was walked. If a lane turns out
    # to need it, that is a decision to make on evidence rather than by shipping
    # a browser everywhere in case.
    round_ = Round(
        registry=Registry(db),
        corpus=Corpus(db),
        snapshots=SnapshotStore(gcs),
        fetcher=Fetcher(delay_seconds=0.5),
        extractor=Extractor(PROJECT, MODEL, MODEL_LOCATION, credentials),
        explainer=Explainer(PROJECT, MODEL, MODEL_LOCATION, credentials),
        changes_writer=ChangeWriter(db),
        shortage_reader=ShortageReader(PROJECT, MODEL, MODEL_LOCATION, credentials),
        shortages=Shortages(db),
        researcher=Researcher(project=PROJECT, model=MODEL, location=MODEL_LOCATION,
                              credentials=credentials, fetcher=Fetcher(delay_seconds=0.5),
                              on_event=lambda line: print(line, flush=True))
        if USE_AGENT else None,
        on_event=lambda line: print(line, flush=True),
    )

    result = round_.run(jurisdiction, lane, mode=MODE, max_depth=max_depth)
    doc_id = RunLog(db).record(result)

    print(
        f"\n{jurisdiction} {lane} {MODE}: considered {result.considered}, "
        f"fetched {result.fetched}, unchanged {result.unchanged}, "
        f"changed {result.changed}, extracted {result.extracted}, "
        f"already read {result.skipped_already_read}, unreadable {result.unreadable}, "
        f"failed {result.failed}",
        flush=True,
    )
    print(
        f"kept {result.kept}, dropped {result.dropped}, retired {result.retired}, "
        f"material changes {result.material_changes}, {result.seconds}s",
        flush=True,
    )
    print(f"round recorded as {doc_id}", flush=True)

    # A round that could not read a single page it was asked to read is a broken
    # round, and it exits non zero so the job says so rather than reporting a
    # green tick over an empty result. A round where some pages failed is not
    # broken: government websites have bad afternoons, and the count is on the
    # record either way.
    if result.considered and result.fetched == 0 and result.skipped_already_read == 0:
        print("nothing could be read at all", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
