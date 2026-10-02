"""Check the guide citation gate, without a model or a database.

    python -m tools.test_guides

migragent/guides.py claims a guide keeps only lines that cite requirements it
was given, and drops the rest.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent.guides import validate  # noqa: E402


def main() -> int:
    results = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    known = {"r1", "r2", "r3"}
    parsed = {
        "title": "UK Skilled Worker visa \u2014 requirements",
        "dek": "For people with a job offer from a UK employer.",
        "sections": [
            {"heading": "Who can apply", "paragraphs": [
                {"text": "You need a job offer from an approved sponsor.", "cites": ["r1"]},
                {"text": "Invented claim with no support.", "cites": []},
                {"text": "Claim citing a requirement it was not given.", "cites": ["r9"]}]},
            {"heading": "Empty section", "paragraphs": [{"text": "x", "cites": ["nope"]}]}],
        "checklist": [{"item": "Certificate of sponsorship", "cites": ["r2"]}, {"item": "Bad", "cites": []}],
        "faq": [{"q": "How much do I need to earn?", "a": "At least the threshold.", "cites": ["r3", "zz"]}],
        "topics": ["english_test", "crypto_casino"],
    }
    g, kept, dropped = validate(parsed, known)
    check(kept == 3 and dropped == 4, "lines citing nothing or unknown ids are dropped", f"kept {kept}, dropped {dropped}")
    check([s["heading"] for s in g["sections"]] == ["Who can apply"], "a section with nothing left is removed")
    check(g["faq"][0]["cites"] == ["r3"], "only known ids survive in a citation list", g["faq"][0]["cites"])
    check(g["topics"] == ["english_test"], "unknown affiliate topics are dropped")
    check("\u2014" not in g["title"], "the voice tidy removes dashes from the title", g["title"])

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
