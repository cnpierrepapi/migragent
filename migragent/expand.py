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


def _normalise(base: str, href: str) -> str | None:
    try:
        joined = urllib.parse.urljoin(base, href)
    except ValueError:
        return None
    parts = urllib.parse.urlsplit(joined)
    if parts.scheme not in ("http", "https"):
        return None
    path = parts.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def links_on(page: Fetched) -> list[str]:
    """Every link on the page, absolute and de-duplicated, in document order."""
    if not page.ok or page.body is None:
        return []
    base = page.final_url or page.url
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

    # host -> links that appear on more than one page of that host
    _chrome: dict[str, set[str]] = field(default_factory=dict)
    _seen: set[str] = field(default_factory=set)

    def learn_chrome(self, sample_urls: list[str]) -> dict[str, int]:
        """Learn each host's navigation from two or more of its pages.

        A link that appears on more than one page of a site is part of the
        furniture. With only one sample for a host nothing can be learned, and
        the caller is told so rather than being given an empty set that looks
        like a result.
        """
        by_host: dict[str, list[str]] = {}
        for url in sample_urls:
            by_host.setdefault(urllib.parse.urlsplit(url).netloc, []).append(url)

        learned: dict[str, int] = {}
        for host, urls in by_host.items():
            if len(urls) < 2:
                learned[host] = 0
                continue
            counts: Counter[str] = Counter()
            for url in urls:
                counts.update(set(links_on(self.fetcher.fetch(url))))
            chrome = {link for link, n in counts.items() if n >= 2}
            self._chrome[host] = chrome
            learned[host] = len(chrome)
        return learned

    def worth_reading(self, url: str, entry_url: str, depth: int) -> tuple[bool, str]:
        parts = urllib.parse.urlsplit(url)
        entry_parts = urllib.parse.urlsplit(entry_url)

        if parts.netloc != entry_parts.netloc:
            return False, "different host"
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

    def walk(self, entry_url: str) -> tuple[list[Discovered], dict[str, Fetched]]:
        found: list[Discovered] = []
        pages: dict[str, Fetched] = {}

        entry = self.fetcher.fetch(entry_url)
        pages[entry_url] = entry
        if not entry.ok:
            return found, pages

        queue: list[tuple[str, str, int]] = []
        for url in links_on(entry):
            ok, why = self.worth_reading(url, entry_url, depth=1)
            if ok and url not in self._seen:
                self._seen.add(url)
                queue.append((url, entry_url, 1))
                found.append(Discovered(url=url, lead_url=entry_url, depth=1, reason=why))

        head = 0
        while head < len(queue) and len(pages) < self.max_pages:
            url, _lead, depth = queue[head]
            head += 1

            page = self.fetcher.fetch(url)
            pages[url] = page
            if not page.ok or depth >= self.max_depth:
                continue

            for candidate in links_on(page):
                if len(pages) + (len(queue) - head) >= self.max_pages:
                    break
                ok, why = self.worth_reading(candidate, entry_url, depth=depth + 1)
                if ok and candidate not in self._seen:
                    self._seen.add(candidate)
                    queue.append((candidate, url, depth + 1))
                    found.append(
                        Discovered(url=candidate, lead_url=url, depth=depth + 1, reason=why)
                    )

        return found, pages
