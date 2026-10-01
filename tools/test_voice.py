"""Check the house voice is enforced on articles, without a network.

    python -m tools.test_voice

migragent/voice.py claims dashes are removed in code, the skill's banned words
are caught, quotes are never touched, a failing headline gets one rewrite, a
failing "why" is dropped, and whatever still fails is written into the report.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent import articles  # noqa: E402
from migragent.articles import Report, Writer  # noqa: E402
from migragent.voice import hits, tidy  # noqa: E402


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    check(tidy("The fee rose — again") == "The fee rose, again", "an em dash becomes a comma", tidy("The fee rose — again"))
    check(tidy("Valid 2024–2026") == "Valid 2024 to 2026", "a dash in a range becomes 'to'")
    check(tidy("“plain”") == '"plain"', "curly quotes become straight")
    check("comprehensive" in hits("UAE publishes comprehensive guide"), "selling words are caught")
    check("delve" in hits("We delve into the rules") and "moreover" in hits("Moreover, it changed."),
          "the skill's vocabulary is caught")
    check("serves as" in hits("The page serves as a guide"), "significance inflation is caught")
    check("not just ... but" in hits("It is not just a fee but a deposit"), "negative parallelism is caught")
    check(hits("Keyboard and keys are fine") == [], "word boundaries: 'keyboard' is not 'key'")
    check(hits("Canada removes four Ontario colleges from its school list") == [], "a plain headline is clean")
    check("key changes" in hits("The key changes are listed"), "'key' as a puff adjective is caught")

    # The enforcement inside the article writer, with the model replaced.
    calls = []

    def fake_call_json(**kw):
        calls.append(kw)
        return {"headline": "UAE sets out the Emirates ID rules", "dek": "Residents must hold an Emirates ID."}

    import migragent.model as model
    model.call_json = fake_call_json
    w = Writer(db=None, snapshots=None, project="p", model="m", location="l", credentials=None)
    kept = {"what_changed": [{"text": "New rules — for renewals", "quote": "Q — kept as is"}],
            "who_for": [{"group": "UAE residents", "why": "This is a pivotal requirement", "quote": "q",
                         "conditions": [{"text": "Apply online — or in person", "quote": "q2"}]},
                        {"group": "Children over 15", "why": "They must give fingerprints", "quote": "q3"}],
            "who_not_for": [], "dates": [], "what_to_do": [], "not_said": ["Who is exempt — unclear"]}
    report = Report(change_ids=[], jurisdiction="AE", lane="work", sources=[], model="m")
    h, d = w._voice(kept, "UAE publishes comprehensive Emirates ID guide",
                    "A landmark update — for everyone", report)
    check(len(calls) == 1 and h == "UAE sets out the Emirates ID rules", "a failing headline is rewritten once", h)
    check(hits(h) == [] and hits(d) == [], "the rewrite is clean")
    check(kept["what_changed"][0]["text"] == "New rules, for renewals", "claim text is tidied")
    check(kept["what_changed"][0]["quote"] == "Q — kept as is", "a quote is never touched")
    check(kept["who_for"][0]["conditions"][0]["text"] == "Apply online, or in person", "conditions are tidied")
    check("why" not in kept["who_for"][0] and kept["who_for"][1]["why"] == "They must give fingerprints",
          "a failing 'why' is dropped, a clean one stays")
    check(kept["not_said"] == ["Who is exempt, unclear"], "gaps are tidied")
    check(report.voice["rewritten"] and report.voice["dropped_why"] == 1 and report.voice["remaining"] == [],
          "the report records what the voice check did", report.voice)

    calls.clear()
    model.call_json = lambda **kw: {"headline": "Still a comprehensive guide", "dek": "fine"}
    report2 = Report(change_ids=[], jurisdiction="AE", lane="work", sources=[], model="m")
    k2 = {s: [] for s in ("what_changed", "who_for", "who_not_for", "dates", "what_to_do")} | {"not_said": []}
    h2, _ = w._voice(k2, "A comprehensive guide", "fine", report2)
    check(any("comprehensive" in r for r in report2.voice["remaining"]),
          "if the rewrite still fails, the report names it", report2.voice["remaining"])

    check("No em dashes" in articles.PROMPT and articles.PROMPT.rstrip().endswith("DIFF SAMPLE:"),
          "the voice rules are in the prompt, just before the material")

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
