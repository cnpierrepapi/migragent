"""Prove the country filter and the internal rubric behave.

    python -m tools.test_eligibility

No network and no model. Both modules are pure functions over rows we already
hold, which is the reason they were written as pure functions: the part of this
worth testing is the judgement, and judgement tested against a live database is
tested against whatever the database happened to contain that morning.

WHAT IS BEING CHECKED
---------------------
  - a country appears only when its own published list matches the CV
  - every reason carries the role from the CV that produced it
  - a country with no course data produces nothing, rather than everything
  - a closed intake is not an option
  - the rubric prefers the country we can actually deliver in today
  - a cheaper school overturns the route weights, which is the one behaviour
    the rubric was specified around
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent.eligibility import (Eligible, next_level, study_countries,  # noqa: E402
                                   work_countries)
from migragent.rubric import best, score_study, score_work  # noqa: E402

SHORTAGES = {
    "CA": [{"title": "Welders and related machine operators",
            "quote": "Welders and related machine operators",
            "source_url": "https://example.gov.ca/short"},
           {"title": "Registered nurses", "quote": "Registered nurses",
            "source_url": "https://example.gov.ca/short"}],
    # The real UK row, near enough. It is long because the published list
    # qualifies the occupation in the title itself, and that length is what
    # makes it match: "Welder" reaches it through "welders".
    #
    # KNOWN EDGE, and it is real. The same list also carries the bare title
    # "Welding trades", and a CV saying "Welder" does NOT match that on its own,
    # because the stemmer is plurals-only and deliberately does not decide that
    # "welder" and "welding" are the same word. It got away with it here only
    # because the qualified row exists beside the bare one. See D34: the moment
    # this starts guessing at word families it starts putting people in front of
    # jobs they cannot do, and there is no line in their CV to point at when it
    # does. The cost is a country occasionally not appearing, which is the safe
    # direction to be wrong in.
    "UK": [{"title": "Welding trades — only high integrity pipe welders, where the "
                     "job requires 3 or more years related on-the-job experience",
            "quote": "Welding trades — only high integrity pipe welders",
            "source_url": "https://example.gov.uk/short"}],
    "ES": [{"title": "Marine engineers", "quote": "Marine engineers",
            "source_url": "https://example.gob.es/short"}],
}

COURSES = {
    "CA": [{"title": "MSc Civil Engineering", "level": "masters", "intake_open": True,
            "institution": "A Canadian university", "quote": "MSc Civil Engineering",
            "source_url": "https://example.ca/course"}],
    "UK": [{"title": "MSc Civil Engineering", "level": "masters", "intake_open": True,
            "institution": "A British university", "quote": "MSc Civil Engineering",
            "source_url": "https://example.uk/course"},
           {"title": "MSc Civil Engineering (closed)", "level": "masters",
            "intake_open": False, "institution": "A closed school",
            "quote": "x", "source_url": "https://example.uk/shut"}],
    # A country on the register with nothing read for it. It must not appear.
    "AU": [],
}


def main() -> int:
    failures: list[str] = []

    # -- work ------------------------------------------------------------
    found = work_countries(["Welder"], SHORTAGES,
                           requirements={"CA": 600, "UK": 150, "ES": 219},
                           postings={"CA": 2042})
    places = [e.jurisdiction for e in found]
    print(f"a welder qualifies for: {places}")

    if "ES" in places:
        failures.append("Spain appeared for a welder, and nothing on its list is welding")
    if sorted(places) != ["CA", "UK"]:
        failures.append(f"expected Canada and the UK, got {places}")
    for item in found:
        for reason in item.reasons:
            if not reason.quote:
                failures.append(f"{item.jurisdiction} gave a reason with no quote")
            if reason.because.lower() != "welder":
                failures.append(f"{item.jurisdiction} cited {reason.because!r}, "
                                f"which is not what the CV said")

    ranked = score_work(found)
    for score in ranked:
        print(f"  {score.explain()}")
    if best(ranked) != "CA":
        failures.append(f"the work rubric served {best(ranked)}, but only Canada has "
                        f"postings to show and the deeper corpus")

    # -- study -----------------------------------------------------------
    eligible = study_countries("masters", ["Civil Engineering"], COURSES,
                               requirements={"CA": 600, "UK": 1004})
    places = [e.jurisdiction for e in eligible]
    print(f"\na civil engineering graduate qualifies for: {places}")

    if "AU" in places:
        failures.append("Australia appeared with no course data read for it")
    if sorted(places) != ["CA", "UK"]:
        failures.append(f"expected Canada and the UK, got {places}")
    shut = [r for e in eligible for r in e.reasons if "closed" in r.matched]
    if shut:
        failures.append("a course whose intake is closed was offered as an option")

    # Route weights alone: Canada wins, which is the general case in the spec.
    even = score_study(eligible, costs={"CA": 20000, "UK": 21000}, has_partner=True)
    for score in even:
        print(f"  {score.explain()}")
    if best(even) != "CA":
        failures.append(f"at similar prices the study rubric served {best(even)}, "
                        f"and Canada outranks the UK on every route weight")

    # A much cheaper British school has to overturn that. This is the exact
    # behaviour the rubric was specified around.
    cheaper = score_study(eligible, costs={"CA": 34000, "UK": 12000}, has_partner=True)
    print()
    for score in cheaper:
        print(f"  {score.explain()}")
    if best(cheaper) != "UK":
        failures.append("a British school at a third of the price did not overturn "
                        "the route weights, so cost is not doing what it was built to do")

    # A research degree narrows the dependant gap rather than removing it.
    taught = score_study(eligible, costs={"CA": 20000, "UK": 20000}, has_partner=True)
    research = score_study(eligible, costs={"CA": 20000, "UK": 20000},
                           has_partner=True, research=True)
    gap_taught = taught[0].total - taught[-1].total
    gap_research = research[0].total - research[-1].total
    print(f"\ndependant gap: taught {gap_taught:.1f}, research {gap_research:.1f}")
    if gap_research >= gap_taught:
        failures.append("a research degree did not narrow the gap between the two, "
                        "and the countries that removed dependants kept them for research")

    # -- the ladder ------------------------------------------------------
    if next_level("bachelors") != "masters" or next_level("") != "bachelors":
        failures.append("the qualification ladder does not point where it should")

    if failures:
        print("\nFAIL")
        for line in failures:
            print(f"  {line}")
        return 1

    print("\nPASS  countries appear only on published evidence, and the rubric "
          "serves what can actually be delivered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
