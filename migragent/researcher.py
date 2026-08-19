"""The researcher, as an agent that decides what to read.

WHAT THE AGENT ACTUALLY DECIDES
-------------------------------
Until now a lane was read by a walker: follow every link the government publishes
down to depth one, then run the same extraction prompt over every page that came
back. It works, and it is indiscriminate. Most of a lane's budget goes on pages
that are linked from the same index as the pages that matter and say nothing an
applicant needs.

The agent's job is that choice. It starts at one page, reads it, sees what that
page links to, and decides which of those are worth opening for the question it
was asked, and when it has enough. That is judgment, it is the part a rule cannot
express, and it is the only part handed over.

WHAT THE AGENT CANNOT DO, BY CONSTRUCTION
-----------------------------------------
Everything the agent can touch, it touches through a tool, and every rule this
product has lives inside those tools rather than in the instruction:

  - `read_page` asks robots.txt first and returns a refusal if the answer is no.
    The agent cannot fetch anything, so it cannot fetch something it should not.
  - `record_requirement` checks the quote against the text of the page that was
    actually fetched, in this session, and refuses anything that is not there
    word for word. The refusals are counted and returned.
  - Nothing here writes to Firestore or to the snapshot archive. A session
    returns what it found and the caller decides what becomes of it, so a
    confused agent produces a bad return value rather than a bad corpus.

A rule an agent can decide to skip is not a rule, so none of the above is in the
prompt as a request. The prompt describes the job. The tools enforce the law.

THE BUDGET IS ALSO NOT A REQUEST
--------------------------------
Pages read and turns taken are capped in code. The instruction mentions the cap
so the agent can plan around it, but the cap holds whether or not it does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .expand import links_on
from .extract import MAX_CHARS, Requirement, _normalise, page_text
from .fetcher import Fetched

# How much of a page the agent is shown at once. Same budget the one shot
# extractor gets, so a comparison between them is about judgment rather than
# about one of them having seen more of the page.
PAGE_CHARS = MAX_CHARS

MAX_PAGES = 8
MAX_TURNS = 40
MAX_LINKS_SHOWN = 60


@dataclass
class Session:
    """What one research session did, including what it was refused."""

    entry_url: str
    jurisdiction: str
    lane: str
    requirements: list[Requirement] = field(default_factory=list)
    refused: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    pages_read: list[str] = field(default_factory=list)
    pages_refused: list[dict[str, str]] = field(default_factory=list)
    turns: int = 0
    stopped_because: str = ""
    error: str = ""

    @property
    def kept(self) -> int:
        return len(self.requirements)


INSTRUCTION = """You are researching one official government website to find what an applicant must do to get a {lane} visa or permit for {place}.

You start at this page: {entry_url}

Read it. Look at what it links to. Open the pages that would tell an applicant something they must do, have, pay or prove, and ignore the ones that would not. You may read up to {max_pages} pages in total, so spend them on the pages a person applying would actually need.

For every requirement a page states, call record_requirement with a quote copied character for character from that page. The quote is checked against the page before the requirement is accepted, and anything that is not on the page word for word is refused and told back to you. Do not try to reword a refused quote into something that passes; find the sentence that actually says it, or leave it out.

Only record what a page itself states. You have read many immigration pages before. What you remember is not evidence and does not belong in this corpus.

Write each requirement in plain words, one sentence, addressed to the applicant, in the same language as the page.

If a page refers to something an applicant would need to know but does not state it, call note_open_question.

When you have read what matters and recorded what those pages state, call finish and say in one line why you stopped. Finishing early with the right pages read is better than spending the budget."""


class Desk:
    """The only surface the agent can reach, and the place the rules live."""

    def __init__(self, *, fetcher, jurisdiction: str, lane: str, language: str,
                 provenance: str, on_event: Callable[[str], None] | None = None) -> None:
        self._fetcher = fetcher
        self._jurisdiction = jurisdiction
        self._lane = lane
        self._language = language
        self._provenance = provenance
        self._on_event = on_event or (lambda _line: None)

        self.pages: dict[str, Fetched] = {}
        self.texts: dict[str, str] = {}
        self.haystacks: dict[str, str] = {}
        self.session = Session(entry_url="", jurisdiction=jurisdiction, lane=lane)

    # ------------------------------------------------------------------ tools

    def read_page(self, url: str) -> str:
        """Fetch one page from the government website and return its text.

        Args:
            url: the full address of the page to read.
        """
        if url in self.texts:
            return self.texts[url][:PAGE_CHARS]

        if len(self.session.pages_read) >= MAX_PAGES:
            return ("You have used your page budget. Record what the pages you have "
                    "already read state, then call finish.")

        state, why = self._fetcher.permission(url)
        if state != "allowed":
            # Not a thing the agent can argue with, and not a thing it can route
            # around: this is the only way it has of fetching anything.
            self.session.pages_refused.append({"url": url, "why": why})
            self._on_event(f"      refused  {url[-58:]}  {why[:60]}")
            return (f"That page was not read and its text is not available: {why}. "
                    "Do not record anything from it. Choose a different page.")

        page = self._fetcher.fetch(url)
        if not page.ok:
            self.session.pages_refused.append(
                {"url": url, "why": f"{page.outcome}: {page.reason or page.status}"})
            return (f"That page could not be fetched: {page.outcome}. "
                    "Choose a different page.")

        text = page_text(page)
        final = page.final_url or url
        for key in {url, final}:
            self.pages[key] = page
            self.texts[key] = text
            self.haystacks[key] = _normalise(text)
        self.session.pages_read.append(final)
        self._on_event(f"      read     {final[-58:]}  {len(text)} chars")

        if not text:
            return "That page came back with no readable text. Choose a different page."
        return text[:PAGE_CHARS]

    def links_from(self, url: str) -> list[str]:
        """List the pages that a page you have already read links to.

        Args:
            url: a page you have already read.
        """
        page = self.pages.get(url)
        if page is None:
            return [f"You have not read {url} yet. Call read_page first."]
        return links_on(page)[:MAX_LINKS_SHOWN]

    def record_requirement(self, text: str, quote: str, source_url: str,
                           category: str = "requirement", cost: str = "",
                           duration: str = "", depends_on: str = "") -> str:
        """Record one thing the applicant must do, have, pay or prove.

        Args:
            text: the requirement in plain words, one sentence, addressed to the applicant.
            quote: a span copied character for character from the page that states it.
            source_url: the page the quote came from.
            category: one of requirement, cost, timing, eligibility, document.
            cost: the amount if the page states one, otherwise empty.
            duration: how long it takes if the page states one, otherwise empty.
            depends_on: what must happen first if the page says so, otherwise empty.
        """
        text, quote = text.strip(), quote.strip()

        haystack = self.haystacks.get(source_url)
        if haystack is None:
            # It named a page it never opened. That is either a URL it
            # remembered or one it inferred, and neither has been fetched, so
            # there is nothing to check the quote against.
            self.session.refused.append(
                {"text": text, "quote": quote,
                 "why": "that page was not read in this session"})
            return (f"Refused. You have not read {source_url} in this session, so there "
                    "is nothing to check the quote against. Read it first, or record "
                    "this from a page you have read.")

        if not text or not quote:
            self.session.refused.append({"text": text, "quote": quote,
                                         "why": "no quote given"})
            return "Refused. A requirement needs both a plain sentence and a quote."

        if _normalise(quote) not in haystack:
            self.session.refused.append(
                {"text": text, "quote": quote, "why": "the quote is not on the page"})
            self._on_event(f"      refused a quote: {quote[:60]}")
            return ("Refused. That quote does not appear on that page word for word. "
                    "Find the sentence that actually states this and copy it exactly, "
                    "or leave the requirement out.")

        page = self.pages[source_url]
        self.session.requirements.append(Requirement(
            text=text,
            quote=quote,
            category=category or "requirement",
            cost=cost or None,
            duration=duration or None,
            depends_on=depends_on or None,
            # Assembled here from the fetch, exactly as the one shot extractor
            # does it. The agent named which page, and that name was checked
            # against pages actually fetched; it did not supply the citation.
            source_url=page.final_url or source_url,
            read_at=page.read_at,
            source_language=self._language,
            provenance=self._provenance,
            jurisdiction=self._jurisdiction,
            lane=self._lane,
        ))
        return "Recorded."

    def note_open_question(self, question: str) -> str:
        """Note something a page refers to but does not state.

        Args:
            question: what a reader would still need to know.
        """
        question = question.strip()
        if question:
            self.session.open_questions.append(question)
        return "Noted."

    def finish(self, why: str) -> str:
        """Stop researching, when the pages that matter have been read.

        Args:
            why: one line saying why this is enough.
        """
        self.session.stopped_because = why.strip() or "the agent said it was done"
        return "Finished."


class Researcher:
    """Runs one research session with ADK, and returns what it found.

    The agent is built fresh per session, because its tools are bound to one
    desk and a desk holds the pages fetched in that session. Sharing a desk
    between lanes would let a quote from a Canadian page satisfy a check on a
    British one.
    """

    def __init__(self, *, project: str, model: str, location: str, credentials,
                 fetcher, on_event: Callable[[str], None] | None = None) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials
        self._fetcher = fetcher
        self._on_event = on_event or (lambda _line: None)

    def _agent(self, desk: Desk, entry_url: str, place: str, lane: str):
        from google.adk.agents import LlmAgent
        from google.adk.tools import FunctionTool

        from .agent_llm import MigragentLlm

        return LlmAgent(
            name="researcher",
            description="Reads official government pages and records what they require.",
            model=MigragentLlm(model=self._model, project=self._project,
                               location=self._location, credentials=self._credentials),
            instruction=INSTRUCTION.format(lane=lane, place=place, entry_url=entry_url,
                                           max_pages=MAX_PAGES),
            tools=[FunctionTool(desk.read_page), FunctionTool(desk.links_from),
                   FunctionTool(desk.record_requirement),
                   FunctionTool(desk.note_open_question), FunctionTool(desk.finish)],
        )

    def research(self, entry_url: str, *, jurisdiction: str, lane: str, place: str,
                 language: str = "en", provenance: str = "official") -> Session:
        import asyncio

        desk = Desk(fetcher=self._fetcher, jurisdiction=jurisdiction, lane=lane,
                    language=language, provenance=provenance, on_event=self._on_event)
        desk.session.entry_url = entry_url
        try:
            asyncio.run(self._run(desk, entry_url, place, lane))
        except Exception as exc:  # noqa: BLE001
            # A session that falls over keeps what it had already recorded and
            # says why it stopped. Requirements already accepted passed the quote
            # check when they were accepted; a later failure does not unmake that.
            desk.session.error = f"{type(exc).__name__}: {exc}"[:300]
        return desk.session

    async def _run(self, desk: Desk, entry_url: str, place: str, lane: str) -> None:
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        agent = self._agent(desk, entry_url, place, lane)
        runner = InMemoryRunner(agent=agent, app_name="migragent")
        session = await runner.session_service.create_session(
            app_name="migragent", user_id="ingestion")

        message = types.Content(role="user", parts=[types.Part(
            text=f"Start at {entry_url} and research the {lane} route for {place}.")])

        events = runner.run_async(user_id="ingestion", session_id=session.id,
                                  new_message=message)

        # Iterated by hand rather than with `async for`, so the stream can be
        # closed from inside the coroutine that opened it. Abandoning an ADK
        # event stream mid flight leaves OpenTelemetry to unwind a span in a
        # context it was not opened in, and it prints a traceback for something
        # that is not an error. A stop we chose should not look like a crash in
        # the job's logs.
        try:
            while True:
                try:
                    event = await events.__anext__()
                except StopAsyncIteration:
                    break

                # A turn is a turn of the model, not an event. ADK emits an
                # event for the tool call and another for the tool's answer, so
                # counting events counted roughly three to one and stopped a
                # Canadian run after three pages while reporting the turn limit.
                # The budget is about how much thinking a lane may cost, so it
                # counts the thing that costs.
                content = getattr(event, "content", None)
                if content is not None and getattr(content, "role", None) == "model":
                    desk.session.turns += 1
                if desk.session.stopped_because:
                    break
                if desk.session.turns >= MAX_TURNS:
                    # The cap is enforced here rather than asked for in the
                    # prompt. An agent that keeps going is stopped by the loop
                    # it runs in.
                    desk.session.stopped_because = (
                        f"the turn limit of {MAX_TURNS} was reached")
                    break
        finally:
            await events.aclose()

        if not desk.session.stopped_because:
            desk.session.stopped_because = "the agent stopped without calling finish"
