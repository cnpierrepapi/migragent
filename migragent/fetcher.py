"""Fetching official pages, politely, and stamping what was actually read.

This is plain code on purpose and there is no model anywhere in this file. It is
the part of the system that produces evidence, so it has to be boring and it has
to be inspectable. A model decides what a requirement means. It never decides
where the requirement came from.

The date on a citation is written here, from the clock, at the moment the bytes
arrived. It is never asked for, never inferred and never passed through a
prompt, which is what makes "read on 18 August 2026" a fact rather than a
plausible sentence.
"""
from __future__ import annotations

import hashlib
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

# The crawler says who it is and how to complain. Rule 10 in docs/RULES.md is
# that robots.txt is a gate, and identifying honestly is the other half of that
# bargain: a site owner who wants us gone must be able to act on it.
USER_AGENT = (
    "MIGRAGENT/0.1 (+https://migragent.onenept.com/crawler; immigration guidance; "
    "contact: crawler@onenept.com)"
)

# One request at a time per host, with a gap. Government sites are not our
# infrastructure and a guide is not worth degrading one.
DEFAULT_DELAY_SECONDS = 2.0
TIMEOUT_SECONDS = 30

# A DNS or connection failure says something about the network between here and
# the host. It does not say anything about the source, and it must never be
# written into the registry as though it did. See D8: a run of transient
# getaddrinfo failures nearly recorded six working government sites as
# unreachable, permanently, on the strength of one attempt each.
#
# So transport level failures are retried with a backoff, and if they still
# fail they get their own outcome that says the cause is unknown rather than
# claiming the source is dead.
TRANSPORT_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0


def _tls_context() -> ssl.SSLContext:
    """Verify certificates against the operating system's trust store.

    Spain's official sites chain to AC RAIZ FNMT-RCM, the Spanish national CA.
    Python's default context rejected them with "self-signed certificate in
    certificate chain", while the same roots verify fine through the OS store.
    That root is present in certifi too, so this is about how the default
    context assembles its chain rather than about a missing CA. See D9.

    The fix is to trust the right roots, never to stop checking. This code
    fetches pages for a product that holds people's passports, and an
    unverified TLS connection to a government site is not a shortcut worth
    having. If `truststore` is unavailable we keep full verification with the
    stock context and let Spain fail loudly rather than silently downgrading.
    """
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


TLS = _tls_context()

Outcome = Literal["fetched", "blocked_by_robots", "refused", "unreachable", "network_unknown", "not_html"]

# Hashing the raw bytes does not work, and this was measured rather than
# assumed. Two fetches of the same canada.ca study permit page, seconds apart,
# produce different sha256 digests. The diff is one line: an Akamai mPulse
# beacon script carrying a per request nonce.
#
# If the hash never matches, rule 14 never fires, every daily round calls the
# model on every page, and the cost model of the watcher collapses. So the
# digest is taken over the page with the volatile parts removed. See D6.
#
# This stays plain code. It is a text substitution, not an understanding of the
# page, and it deliberately does not try to identify "the main content", because
# a heuristic that guesses which part of a page matters is exactly the mistake
# recorded in docs/INHERITED.md.
_SCRIPT = re.compile(rb"<script\b[^>]*>.*?</script\s*>", re.I | re.S)
_STYLE = re.compile(rb"<style\b[^>]*>.*?</style\s*>", re.I | re.S)
_COMMENT = re.compile(rb"<!--.*?-->", re.S)
_NONCE_ATTR = re.compile(rb'\s(?:nonce|data-nonce|csrf[-_]token)="[^"]*"', re.I)
_WHITESPACE = re.compile(rb"\s+")


def stable_digest(body: bytes) -> str:
    """A digest that survives per request noise but not a real edit.

    Scripts, styles, comments and nonce attributes come out, then whitespace is
    collapsed. What is left is the markup and the words, which is what a change
    to a requirement actually touches.
    """
    cleaned = _SCRIPT.sub(b"", body)
    cleaned = _STYLE.sub(b"", cleaned)
    cleaned = _COMMENT.sub(b"", cleaned)
    cleaned = _NONCE_ATTR.sub(b"", cleaned)
    cleaned = _WHITESPACE.sub(b" ", cleaned).strip()
    return hashlib.sha256(cleaned).hexdigest()


@dataclass(frozen=True)
class Fetched:
    """What came back, and everything a citation needs.

    `read_at` is the moment the bytes arrived, taken from the clock here. It is
    the field the whole product's honesty rests on.

    `sha256` is the stable digest and is what change detection compares.
    `raw_sha256` is the digest of the exact bytes stored in the snapshot, so the
    stored file can still be proved untampered.
    """

    url: str
    outcome: Outcome
    read_at: str
    status: int | None = None
    body: bytes | None = None
    sha256: str | None = None
    raw_sha256: str | None = None
    content_type: str | None = None
    final_url: str | None = None
    reason: str | None = None
    attempts: int = 1

    @property
    def ok(self) -> bool:
        return self.outcome == "fetched"

    def unchanged_from(self, previous_sha256: str | None) -> bool:
        """Hash first, per rule 14.

        A byte-identical page stops the round right here: no diff, no model
        call, no cost. Most government pages do not change most days, so this is
        the difference between a fetch bill and an inference bill.
        """
        return bool(self.sha256 and previous_sha256 and self.sha256 == previous_sha256)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Fetcher:
    """Fetches pages, respecting robots.txt and pacing itself per host."""

    user_agent: str = USER_AGENT
    delay_seconds: float = DEFAULT_DELAY_SECONDS
    timeout: int = TIMEOUT_SECONDS

    _robots: dict[str, tuple[urllib.robotparser.RobotFileParser | None, str, bool]] = \
        field(default_factory=dict)
    _last_hit: dict[str, float] = field(default_factory=dict)

    # -- politeness ------------------------------------------------------

    def _robots_for(self, url: str) -> tuple[urllib.robotparser.RobotFileParser | None, str, bool]:
        """Fetch and cache robots.txt for the host, under our own name.

        Returns the parser, the reason in words, and whether anything may be
        fetched when there is no parser.

        THE PART THAT WAS WRONG. This used `RobotFileParser.read()`, which
        fetches robots.txt as `Python-urllib`, and which turns a 401 or 403 on
        that fetch into "disallow everything" without telling anybody. Spain's
        immigration portal serves 403 to `Python-urllib` and 404 to a client
        that says who it is. A 404 means there is no robots.txt, which is
        permission, so the whole portal was recorded as refusing us when it had
        simply refused a user agent we do not use. That is D24.

        So robots.txt is fetched the same way every other page is fetched, by a
        client that identifies itself, and the three outcomes are kept apart:

          200  the host stated its rules, and they are obeyed
          404  there are no rules, which is permission
          401, 403, 5xx, or no answer
               the host would not tell us its rules. We do not crawl it, and
               the reason recorded says it was refused rather than disallowed,
               because those are different facts about the world.
        """
        parts = urllib.parse.urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host in self._robots:
            return self._robots[host]

        request = urllib.request.Request(
            f"{host}/robots.txt", headers={"User-Agent": self.user_agent},
        )
        # Retried, because pages are. Without this the gate was strictly less
        # forgiving than the thing it guards: bamf.de drops a robots.txt request
        # every so often, and one dropped request was enough to skip the whole
        # of Germany for a run, while the page fetcher next to it would have
        # tried three times for the same page.
        #
        # An HTTP answer is an answer and is never retried. Only silence is.
        state: tuple[urllib.robotparser.RobotFileParser | None, str, bool] | None = None
        last_error: Exception | None = None

        for attempt in range(1, TRANSPORT_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout,
                                            context=TLS) as response:
                    body = response.read().decode("utf-8", "ignore")
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(f"{host}/robots.txt")
                parser.parse(body.splitlines())
                state = (parser, "the host stated its rules", True)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 410):
                    state = (None, f"no robots.txt on this host (HTTP {exc.code}), "
                                   "which is permission", True)
                else:
                    state = (None, f"the host would not serve its robots.txt "
                                   f"(HTTP {exc.code}), so we do not crawl it", False)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < TRANSPORT_ATTEMPTS:
                    time.sleep(BACKOFF_SECONDS * attempt)

        if state is None:
            state = (None, f"robots.txt could not be reached after "
                           f"{TRANSPORT_ATTEMPTS} attempts "
                           f"({type(last_error).__name__}), so we do not crawl it",
                     False)

        self._robots[host] = state
        return state

    def permission(self, url: str) -> tuple[str, str]:
        """Three states, kept apart, because two of them are not the same fact.

          allowed     robots.txt was read and permits this, or there is none
          disallowed  robots.txt was read and forbids this. A fact about the
                      source, and it is written into the registry as one.
          unknown     we could not read robots.txt at all. A fact about a
                      moment, not about the source.

        THE DISTINCTION IS NOT PEDANTRY. Collapsing unknown into disallowed
        marked twelve Spanish pages as refusing us, an hour after they had been
        read successfully, because one robots.txt fetch went wrong once. Two
        German pages went the same way on a network blip that had cleared by the
        time anybody looked.

        That is D8 exactly: a transient failure written down as a permanent
        property of a source, so a working government site is recorded as dead
        and nothing ever tries it again. D8 was about page fetches. This is the
        same mistake one layer up, in the gate, introduced by the code that
        fixed D24.

        A caller that gets unknown does not crawl, and records the source as
        unverified and retryable rather than blocked.
        """
        parser, why, permissive_without_parser = self._robots_for(url)
        if parser is None:
            return ("allowed" if permissive_without_parser else "unknown"), why
        if parser.can_fetch(self.user_agent, url):
            return "allowed", "allowed by robots.txt"
        return "disallowed", "disallowed by robots.txt"

    def allowed(self, url: str) -> tuple[bool, str]:
        """May we fetch this? Checked before every request, never skipped."""
        state, why = self.permission(url)
        return state == "allowed", why

    def _wait_turn(self, url: str) -> None:
        """One request per host at a time, with a gap, honouring crawl-delay."""
        host = urllib.parse.urlsplit(url).netloc
        delay = self.delay_seconds
        cached = self._robots.get(f"{urllib.parse.urlsplit(url).scheme}://{host}")
        parser = cached[0] if cached else None
        if parser is not None:
            try:
                declared = parser.crawl_delay(self.user_agent)
                if declared:
                    delay = max(delay, float(declared))
            except Exception:  # noqa: BLE001
                pass

        last = self._last_hit.get(host)
        if last is not None:
            waited = time.monotonic() - last
            if waited < delay:
                time.sleep(delay - waited)
        self._last_hit[host] = time.monotonic()

    # -- fetching --------------------------------------------------------

    def fetch(self, url: str) -> Fetched:
        state, why = self.permission(url)
        if state == "disallowed":
            # Rule 10. No fetching anyway, no swapping the user agent. The row
            # records the refusal so the source does not silently vanish.
            return Fetched(url=url, outcome="blocked_by_robots", read_at=_now(), reason=why)
        if state == "unknown":
            # We could not read the rules, so we do not crawl, and we do not
            # write that down as the source refusing us. It is retryable and it
            # says why. D8, and D25 for how it came back.
            return Fetched(url=url, outcome="network_unknown", read_at=_now(), reason=why)

        self._wait_turn(url)

        request = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en,fr;q=0.8,es;q=0.8,ar;q=0.8",
        })

        last_error: Exception | None = None
        for attempt in range(1, TRANSPORT_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout,
                                            context=TLS) as response:
                    body = response.read()
                    read_at = _now()
                    content_type = response.headers.get("Content-Type", "")
                    final_url = response.geturl()
                    status = response.status
                break
            except urllib.error.HTTPError as exc:
                # The server answered. That is information about the source, so
                # it is final and there is nothing to retry.
                outcome = "refused" if exc.code in (401, 403, 429) else "unreachable"
                return Fetched(url=url, outcome=outcome, read_at=_now(), status=exc.code,
                               reason=f"HTTP {exc.code}", attempts=attempt)
            except Exception as exc:  # noqa: BLE001
                # Nothing answered. Could be the host, could be us. Try again.
                last_error = exc
                if attempt < TRANSPORT_ATTEMPTS:
                    time.sleep(BACKOFF_SECONDS * attempt)
        else:
            return Fetched(
                url=url,
                outcome="network_unknown",
                read_at=_now(),
                reason=(f"{type(last_error).__name__}: {last_error} "
                        f"(after {TRANSPORT_ATTEMPTS} attempts; this may be our network "
                        f"rather than the source, so it is not recorded as a property "
                        f"of the source)"),
                attempts=TRANSPORT_ATTEMPTS,
            )

        if "html" not in content_type.lower() and "xml" not in content_type.lower():
            return Fetched(url=url, outcome="not_html", read_at=read_at, status=status,
                           content_type=content_type, final_url=final_url,
                           reason=f"content type was {content_type or 'absent'}")

        return Fetched(
            url=url,
            outcome="fetched",
            read_at=read_at,
            status=status,
            body=body,
            sha256=stable_digest(body),
            raw_sha256=hashlib.sha256(body).hexdigest(),
            content_type=content_type,
            final_url=final_url,
        )
