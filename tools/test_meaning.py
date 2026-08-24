"""Check the meaning gate errs the safe way, without a network or a model.

    python -m tools.test_meaning

`migragent/meaning.py` decides whether a diff moved the meaning or only the
wording. The two ways of being wrong are not comparable:

  calling a real change cosmetic   -> a rule moved and nobody was told
  calling a rewording substantive  -> one wasted re-extraction

So almost every check here is about the first one being impossible. A number
that moved, a model that did not answer, text that appeared rather than being
rewritten: all of those must come back as a change.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent.meaning import (Embedder, SAME_MEANING, assess,  # noqa: E402
                               changed_lines, numbers_in)


def diff_of(removed: list[str], added: list[str]) -> str:
    return "\n".join(["--- before", "+++ after"]
                     + [f"-{line}" for line in removed]
                     + [f"+{line}" for line in added])


class Fixed(Embedder):
    """An embedder that returns whatever the test needs, and calls nothing."""

    def __init__(self, vectors=None, boom: Exception | None = None):
        super().__init__("project", None)
        self._vectors = vectors
        self._boom = boom
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        if self._boom:
            raise self._boom
        return self._vectors


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    # ---- numbers -----------------------------------------------------------
    check(numbers_in("the fee is 1.270 euros") == numbers_in("the fee is 1,270 euros"),
          "1.270 and 1,270 are the same figure")
    check(numbers_in("28 days") != numbers_in("29 days"), "28 and 29 are not")

    # ---- the number guard, which no similarity may overrule -----------------
    same = [[1.0, 0.0], [1.0, 0.0]]          # perfectly identical vectors
    fee = Fixed(same)
    verdict = assess(diff_of(["The fee is 490 euros."], ["The fee is 590 euros."]), fee)
    check(verdict.substantive, "a changed fee is a change even at similarity 1.0", verdict.reason)
    check(fee.calls == 0, "and the embedder was never asked about it")

    days = Fixed(same)
    verdict = assess(diff_of(["You have 10 days."], ["You have 20 days."]), days)
    check(verdict.substantive, "a changed deadline is a change", verdict.reason)

    # ---- appearing and disappearing text ------------------------------------
    only_added = Fixed(same)
    verdict = assess(diff_of([], ["You must now provide a police certificate."]), only_added)
    check(verdict.substantive, "text that appeared is a change, not a rewording")
    check(only_added.calls == 0, "and that needs no model either")

    verdict = assess(diff_of(["You must provide a police certificate."], []), Fixed(same))
    check(verdict.substantive, "text that vanished is a change")

    # ---- a genuine rewording ------------------------------------------------
    verdict = assess(diff_of(["You must hold a passport."],
                             ["Applicants must hold a passport."]), Fixed(same))
    check(verdict.cosmetic, "identical meaning with no figures moving is wording", verdict.reason)
    check(verdict.similarity is not None and verdict.similarity >= SAME_MEANING,
          "and it reports the score it decided on", verdict.similarity)

    # ---- a real change the numbers cannot catch -----------------------------
    apart = [[1.0, 0.0], [0.0, 1.0]]         # orthogonal, similarity 0
    verdict = assess(diff_of(["You may work while studying."],
                             ["You may not work while studying."]), Fixed(apart))
    check(verdict.substantive, "a meaning that moved is a change even with no figures",
          verdict.reason)

    # ---- every failure lands on substantive ---------------------------------
    for label, embedder in [
        ("the embedder raised", Fixed(boom=RuntimeError("boom"))),
        ("the embedder returned junk", Fixed([[1.0, 0.0]])),
        ("there is no embedder", None),
    ]:
        verdict = assess(diff_of(["You must hold a passport."],
                                 ["Applicants must hold a passport."]), embedder)
        check(verdict.substantive, f"{label}: it stays a change", verdict.reason[:70])

    # ---- the threshold is not on the edge of the measurement ----------------
    check(SAME_MEANING < 0.9878,
          "the threshold admits the reworded Spanish that was measured", SAME_MEANING)
    check(SAME_MEANING > 0.6154,
          "and excludes the different requirement that was measured", SAME_MEANING)

    # ---- diff parsing --------------------------------------------------------
    removed, added = changed_lines(diff_of(["a", "b"], ["c"]))
    check(removed == "a\nb" and added == "c", "the two sides of a diff are read apart",
          repr((removed, added)))

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
