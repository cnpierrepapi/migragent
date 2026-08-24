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
from migragent.verify import SecondReader, Verdict, _read, enabled, review  # noqa: E402

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
