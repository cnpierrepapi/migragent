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
                               changed_lines, modality_in, numbers_in)


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

    # ---- the modality guard -------------------------------------------------
    # Measured against the real model: the three worst cases in the whole set
    # were modal swaps scoring 0.976 to 0.979, ABOVE several genuine rewordings.
    # Similarity alone cannot do this job, so these never reach the model.
    same = [[1.0, 0.0], [1.0, 0.0]]
    for before, after, why in [
        ("The certificate must be issued.", "The certificate may be issued.", "must to may"),
        ("Debe presentar el certificado.", "Puede presentar el certificado.", "debe to puede"),
        ("Vous devez fournir un justificatif.", "Vous pouvez fournir un justificatif.", "devez to pouvez"),
        ("You may work while studying.", "You may not work while studying.", "a negation appeared"),
        ("Le titre est renouvelable.", "Le titre n'est pas renouvelable.", "a French negation appeared"),
        ("You cannot work.", "You can work.", "cannot to can"),
    ]:
        guard = Fixed(same)
        verdict = assess(diff_of([before], [after]), guard)
        check(verdict.substantive, f"{why} is a change even at similarity 1.0", verdict.reason[:70])
        check(guard.calls == 0, f"{why}: and the model was never asked")

    # Folded to classes, not tokens, or the same obligation in two words trips it.
    check(modality_in("Debe presentar") == modality_in("Deberá aportar"),
          "debe and deberá are the same obligation")
    check(modality_in("Vous devez fournir") == modality_in("doit être fourni"),
          "devez and doit are the same obligation")
    check(modality_in("must be issued") != modality_in("may be issued"),
          "obligation and permission are not")

    # A multiset, not a set: "may" to "may not" keeps the permission and adds a
    # negation, and a set would call that unchanged.
    check(modality_in("may work") != modality_in("may not work"),
          "a negation added alongside a permission still registers",
          (modality_in("may work"), modality_in("may not work")))

    # ---- the threshold is not on the edge of the measurement ----------------
    check(SAME_MEANING < 0.9741,
          "the threshold admits the rewordings measured against the real model",
          SAME_MEANING)
    # The safety margin that matters. With both guards applied, the highest
    # scoring real change in the calibration set was 0.9302. The threshold must
    # sit clear above it, because everything above it is called cosmetic and a
    # real change called cosmetic is a rule that moved with nobody told.
    check(SAME_MEANING > 0.9302 + 0.02,
          "and stays clear of the highest real change measured (0.9302)",
          f"margin {SAME_MEANING - 0.9302:.4f}")

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
