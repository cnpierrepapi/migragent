"""Job postings, from government run boards only.

WHY GOVERNMENT BOARDS AND NOTHING ELSE
--------------------------------------
The large commercial boards disallow crawling, and the robots gate is not
negotiable, so they are out. That is not a limitation to apologise for: a
government job service is public by design, dated, and already the kind of page
this pipeline reads.

Checked on 19 August 2026 with our own gate, which is the only evidence worth
having about this:

    allowed      jobbank.gc.ca, europa.eu/eures, empleate.gob.es, sepe.es,
                 candidat.francetravail.fr, arbeitsagentur.de, iefp.pt
    unknown      findajob.dwp.gov.uk (503 on robots.txt), anpal.gov.it, mohre.gov.ae

Canada's Job Bank is the one built against first, because it is allowed, it
answers a plain client, and its results carry everything a listing needs in the
markup. Its RSS feed answers 406 to a client that says who it is, so the HTML
search results are what we read. We do not send a different user agent to get a
different answer.

WHAT A LISTING IS AND IS NOT
----------------------------
**A posting is never a source for a requirement.** It is an opportunity.
Requirements come from governments and regulators. A posting that says something
about a visa is evidence of what an employer believes, not of what the law is,
and `provenance` says `employer` on every one of these rows so nothing downstream
can quietly promote it.

The board is a government service. The posting on it usually is not: Job Bank
carries employer submissions and postings gathered from commercial sites, and it
names which. So a row carries both, `board` and `posted_via`, because collapsing
them would let a Talent.com advert inherit the Government of Canada's authority.

NO SEARCH, HERE EITHER
----------------------
Nobody types a query. Ingestion asks the board about occupations we already hold,
and a user is matched against what was ingested. The user never searches and
never sees anything their own case did not match.
"""
from __future__ import annotations

import hashlib
import html
import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .fetcher import Fetched, decode_body

LISTINGS = "listings"

# A page that answers 200 and says 404 in its own title. Job Bank does this, and
# a fetcher that trusts the status code would store an error page as a result
# set with no listings in it and nothing to say why.
_SOFT_404 = re.compile(r"<title>\s*HTTP Error 40[34]", re.I)

_ARTICLE = re.compile(r"<article\b[^>]*id=\"article-(\d+)\"(.*?)</article>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")

# Session ids in the path, tracking in the query. Neither says which page this
# is, and keeping them would give the same posting a new identity every time the
# board handed us a new session.
_SESSION_IN_PATH = re.compile(r";jsessionid=[^/?#]*", re.I)
_DROP_PARAMS = {"source", "jsessionid", "utm_source", "utm_medium", "utm_campaign"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def clean_listing_url(url: str) -> str:
    """The address of a posting, with the session and the tracking taken off."""
    url = _SESSION_IN_PATH.sub("", url)
    split = urllib.parse.urlsplit(url)
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(split.query)
            if k.lower() not in _DROP_PARAMS]
    return urllib.parse.urlunsplit(
        (split.scheme, split.netloc, split.path, urllib.parse.urlencode(kept), ""))


def listing_id(board: str, posting_id: str) -> str:
    digest = hashlib.sha256(f"{board}\n{posting_id}".encode()).hexdigest()[:10]
    return f"{board}-{posting_id}-{digest}"


@dataclass
class Listing:
    """One job posting, as the board published it."""

    listing_id: str
    jurisdiction: str
    board: str
    title: str
    url: str
    read_at: str
    source_url: str

    employer: str | None = None
    location: str | None = None
    salary: str | None = None
    posted_on: str | None = None

    # Which commercial site the board gathered this from, when it says so. A
    # government board is not the author of every advert it carries.
    posted_via: str | None = None

    # The occupation we asked the board about. Not a claim about the job, a
    # record of how we came to be holding it.
    matched_occupation: str | None = None
    occupation_id: str | None = None

    # The words actually sent to the board. Differs from the occupation when the
    # full classification title found nothing. See JobBank.queries_for.
    matched_query: str | None = None

    # Never "official". See the module docstring.
    provenance: str = "employer"

    first_seen_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class JobBank:
    """Canada's Job Bank, read from its search results.

    Parsing is plain code and stays that way. Which fields a row has is a fact
    about the markup, not a judgment, and a model asked to read a results page
    would invent a salary on the day the markup changed rather than failing.
    """

    BOARD = "jobbank.gc.ca"
    JURISDICTION = "CA"
    SEARCH = "https://www.jobbank.gc.ca/jobsearch/jobsearch"

    def search_url(self, occupation: str) -> str:
        return f"{self.SEARCH}?{urllib.parse.urlencode({'searchstring': occupation})}"

    @staticmethod
    def queries_for(occupation: str) -> list[str]:
        """What to ask the board, in order, most specific first.

        Governments name occupations in classification language: "Aircraft
        instrument, electrical and avionics mechanics, technicians and
        inspectors" is one entry on Canada's list and finds nothing at all as a
        literal search, because no employer advertises in that dialect.

        So there is one narrowing step, the part before the first comma, and
        only when the full title came back empty. Which query actually produced
        a listing is stored on the row, so a result from "Aircraft instrument"
        is never presented as the board answering the whole title.

        One step, not a ladder. Chopping further gets to single words like
        "Aircraft", which returns jobs that have nothing to do with the
        occupation, and a match nobody can defend is worse than a gap.
        """
        queries = [occupation]
        head = occupation.split(",")[0].strip()
        if head and head.lower() != occupation.lower() and len(head.split()) > 1:
            queries.append(head)
        return queries

    def parse(self, page: Fetched, occupation: str,
              occupation_id: str | None = None,
              query: str | None = None) -> tuple[list[Listing], str | None]:
        """Listings on one results page, and why there are none if there are none."""
        if not page.ok or page.body is None:
            return [], f"the page was not read: {page.outcome}"

        text = decode_body(page.body, page.content_type)
        if _SOFT_404.search(text):
            # Answered 200 and means 404. Saying so beats reporting an empty
            # result set, which is what an employment service having no welders
            # would also look like.
            return [], "the board answered 200 with its own 404 page"

        found: list[Listing] = []
        for posting_id, block in _ARTICLE.findall(text):
            href = re.search(r'href="([^"]+)"', block)
            if not href:
                continue
            url = clean_listing_url(urllib.parse.urljoin(page.final_url or page.url,
                                                         html.unescape(href.group(1))))

            title = self._field(block, r'<span class="noctitle">(.*?)</span>')
            if not title:
                continue

            found.append(Listing(
                listing_id=listing_id(self.BOARD, posting_id),
                jurisdiction=self.JURISDICTION,
                board=self.BOARD,
                title=title,
                url=url,
                read_at=page.read_at,
                source_url=page.final_url or page.url,
                employer=self._field(block, r'<li class="business">(.*?)</li>'),
                location=self._field(block, r'<li class="location">(.*?)</li>'),
                salary=self._field(block, r'<li class="salary">(.*?)</li>'),
                posted_on=self._field(block, r'<li class="date">(.*?)</li>'),
                posted_via=self._field(block, r'<span class="wb-inv">(.*?)</span>'),
                matched_occupation=occupation,
                occupation_id=occupation_id,
                matched_query=query or occupation,
            ))

        if not found:
            return [], "the results page held no postings"
        return found, None

    @staticmethod
    def _field(block: str, pattern: str) -> str | None:
        match = re.search(pattern, block, re.I | re.S)
        if not match:
            return None
        value = _text(match.group(1))
        # The location cell carries a screen reader label before the place, and
        # the salary cell carries the currency icon's text. Both are markup, not
        # content, and neither belongs in a stored field.
        value = re.sub(r"^(Location|Salary)\s+", "", value).strip()
        return value or None


class Listings:
    """Reads and writes listings."""

    COLLECTION = LISTINGS

    def __init__(self, client) -> None:
        self._db = client

    def record(self, listings: list[Listing]) -> int:
        """Store what a board published, keeping the date we first saw each one.

        `first_seen_at` is never overwritten, because how long a post has been up
        is the only thing we can honestly say about how live it is, and merging
        would reset it to today on every round.
        """
        if not listings:
            return 0

        refs = [self._db.collection(LISTINGS).document(x.listing_id) for x in listings]
        # One read for the whole page of results rather than one per listing.
        already = {snap.id for snap in self._db.get_all(refs) if snap.exists}

        batch = self._db.batch()
        written = 0
        for listing, ref in zip(listings, refs):
            payload = listing.to_dict()
            payload["last_seen_at"] = listing.read_at
            if listing.listing_id in already:
                payload.pop("first_seen_at", None)
            batch.set(ref, payload, merge=True)
            written += 1
            if written % 200 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return written

    def for_jurisdiction(self, jurisdiction: str, limit: int = 200) -> list[dict[str, Any]]:
        from google.cloud import firestore

        query = (self._db.collection(LISTINGS)
                 .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
                 .limit(limit))
        return [d.to_dict() for d in query.stream()]

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in self._db.collection(LISTINGS).stream():
            key = doc.to_dict().get("jurisdiction", "?")
            counts[key] = counts.get(key, 0) + 1
        return counts


# Words that appear in half the occupation titles a government publishes and
# carry no information about what the job is.
_NOISE = {"and", "or", "of", "the", "in", "other", "related", "occupations",
          "workers", "specialists", "technicians", "managers", "assistants",
          "supervisors", "professionals", "services", "service", "senior",
          "junior", "trades", "general"}


def _words(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", value.lower()) if len(w) > 2} - _NOISE


def matched_for(roles: list[str], listings: list[dict[str, Any]],
                limit: int = 20) -> list[dict[str, Any]]:
    """The listings a person's own CV matched, and the role that matched each.

    THIS IS THE WHOLE OF WHAT A USER SEES. There is no search box anywhere in
    this product: a person uploads a CV and is shown what it matched, and
    nothing else exists for them. So this function is not a ranking nicety, it
    is the entire surface, and it says why every row is there.

    Matching is word overlap between the roles the CV states and the occupation
    the board was asked about, which is deliberately dull. A model deciding that
    a pipefitter is basically a welder would be making a claim about somebody's
    career that nobody asked it to make, and the person would have no way to see
    where it came from. Overlap can be shown: "this is here because your CV says
    welder".
    """
    ranked: list[tuple[int, dict[str, Any]]] = []
    role_words = [(role, _words(role)) for role in roles if role.strip()]

    for listing in listings:
        against = _words(f"{listing.get('matched_occupation') or ''} "
                         f"{listing.get('title') or ''}")
        best_role, best_score = None, 0
        for role, words in role_words:
            shared = len(words & against)
            if shared > best_score:
                best_role, best_score = role, shared
        if best_score:
            row = dict(listing)
            row["matched_because"] = best_role
            row["match_strength"] = best_score
            ranked.append((best_score, row))

    ranked.sort(key=lambda pair: (-pair[0], pair[1].get("title", "")))
    return [row for _score, row in ranked[:limit]]
