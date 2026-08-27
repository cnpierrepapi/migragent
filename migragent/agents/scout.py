"""The Scout: which page is a lane's real entry, and which is a shell.

THE FAILURE THIS CLOSES
----------------------
Spain sat in the pipeline for days producing one citable requirement, because
both seeded entries were navigation. The consular index and a ministry homepage
are pages of links, not pages of requirements, and nothing noticed: the round
read them, extracted almost nothing, and reported almost nothing, which is what
a genuinely thin lane also looks like. Someone eventually read the pages by hand
and found the real content two hops away at a different host.

Seeding is done by hand in `tools/seed_registry.py`. A wrong entry there does
not announce itself. The Scout is the judgment that a hand-maintained list
cannot carry: given a lane and one or more candidate URLs, read them, and say
which ones actually carry what an applicant must do, have, pay or prove, and
where the real content is when a candidate turns out to be a shell.

WHAT IT DECIDES, AND WHAT IT CANNOT DO
------------------------------------
It proposes entry pages. It does not write to the registry: it returns
nominations and the round or a seeding tool decides what becomes of them, the
same shape as the researcher.

Every nomination carries a sentence from the page showing the page states a
requirement rather than just linking to one, checked against the page the same
way a requirement's quote is checked. It fetches only through a tool that asks
robots.txt first. Neither of those is in the prompt as a request.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..expand import links_on
from ..extract import MAX_CHARS, _normalise, page_text
from .base import Outcome, build_llm, function_tools, run_to_completion

MAX_PAGES = 10
MAX_LINKS_SHOWN = 80


def enabled() -> bool:
    return os.environ.get("MIGRAGENT_AGENT_SCOUT", "").strip().lower() in {
        "1", "true", "on", "yes"}


@dataclass
class Nomination:
    """One page the Scout says is a real entry for the lane."""

    url: str
    reason: str
    quote: str


@dataclass
class ScoutReport:
    """What one scouting session decided."""

    jurisdiction: str
    lane: str
    nominations: list[Nomination] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    refused: list[dict[str, str]] = field(default_factory=list)
    pages_read: list[str] = field(default_factory=list)
    pages_refused: list[dict[str, str]] = field(default_factory=list)
    turns: int = 0
    stopped_because: str = ""
    error: str = ""

    @property
    def answered(self) -> bool:
        return not self.error and bool(self.stopped_because)


INSTRUCTION = """You are finding the page on an official government website where the {lane} route for {place} really begins: the page that states what an applicant must do, have, pay or prove, not a page of links to other pages.

Start from the candidate pages you are given. Read each one. A candidate is a real entry page if the page itself states requirements. A candidate is a shell if it is mostly navigation, a news list, or a landing page that only points elsewhere; when a candidate is a shell, follow its links to find the page that carries the actual content, and propose that instead.

For every page that is a real entry, call propose_entry with the page's address, one line saying why it is the entry, and a sentence copied from the page, character for character, that states a requirement. The sentence is checked against the page. Anything not on the page word for word is refused and told back to you.

For a candidate that is a shell with nothing usable behind it, or a dead or wrong page, call reject with its address and one line saying what it was.

You may read up to {max_pages} pages. Use what you remember about this country only to decide which links look promising, never as evidence: a page has to state a requirement for you to propose it.

When you have proposed the real entry pages and rejected the shells, call finish and say in one line what you found."""


class ScoutDesk:
    """The only surface the Scout can reach. Robots gate and quote check live here."""

    def __init__(self, *, fetcher, jurisdiction: str, lane: str) -> None:
        self._fetcher = fetcher
        self.report = ScoutReport(jurisdiction=jurisdiction, lane=lane)
        self._text: dict[str, str] = {}
        self._haystack: dict[str, str] = {}
        self._pages: dict[str, object] = {}

    def read_page(self, url: str) -> str:
        """Fetch one page from the government website and return its text.

        Args:
            url: the full address of the page to read.
        """
        if url in self._text:
            return self._text[url][:MAX_CHARS]
        if len(self.report.pages_read) >= MAX_PAGES:
            return ("You have used your page budget. Propose the real entries you have "
                    "found and call finish.")

        state, why = self._fetcher.permission(url)
        if state != "allowed":
            self.report.pages_refused.append({"url": url, "why": why})
            return (f"That page was not read: {why}. Do not propose it. Try another.")

        page = self._fetcher.fetch(url)
        if not page.ok:
            self.report.pages_refused.append(
                {"url": url, "why": f"{page.outcome}: {page.reason or page.status}"})
            return f"That page could not be fetched: {page.outcome}. Try another."

        text = page_text(page)
        final = page.final_url or url
        for key in {url, final}:
            self._pages[key] = page
            self._text[key] = text
            self._haystack[key] = _normalise(text)
        self.report.pages_read.append(final)
        return text[:MAX_CHARS] or "That page came back with no readable text."

    def links_from(self, url: str) -> list[str]:
        """List the pages a page you have already read links to.

        Args:
            url: a page you have already read.
        """
        page = self._pages.get(url)
        if page is None:
            return [f"You have not read {url} yet. Call read_page first."]
        return links_on(page)[:MAX_LINKS_SHOWN]

    def propose_entry(self, url: str, reason: str, quote: str) -> str:
        """Nominate a page as a real entry for this lane.

        Args:
            url: the page's address. You must have read it.
            reason: one line on why this is the entry page.
            quote: a sentence copied from the page that states a requirement.
        """
        url, reason, quote = url.strip(), reason.strip(), quote.strip()
        haystack = self._haystack.get(url)
        if haystack is None:
            self.report.refused.append(
                {"url": url, "quote": quote, "why": "that page was not read in this session"})
            return f"Refused. You have not read {url} in this session. Read it first."
        if not quote or _normalise(quote) not in haystack:
            self.report.refused.append(
                {"url": url, "quote": quote, "why": "the quote is not on the page"})
            return ("Refused. That sentence is not on the page word for word. Copy one "
                    "that states a requirement, or do not propose this page.")
        self.report.nominations.append(Nomination(url=url, reason=reason or "", quote=quote))
        return "Proposed."

    def reject(self, url: str, why: str) -> str:
        """Record that a candidate is a shell, or dead, or the wrong page.

        Args:
            url: the candidate's address.
            why: one line on what it was.
        """
        self.report.rejected.append({"url": url.strip(), "why": why.strip()})
        return "Noted."

    def finish(self, why: str) -> str:
        """Stop, once the real entries are proposed and the shells rejected.

        Args:
            why: one line on what was found.
        """
        self.report.stopped_because = why.strip() or "the scout said it was done"
        return "Finished."


class Scout:
    """Runs one scouting session with ADK and returns the nominations."""

    def __init__(self, *, project: str, model: str, location: str, credentials,
                 fetcher) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials
        self._fetcher = fetcher

    def _agent(self, desk: ScoutDesk, place: str, lane: str):
        from google.adk.agents import LlmAgent

        return LlmAgent(
            name="scout",
            description="Finds the page where a lane's requirements really begin.",
            model=build_llm(project=self._project, model=self._model,
                            location=self._location, credentials=self._credentials),
            instruction=INSTRUCTION.format(lane=lane, place=place, max_pages=MAX_PAGES),
            tools=function_tools([desk.read_page, desk.links_from, desk.propose_entry,
                                  desk.reject, desk.finish]),
        )

    def scout(self, *, jurisdiction: str, lane: str, place: str,
              candidates: list[str]) -> ScoutReport:
        if not candidates:
            report = ScoutReport(jurisdiction=jurisdiction, lane=lane)
            report.error = "no candidate pages were given to scout from"
            return report

        desk = ScoutDesk(fetcher=self._fetcher, jurisdiction=jurisdiction, lane=lane)
        listed = "\n".join(f"  {u}" for u in candidates)
        outcome: Outcome = run_to_completion(
            agent=self._agent(desk, place, lane),
            message=(f"Candidate pages for the {lane} route for {place}:\n{listed}\n\n"
                     "Read them, propose the real entry pages with a sentence from each, "
                     "reject the shells, then finish."),
            stop_when=lambda: bool(desk.report.stopped_because),
            user_id="ingestion",
        )
        desk.report.turns = outcome.turns
        desk.report.error = outcome.error
        if not desk.report.stopped_because:
            desk.report.stopped_because = outcome.stopped_because
        return desk.report
