"""Check what the agent is not allowed to do, without a network or a model.

    python -m tools.test_agent

Build 4 hands one decision to an agent and keeps every rule in code. That is a
claim, and rule 3 says a claim gets a test before it gets a sentence. Four things
are checked here, each of which would be silent if it broke:

  1. The agent's model calls go through migragent.model, so the retries and the
     status codes that D20 exists for cover the chattiest caller in the system.
     ADK's own client is booby trapped for the length of the test, so if anything
     routes around us the test fails rather than quietly working.

  2. A quote that is not on the page is refused, and the refusal is told back to
     the agent in words rather than swallowed.

  3. A page robots.txt disallows is never fetched, whatever the agent asks for.

  4. Tools survive the trip to Vertex. They sit at the top level of the request
     and sampling settings sit inside generationConfig, and putting a tool in the
     wrong place does not raise: it is simply ignored, and an agent with no tools
     looks like an agent that chose not to use any.

The model is scripted, so this tests our side of the conversation and not
Gemini's. What the agent decides is a separate question and needs real pages.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone  # noqa: E402

from migragent import model as model_module  # noqa: E402
from migragent.fetcher import Fetched  # noqa: E402

PAGE_HTML = (b"<html><body><h1>Skilled Worker visa</h1>"
             b"<p>You must have a confirmation of sponsorship from an approved "
             b"employer.</p>"
             b"<p>The fee is 719 pounds.</p>"
             b"<a href='/skilled-worker-visa/eligibility'>Eligibility</a>"
             b"</body></html>")

ENTRY = "https://www.example.gov.uk/skilled-worker-visa"
FORBIDDEN = "https://www.example.gov.uk/private/internal-notes"


class FakeFetcher:
    """A fetcher that serves one page and disallows one path."""

    def __init__(self) -> None:
        self.fetched: list[str] = []

    def permission(self, url: str) -> tuple[str, str]:
        if "/private/" in url:
            return "disallowed", "robots.txt disallows /private/"
        return "allowed", ""

    def fetch(self, url: str) -> Fetched:
        self.fetched.append(url)
        return Fetched(url=url, outcome="fetched", status=200, body=PAGE_HTML,
                       content_type="text/html; charset=utf-8", final_url=url,
                       read_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       sha256="x", raw_sha256="y")


def _call(name: str, args: dict) -> dict:
    return {"candidates": [{"content": {"role": "model",
                                        "parts": [{"functionCall": {"name": name,
                                                                    "args": args}}]},
                            "finishReason": "STOP"}]}


# What the scripted model does, in order. Two of these are things the agent is
# not allowed to do, and the test is that it is stopped.
SCRIPT = [
    _call("read_page", {"url": ENTRY}),
    # A requirement that is true of this visa and is NOT on this page. This is
    # the failure the quote check exists for: nothing is invented except the
    # evidence.
    _call("record_requirement", {
        "text": "You must prove you can speak English to at least B1.",
        "quote": "You must prove you know English to level B1 on the Common European "
                 "Framework of Reference for Languages.",
        "source_url": ENTRY}),
    _call("record_requirement", {
        "text": "You need a confirmation of sponsorship from an approved employer.",
        "quote": "You must have a confirmation of sponsorship from an approved employer.",
        "source_url": ENTRY}),
    # A quote that IS real, attributed to a page never opened in this session.
    _call("record_requirement", {
        "text": "You must pay the fee.",
        "quote": "The fee is 719 pounds.",
        "source_url": "https://www.example.gov.uk/some-other-page"}),
    _call("read_page", {"url": FORBIDDEN}),
    _call("finish", {"why": "the entry page states the sponsorship requirement"}),
]


class Recorder:
    """Stands in for Vertex, and counts what came through migragent.model."""

    def __init__(self) -> None:
        self.bodies: list[dict] = []
        self.step = 0

    def __call__(self, *, project, model, location, credentials, body):
        self.bodies.append(body)
        response = SCRIPT[min(self.step, len(SCRIPT) - 1)]
        self.step += 1
        return response


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok: bool, name: str, detail: str) -> None:
        results.append((bool(ok), name, detail))

    recorder = Recorder()
    model_module.call_content = recorder

    # If ADK reaches for its own client, this raises rather than working.
    import google.genai as genai

    class Trapped:
        def __init__(self, *a, **k):
            raise AssertionError("ADK built its own model client, bypassing migragent.model")

    real_client = genai.Client
    genai.Client = Trapped

    try:
        from migragent.researcher import Researcher

        fetcher = FakeFetcher()
        researcher = Researcher(project="p", model="gemini-3.5-flash", location="global",
                                credentials=None, fetcher=fetcher)
        session = researcher.research(ENTRY, jurisdiction="UK", lane="work",
                                      place="the United Kingdom", language="en")
    finally:
        genai.Client = real_client

    check(not session.error, "the session ran without falling over",
          session.error or "no error")

    # 1. Every model call came through our caller.
    check(len(recorder.bodies) > 0,
          "the agent's model calls went through migragent.model",
          f"{len(recorder.bodies)} call(s) recorded, ADK's own client was trapped and "
          "never fired")

    # 4. The tools survived the trip.
    first = recorder.bodies[0] if recorder.bodies else {}
    declared = []
    for tool in first.get("tools", []):
        declared += [d["name"] for d in tool.get("functionDeclarations", [])]
    check(set(declared) >= {"read_page", "record_requirement", "finish"},
          "the tools are declared at the top level of the request",
          f"declared: {', '.join(sorted(declared)) or 'none'}")
    check("tools" not in first.get("generationConfig", {}),
          "sampling settings and tools did not get mixed up",
          f"generationConfig: {sorted(first.get('generationConfig', {}))}")

    # 2. The quote check.
    kept = [r.text for r in session.requirements]
    check(len(session.requirements) == 1,
          "only the requirement the page actually states was kept",
          f"kept {len(session.requirements)}: {kept}")
    check(any(r["why"] == "the quote is not on the page" for r in session.refused),
          "a quote that is not on the page was refused",
          "; ".join(r["why"] for r in session.refused))
    check(any(r["why"] == "that page was not read in this session" for r in session.refused),
          "a real quote attributed to an unopened page was refused",
          f"{len(session.refused)} refusal(s) in total")
    check(all("English" not in r.text for r in session.requirements),
          "the invented requirement did not reach the corpus",
          "the model asserted a true fact this page does not state")

    # Citations come from the fetch, never from the model.
    check(all(r.source_url == ENTRY and r.read_at for r in session.requirements),
          "the citation was built from the fetch",
          f"{[(r.source_url, bool(r.read_at)) for r in session.requirements]}")

    # 3. The robots gate.
    check(FORBIDDEN not in fetcher.fetched,
          "the disallowed page was never fetched",
          f"fetched: {fetcher.fetched}")
    check(any(p["url"] == FORBIDDEN for p in session.pages_refused),
          "the refusal was recorded rather than passed over in silence",
          "; ".join(f"{p['why']}" for p in session.pages_refused))

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    print(f"\nthe agent stopped because: {session.stopped_because}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
