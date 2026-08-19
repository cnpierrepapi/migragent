"""The source registry: what we read, and what we know about each page.

A source is a row in Firestore. Adding source 400 is a write, not a deploy. That
is the only reason a count of sources can be an honest claim rather than a
number somebody typed into marketing copy, and it is rule 28 in docs/RULES.md.

Nothing in this file decides what a page means. It records what a page is, where
it came from, whether we are allowed to read it, and what happened last time we
tried.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from google.cloud import firestore

COLLECTION = "sources"

Lane = Literal["work", "study"]
Kind = Literal["government", "institution", "shortage_list"]

# Where a requirement was actually read from. This rides along with every
# extraction and is shown in the guide, per rule 8. The institution's own site
# and a course portal are both real citations with real links and real dates.
# They are not equally close to the registrar, and the reader gets told which
# one they are looking at.
Provenance = Literal["official", "portal"]

# Why a source is not being read. Nothing silently disappears, per rule 11.
Blocked = Literal[
    "robots_disallowed",     # robots.txt said no, and no means no
    "server_refused",        # a polite identified request got 401, 403 or 429
    "gone",                  # the server answered 404 or 410, the page is not there
    "not_html",              # a PDF or a download, needs a different reader
    "duplicate_language",    # the same page in a language this jurisdiction does not publish in
]

# Hosts that serve one page many times, once per interface language, at URLs
# that differ only by a language segment. Spain's consular site does this in six
# languages, so one procedure page arrived as six sources and was extracted six
# times, producing six near identical copies of the same requirement and paying
# for each one. See D22.
#
# The rule stays what it always was: extract from the language the source
# publishes in, and keep the original sentence. Spain publishes in Spanish, so
# the Spanish page is the source and the Basque, Galician, Catalan, French and
# English renderings of it are not five more sources. They are the same source
# wearing a different interface, and counting them would inflate every number on
# the front of the product.
LANGUAGE_SEGMENT = "/language/"

# Deliberately NOT a Blocked state. A DNS or connection failure is a fact about
# the network between us and the host, not about the source, and writing it in
# as a property of the source is how a working government page ends up
# permanently marked dead. See D8. A row in this state is unverified and gets
# retried, and it is counted apart from both readable and blocked.

JURISDICTIONS = {
    "UK": {"name": "United Kingdom", "languages": ["en"]},
    "US": {"name": "United States", "languages": ["en"]},
    "CA": {"name": "Canada", "languages": ["en", "fr"]},
    "AU": {"name": "Australia", "languages": ["en"]},
    "FR": {"name": "France", "languages": ["fr"]},
    "ES": {"name": "Spain", "languages": ["es"]},
    "AE": {"name": "United Arab Emirates", "languages": ["ar", "en"]},
    # Added 19 August 2026, after checking where people actually go. Most
    # African migration is inside Africa, and off the continent the corridors
    # that matter are Europe, the Gulf and North America. Italy, Germany and
    # Portugal are three of the largest European destinations and none of them
    # was covered; Saudi Arabia is the Gulf corridor alongside the UAE.
    #
    # Where a government publishes the same guidance in its own language and in
    # English, both are listed, because the English page is published by the
    # source itself rather than translated by us. Rule 2 is about not extracting
    # from a translation WE made.
    "IT": {"name": "Italy", "languages": ["it", "en"]},
    "DE": {"name": "Germany", "languages": ["de", "en"]},
    "PT": {"name": "Portugal", "languages": ["pt", "en"]},
    "SA": {"name": "Saudi Arabia", "languages": ["ar", "en"]},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Source:
    """One page we read, or one page we are not allowed to read.

    `source_id` is stable and derived from what the source is, not from when it
    was added, so re-seeding updates rows instead of duplicating them.
    """

    source_id: str
    jurisdiction: str
    lane: Lane
    kind: Kind
    url: str
    title: str
    language: str
    provenance: Provenance = "official"

    # How we got here. A lead is how we found it, a source is what we read, and
    # they stay two fields, per rule 9.
    discovered_via: str = "seed"
    lead_url: str | None = None

    # How many links from the lane's entry page. 0 is the entry itself, 1 is a
    # page the entry links to directly, 2 is a page one hop further out.
    #
    # This decides what the GUIDE may cite, not what the registry may hold. The
    # walk reaches other visa types at depth 2, so a UK study walk collects the
    # Ancestry visa and airport transit pages. Those are worth watching, because
    # they are real UK immigration pages that really change, and they have no
    # business in a study guide. The corpus stays wide and the guide stays
    # close, which is why one number can serve both.
    depth: int | None = None

    # Politeness state, refreshed on a schedule rather than trusted forever.
    robots_allowed: bool | None = None
    robots_checked_at: str | None = None

    # What happened last time.
    last_read_at: str | None = None
    last_status: int | None = None
    stable_sha256: str | None = None
    raw_sha256: str | None = None
    snapshot_path: str | None = None

    # Why it is not being read, in words a person can act on.
    blocked: Blocked | None = None
    blocked_reason: str | None = None

    # Set when we could not reach the host and cannot say whose fault that is.
    # Never treated as the source being unavailable.
    unverified_reason: str | None = None
    last_attempt_at: str | None = None

    # Institutions only. "Top fifty by international share" is itself a claim,
    # so it carries its publisher and its data year, per rule 7. The list size
    # is stored too, so the product can say "the top 12 of 118 registered
    # institutions" rather than an unexplained number.
    international_share: float | None = None
    share_publisher: str | None = None
    share_data_year: int | None = None
    ranked_within: int | None = None
    rank_position: int | None = None
    replaced_source_id: str | None = None

    added_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @property
    def readable(self) -> bool:
        """Confirmed readable: we fetched it and nothing blocked us."""
        return self.blocked is None and self.last_read_at is not None

    @property
    def unverified(self) -> bool:
        """We do not know yet, and we are not going to pretend either way."""
        return self.blocked is None and self.last_read_at is None


class Registry:
    """Reads and writes source rows.

    The researcher holds datastore.viewer, so it can construct this and read.
    Any write from the researcher raises PermissionDenied, which is proved by
    tools/test_isolation.py rather than asserted here.
    """

    def __init__(self, client: firestore.Client) -> None:
        self._db = client

    def put(self, source: Source) -> None:
        """Write the row, including the fields that are now empty.

        `to_dict()` drops None, and a merge write ignores what is not there. So
        setting a field back to None left the old value sitting in Firestore,
        and nothing said so. Two things had been quietly broken by it:

        A source cleared of a block stayed blocked. Eighteen Spanish and German
        pages were marked as refusing us by a transient robots failure, and the
        repair that cleared them did nothing at all.

        `unverified_reason` could never be cleared, so a source that failed once
        on a bad network carried "unreachable" forever, even while being read
        successfully every day.

        The dataclass is the whole state of the row, so a field that is None on
        the object is deleted on the document rather than left behind. See D25.
        """
        payload: dict[str, Any] = {}
        for key, value in asdict(source).items():
            payload[key] = firestore.DELETE_FIELD if value is None else value
        self._db.collection(COLLECTION).document(source.source_id).set(
            payload, merge=True
        )

    def get(self, source_id: str) -> Source | None:
        snap = self._db.collection(COLLECTION).document(source_id).get()
        if not snap.exists:
            return None
        return Source(**snap.to_dict())

    def all(self) -> list[Source]:
        return [Source(**d.to_dict()) for d in self._db.collection(COLLECTION).stream()]

    def for_lane(self, jurisdiction: str, lane: Lane) -> list[Source]:
        """Every source for one jurisdiction and lane.

        Filtered with two equality clauses and then sorted in Python, because a
        composite index is required the moment a where and an order_by disagree,
        and a fresh clone of this project would 400 on an index nobody created.
        That is rule 30 and it is already in docs/INHERITED.md.
        """
        query = (
            self._db.collection(COLLECTION)
            .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
            .where(filter=firestore.FieldFilter("lane", "==", lane))
        )
        rows = [Source(**d.to_dict()) for d in query.stream()]
        return sorted(rows, key=lambda s: (s.kind != "government", s.rank_position or 0, s.url))

    def _count(self, query) -> int:
        """Count on the server rather than by dragging every row back.

        Streaming a collection to call len() on it costs one document read per
        row and gets slower every time the registry grows, which for a product
        whose whole point is a growing registry is the wrong direction. The
        aggregation returns a number.
        """
        result = query.count().get()
        return int(result[0][0].value)

    def total_sources(self) -> int:
        """The one number the product shows: every page and subpage we hold.

        Set on 18 August 2026. The surface carries a single total rather than a
        breakdown, because a visitor is asking how much ground this covers and
        four numbers do not answer that better than one.

        It is still the real number, read live, per rule 5. The breakdown has not
        gone anywhere: `counts()` keeps it for the runs, the logs and the docs,
        and a blocked or unverified source is still a source we know about and
        still counted here rather than dropped to make the figure prettier.
        """
        return self._count(self._db.collection(COLLECTION))

    def near_lane(self, jurisdiction: str, lane: Lane, max_depth: int = 1) -> list["Source"]:
        """Sources close enough to the entry page to belong in the guide."""
        return [s for s in self.for_lane(jurisdiction, lane)
                if (s.depth or 0) <= max_depth]

    def counts(self) -> dict[str, int]:
        """The full breakdown, for runs and logs rather than for the page.

        Rule 5. On the day it is nine it says nine. `readable` is reported apart
        from `total` because a source we are not allowed to read is still a
        source we know about, and hiding it would be the more flattering
        arrangement and the less honest one.
        """
        rows = self.all()
        return {
            "total": len(rows),
            "readable": sum(1 for r in rows if r.readable),
            "blocked": sum(1 for r in rows if r.blocked is not None),
            "unverified": sum(1 for r in rows if r.unverified),
            "government": sum(1 for r in rows if r.kind == "government"),
            "institution": sum(1 for r in rows if r.kind == "institution"),
            "jurisdictions": len({r.jurisdiction for r in rows}),
        }

    @staticmethod
    def redundant_language(url: str, jurisdiction: str) -> str | None:
        """Whether this URL is the same page in a language we do not read from.

        Returns the reason when it is redundant and None when it is not, so a
        caller can record why rather than dropping the row and leaving a hole in
        the count. Rule 11.
        """
        if LANGUAGE_SEGMENT not in url:
            return None
        tag = url.split(LANGUAGE_SEGMENT, 1)[1].split("/", 1)[0].lower()
        wanted = JURISDICTIONS.get(jurisdiction, {}).get("languages", [])
        if any(tag.startswith(w.lower()) for w in wanted):
            return None
        return (f"the same page in {tag}, and {jurisdiction} publishes in "
                f"{', '.join(wanted) or 'no recorded language'}")

    def bulk_put(self, sources: Iterable[Source]) -> int:
        batch = self._db.batch()
        count = 0
        for source in sources:
            batch.set(
                self._db.collection(COLLECTION).document(source.source_id),
                source.to_dict(),
                merge=True,
            )
            count += 1
            # Firestore caps a batch at 500 writes.
            if count % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return count
