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
from .extract import Extraction, page_text
from .verify import review
from .fetcher import Fetched

Mode = str  # "extract" or "watch"

CHANGES = "changes"
ROUNDS = "rounds"

# The five jurisdictions this product offers, in a fixed order.
#
# US and Australia are not here, and the reason is narrower than "they disallow
# us", which is what was first recorded and is not true of either. US
# immigration hosts refuse to serve their robots.txt to anybody, so their rules
# cannot be read. Australia serves its robots.txt to a generic client and
# refuses it to one that names itself. A host that will not state its rules has
# not given permission, so we stop, and the registry records which of the two it
# was. See D24. Their rows stay, marked blocked, because a source that
# disappears from a count is how a count starts lying.
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

    # What the second reader made of this page. Carried per page as well as per
    # round, because a single page disagreeing about everything is a different
    # problem from a lane disagreeing about a little, and the round total cannot
    # tell them apart.
    agreed: int = 0
    disputed: int = 0
    unverified: int = 0


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

    # The second reader's score for the whole round. If disputed is always zero
    # the check is theatre, and this is the number that says so.
    agreed: int = 0
    disputed: int = 0
    unverified: int = 0

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
                 shortage_reader=None, shortages=None, researcher=None,
                 second_reader=None,
                 on_event: Callable[[str], None] | None = None) -> None:
        # Optional on purpose. Without it a round reads the way it always has,
        # which is what watch mode needs and what a round with no model access
        # falls back to.
        self._researcher = researcher
        # Optional the same way the researcher is. Without it a round reads
        # exactly the way it always has, and nothing downstream can tell the
        # difference except that second_read is empty.
        self._second_reader = second_reader
        self._shortage_reader = shortage_reader
        self._shortages = shortages
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

        # Rows blocked by robots.txt come back for a re-check, and nothing else
        # blocked does. A 404 is a fact about a page and stays one; permission is
        # a fact about a host on a day, and hosts change their minds.
        #
        # This matters more than it sounds. On 20 August the daily round marked
        # all sixteen Spanish rows `robots_disallowed`, and the filter below meant
        # they would never be looked at again: Spain left the pipeline silently
        # and permanently, from one reading, while the product still offered it.
        # A minute later the same check from a laptop said Spain allows us. One
        # of those two answers is about the network the question was asked from,
        # and neither is a reason to retire a country forever.
        sources = [s for s in self._registry.for_lane(jurisdiction, lane)
                   if s.blocked is None or s.blocked == "robots_disallowed"]
        if max_depth is not None:
            sources = [s for s in sources if (s.depth or 0) <= max_depth]
        if self._researcher is not None:
            # Entry pages first. They are where the agent starts, and a limited
            # run that never reached one would report that the agent did nothing
            # when what happened is that it was never asked.
            # An unset depth means a hand seeded entry, which is what the rest
            # of this file already means by `s.depth or 0`. Sorting it as
            # missing instead put the entry pages last, and a limited run picked
            # up a shortage list and reported that the agent had done nothing.
            sources.sort(key=lambda s: s.depth or 0)
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
                elif outcome.outcome in ("extracted", "researched"):
                    result.extracted += 1

            result.kept += outcome.kept
            result.dropped += outcome.dropped
            result.retired += outcome.retired
            result.agreed += outcome.agreed
            result.disputed += outcome.disputed
            result.unverified += outcome.unverified
            if outcome.material:
                result.material_changes += 1

            self._on_event(
                f"  {i:>4}/{len(sources)}  {outcome.outcome:<12} "
                f"kept {outcome.kept:>2}  {outcome.url[-58:]}"
            )

        result.seconds = round(time.monotonic() - started, 1)
        result.finished_at = _now()
        return result

    def _second_read(self, page: Fetched, extraction, out: SourceOutcome) -> None:
        """Put an extraction past the second reader, if there is one.

        Runs before the corpus is written, because the point of a second reader
        is to stop something reaching the guide, and a requirement that has to be
        retired afterwards was already published.
        """
        if self._second_reader is None or not extraction.requirements:
            return
        counts = review(self._second_reader, page_text(page), extraction)
        out.agreed += counts["agreed"]
        out.disputed += counts["disputed"]
        out.unverified += counts["unverified"]

    # -------------------------------------------------------------- one page

    def _one(self, source, jurisdiction: str, lane: str, mode: Mode,
             force: bool) -> SourceOutcome:
        out = SourceOutcome(source_id=source.source_id, url=source.url, outcome="")

        if mode == "extract" and not force and self._corpus.has_been_read(source.source_id):
            # Resumable by construction. A run that died half way does not pay
            # for the half it finished.
            out.outcome = "already read"
            return out

        state, why = self._fetcher.permission(source.url)
        if state == "disallowed":
            out.outcome = "unreadable"
            out.detail = why
            self._mark_blocked(source, why)
            return out

        if source.blocked == "robots_disallowed":
            # It said no before and says yes now. The block lifts, because the
            # only thing it ever recorded was an answer on a particular day.
            out.detail = "robots.txt allows this again"
            source.blocked = None
            source.blocked_reason = None
            self._registry.put(source)
        if state == "unknown":
            # Could not read the rules this time. Not a verdict on the source,
            # so it is recorded as unverified and tried again. D25.
            out.outcome = "unreadable"
            out.detail = why
            source.unverified_reason = why
            source.last_attempt_at = _now()
            self._registry.put(source)
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

        # Second gate, and the one that stops the watcher crying wolf.
        #
        # The stable digest strips scripts, styles, comments and nonces, and on
        # the first real watch round 95 pages out of 143 still came back with a
        # different digest and NOT ONE ADDED OR REMOVED LINE OF TEXT. Two thirds
        # of the corpus reported a change that did not happen, and each one paid
        # for a re-extraction. That is D23.
        #
        # Chasing the digest until it is perfect is a game with no end: every
        # host has its own idea of what to vary per request, per region and per
        # edge cache. So the digest stays a cheap first filter, and what decides
        # whether anything happened is the text itself. If not one line of words
        # moved, nothing moved, whatever the bytes say.
        #
        # A watcher that cries change every day is worse than no watcher,
        # because it teaches the person receiving the notifications to ignore
        # them, and the day something real moves they will ignore that too.
        if mode == "watch":
            settled = self._settle(source, page, out)
            if settled is not None:
                return settled

        snapshot_path = self._snapshots.store(source.source_id, page)

        if mode == "watch":
            out = self._record_change(source, page, snapshot_path, jurisdiction, lane, out)

        # What a page is read AS depends on what kind of source it is, and
        # getting that wrong is not a small error.
        #
        # A shortage list sits in the registry with lane "work", because it is
        # about work, which means the round picks it up alongside the visa pages.
        # Run the requirement extractor over it and every occupation on it
        # becomes a requirement in somebody's work guide: "you must be a welder",
        # quoted correctly, linked correctly, dated correctly, and nonsense. That
        # is D29's shape exactly, a true sentence filed under the wrong question,
        # and the quote check cannot see it because nothing is invented.
        #
        # An institution register is a table parsed by its own tool. There is
        # nothing here for a model to read, and it is watched rather than
        # extracted so a change still gets noticed.
        if source.kind == "shortage_list":
            return self._read_shortage_list(source, page, snapshot_path, out)
        if source.kind == "institution":
            out.outcome = out.outcome or "watched only"
            out.detail = "a register, parsed by tools/seed_institutions.py"
            self._mark_read(source, page, snapshot_path)
            return out

        # An entry page is where a lane starts, and it is the one place where
        # choosing what to read next is worth a decision rather than a rule. So
        # if there is an agent, the entry page is handed to it and it reads out
        # from there. Every other row is read the way it always was.
        if (self._researcher is not None and mode == "extract"
                and (source.depth or 0) == 0):
            return self._research(source, jurisdiction, lane, page, snapshot_path, out)

        extraction = self._extractor.extract(
            page, jurisdiction=jurisdiction, lane=lane,
            language=source.language, provenance=source.provenance,
        )
        if extraction.model_error:
            out.outcome = out.outcome or "failed"
            out.detail = extraction.model_error[:200]
            self._mark_read(source, page, snapshot_path)
            return out

        self._second_read(page, extraction, out)

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

    # -------------------------------------------------------------- the agent

    def _research(self, source, jurisdiction: str, lane: str, page: Fetched,
                  snapshot_path: str | None, out: SourceOutcome) -> SourceOutcome:
        """Hand the entry page to the agent, and file what it comes back with.

        The agent reads pages of its own choosing, so some of what it returns is
        about pages this registry has never heard of. Those get rows, because a
        page a requirement is cited from has to be a page the watcher re-reads
        tomorrow. A citation to something nothing is watching goes stale in
        silence, which is the whole failure this pipeline exists to avoid.

        Rows are looked up by URL before being created, so a page the walk
        already found keeps the name it already has rather than gaining a second
        one. See D31.
        """
        from .registry import JURISDICTIONS, Source, source_id

        place = JURISDICTIONS.get(jurisdiction, {}).get("name", jurisdiction)
        session = self._researcher.research(
            source.url, jurisdiction=jurisdiction, lane=lane, place=place,
            language=source.language, provenance=source.provenance,
        )

        by_url: dict[str, list] = {}
        for requirement in session.requirements:
            by_url.setdefault(requirement.source_url, []).append(requirement)

        for url in session.pages_read:
            fetched = session.fetched.get(url)
            if fetched is None:
                continue

            if url == source.url or url == (page.final_url or source.url):
                row, path = source, snapshot_path
            else:
                row = self._registry.by_url(jurisdiction, lane, url)
                if row is None:
                    row = Source(
                        source_id=source_id(jurisdiction, lane, url),
                        jurisdiction=jurisdiction, lane=lane, kind="government",
                        url=url,
                        title=url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
                                 .replace(".html", ""),
                        language=source.language, provenance=source.provenance,
                        discovered_via=f"chosen by the researcher from {source.source_id}",
                        lead_url=source.url,
                        # Depth is how far the GUIDE may cite from, and the agent
                        # opened this because the entry page pointed at it, which
                        # is what depth 1 means.
                        depth=1,
                        robots_allowed=True, robots_checked_at=fetched.read_at,
                    )
                path = self._snapshots.store(row.source_id, fetched)

            requirements = by_url.get(url, [])
            extraction = Extraction(
                source_url=url, read_at=fetched.read_at, requirements=requirements,
                # Open questions belong to the session rather than to any one
                # page, so they are filed against the entry page and not
                # repeated under every page the agent opened.
                open_questions=session.open_questions if row is source else [],
            )

            self._second_read(fetched, extraction, out)

            before = self._corpus.live_ids_for_source(row.source_id)
            read = self._corpus.record(row.source_id, extraction, jurisdiction, lane)
            gone = before - self._corpus.live_ids_for_source(row.source_id)
            if gone:
                out.retired += self._corpus.retire(
                    gone, fetched.read_at, "the page no longer says this")

            out.kept += read.kept
            self._mark_read(row, fetched, path)

        out.dropped += len(session.refused)
        out.outcome = out.outcome or "researched"
        out.detail = (f"{len(session.pages_read)} page(s) chosen, {session.turns} turn(s), "
                      f"{len(session.refused)} refused: {session.stopped_because}")[:200]
        if session.error:
            out.detail = f"{out.detail} | {session.error}"[:200]
        return out

    # ------------------------------------------------------------- shortages

    def _read_shortage_list(self, source, page: Fetched, snapshot_path: str | None,
                            out: SourceOutcome) -> SourceOutcome:
        """Read a shortage list as a shortage list, into its own collection.

        Occupations never touch the requirements collection. A guide is built
        from requirements, so keeping them apart is what stops "shortage
        occupation: welder" appearing in somebody's list of things they must do.
        """
        if self._shortage_reader is None or self._shortages is None:
            out.outcome = out.outcome or "skipped"
            out.detail = "no shortage reader was given to this round"
            self._mark_read(source, page, snapshot_path)
            return out

        reading = self._shortage_reader.read(page, source.jurisdiction, source.language)
        if reading.model_error:
            out.outcome = out.outcome or "failed"
            out.detail = reading.model_error[:200]
            self._mark_read(source, page, snapshot_path)
            return out

        out.kept = self._shortages.record(reading, source.source_id)
        out.dropped = len(reading.dropped)
        out.outcome = out.outcome or "extracted"
        self._mark_read(source, page, snapshot_path)
        return out

    # ---------------------------------------------------------------- change

    def _settle(self, source, page: Fetched, out: SourceOutcome) -> SourceOutcome | None:
        """Decide whether a different digest means a different page.

        Returns a finished outcome when the words are identical and the round
        should stop here, and None when something really did move and the round
        should carry on to the diff and the re-read.

        When the words are identical the new digest is written down, so the same
        page does not report the same non change again tomorrow, and the snapshot
        is NOT stored. The archive holds versions of a page, not readings of it.
        Storing a byte variant that says exactly the same thing would fill the
        evidence store with noise and make the real history harder to find.
        """
        if not source.snapshot_path:
            return None
        previous = self._snapshots.read(source.snapshot_path)
        if previous is None:
            return None

        before = Fetched(url=source.url, outcome="fetched",
                         read_at=source.last_read_at or "unknown",
                         status=200, body=previous)
        added, removed, _ = text_diff(page_text(before), page_text(page))
        if added or removed:
            return None

        out.outcome = "unchanged"
        out.detail = "the bytes differ and not one line of text does"
        self._mark_read(source, page, source.snapshot_path)
        return out

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
        source.blocked = "robots_disallowed"
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
