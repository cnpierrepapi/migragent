"""Check which calls may go to Orbio, and that Vertex catches every failure.

    python -m tools.test_orbio_route

No network: the Orbio transport and the Vertex call are both replaced here.
migragent/orbio.py claims that nothing about a person can reach Orbio, that a
public call carrying a file is refused before it is sent, and that a dry
balance or a broken gateway falls back to Vertex without the caller noticing.
Each of those gets a check.
"""
from __future__ import annotations

import io
import os
import re
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, ".")

from migragent import model, orbio  # noqa: E402

# The only modules allowed to mark a call public: they read public web pages.
ALLOWED = {"extract.py", "changes.py", "lanes.py", "occupations.py", "schools.py", "articles.py", "guides.py"}
# Modules that handle a person's documents, CV or case. Never public.
PERSONAL = {"cv.py", "documents.py", "drafts.py", "fit.py", "coverage.py", "form.py",
            "routes.py", "people.py", "verify.py", "agent_llm.py"}


def vertex_answer(obj: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": obj}]}, "finishReason": "STOP"}]}


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    # --- who may mark a call public, read from the source ---------------------------
    marked = {p.name for p in Path("migragent").rglob("*.py")
              if re.search(r"^\s*public=True", p.read_text(encoding="utf-8"), re.M)}
    check(marked <= ALLOWED, "only public-page readers mark calls public", sorted(marked))
    check(marked == ALLOWED, "and all seven of them do", sorted(ALLOWED - marked) or "all")
    check(not (marked & PERSONAL), "no module that touches a person is marked public")

    # --- refusing anything that is not text ------------------------------------------
    try:
        orbio.to_messages([{"text": "read this"}, {"inlineData": {"mimeType": "application/pdf",
                                                                  "data": "JVBERi0="}}])
        check(False, "a file in a public call is refused before sending")
    except orbio.NotPublic:
        check(True, "a file in a public call is refused before sending")
    check(orbio.to_messages([{"text": "a"}, {"text": "b"}]) == [{"role": "user", "content": "ab"}],
          "text parts are joined into one message")
    check(orbio.model_id("gemini-3.5-flash") == "google/gemini-3.5-flash"
          and orbio.model_id("google/x") == "google/x", "model names gain their publisher once")

    # --- shape translation --------------------------------------------------------------
    v = orbio.to_vertex({"model": "google/gemini-3.5-flash", "choices": [
        {"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}]})
    check(model._json_from(v) == ({"ok": 1}, ""), "an Orbio answer parses like a Vertex one")
    cut = orbio.to_vertex({"choices": [{"message": {"content": '{"a": "trunc'},
                                        "finish_reason": "length"}]})
    check("token limit" in model._json_from(cut)[1], "a cut-off answer still reads as cut off")

    # --- routing through call_json -------------------------------------------------------
    vertex_calls: list[dict] = []

    def fake_vertex(**kwargs):
        vertex_calls.append(kwargs)
        return vertex_answer('{"via": "vertex"}')

    model.call_content = fake_vertex
    orbio.time.sleep = lambda s: None
    sent: list[bytes] = []

    def orbio_ok(body: bytes):
        sent.append(body)
        return {"choices": [{"message": {"content": '{"via": "orbio"}'}, "finish_reason": "stop"}]}

    def http(code):
        def fail(body):
            raise urllib.error.HTTPError(orbio.ENDPOINT, code, "x", {}, io.BytesIO(b""))
        return fail

    common = dict(project="p", model="gemini-3.5-flash", location="global", credentials=None,
                  parts=[{"text": "page"}])

    os.environ.pop("ORBIO_API_KEY", None)
    orbio._off_until = 0
    check(model.call_json(**common, public=True) == {"via": "vertex"},
          "with no key configured, public calls stay on Vertex")

    os.environ["ORBIO_API_KEY"] = "sk-orb-test"
    orbio._post = orbio_ok
    vertex_calls.clear()
    check(model.call_json(**common, public=True) == {"via": "orbio"} and not vertex_calls,
          "with a key, a public call goes to Orbio and not Vertex")
    check(b'"response_format": {"type": "json_object"}' in sent[-1]
          and b'"google/gemini-3.5-flash"' in sent[-1], "and asks for JSON from the same model")

    sent.clear()
    check(model.call_json(**common) == {"via": "vertex"} and not sent,
          "a call not marked public never reaches Orbio, key or no key")

    orbio._post = http(402)
    vertex_calls.clear()
    check(model.call_json(**common, public=True) == {"via": "vertex"} and len(vertex_calls) == 1,
          "an empty balance (402) falls back to Vertex")
    check(not orbio.enabled(), "and switches Orbio off for a while")
    orbio._post = orbio_ok
    sent.clear()
    model.call_json(**common, public=True)
    check(not sent, "so the next call does not try Orbio again straight away")

    orbio._off_until = 0
    tries = []

    def flaky(body):
        tries.append(1)
        raise urllib.error.HTTPError(orbio.ENDPOINT, 503, "x", {}, io.BytesIO(b""))
    orbio._post = flaky
    vertex_calls.clear()
    check(model.call_json(**common, public=True) == {"via": "vertex"}
          and len(tries) == orbio.MAX_ATTEMPTS and len(vertex_calls) == 1,
          "a failing gateway is retried, then Vertex answers", f"{len(tries)} tries")
    check(orbio.enabled(), "a 503 does not switch Orbio off")

    orbio._post = lambda body: {"error": "nothing"}
    vertex_calls.clear()
    check(model.call_json(**common, public=True) == {"via": "vertex"} and len(vertex_calls) == 1,
          "an answer with no choices falls back to Vertex")

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
