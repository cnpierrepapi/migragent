"""A real browser, for pages that a plain HTTP client cannot read.

WHEN THIS IS ALLOWED, AND WHEN IT IS NOT
----------------------------------------
This exists for one situation: **robots.txt says yes and the transport says no.**

Australia is the case. `immi.homeaffairs.gov.au` publishes a robots.txt that
allows the visa pages, and then returns HTTP 403 to a polite, identified
urllib request. The site's own machine-readable statement of crawl policy
permits us; something in front of it refuses anything that does not look like a
browser. Rendering the page in an actual browser is not getting around their
policy, it is meeting their transport.

**It is never used to get around robots.txt.** The United States pages are
disallowed by robots.txt at travel.state.gov, uscis.gov and
studyinthestates.dhs.gov. A browser does not change that answer, and using one
there would be exactly the "no fetching anyway, no changing the user agent to
get around it" that rule 10 rules out. Those lanes stay blocked until a
different official source permits us, or they go through the portal fallback in
docs/SOURCES.md. This module refuses to run on a disallowed URL rather than
leaving that to the caller's good intentions.

**The browser identifies itself as MIGRAGENT.** It does not pretend to be a
person browsing. If a site refuses our honest user agent in a real browser,
that is a clear answer and we stop, and the source is recorded as refused.
Passing ourselves off as somebody else to collect a page would undermine the
one thing this product is selling.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from .fetcher import Fetched, Fetcher, USER_AGENT, stable_digest
from .clock import now_iso as _now

RENDER_TIMEOUT_MS = 45_000

# Long enough for a page that assembles itself after load, short enough that a
# lane is not held up by one slow site.
SETTLE_MS = 2_500



@dataclass
class BrowserFetcher:
    """Fetches a page by rendering it, for sites that refuse a plain client.

    Holds one browser for the life of the object, because launching Chromium per
    page is slow enough to change how wide a walk can be.
    """

    fetcher: Fetcher
    user_agent: str = USER_AGENT
    timeout_ms: int = RENDER_TIMEOUT_MS

    _playwright = None
    _browser = None

    def __enter__(self) -> "BrowserFetcher":
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def fetch(self, url: str) -> Fetched:
        # The gate comes first and it is not optional. A browser is a way past a
        # WAF, never a way past a stated policy.
        allowed, why = self.fetcher.allowed(url)
        if not allowed:
            return Fetched(
                url=url,
                outcome="blocked_by_robots",
                read_at=_now(),
                reason=(f"{why}. A browser does not change this answer and is not "
                        f"used to get around it."),
            )

        if self._browser is None:
            raise RuntimeError("BrowserFetcher must be used as a context manager")

        context = self._browser.new_context(user_agent=self.user_agent)
        page = context.new_page()
        try:
            response = page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(SETTLE_MS)
            html = page.content()
            read_at = _now()
            status = response.status if response else None
            final_url = page.url
        except Exception as exc:  # noqa: BLE001
            context.close()
            return Fetched(url=url, outcome="network_unknown", read_at=_now(),
                           reason=f"{type(exc).__name__}: {exc}")
        finally:
            if not page.is_closed():
                page.close()
            context.close()

        if status is not None and status >= 400:
            # An honest user agent in a real browser was still refused. That is a
            # clear answer, and we take it.
            outcome = "refused" if status in (401, 403, 429) else "unreachable"
            return Fetched(url=url, outcome=outcome, read_at=read_at, status=status,
                           reason=f"HTTP {status} to an identified browser")

        body = html.encode("utf-8")
        return Fetched(
            url=url,
            outcome="fetched",
            read_at=read_at,
            status=status,
            body=body,
            sha256=stable_digest(body),
            raw_sha256=hashlib.sha256(body).hexdigest(),
            content_type="text/html; charset=utf-8",
            final_url=final_url,
        )
