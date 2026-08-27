"""Check the Extractor agent keeps extract.py's rule, without a network or model.

    python -m tools.test_extractor_agent

  1. A requirement whose quote is not on the page is refused, told back, and the
     agent's retry with the real sentence is kept.
  2. The citation is built from the fetch, never from the model.
  3. It returns the same Extraction shape the one-shot extractor returns.
  4. An empty page reports model_error, so the round's existing branch still
     means "this page produced nothing and here is why".
  5. Model calls go through migragent.model. ADK's own client is trapped.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone  # noqa: E402

from migragent import model as model_module  # noqa: E402
from migragent.extract import Extraction  # noqa: E402
from migragent.fetcher import Fetched  # noqa: E402

PAGE = (b"<html><body><h1>Student visa</h1>"
        b"<p>You must show that you have enough money to support yourself.</p>"
        b"<p>The application fee is 490 dollars.</p></body></html>")

URL = "https://immi.example.gov/student-visa"


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


def _page(body=PAGE):
    return Fetched(url=URL, outcome="fetched",
                   read_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   status=200, body=body, sha256="a", raw_sha256="b",
                   content_type="text/html", final_url=URL)


def run(script, page):
    from migragent.agents.extractor import AgentExtractor

    scripted = Scripted(script)
    model_module.call_content = scripted
    import google.genai as genai

    class Trapped:
        def __init__(self, *a, **k):
            raise AssertionError("ADK built its own model client")
    real = genai.Client
    genai.Client = Trapped
    try:
        ex = AgentExtractor("p", "gemini-3.5-flash", "global", None)
        out = ex.extract(page, jurisdiction="CA", lane="study", language="en")
    finally:
        genai.Client = real
    return out, scripted


def main() -> int:
    results = []
    def check(ok, name, detail): results.append((bool(ok), name, detail))

    out, scripted = run([
        # An invented requirement: true of student visas, not on this page.
        _fn("record_requirement", {
            "text": "You must provide a police certificate.",
            "quote": "You must provide a police clearance certificate from every country "
                     "you have lived in.",
            "category": "document"}),
        # The retry: a real sentence.
        _fn("record_requirement", {
            "text": "You must show you can support yourself financially.",
            "quote": "You must show that you have enough money to support yourself.",
            "category": "eligibility"}),
        _fn("record_requirement", {
            "text": "You must pay the application fee.",
            "quote": "The application fee is 490 dollars.", "category": "cost",
            "cost": "490 dollars"}),
        _fn("note_open_question", {"question": "How is proof of funds calculated?"}),
        _fn("finish", {"why": "recorded what the page states"}),
    ], _page())

    check(isinstance(out, Extraction), "it returns an Extraction", type(out).__name__)
    kept = [r.text for r in out.requirements]
    check(len(out.requirements) == 2,
          "only the two requirements the page states were kept", f"kept: {kept}")
    check(any(d["why"] == "the quote is not on the page" for d in out.dropped),
          "the invented requirement was refused", f"dropped: {out.dropped}")
    check(all("police" not in r.text for r in out.requirements),
          "the invented requirement did not reach the extraction", kept)
    check(all(r.source_url == URL and r.read_at for r in out.requirements),
          "the citation was built from the fetch",
          f"{[(r.source_url, bool(r.read_at)) for r in out.requirements]}")
    check(out.open_questions == ["How is proof of funds calculated?"],
          "the open question was carried", f"{out.open_questions}")
    check(not out.model_error, "no model_error on a page that produced requirements",
          out.model_error or "none")

    first = scripted.bodies[0] if scripted.bodies else {}
    declared = []
    for tool in first.get("tools", []):
        declared += [d["name"] for d in tool.get("functionDeclarations", [])]
    check(set(declared) >= {"record_requirement", "note_open_question", "finish"},
          "the tools are declared at the top level",
          f"declared: {', '.join(sorted(declared)) or 'none'}")
    check("tools" not in first.get("generationConfig", {}),
          "tools did not get mixed into sampling settings",
          f"generationConfig: {sorted(first.get('generationConfig', {}))}")

    # Empty page.
    out2, _ = run([_fn("finish", {})], _page(b"<html><body></body></html>"))
    check(out2.model_error and not out2.requirements,
          "an empty page reports model_error and no requirements",
          f"model_error={out2.model_error!r}, kept={len(out2.requirements)}")

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
