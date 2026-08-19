"""One round of ingestion over one lane.

The same code fills the corpus and keeps it current. Two modes, one path:

  EXTRACT  read pages that have never been read, and record what they say
  WATCH    re-read pages that have, and record what moved

They share the fetcher, the robots gate, the quote check and the snapshot
archive. That is the point of putting them in one file. Two separate programs
would drift on what they will accept, and the day they disagree is the day a
requirement that could never have entered through the front door arrives through
the back one.

WHY THIS EXISTS AT ALL
----------------------
Ingestion used to be a tool somebody ran in a terminal. A run over hundreds of
pages outlives the window it started in, dies with it, retries nothing when one
host blips, and leaves nothing anybody can read afterwards. Two lanes of
fourteen were deep, and that was not a decision anybody made. It was as far as a
laptop got.

So a round is a thing that runs somewhere, reports what it did, survives one bad
page, and can be started again without paying twice for the pages it already
finished.

WHAT A ROUND WILL NOT DO
------------------------
It will not fetch a page robots.txt disallows, and it does not get to decide
that today is different.

It will not call the model on a page whose stable digest matches what we stored.
Most government pages do not change most days, and that check is the difference
between a fetch bill and an inference bill. Rule 14.

It will not record a date it did not observe. Every requirement carries the
moment its page was actually read on this run, and every change carries both
snapshots and both of their dates.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .changes import Change, change_id, text_diff
from .extract import page_text
from .fetcher import Fetched

Mode = str  # "extract" or "watch"

CHANGES = "changes"
ROUNDS = "rounds"

# The five jurisdictions this product offers, in a fixed order. US and Australia
# are not here: US federal immigration sites disallow us in robots.txt and
# Australia refuses our crawler outright, so they are shown as coming soon with
# the reason on the screen. Their rows stay in the registry marked blocked,
# because a source that disappears from a count is how a count starts lying.
OFFERED = ["UK", "CA", "FR", "ES", "AE"]

# A page that comes back this thin is usually a host that hides its content
# behind scripts rather than a page that says nothing. Worth one browser try
# before concluding either way. This is D15: Spain served nine links to a plain
# client and a hundred and seventeen to a browser.
THIN_PAGE_BYTES = 4000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SourceOutcome:
    """What happened to one page, in words that survive the run."""

    source_id: str
    url: str
    outcome: str
    detail: str | None = None
    kept: int = 0
    dropped: int = 0
    retired: int = 0
    material: bool | None = None
    seconds: float = 0.0


@dataclass
class RoundResult:
    """What a round did, written down so a pipeline can be audited later.

    A round nobody can inspect afterwards is a round that can quietly stop
    working, and the first anybody would know is a guide going stale with no
    sign on its face that it had.
    """

    jurisdiction: str
    lane: str
    mode: Mode
    started_at: str
    finished_at: str | None = None
    seconds: float = 0.0

    considered: int = 0
    fetched: int = 0
    unchanged: int = 0
    changed: int = 0
    extracted: int = 0
    skipped_already_read: int = 0
    unreadable: int = 0
    failed: int = 0

    kept: int = 0
    dropped: int = 0
    retired: int = 0
    material_changes: int = 0

    outcomes: list[SourceOutcome] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # The per page detail is useful while a round is running and is far too
        # much to keep forever on every row. The counts are the record; the last
        # few outcomes are there to make a bad round diagnosable.
        d["outcomes"] = [asdict(o) for o in self.outcomes[-40:]]
        return d


class Round:
    """Reads one lane, in one mode, and reports honestly as it goes.

    Everything is injected. That is not ceremony: it is what lets the same class
    run inside a Cloud Run job as the watcher, and inside a test with a fetcher
    that returns pages from disk and never touches somebody else's website.
    """

    def __init__(self, *, registry, corpus, snapshots, fetcher, extractor,
                 explainer, changes_writer, browser=None,
                 on_event: Callable[[str], None] | None = None) -> None:
        self._registry = registry
        self._corpus = corpus
        self._snapshots = snapshots
        self._fetcher = fetcher
        self._extractor = extractor
        self._explainer = explainer
        self._changes = changes_writer
        self._browser = browser
        self._on_event = on_event or (lambda line: None)

    # ------------------------------------------------------------------ fetch

    def _fetch(self, url: str) -> Fetched:
        """Plain client first, browser only if the page came back suspiciously thin."""
        page = self._fetcher.fetch(url)
        if page.ok and self._browser is not None and len(page.body or b"") < THIN_PAGE_BYTES:
            rendered = self._browser.fetch(url)
            if rendered.ok and len(rendered.body or b"") > len(page.body or b""):
                return rendered
        return page

    # ------------------------------------------------------------------- run

    def run(self, jurisdiction: str, lane: str, mode: Mode = "extract",
            max_depth: int | None = 1, limit: int | None = None,
            force: bool = False) -> RoundResult:
        """Read a lane and return what happened.

        `max_depth` defaults to 1, which is the entry page and what the
        government links directly, because that is all the guide is allowed to
        cite. Depth 2 pages stay in the registry and stay watched. Passing None
        reads everything, for when the corpus is the point rather than the guide.
        """
        started = time.monotonic()
        result = RoundResult(jurisdiction=jurisdiction, lane=lane, mode=mode,
                             started_at=_now())

        sources = [s for s in self._registry.for_lane(jurisdiction, lane)
                   if s.blocked is None]
        if max_depth is not None:
            sources = [s for s in sources if (s.depth or 0) <= max_depth]
        if limit:
            sources = sources[:limit]
        result.considered = len(sources)

        self._on_event(f"{len(sources)} sources for {jurisdiction} {lane}, mode {mode}")

        for i, source in enumerate(sources, 1):
            page_started = time.monotonic()
            try:
                outcome = self._one(source, jurisdiction, lane, mode, force)
            except Exception as exc:  # noqa: BLE001
                # One page's bad luck does not end the round. A UK run died two
                # thirds through on a transient network error from Firestore and
                # took every page after it. That is D18, and it is why this
                # catch is here rather than at the top of the loop.
                outcome = SourceOutcome(source_id=source.source_id, url=source.url,
                                        outcome="failed",
                                        detail=f"{type(exc).__name__}: {exc}"[:200])

            outcome.seconds = round(time.monotonic() - page_started, 2)
            result.outcomes.append(outcome)

            if outcome.outcome == "unreadable":
                result.unreadable += 1
            elif outcome.outcome == "failed":
                result.failed += 1
            elif outcome.outcome == "already read":
                result.skipped_already_read += 1
            else:
                result.fetched += 1
                if outcome.outcome == "unchanged":
                    result.unchanged += 1
                elif outcome.outcome == "changed":
                    result.changed += 1
                elif outcome.outcome == "extracted":
                    result.extracted += 1

            result.kept += outcome.kept
            result.dropped += outcome.dropped
            result.retired += outcome.retired
            if outcome.material:
                result.material_changes += 1

            self._on_event(
                f"  {i:>4}/{len(sources)}  {outcome.outcome:<12} "
                f"kept {outcome.kept:>2}  {outcome.url[-58:]}"
            )

        result.seconds = round(time.monotonic() - started, 1)
        result.finished_at = _now()
        return result

    # -------------------------------------------------------------- one page

    def _one(self, source, jurisdiction: str, lane: str, mode: Mode,
             force: bool) -> SourceOutcome:
        out = SourceOutcome(source_id=source.source_id, url=source.url, outcome="")

        if mode == "extract" and not force and self._corpus.has_been_read(source.source_id):
            # Resumable by construction. A run that died half way does not pay
            # for the half it finished.
            out.outcome = "already read"
            return out

        allowed, why = self._fetcher.allowed(source.url)
        if not allowed:
            out.outcome = "unreadable"
            out.detail = why
            self._mark_blocked(source, why)
            return out

        page = self._fetch(source.url)
        if not page.ok:
            out.outcome = "unreadable"
            out.detail = f"{page.outcome}: {page.reason or page.status}"
            self._mark_attempt(source, page)
            return out

        # Hash first, before anything expensive. Rule 14.
        if mode == "watch" and page.unchanged_from(source.stable_sha256):
            out.outcome = "unchanged"
            self._mark_read(source, page, source.snapshot_path)
            return out

        snapshot_path = self._snapshots.store(source.source_id, page)

        if mode == "watch":
            out = self._record_change(source, page, snapshot_path, jurisdiction, lane, out)

        extraction = self._extractor.extract(
            page, jurisdiction=jurisdiction, lane=lane,
            language=source.language, provenance=source.provenance,
        )
        if extraction.model_error:
            out.outcome = out.outcome or "failed"
            out.detail = extraction.model_error[:200]
            self._mark_read(source, page, snapshot_path)
            return out

        # Anything this page used to say and no longer says stops being told to
        # anybody, from now, with the date we noticed it.
        before_ids = self._corpus.live_ids_for_source(source.source_id)
        read = self._corpus.record(source.source_id, extraction, jurisdiction, lane)
        after_ids = self._corpus.live_ids_for_source(source.source_id)
        gone = before_ids - after_ids
        if gone:
            out.retired = self._corpus.retire(
                gone, page.read_at, "the page no longer says this",
            )

        out.kept = read.kept
        out.dropped = read.dropped
        out.outcome = out.outcome or "extracted"
        self._mark_read(source, page, snapshot_path)
        return out

    # ---------------------------------------------------------------- change

    def _record_change(self, source, page: Fetched, snapshot_path: str | None,
                       jurisdiction: str, lane: str,
                       out: SourceOutcome) -> SourceOutcome:
        """Write down what moved, with both versions attached."""
        previous = None
        if source.snapshot_path:
            previous = self._snapshots.read(source.snapshot_path)

        after_text = page_text(page)
        if previous is None:
            # We hold today and not yesterday. The page is different from what
            # the registry recorded, and when it changed is not knowable from
            # what we have. Saying so beats inventing a date.
            change = Change(
                change_id=change_id(source.source_id, source.stable_sha256 or "none",
                                    page.sha256 or ""),
                source_id=source.source_id, source_url=page.final_url or page.url,
                jurisdiction=jurisdiction, lane=lane,
                before_read_at=source.last_read_at or "unknown",
                after_read_at=page.read_at,
                before_sha256=source.stable_sha256 or "",
                after_sha256=page.sha256 or "",
                before_snapshot=source.snapshot_path, after_snapshot=snapshot_path,
                added=0, removed=0, diff_sample="",
                history_incomplete=True,
            )
        else:
            before_page = Fetched(url=source.url, outcome="fetched",
                                  read_at=source.last_read_at or "unknown",
                                  status=200, body=previous)
            added, removed, sample = text_diff(page_text(before_page), after_text)
            summary, material = self._explainer.explain(sample)
            change = Change(
                change_id=change_id(source.source_id, source.stable_sha256 or "none",
                                    page.sha256 or ""),
                source_id=source.source_id, source_url=page.final_url or page.url,
                jurisdiction=jurisdiction, lane=lane,
                before_read_at=source.last_read_at or "unknown",
                after_read_at=page.read_at,
                before_sha256=source.stable_sha256 or "",
                after_sha256=page.sha256 or "",
                before_snapshot=source.snapshot_path, after_snapshot=snapshot_path,
                added=added, removed=removed, diff_sample=sample[:4000],
                summary=summary, summary_by="model" if summary else None,
                material=material,
            )

        self._changes.record(change)
        out.outcome = "changed"
        out.material = change.material
        return out

    # -------------------------------------------------------------- registry

    def _mark_read(self, source, page: Fetched, snapshot_path: str | None) -> None:
        source.last_read_at = page.read_at
        source.last_attempt_at = page.read_at
        source.last_status = page.status
        source.stable_sha256 = page.sha256
        source.raw_sha256 = page.raw_sha256
        if snapshot_path:
            source.snapshot_path = snapshot_path
        source.unverified_reason = None
        self._registry.put(source)

    def _mark_attempt(self, source, page: Fetched) -> None:
        """A failed fetch is an attempt, never a verdict on the source.

        A transient DNS failure once nearly wrote "unreachable" permanently onto
        six working government sites. That is D8, and it is why this touches the
        attempt fields and leaves everything the product relies on alone.
        """
        source.last_attempt_at = page.read_at
        source.unverified_reason = f"{page.outcome}: {page.reason or page.status}"
        self._registry.put(source)

    def _mark_blocked(self, source, why: str) -> None:
        source.blocked = "robots"
        source.blocked_reason = why
        source.last_attempt_at = _now()
        self._registry.put(source)


class ChangeWriter:
    """Writes changes, keyed so a repeated round cannot record one twice."""

    def __init__(self, client) -> None:
        self._db = client

    def record(self, change: Change) -> None:
        self._db.collection(CHANGES).document(change.change_id).set(
            change.to_dict(), merge=True,
        )

    def for_jurisdiction(self, jurisdiction: str, lane: str | None = None,
                         limit: int = 50) -> list[dict[str, Any]]:
        """Recent observed changes, newest first.

        One equality filter and sorting in Python, because a where plus an
        order_by wants a composite index and a fresh clone would fail on an
        index nobody created. Rule 30.
        """
        from google.cloud import firestore

        query = self._db.collection(CHANGES).where(
            filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction)
        )
        rows = [{**d.to_dict(), "id": d.id} for d in query.stream()]
        if lane:
            rows = [r for r in rows if r.get("lane") == lane]
        rows.sort(key=lambda r: r.get("after_read_at", ""), reverse=True)
        return rows[:limit]


class RunLog:
    """Every round, written down. A pipeline nobody can audit can quietly stop."""

    def __init__(self, client) -> None:
        self._db = client

    def record(self, result: RoundResult) -> str:
        doc_id = f"{result.jurisdiction}-{result.lane}-{result.mode}-{result.started_at}"
        self._db.collection(ROUNDS).document(doc_id).set(result.to_dict())
        return doc_id

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = [{**d.to_dict(), "id": d.id}
                for d in self._db.collection(ROUNDS).stream()]
        rows.sort(key=lambda r: r.get("started_at", ""), reverse=True)
        return rows[:limit]


def lanes(offered: list[str] | None = None) -> list[tuple[str, str]]:
    """Every offered jurisdiction crossed with work and study, in a fixed order.

    Fixed, because a Cloud Run job hands each parallel task an index and that
    index has to mean the same lane on every run. A set would reorder itself and
    task three would read Spain one day and France the next, which would make
    every per lane number in the run log meaningless.
    """
    return [(j, lane) for j in (offered or OFFERED) for lane in ("study", "work")]
