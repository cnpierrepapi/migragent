"""The watch: what happened since you last looked, and why it matters to you.

WHY THIS IS THE PRODUCT
-----------------------
Everything before this build produces a document. A document is the half of the
job that stops being true the moment you close the tab: the salary floor moves,
the intake opens on a Tuesday with no announcement, the job that would have
carried your visa is filled in nine days, and the guide sitting in your bookmarks
says none of it.

This module is the other half. It takes the three things the pipeline already
observes and turns them into things a particular person is told:

    rule     a page your route depends on changed, materially
    opening  a door you can now walk through that was shut before: an occupation
             added to a country's shortage list, a school added to the register
             that licenses it to take you
    job      a posting in an occupation your own CV matched

Nothing here goes and finds anything new. Every alert is a row the daily round
already wrote, pointed at the one person it means something to. That is the
whole trick, and it is why an alert can carry the same evidence a requirement
carries: the government's own sentence, on the government's own page, with the
date it was read.

THREE THINGS THIS REFUSES TO DO
-------------------------------
It never invents urgency. There is no "act now", no countdown, no "3 people are
looking at this". The change is stated, the date is stated, and the person
decides. A product that manufactures pressure around somebody's immigration
status is doing something worse than being annoying.

It never announces a change it cannot show. A rule alert carries the change row,
which carries both snapshots and both dates. Where the summary was written by a
model, the alert says so on its face, because a sentence a model wrote and a
sentence a government wrote are different kinds of thing.

It never sends the same thing twice. Every alert id is derived from the case and
the thing that happened, so a digest that runs twice, or a round that retries,
writes the same document rather than a second copy. A watcher that repeats
itself teaches somebody to stop reading it, and the day something real moves
they will not read that either.

WHAT "SINCE" MEANS
------------------
A watch remembers when it was last checked. A digest looks only at rows observed
after that mark, and moves the mark forward only for the watches it actually ran.
Where a watch has never been checked, the mark is the day it started: signing up
does not deliver you a year of history you have already lived through.

DELIVERY
--------
Alerts are written to a collection and read on `/alerts`. There is no mail sender
in this project and none is pretended: `pending()` hands out exactly what an
email or a push would need, and the day a sender exists it reads from there. A
notification channel that half exists is worse than one that does not, because
somebody plans around it.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from google.cloud import firestore
from .clock import now_iso as _now

WATCHES = "watches"
ALERTS = "alerts"

# What an alert can be about. Held here rather than as loose strings, because a
# typo in a kind is an alert that renders with no icon and no explanation.
KINDS = ("rule", "opening", "job")

KIND_LABELS = {
    "rule": "A rule moved",
    "opening": "A door opened",
    "job": "A job you qualify for",
}

# How many of each kind one digest will produce for one person. A country that
# posts six hundred welding jobs overnight must not produce six hundred rows in
# front of somebody: they will close the page and never come back, and the rule
# change underneath will go with it.
PER_KIND = 6



def alert_id(case_id: str, kind: str, key: str) -> str:
    """Same person, same kind, same thing that happened: same id, forever."""
    digest = hashlib.sha256(f"{case_id}|{kind}|{key}".encode()).hexdigest()
    return f"{kind}-{digest[:24]}"


@dataclass
class Watch:
    """One person asking to be told. Nothing about them is stored here."""

    case_id: str
    jurisdiction: str
    lane: str
    started_at: str
    checked_at: str | None = None
    active: bool = True

    # The only channel that exists. Written down so that the day a second one
    # does, the rows already say which is which rather than being assumed.
    channel: str = "in_app"

    def since(self) -> str:
        return self.checked_at or self.started_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Alert:
    """One thing that happened, addressed to one case.

    `evidence` is what can be shown, and `evidence_by` says who wrote it. Those
    are two fields rather than one on purpose: "the government's page says this"
    and "a model summarised the difference" cannot be allowed to look alike.
    """

    alert_id: str
    case_id: str
    kind: str
    headline: str
    observed_at: str
    created_at: str

    detail: str = ""
    url: str = ""
    evidence: str = ""
    evidence_by: str = ""
    seen_at: str | None = None
    delivered_at: str | None = None

    # Free-form, small, and only ever things already stored elsewhere: a change
    # id, a listing id. Enough to open the underlying row from the page.
    refs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class Watches:
    """Who has asked to be told."""

    def __init__(self, client) -> None:
        self._db = client

    def start(self, case_id: str, jurisdiction: str, lane: str) -> Watch:
        """Turn the watch on. Idempotent: asking twice does not reset the mark.

        Re-arming a watch that was already running would move `started_at`
        forward and silently swallow anything observed in between.
        """
        existing = self.get(case_id)
        if existing is not None:
            if not existing.active:
                self._db.collection(WATCHES).document(case_id).update({"active": True})
                existing.active = True
            return existing

        watch = Watch(case_id=case_id, jurisdiction=jurisdiction, lane=lane,
                      started_at=_now())
        self._db.collection(WATCHES).document(case_id).set(watch.to_dict())
        return watch

    def stop(self, case_id: str) -> None:
        """Off means off, and it means it immediately.

        The row stays so the mark survives somebody turning it back on, and so
        `active: False` is a record of a choice rather than an absence. It goes
        entirely when the case is deleted.
        """
        ref = self._db.collection(WATCHES).document(case_id)
        if ref.get().exists:
            ref.update({"active": False})

    def get(self, case_id: str) -> Watch | None:
        snap = self._db.collection(WATCHES).document(case_id).get()
        if not snap.exists:
            return None
        row = snap.to_dict()
        return Watch(**{k: v for k, v in row.items() if k in Watch.__annotations__})

    def active(self, limit: int = 1000) -> list[Watch]:
        query = self._db.collection(WATCHES).where(
            filter=firestore.FieldFilter("active", "==", True)).limit(limit)
        return [Watch(**{k: v for k, v in s.to_dict().items()
                         if k in Watch.__annotations__})
                for s in query.stream()]

    def mark_checked(self, case_id: str, when: str) -> None:
        self._db.collection(WATCHES).document(case_id).update({"checked_at": when})

    def delete(self, case_id: str) -> int:
        ref = self._db.collection(WATCHES).document(case_id)
        if not ref.get().exists:
            return 0
        ref.delete()
        return 1


class Alerts:
    """What has been said to somebody, and what has not been said yet."""

    def __init__(self, client) -> None:
        self._db = client

    def record(self, alerts: list[Alert]) -> int:
        """Write a digest. Re-running writes the same rows, not more of them.

        `seen_at` and `delivered_at` are kept off the merge payload, so a
        re-run cannot mark something unread that a person has already read.
        """
        if not alerts:
            return 0
        batch = self._db.batch()
        for n, alert in enumerate(alerts, 1):
            payload = alert.to_dict()
            payload.pop("seen_at", None)
            payload.pop("delivered_at", None)
            batch.set(self._db.collection(ALERTS).document(alert.alert_id),
                      payload, merge=True)
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return len(alerts)

    def for_case(self, case_id: str, limit: int = 60) -> list[dict[str, Any]]:
        """Newest first. One equality filter, sorted here. Rule 30."""
        query = self._db.collection(ALERTS).where(
            filter=firestore.FieldFilter("case_id", "==", case_id)).limit(limit * 2)
        rows = [{**s.to_dict(), "id": s.id} for s in query.stream()]
        rows.sort(key=lambda r: (r.get("observed_at") or "", r.get("created_at") or ""),
                  reverse=True)
        return rows[:limit]

    def unseen_count(self, case_id: str) -> int:
        return sum(1 for r in self.for_case(case_id, limit=200) if not r.get("seen_at"))

    def mark_seen(self, case_id: str) -> int:
        """Called when the person opens the page. Reading is the acknowledgement."""
        now = _now()
        rows = [r for r in self.for_case(case_id, limit=200) if not r.get("seen_at")]
        batch = self._db.batch()
        for n, row in enumerate(rows, 1):
            batch.update(self._db.collection(ALERTS).document(row["id"]), {"seen_at": now})
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        if rows:
            batch.commit()
        return len(rows)

    def pending(self, limit: int = 200) -> list[dict[str, Any]]:
        """Everything written and not yet sent anywhere.

        Nothing consumes this yet, and that is the honest state of it: there is
        no mail sender in this project. When there is one, it reads from here and
        stamps `delivered_at`, and this function is the whole contract between
        the two halves.
        """
        query = self._db.collection(ALERTS).limit(limit * 3)
        rows = [{**s.to_dict(), "id": s.id} for s in query.stream()
                if not s.to_dict().get("delivered_at")]
        rows.sort(key=lambda r: r.get("created_at") or "")
        return rows[:limit]

    def delete_for_case(self, case_id: str) -> int:
        query = self._db.collection(ALERTS).where(
            filter=firestore.FieldFilter("case_id", "==", case_id))
        batch = self._db.batch()
        n = 0
        for snap in query.stream():
            batch.delete(snap.reference)
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        if n:
            batch.commit()
        return n


@dataclass
class LaneFeed:
    """What happened in one country and one lane, read once for everybody in it.

    Two people going to Canada to work share every rule change and every new
    shortage occupation. Reading those per person would multiply the same query
    by the number of watches, so the feed is built once per lane and fanned out.
    Jobs are not in here: those depend on the individual CV.
    """

    changes: list[dict[str, Any]] = field(default_factory=list)
    openings: list[dict[str, Any]] = field(default_factory=list)


class Watcher:
    """Turns what the round observed into what particular people are told."""

    def __init__(self, client, *, changes, shortages, institutions,
                 listings, cvs) -> None:
        self._db = client
        self._changes = changes
        self._shortages = shortages
        self._institutions = institutions
        self._listings = listings
        self._cvs = cvs

    # -- the lane half, read once ------------------------------------------

    def lane_feed(self, jurisdiction: str, lane: str, since: str) -> LaneFeed:
        feed = LaneFeed()

        for row in self._changes.for_jurisdiction(jurisdiction, lane, limit=100):
            # Only material changes reach a person. The explainer already
            # decides this and says so on the row; a change to a cookie banner
            # is not news, and D23 is the whole reason that field exists.
            if not row.get("material"):
                continue
            if (row.get("after_read_at") or "") <= since:
                continue
            feed.changes.append(row)

        if lane == "work":
            for row in self._shortages.for_jurisdiction(jurisdiction):
                if (row.get("first_seen_at") or "") > since:
                    feed.openings.append({"kind": "occupation", **row})
        else:
            for row in self._new_institutions(jurisdiction, since):
                feed.openings.append({"kind": "institution", **row})

        return feed

    def _new_institutions(self, jurisdiction: str, since: str) -> list[dict[str, Any]]:
        """Schools added to the register since the mark.

        `first_seen_at` only started being written in this build, so a register
        loaded before it has no new rows and produces no alerts. That is the
        correct behaviour and not a bug to work around: we do not know when
        those schools were added, so we do not say.
        """
        query = self._db.collection(self._institutions.COLLECTION).where(
            filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction)).where(
            filter=firestore.FieldFilter("first_seen_at", ">", since)).limit(50)
        try:
            return [{**s.to_dict(), "id": s.id} for s in query.stream()]
        except Exception:  # noqa: BLE001
            # A two-filter query wants a composite index, and a fresh clone will
            # not have one. Rule 30 says the product still works: no index means
            # no register alerts, not a failed digest.
            return []

    # -- the personal half --------------------------------------------------

    def for_watch(self, watch: Watch, feed: LaneFeed) -> list[Alert]:
        now = _now()
        since = watch.since()
        out: list[Alert] = []

        for row in feed.changes[:PER_KIND]:
            out.append(Alert(
                alert_id=alert_id(watch.case_id, "rule", row.get("id", "")),
                case_id=watch.case_id,
                kind="rule",
                headline=row.get("summary") or "A page your route depends on changed.",
                detail=(f"{row.get('added', 0)} lines added, "
                        f"{row.get('removed', 0)} removed, "
                        f"read on {row.get('after_read_at', '')[:10]}."),
                url=row.get("source_url", ""),
                evidence="Both versions of the page are kept and can be compared.",
                # Named, every time. The measurement is ours; the sentence is not.
                evidence_by=("summary written by a model, from a diff of two pages we hold"
                             if row.get("summary_by") else "measured from two stored pages"),
                observed_at=row.get("after_read_at", now),
                created_at=now,
                refs={"change_id": row.get("id", "")},
            ))

        for row in feed.openings[:PER_KIND]:
            if row.get("kind") == "occupation":
                headline = (f"{row.get('title', 'An occupation')} was added to the "
                            f"shortage list.")
                evidence = row.get("quote", "")
                by = "quoted from the government's own list"
            else:
                headline = (f"{row.get('name', 'A school')} was added to the register "
                            f"of institutions licensed to take international students.")
                evidence = row.get("register_name", "")
                by = "read from the official register"
            out.append(Alert(
                alert_id=alert_id(watch.case_id, "opening", row.get("id", "")),
                case_id=watch.case_id,
                kind="opening",
                headline=headline,
                detail=row.get("note") or row.get("location") or "",
                url=row.get("source_url", ""),
                evidence=evidence,
                evidence_by=by,
                observed_at=row.get("first_seen_at", now),
                created_at=now,
                refs={"row_id": row.get("id", "")},
            ))

        out.extend(self._jobs_for(watch, since, now))
        return out

    def _jobs_for(self, watch: Watch, since: str, now: str) -> list[Alert]:
        """Postings that went up since the mark, in occupations this CV matched.

        The occupations are recomputed rather than stored on the watch, so a
        person who uploads a better CV starts being told about the jobs it
        matches instead of the ones the old one did.
        """
        if watch.lane != "work":
            return []

        cv = self._cvs.get(watch.case_id)
        if cv is None:
            return []

        from .listings import matched_for, occupations_matching

        roles = ([c.value for c in cv.of_kind("role")]
                 + [c.value for c in cv.of_kind("licence")])
        wanted = occupations_matching(
            roles, self._shortages.for_jurisdiction(watch.jurisdiction))
        if not wanted:
            return []

        rows = self._listings.for_occupations(watch.jurisdiction, wanted)
        fresh = [r for r in rows if (r.get("first_seen_at") or "") > since]
        matched = matched_for(roles, fresh)

        out: list[Alert] = []
        for listing in matched[:PER_KIND]:
            because = listing.get("matched_because")
            out.append(Alert(
                alert_id=alert_id(watch.case_id, "job", listing.get("listing_id", "")),
                case_id=watch.case_id,
                kind="job",
                headline=listing.get("title", "A posting you match"),
                detail=" · ".join(x for x in (listing.get("employer"),
                                              listing.get("location"),
                                              listing.get("salary")) if x),
                url=listing.get("url", ""),
                # The same sentence the work screen shows: this is here because
                # your own CV says so, not because something decided it for you.
                evidence=(f'Your CV says "{because}", which matches the occupation '
                          f'this was filed under.' if because else ""),
                # A posting is never a source for a requirement. It is an
                # opportunity, and the row says whose word it is.
                evidence_by=(f"{listing.get('board') or 'a government job board'}, "
                             f"posted by an employer"),
                observed_at=listing.get("first_seen_at") or listing.get("read_at", now),
                created_at=now,
                refs={"listing_id": listing.get("listing_id", "")},
            ))
        return out

    # -- the whole run ------------------------------------------------------

    def digest(self, watches: list[Watch], store: Alerts,
               marks: Watches) -> dict[str, int]:
        """Run every watch, group by lane so the shared half is read once.

        The mark moves only for watches that were actually run, and only after
        their alerts are written. A crash between the two means a repeat, and a
        repeat is harmless because the ids are derived; a mark moved first would
        mean a change nobody is ever told about.
        """
        counted = {"watches": 0, "alerts": 0, "rule": 0, "opening": 0, "job": 0}
        by_lane: dict[tuple[str, str], list[Watch]] = {}
        for watch in watches:
            by_lane.setdefault((watch.jurisdiction, watch.lane), []).append(watch)

        for (jurisdiction, lane), group in by_lane.items():
            # One feed per lane, cut at the oldest mark in the group, then each
            # watch filters it down to its own window.
            oldest = min(w.since() for w in group)
            feed = self.lane_feed(jurisdiction, lane, oldest)

            for watch in group:
                mine = LaneFeed(
                    changes=[r for r in feed.changes
                             if (r.get("after_read_at") or "") > watch.since()],
                    openings=[r for r in feed.openings
                              if (r.get("first_seen_at") or "") > watch.since()],
                )
                alerts = self.for_watch(watch, mine)
                now = _now()
                store.record(alerts)
                marks.mark_checked(watch.case_id, now)

                counted["watches"] += 1
                counted["alerts"] += len(alerts)
                for alert in alerts:
                    counted[alert.kind] = counted.get(alert.kind, 0) + 1

        return counted
