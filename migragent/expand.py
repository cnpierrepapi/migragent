"""Growing the registry outward from an entry page.

Fourteen entry points is not a source registry, it is fourteen front doors. The
requirements for one study permit are spread across eligibility, funds,
biometrics, medical exams, fees, processing times, work rights and dependants,
and each of those is a separate page with its own last-updated date.

This module walks out from an entry page and reports what it finds.

HOW IT DECIDES WHAT BELONGS, AND THE APPROACH THAT FAILED FIRST
---------------------------------------------------------------
The tempting approach is to keep links whose text or URL contains words like
"visa", "fees" or "eligibility". That is a heuristic over names, which is the
specific mistake recorded in docs/INHERITED.md. It fails both ways: it misses a
page called "Before you apply" and it happily collects a press release that
happens to mention a visa.

So the first attempt used structure instead: same host, plus either the entry
page's section path or a direct link from the entry page. That failed too, and
measurably. On gov.uk/student-visa the "section" resolves to the whole of
gov.uk, because the path has one segment, and "linked from the entry page"
collected the entire global navigation: benefits, driving, childcare. 55 of 68
links kept, almost none of them requirements. See D10.

WHAT WORKS
----------
Navigation appears on every page of a site. Content does not.

So the chrome is learned by intersecting the links of two or more pages from the
same host, and whatever survives that intersection is what makes this page
different from its neighbours. On gov.uk it takes 68 links down to 26, and what
is left is /student-visa/money, /student-visa/knowledge-of-english,
/student-visa/documents-you-must-provide. On canada.ca it takes 43 down to 10,
leaving eligibility, get-documents, prepare and apply.

That is a fact about how the site is built, not an opinion about what its words
mean, and no model is involved at any point. A model reads a page later to say
what a requirement is. It has no say in which pages get read.
"""
from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field

from .fetcher import Fetched, Fetcher

_SKIP_SUFFIXES = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".jpg", ".jpeg", ".png",
    ".gif", ".svg", ".mp4", ".mp3", ".ics", ".csv", ".rss", ".xml", ".json",
)

# Same page, different rendering or different audience. Structural, not
# vocabulary: these are alternate views of a document we already have.
_ALTERNATE_VIEW = re.compile(r"/(print|printable|text-only|amp)(/|$)", re.I)

# Language subtrees. If the entry page is the English one, the French twin is
# the same document again, and registering both doubles the count without
# adding a single requirement.
_LANG_SEGMENT = re.compile(r"^/(en|fr|es|ar|de|it|pt|zh)(/|$)", re.I)

_HREF = re.compile(rb'<a\b[^>]*?href="([^"#][^"]*)"', re.I)


# A jurisdiction's official web estate is not one hostname. France publishes the
# same procedure across service-public.gouv.fr, france-visas.gouv.fr and
# legifrance.gouv.fr, while the page we seeded sits on the older
# service-public.fr. A strict same-host rule discarded all of that and returned
# nothing at all for France, which is D12.
#
# So the boundary is the jurisdiction's official government domain suffix. That
# is structural: it is a fact about who operates the domain, readable from the
# name itself, and it is not an opinion about the words on the page. Anything
# outside these suffixes is a lead and never a source, per rule 9.
OFFICIAL_SUFFIXES = {
    "UK": (".gov.uk",),
    "US": (".gov",),
    "CA": (".gc.ca", "canada.ca"),
    "AU": (".gov.au",),
    "FR": (".gouv.fr", "service-public.fr"),
    "ES": (".gob.es",),
    "AE": (".gov.ae", "u.ae"),
}


@dataclass(frozen=True)
class Discovered:
    """A page found by walking out from an entry point.

    `lead_url` is the page we were on when we found this. How we found something
    and what we read are different facts, per rule 9, and the trail is what lets
    somebody check we did not wander off.
    """

    url: str
    lead_url: str
    depth: int
    reason: str


# Parameters that identify a visitor or a campaign rather than a page. Keeping
# them would give the same page a different URL on every visit, and a session id
# would give it a different source id on every walk.
_NOISE_PARAMS = {
    "jsessionid", "phpsessid", "sid", "sessionid", "aspxauth", "cfid", "cftoken",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "_ga", "ref", "referrer",
}

# Some servers put the session in the path rather than the query, after a
# semicolon: /infovisto;jsessionid=B3313179C6DA723CECAC57D8EF290FF8
_PATH_SESSION = re.compile(r";(?:jsessionid|phpsessid|sid)=[^/;?]*", re.I)


def _clean_query(query: str) -> str:
    """Drop the parameters that identify a visitor, keep the ones that identify a page.

    The query string used to be discarded outright. That is safe against
    infinite crawl spaces and it made a whole country invisible: Italy's visa
    portal publishes a page per visa type at one path, telling them apart only
    by query parameter, so every visa type collapsed onto the same URL and the
    walk saw one page where there are dozens. See D27.

    The page cap still bounds the walk, so keeping meaningful parameters cannot
    run away.
    """
    if not query:
        return ""
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(query, keep_blank_values=True)
            if k.lower() not in _NOISE_PARAMS]
    return urllib.parse.urlencode(sorted(kept))


def _normalise(base: str, href: str) -> str | None:
    try:
        joined = urllib.parse.urljoin(base, href)
    except ValueError:
        return None
    parts = urllib.parse.urlsplit(joined)
    if parts.scheme not in ("http", "https"):
        return None
    path = _PATH_SESSION.sub("", parts.path)
    path = path.rstrip("/") or "/"
    # Hosts are case insensitive, and one site writing itself differently in two
    # places is enough to break everything downstream. BAMF's base tag says
    # www.BAMF.de while its seed URL says www.bamf.de, which would make the
    # same page look like two sources, put it on a host the same-host check does
    # not recognise, and give it a different source id on every walk. The path
    # is left alone, because paths are case sensitive and changing one would
    # change which page we mean.
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, _clean_query(parts.query), "")
    )


_BASE_TAG = re.compile(rb"<base[^>]+href=[\"']([^\"']+)[\"']", re.I)


def _base_for(page: Fetched) -> str:
    """What relative links on this page are relative to.

    Usually the page's own URL. Not always: a page may carry `<base href>`, and
    then every relative link is relative to that instead, and the page URL is
    the wrong answer.

    Germany's BAMF does exactly this. It serves
    `<base href="https://www.BAMF.de/"/>` and writes its links as
    `EN/Themen/...` with no leading slash. Joined against the page's own deep
    URL, every one of them resolved to a path that does not exist, so the walk
    over both German lanes discovered zero pages and looked like a country with
    no content rather than a bug in us. See D26.
    """
    if page.body is None:
        return page.final_url or page.url
    # Only the head can carry it, and looking further costs nothing but is more
    # likely to catch a <base> written inside body text as an example.
    match = _BASE_TAG.search(page.body[:8000])
    if not match:
        return page.final_url or page.url
    declared = match.group(1).decode("utf-8", "replace").strip()
    # A relative base is itself relative to the page, which is rare and legal.
    return urllib.parse.urljoin(page.final_url or page.url, declared)


def links_on(page: Fetched) -> list[str]:
    """Every link on the page, absolute and de-duplicated, in document order."""
    if not page.ok or page.body is None:
        return []
    base = _base_for(page)
    seen: dict[str, None] = {}
    for raw in _HREF.findall(page.body):
        url = _normalise(base, raw.decode("utf-8", "replace").strip())
        if url and url not in seen:
            seen[url] = None
    return list(seen)


def _language_of(url: str) -> str | None:
    match = _LANG_SEGMENT.match(urllib.parse.urlsplit(url).path)
    return match.group(1).lower() if match else None


@dataclass
class Expander:
    """Walks out from an entry page, politely, and reports what it found.

    Nothing here writes to the registry. It returns candidates and lets the
    caller decide, which keeps discovery separate from the decision to record.
    """

    fetcher: Fetcher
    max_depth: int = 2
    max_pages: int = 80

    # Optional. When present, hosts whose links only exist after scripts run get
    # rendered instead of plainly fetched. See _decide_render.
    browser: object | None = None

    # host -> links that appear on more than one page of that host
    _chrome: dict[str, set[str]] = field(default_factory=dict)
    _seen: set[str] = field(default_factory=set)
    _late_pages: dict[str, Fetched] = field(default_factory=dict)
    _render_host: dict[str, bool] = field(default_factory=dict)

    # A page whose links are written by scripts hands a plain fetcher almost
    # nothing. Spain's ministry site returns 9 links to urllib and 117 to a
    # browser, which is why Spain walked to zero three runs in a row while
    # looking like a site with nothing on it. The floor is deliberately low, so
    # that rendering is the exception and not the default.
    LINK_FLOOR = 25
    RENDER_GAIN = 2.0

    def _decide_render(self, host: str, url: str, plain: Fetched) -> bool:
        """Decide once per host whether its pages have to be rendered.

        Measured rather than assumed, and measured per host rather than per
        page, so a site is not re-tested on every URL. A page that already
        yields plenty of links is never rendered, because rendering costs
        seconds and usually returns the same page.
        """
        if host in self._render_host:
            return self._render_host[host]
        if self.browser is None:
            self._render_host[host] = False
            return False

        plain_links = len(links_on(plain))
        if plain_links >= self.LINK_FLOOR:
            self._render_host[host] = False
            return False

        rendered = self.browser.fetch(url)  # type: ignore[attr-defined]
        gain = len(links_on(rendered))
        needed = gain >= max(self.LINK_FLOOR, plain_links * self.RENDER_GAIN)
        self._render_host[host] = needed
        if needed:
            self._late_pages[url] = rendered
        return needed

    def fetch_page(self, url: str) -> Fetched:
        """Fetch a page the way this host needs to be fetched."""
        host = urllib.parse.urlsplit(url).netloc
        if self._render_host.get(host) and self.browser is not None:
            return self.browser.fetch(url)  # type: ignore[attr-defined]
        plain = self.fetcher.fetch(url)
        if plain.ok and self._decide_render(host, url, plain):
            return self._late_pages.get(url) or self.browser.fetch(url)  # type: ignore[attr-defined]
        return plain

    def learn_chrome(self, sample_urls: list[str]) -> dict[str, int]:
        """Learn each host's navigation from two or more DISTINCT pages.

        A link that appears on more than one page of a site is part of the
        furniture. With only one sample for a host nothing can be learned, and
        the caller is told so rather than being given an empty set that looks
        like a result.

        The sample is de-duplicated first, and this is not a tidiness measure.
        Spain was seeded with the same consular URL for both its lanes, so the
        sample held that page twice, every one of its links appeared "on two
        pages", the whole page was classified as navigation and Spain returned
        zero sources while looking like it had been walked. That is D11.
        """
        by_host: dict[str, list[str]] = {}
        for url in dict.fromkeys(sample_urls):
            by_host.setdefault(urllib.parse.urlsplit(url).netloc, []).append(url)

        learned: dict[str, int] = {}
        for host, urls in by_host.items():
            if len(urls) < 2:
                learned[host] = 0
                continue
            counts: Counter[str] = Counter()
            for url in urls:
                counts.update(set(links_on(self.fetch_page(url))))
            chrome = {link for link, n in counts.items() if n >= 2}
            self._chrome[host] = chrome
            learned[host] = len(chrome)
        return learned

    def _within_scope(
        self, url: str, entry_url: str, jurisdiction: str | None
    ) -> tuple[bool, str]:
        """Is this page inside the estate we are allowed to walk at all?

        Separate from worth_reading because the walk has to know a page is in
        scope before it can learn that page's host well enough to say whether
        the link is navigation.
        """
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc.lower()
        suffixes = OFFICIAL_SUFFIXES.get(jurisdiction or "", ())
        if suffixes:
            if not any(host == s.lstrip(".") or host.endswith(s) for s in suffixes):
                return False, "outside this jurisdiction's official domains"
            return True, "an official domain for this jurisdiction"
        if host != urllib.parse.urlsplit(entry_url).netloc:
            return False, "different host"
        return True, "same host"

    def worth_reading(
        self, url: str, entry_url: str, depth: int, jurisdiction: str | None = None
    ) -> tuple[bool, str]:
        parts = urllib.parse.urlsplit(url)
        entry_parts = urllib.parse.urlsplit(entry_url)
        host = parts.netloc.lower()

        in_scope, why = self._within_scope(url, entry_url, jurisdiction)
        if not in_scope:
            return False, why
        if parts.path.lower().endswith(_SKIP_SUFFIXES):
            return False, "not a web page"
        if _ALTERNATE_VIEW.search(parts.path):
            return False, "another rendering of a page we already have"
        if url.rstrip("/") == entry_url.rstrip("/"):
            return False, "the entry page itself"

        entry_language = _language_of(entry_url)
        if entry_language and _language_of(url) not in (None, entry_language):
            return False, "the same document in another language"

        if url in self._chrome.get(parts.netloc, set()):
            return False, "site navigation, it appears on other pages too"

        if not self._chrome.get(parts.netloc):
            return False, "no navigation learned for this host, so nothing can be told apart"

        return True, f"unique to this page at depth {depth}"

    def _ensure_chrome(self, host: str, candidates: list[str]) -> None:
        """Learn a host's navigation the first time we need to judge one of its pages.

        Opening the walk to a jurisdiction's whole official estate means meeting
        hosts that were never in the seed sample. France reaches
        service-public.gouv.fr from a page on service-public.fr, and with no
        navigation learned for the new host its menus came back looking like
        content: the site root, the sign-in page, the news index.

        So chrome is learned on demand, from two pages of that host, using
        candidates we were going to fetch anyway.
        """
        if host in self._chrome or len(candidates) < 2:
            return

        # Which pages to learn from matters. The first attempt took the first two
        # candidates in document order, which on service-public.gouv.fr were the
        # site root and the sign-in page. Those two share almost no links, so
        # almost nothing was classified as navigation and the menus came back
        # looking like requirements.
        #
        # Deep paths are leaf content and shallow ones are menus. That is a fact
        # about how URLs are built, not about what the words in them mean, so
        # the sample is the deepest candidates available.
        by_depth = sorted(
            candidates,
            key=lambda u: (-urllib.parse.urlsplit(u).path.count("/"), u),
        )
        sample = by_depth[:3]
        if len(sample) < 2:
            return

        counts: Counter[str] = Counter()
        for url in sample:
            page = self.fetch_page(url)
            self._late_pages[url] = page
            counts.update(set(links_on(page)))
        self._chrome[host] = {link for link, n in counts.items() if n >= 2}

    def walk(
        self, entry_url: str, jurisdiction: str | None = None
    ) -> tuple[list[Discovered], dict[str, Fetched]]:
        found: list[Discovered] = []
        pages: dict[str, Fetched] = {}

        entry = self.fetch_page(entry_url)
        pages[entry_url] = entry
        if not entry.ok:
            return found, pages

        # Group the entry page's links by host, so any host we have not sampled
        # can have its navigation learned before we judge its pages.
        by_host: dict[str, list[str]] = {}
        for url in links_on(entry):
            allowed, _ = self._within_scope(url, entry_url, jurisdiction)
            if allowed:
                by_host.setdefault(urllib.parse.urlsplit(url).netloc, []).append(url)
        for host, candidates in by_host.items():
            self._ensure_chrome(host, candidates)

        queue: list[tuple[str, str, int]] = []
        for url in links_on(entry):
            ok, why = self.worth_reading(url, entry_url, depth=1, jurisdiction=jurisdiction)
            if ok and url not in self._seen:
                self._seen.add(url)
                queue.append((url, entry_url, 1))
                found.append(Discovered(url=url, lead_url=entry_url, depth=1, reason=why))

        head = 0
        while head < len(queue) and len(pages) < self.max_pages:
            url, _lead, depth = queue[head]
            head += 1

            page = self.fetch_page(url)
            pages[url] = page
            if not page.ok or depth >= self.max_depth:
                continue

            for candidate in links_on(page):
                if len(pages) + (len(queue) - head) >= self.max_pages:
                    break
                ok, why = self.worth_reading(
                    candidate, entry_url, depth=depth + 1, jurisdiction=jurisdiction
                )
                if ok and candidate not in self._seen:
                    self._seen.add(candidate)
                    queue.append((candidate, url, depth + 1))
                    found.append(
                        Discovered(url=candidate, lead_url=url, depth=depth + 1, reason=why)
                    )

        return found, pages
