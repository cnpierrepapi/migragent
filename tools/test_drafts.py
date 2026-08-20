"""Check the number guard on rewrites, without a network or a model.

    python -m tools.test_drafts

`migragent/drafts.py` claims that every number in a draft is checked against the
numbers in the person's own claims, and that anything else is named on the draft
in front of them. Rule 3 says a claim gets a test before it gets a sentence.

This is the check worth having a test for, because it is the one standing between
a person and a CV that says they have five years of experience when they have
two. The prompt asks the model not to invent; this catches it when it does
anyway, and a request and a check are not the same kind of thing.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent.cv import CV, Claim  # noqa: E402
from migragent.drafts import CONVENTION_NOTE, DRAFT_NOTE, Drafter  # noqa: E402


def a_cv(verified: bool = True) -> CV:
    return CV(filename="cv.pdf", read_at="2026-08-20T00:00:00+00:00", text_layer=True,
              claims=[
                  Claim(kind="role", value="Welder", quote="Welder", verified=verified,
                        detail="Lagos Steel Works, 2019 to 2026"),
                  Claim(kind="skill", value="Trained four apprentices",
                        quote="Trained four apprentices", verified=verified),
                  Claim(kind="qualification", value="City and Guilds Level 3 Diploma",
                        quote="City and Guilds Level 3 Diploma", verified=verified,
                        detail="2019"),
              ])


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    # No credentials are used: nothing here calls the model.
    drafter = Drafter("project", "model", "global", None)
    cv = a_cv()

    invented = drafter._invented_numbers(
        "Led a team of 12 welders over 15 years, cutting scrap by 30%.", cv)
    check(invented == ["12", "15", "30"],
          "numbers with no claim behind them are caught", f"caught {invented}")

    kept = drafter._invented_numbers(
        "Welding at Lagos Steel Works from 2019 to 2026, City and Guilds Level 3.", cv)
    check(kept == [],
          "numbers the person really wrote are not flagged", f"flagged {kept}")

    # Single digits are ignored on purpose, and this pins that down rather than
    # letting it be discovered later as a surprise. The CV says "four
    # apprentices" in words; a draft saying "4 apprentices" is not flagged,
    # because the guard skips one character numbers entirely. That is a real
    # hole, and it is a deliberate one: flagging every "1" and "2" in ordinary
    # prose produces a warning on every draft, and a warning on every draft is a
    # warning nobody reads. Years, team sizes and percentages are two digits or
    # more, and they are the ones that do the damage.
    check(drafter._invented_numbers("Trained 4 apprentices.", cv) == [],
          "single digits are skipped, deliberately and knowingly",
          "the guard starts at two digits, which is where years and team sizes live")

    note = drafter._note("Led a team of 12 welders.", cv, "Two pages at most.")
    check(DRAFT_NOTE in note, "every draft says it is a draft")
    check(CONVENTION_NOTE in note, "layout advice is labelled convention, not law")
    check("12" in note and "not in your CV" in note,
          "the flagged number is named on the draft itself, in front of the person",
          note[-90:])

    unverified = drafter._note("All fine.", a_cv(verified=False), None)
    check("could not be checked" in unverified,
          "a CV read from a scan says so on the draft")

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if detail:
            print(f"        {detail}")

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
