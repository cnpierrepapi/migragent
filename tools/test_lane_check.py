"""Check the lane check keeps its quote rule, without a network or a model.

    python -m tools.test_lane_check

  1. A route marked with a sentence that is not on the page is dropped, not
     trusted.
  2. A page about neither route is a verdict, not a blank.
  3. An off-topic quote is only used when no route was found, and it is
     quote-checked too.
  4. The verdict disagrees with the walk when the walk was wrong: the whole
     reason the check exists (D29, D32).
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent import lanes as lanes_module  # noqa: E402
from migragent.lanes import LaneCheck  # noqa: E402

WORK_PAGE = ("Skilled Worker visa. You can apply for a Skilled Worker visa to work for an "
             "approved employer in the United Kingdom. You must have a confirmation of "
             "sponsorship from that employer.")

TOURISM_PAGE = ("Visit the UK. You can visit the UK for up to 6 months as a tourist. You "
                "cannot work or study on a visit visa.")


class FakeCall:
    def __init__(self, payload): self.payload = payload; self.calls = 0
    def __call__(self, *, project, model, location, credentials, parts):
        self.calls += 1
        return self.payload


def run(payload, page):
    lanes_module.call_json = FakeCall(payload)
    return LaneCheck("p", "m", "global", None).classify("http://x", page)


def main() -> int:
    results = []
    def check(ok, name, detail): results.append((bool(ok), name, detail))

    # A work page the walk filed under study. The model returns a real work
    # sentence and a study sentence that is NOT on the page.
    v = run({"lanes": [
        {"lane": "work", "quote": "You must have a confirmation of sponsorship from that employer."},
        {"lane": "study", "quote": "If you want to study in the UK you may need a Student visa."},
    ], "off_topic_quote": ""}, WORK_PAGE)

    check(v.answered, "it reached a verdict", v.error or "no error")
    check(v.serves("work") and not v.serves("study"),
          "only the route with a sentence on the page was kept",
          f"lanes: {sorted(v.lanes)}")
    check(any(d["why"] == "the quote is not on the page" for d in v.dropped),
          "the route marked with a sentence not on the page was dropped",
          f"dropped: {v.dropped}")
    check(not v.agrees_with("study"),
          "the verdict disagrees with the walk when the walk was wrong",
          f"walk said study; check says {sorted(v.lanes)}")

    # A page about neither.
    v2 = run({"lanes": [], "off_topic_quote": "You cannot work or study on a visit visa."},
             TOURISM_PAGE)
    check(v2.answered and not v2.about_a_route,
          "a page about neither route is a verdict, not a blank",
          f"lanes: {sorted(v2.lanes)}, off-topic: {v2.off_topic_quote!r}")
    check(not v2.agrees_with("study") and not v2.agrees_with("work"),
          "an off-route page is filed under no lane", "")

    # Off-topic quote not on the page.
    v3 = run({"lanes": [], "off_topic_quote": "This page is about applying for citizenship."},
             TOURISM_PAGE)
    check(not v3.answered and any(d["lane"] == "none" for d in v3.dropped),
          "an off-topic sentence not on the page is dropped like any other",
          f"answered={v3.answered}, dropped={v3.dropped}")

    # Off-topic quote ignored when a route was found.
    v4 = run({"lanes": [
        {"lane": "work", "quote": "You must have a confirmation of sponsorship from that employer."},
    ], "off_topic_quote": "You can apply for a Skilled Worker visa to work for an approved employer in the United Kingdom."},
        WORK_PAGE)
    check(v4.serves("work") and not v4.off_topic_quote,
          "an off-topic quote is ignored when the page is about a route",
          f"lanes={sorted(v4.lanes)}, off-topic={v4.off_topic_quote!r}")

    # No text.
    v5 = run({"lanes": []}, "")
    check(not v5.answered and v5.error,
          "an empty page reports an error, not a verdict", v5.error)

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
