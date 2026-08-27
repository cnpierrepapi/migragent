"""Check the Scout's rules hold, without a network or a model.

    python -m tools.test_scout_agent

  1. A page proposed as an entry must carry a sentence that is on it. A quote
     that is not there is refused and told back.
  2. A shell candidate is rejected, and a real page found behind it is proposed
     instead.
  3. A page robots.txt disallows is never fetched and cannot be proposed.
  4. Model calls go through migragent.model. ADK's own client is trapped.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone  # noqa: E402

from migragent import model as model_module  # noqa: E402
from migragent.fetcher import Fetched  # noqa: E402

SHELL = b"<html><body><h1>Study in Ruritania</h1><ul><li><a href='/study/permit'>Student permit</a></li><li><a href='/news'>News</a></li></ul></body></html>"
REAL = (b"<html><body><h1>Student permit</h1><p>You must show funds of 10,000 credits "
        b"for each year of study.</p></body></html>")
BLOCKED = "https://ruritania.gov/private/notes"


class FakeFetcher:
    def __init__(self): self.fetched: list[str] = []
    def permission(self, url):
        return ("disallowed", "robots.txt disallows /private/") if "/private/" in url else ("allowed", "")
    def fetch(self, url):
        self.fetched.append(url)
        body = REAL if url.endswith("/study/permit") else SHELL
        return Fetched(url=url, outcome="fetched",
                       read_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       status=200, body=body, sha256="a", raw_sha256="b",
                       content_type="text/html", final_url=url)


def _fn(name, args):
    return {"candidates": [{"content": {"role": "model",
                                        "parts": [{"functionCall": {"name": name, "args": args}}]},
                            "finishReason": "STOP"}]}


class Scripted:
    def __init__(self, script): self.script = script; self.bodies = []; self.step = 0
    def __call__(self, *, project, model, location, credentials, body):
        self.bodies.append(body)
        out = self.script[min(self.step, len(self.script) - 1)]
        self.step += 1
        return out


def main() -> int:
    results = []
    def check(ok, name, detail): results.append((bool(ok), name, detail))

    entry = "https://ruritania.gov/study"
    real = "https://ruritania.gov/study/permit"

    script = [
        _fn("read_page", {"url": entry}),                       # the shell
        _fn("reject", {"url": entry, "why": "a page of links, no requirements"}),
        _fn("read_page", {"url": real}),                        # the real page
        # A quote that is NOT on the real page.
        _fn("propose_entry", {"url": real, "reason": "states the funds requirement",
                              "quote": "You must show funds of 12,000 credits per year."}),
        # The real quote.
        _fn("propose_entry", {"url": real, "reason": "states the funds requirement",
                              "quote": "You must show funds of 10,000 credits for each year of study."}),
        _fn("read_page", {"url": BLOCKED}),                     # disallowed
        _fn("finish", {"why": "found the permit page behind the study index"}),
    ]

    scripted = Scripted(script)
    model_module.call_content = scripted

    import google.genai as genai
    class Trapped:
        def __init__(self, *a, **k):
            raise AssertionError("ADK built its own model client")
    realclient = genai.Client
    genai.Client = Trapped
    try:
        from migragent.agents.scout import Scout
        fetcher = FakeFetcher()
        scout = Scout(project="p", model="gemini-3.5-flash", location="global",
                      credentials=None, fetcher=fetcher)
        report = scout.scout(jurisdiction="RU", lane="study", place="Ruritania",
                             candidates=[entry])
    finally:
        genai.Client = realclient

    check(report.answered, "the scout finished", report.error or report.stopped_because)
    check(len(report.nominations) == 1 and report.nominations[0].url == real,
          "one real entry was proposed, and it is the page behind the shell",
          f"nominations: {[(n.url, n.quote[:30]) for n in report.nominations]}")
    check(any(r["why"] == "the quote is not on the page" for r in report.refused),
          "a nomination with a sentence not on the page was refused",
          "; ".join(r["why"] for r in report.refused) or "nothing refused")
    check(any(r["url"] == entry for r in report.rejected),
          "the shell candidate was rejected",
          f"rejected: {report.rejected}")
    check(BLOCKED not in fetcher.fetched,
          "the disallowed page was never fetched", f"fetched: {fetcher.fetched}")
    check(any(p["url"] == BLOCKED for p in report.pages_refused),
          "the refusal was recorded", f"{report.pages_refused}")

    first = scripted.bodies[0] if scripted.bodies else {}
    declared = []
    for tool in first.get("tools", []):
        declared += [d["name"] for d in tool.get("functionDeclarations", [])]
    check(set(declared) >= {"read_page", "links_from", "propose_entry", "reject", "finish"},
          "the five tools are declared at the top level",
          f"declared: {', '.join(sorted(declared)) or 'none'}")
    check("tools" not in first.get("generationConfig", {}),
          "tools did not get mixed into the sampling settings",
          f"generationConfig: {sorted(first.get('generationConfig', {}))}")

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
