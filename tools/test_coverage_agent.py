"""Check the Coverage Matcher agent keeps coverage.py's rule, no network.

    python -m tools.test_coverage_agent

  1. A match citing a document or field that was not uploaded is refused and
     told back, and the agent's retry against a real field is kept.
  2. The score is the share of document-satisfiable requirements covered, and a
     bad match does not shrink the denominator to flatter it.
  3. It returns the same Coverage the one-shot matcher returns.
  4. Model calls go through migragent.model. ADK's own client is trapped.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent import model as model_module  # noqa: E402
from migragent.coverage import Coverage  # noqa: E402
from migragent.documents import Field, ReadDocument  # noqa: E402

REQS = [
    {"id": "r1", "text": "You must hold a valid passport.", "category": "document"},
    {"id": "r2", "text": "You must show proof of funds.", "category": "eligibility"},
    {"id": "r3", "text": "You must pay the application fee.", "category": "cost"},
]

DOCS = [
    ReadDocument(kind="passport", filename="p.pdf", read_at="t",
                 fields=[Field(name="number", value="X1", quote="X1", verified=True),
                         Field(name="expiry", value="2030", quote="2030", verified=True)]),
    ReadDocument(kind="bank_statement", filename="b.pdf", read_at="t",
                 fields=[Field(name="balance", value="20000", quote="20000", verified=True)]),
]


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

    script = [
        _fn("record_match", {"requirement_id": "r1", "document_kind": "passport",
                             "document_field": "number", "note": "the passport itself"}),
        # A field nobody uploaded: bank_statement.proof_of_funds.
        _fn("record_match", {"requirement_id": "r2", "document_kind": "bank_statement",
                             "document_field": "proof_of_funds", "note": "shows funds"}),
        # Retry against the real field.
        _fn("record_match", {"requirement_id": "r2", "document_kind": "bank_statement",
                             "document_field": "balance", "note": "balance shows funds"}),
        _fn("finish", {}),
    ]
    scripted = Scripted(script)
    model_module.call_content = scripted

    import google.genai as genai
    class Trapped:
        def __init__(self, *a, **k):
            raise AssertionError("ADK built its own model client")
    real = genai.Client
    genai.Client = Trapped
    try:
        from migragent.agents.coverage import AgentMatcher
        cov = AgentMatcher("p", "gemini-3.5-flash", "global", None).match(
            "UK", "study", REQS, DOCS)
    finally:
        genai.Client = real

    check(isinstance(cov, Coverage), "it returns a Coverage", type(cov).__name__)
    check(cov.document_requirements == 2 and cov.action_only == 1,
          "the fee requirement is counted as action-only, not held against them",
          f"doc_reqs={cov.document_requirements}, action_only={cov.action_only}")
    check(cov.covered == 2, "both document requirements were matched",
          f"covered={cov.covered}, matched ids={[m.requirement_id for m in cov.matched]}")
    check(any(d.get("why", "").startswith("cites bank_statement.proof_of_funds")
              for d in cov.dropped_matches),
          "the match on a field nobody uploaded was refused",
          f"dropped: {cov.dropped_matches}")
    check(cov.score == 100,
          "the score is covered over document-satisfiable, and the retry recovered r2",
          f"score={cov.score}")
    check(all(m.document_field in ("number", "balance") for m in cov.matched),
          "every kept match cites a field that was actually uploaded",
          f"{[(m.document_kind, m.document_field) for m in cov.matched]}")

    first = scripted.bodies[0] if scripted.bodies else {}
    declared = []
    for tool in first.get("tools", []):
        declared += [d["name"] for d in tool.get("functionDeclarations", [])]
    check(set(declared) >= {"record_match", "finish"},
          "the tools are declared at the top level",
          f"declared: {', '.join(sorted(declared)) or 'none'}")
    check("tools" not in first.get("generationConfig", {}),
          "tools did not get mixed into sampling settings",
          f"generationConfig: {sorted(first.get('generationConfig', {}))}")

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
