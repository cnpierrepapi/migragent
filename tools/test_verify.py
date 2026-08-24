"""Check the second reader routes right, without a network or a model.

    python -m tools.test_verify

`migragent/verify.py` claims three things, and each one is a way to lose data if
it is wrong. A requirement two readers agree on goes live. A requirement they
disagree on never reaches the guide and turns into an open question instead. A
requirement the second reader could not be reached about STAYS LIVE, because an
unreachable optional model must not be able to delete verified, quoted,
government-sourced requirements.

The third is the one worth a test. It is the one where a lazy implementation
looks correct on a good day and quietly empties the corpus on a bad one.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent.extract import Extraction, Requirement  # noqa: E402
from migragent.verify import (MEASURED, SecondReader, Verdict, _read,  # noqa: E402
                              enabled, proven, review)

PAGE = "You must pay the application fee of 490 euros. You must hold a valid passport."


def a_requirement(text: str, quote: str) -> Requirement:
    return Requirement(text=text, quote=quote, source_url="https://example.gov/x",
                       read_at="2026-08-24T00:00:00+00:00", jurisdiction="ES", lane="work")


class Scripted(SecondReader):
    """A second reader that says what the test tells it to, and calls nothing."""

    def __init__(self, answers: list[Verdict]) -> None:
        super().__init__("project", None)
        self._answers = list(answers)
        self.asked: list[tuple[str, str]] = []

    def check(self, page_text: str, claim: str, quote: str) -> Verdict:
        self.asked.append((claim, quote))
        return self._answers.pop(0)


def payload(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    # ---- reading an answer -------------------------------------------------
    check(_read(payload("YES\nThe page states the fee.")).agreed is True,
          "a YES is agreement")
    check(_read(payload("NO\nThe page says nothing about police records.")).agreed is False,
          "a NO is disagreement")
    check(_read(payload("yes.\nfine")).agreed is True,
          "the answer is not case or punctuation sensitive")

    # The three ways an answer can be absent. None of them may read as a NO,
    # because a NO deletes a requirement and an absence must not.
    for label, body in [("empty", payload("")),
                        ("no candidates", {"candidates": []}),
                        ("unreadable", payload("I think probably it does?"))]:
        verdict = _read(body)
        check(verdict.agreed is None, f"an {label} answer is unverified, never a NO",
              verdict.reason[:60])

    check(_read(payload("I think probably it does?")).state == "unverified",
          "an unreadable answer states itself as unverified")

    # ---- routing -----------------------------------------------------------
    extraction = Extraction(source_url="https://example.gov/x",
                            read_at="2026-08-24T00:00:00+00:00",
                            requirements=[
                                a_requirement("You must pay 490 euros.", "pay the application fee of 490 euros"),
                                a_requirement("You must provide a police certificate.", "You must hold a valid passport."),
                                a_requirement("You must hold a valid passport.", "You must hold a valid passport."),
                            ])
    reader = Scripted([Verdict(True, "the fee is on the page"),
                       Verdict(False, "the page says nothing about police records"),
                       Verdict(None, "the second reader did not answer: HTTP 429")])
    counts = review(reader, PAGE, extraction)

    kept = [r.text for r in extraction.requirements]
    check(counts == {"agreed": 1, "disputed": 1, "unverified": 1},
          "every requirement was counted, in the right box", counts)
    check("You must provide a police certificate." not in kept,
          "the disputed requirement did NOT reach the guide")
    check(any("Two readers disagree" in q for q in extraction.open_questions),
          "the disputed requirement became an open question instead")
    check(any("police records" in q for q in extraction.open_questions),
          "the open question carries the second reader's own reason")
    check("You must hold a valid passport." in kept,
          "an unreachable second reader did NOT delete a live requirement")
    check([r.second_read for r in extraction.requirements] == ["agreed", "unverified"],
          "each surviving requirement records which it was",
          [r.second_read for r in extraction.requirements])
    check(len(reader.asked) == 3, "every requirement was actually asked about")
    check(reader.asked[0] == ("You must pay 490 euros.", "pay the application fee of 490 euros"),
          "the claim and its quote were both put in front of the second reader")

    # A second reader can only ever remove. Nothing it says may invent one.
    check(len(extraction.requirements) <= 3,
          "the second reader added nothing that was not already there")

    # ---- D40: the window ---------------------------------------------------
    # The bug this catches shipped, ran on five lanes, and produced a 51.4%
    # disagreement rate on Spanish that looked exactly like a model being weak
    # in a language. It was a smaller window than the extractor's.
    from migragent.extract import MAX_CHARS as EXTRACTOR_WINDOW
    from migragent.verify import MAX_CHARS as VERIFIER_WINDOW
    check(VERIFIER_WINDOW == EXTRACTOR_WINDOW,
          "the second reader sees exactly what the extractor saw, never less",
          f"verifier {VERIFIER_WINDOW}, extractor {EXTRACTOR_WINDOW}")

    far = ("filler. " * 2000) + "You must hold a valid passport."
    check(len(far) > 12_000, "the fixture really is past the old window", len(far))

    asked: list = []

    class Watching(SecondReader):
        def __init__(self):
            super().__init__("project", None)

        def _would_call(self, *a):  # pragma: no cover
            asked.append(a)

    reader = Watching()
    verdict = reader.check("You must pay the fee.", "You must hold a passport.",
                           "You must hold a valid passport.")
    check(verdict.agreed is None,
          "a quote outside the given text is unverified, never a disagreement",
          verdict.reason)
    check("outside the text" in verdict.reason,
          "and it says which of the two it was")
    check(asked == [], "and the model was never called about it")

    # ---- the measured-lanes gate --------------------------------------------
    # An unmeasured lane does not get a check nobody has read the output of.
    # This is the D40 rule as code: 51.4% disagreement on Spanish was a bug, and
    # the only reason it was caught is that somebody looked at the number.
    for j in ["UK", "CA", "ES"]:
        check(proven(j), f"{j} has a measured rate, so it runs", MEASURED[j])
    for j in ["FR", "AE", "DE", "IT", ""]:
        check(not proven(j), f"{j or 'an empty jurisdiction'} is unmeasured, so it does not")
    check(proven("uk"), "the check is not case sensitive")
    check(all(str(v).strip() for v in MEASURED.values()),
          "every measured lane records what was actually measured")

    # ---- the flag ----------------------------------------------------------
    import os
    os.environ.pop("MIGRAGENT_SECOND_READ", None)
    check(enabled() is False, "off unless switched on")
    os.environ["MIGRAGENT_SECOND_READ"] = "on"
    check(enabled() is True, "on when switched on")
    os.environ.pop("MIGRAGENT_SECOND_READ", None)

    # ---- report ------------------------------------------------------------
    failed = 0
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if detail:
            print(f"        {detail}")
        failed += 0 if ok else 1
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
