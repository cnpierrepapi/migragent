"""Check the article quote gate, without a model or a database.

    python -m tools.test_articles

migragent/articles.py claims that no claim reaches an article unless its quote
is on the page, that "who it is for" must survive or nothing is published, and
that every drop is written down with its reason.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent.articles import admin_only, article_id, check, cluster, publishable, same_story, slugify  # noqa: E402

PAGE = """Skilled Worker visa
From 22 July 2026 the general salary threshold is £41,700 a year.
Care workers and senior care workers must be sponsored by a care home registered with the CQC.
If you already hold a Skilled Worker visa issued before 4 April 2024 the old threshold of £29,000 still applies.
"""


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check_(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    parsed = {
        "headline": "UK raises the Skilled Worker salary threshold to £41,700",
        "what_changed": [{"text": "The general threshold rose", "quote": "the general salary threshold is £41,700 a year"}],
        "who_for": [
            {"group": "Care workers applying for a Skilled Worker visa", "why": "must be sponsored by a CQC care home",
             "quote": "Care workers and senior care workers must be sponsored by a care home registered with the CQC"},
            {"group": "Nigerian nurses", "why": "invented", "quote": "Nigerian nurses are prioritised"},
            {"group": "People with no quote", "why": "x"},
        ],
        "who_not_for": [{"group": "Holders of a visa issued before 4 April 2024",
                         "quote": "issued before 4 April 2024 the old threshold of £29,000 still applies"}],
        "dates": [{"what": "takes effect", "date": "22 July 2026", "quote": "From 22 July 2026"}],
        "what_to_do": [],
        "not_said": ["Whether in-country switches are affected", ""],
    }
    kept, dropped, checked = check(parsed, [PAGE])
    check_(len(kept["who_for"]) == 1 and "Care workers" in kept["who_for"][0]["group"],
           "a who-for line quoting the page survives")
    check_(any(d["claim"] == "Nigerian nurses" and d["why"] == "the quote is not on the page" for d in dropped),
           "an invented group is dropped, and the reason is recorded")
    check_(any(d["why"] == "no quote given" for d in dropped), "a line with no quote is dropped")
    check_(checked == 6 and len(dropped) == 2, "every claim is counted as checked", f"{checked} checked, {len(dropped)} dropped")
    check_(kept["who_not_for"] and kept["dates"], "exclusions and dates are checked the same way")
    check_(kept["not_said"] == ["Whether in-country switches are affected"], "empty gaps are removed")
    check_(publishable(kept) == "", "an article with who-for and a change is publishable")

    no_who = check({"what_changed": parsed["what_changed"], "who_for": [parsed["who_for"][1]]}, [PAGE])[0]
    check_("who it is for" in publishable(no_who), "no surviving who-for line means no article")
    spaced = check({"what_changed": [{"text": "x", "quote": "the general   salary\nthreshold is £41,700"}]}, [PAGE])[0]
    check_(len(spaced["what_changed"]) == 1, "whitespace differences do not break a real quote")

    with_conds = check({"who_for": [{"group": "Care workers", "quote": "Care workers and senior care workers",
                                     "conditions": [
                                         {"text": "Paid at least £41,700", "quote": "salary threshold is £41,700 a year"},
                                         {"text": "Must speak English at B2", "quote": "English at level B2"}]}]}, [PAGE])
    kept_c = with_conds[0]["who_for"][0].get("conditions") or []
    check_(len(kept_c) == 1 and "41,700" in kept_c[0]["text"],
           "each condition on a group is checked on its own")
    check_(any(d["section"] == "who_for condition" and "B2" in d["claim"] for d in with_conds[1]),
           "an unquoted condition is dropped and named in the report")

    other = "Second page. Care workers and senior care workers must be sponsored."
    k2 = check({"who_for": [{"group": "g", "quote": "Second page"}]}, [PAGE, other])[0]
    check_(k2["who_for"][0]["source"] == 2, "a kept claim records which page its quote is on")

    news = [{"id": str(i), "jurisdiction": "CA", "after_read_at": "2026-09-29T05:00:00",
             "source_url": f"https://canada.ca/{i}", "summary": text} for i, text in enumerate([
                 "The temporary measures put in place in response to Ebola have been extended from September 28, 2026, to November 27, 2026.",
                 "The temporary measures put in place in response to Ebola disease have been extended from September 28, 2026, to November 27, 2026.",
                 "Several Ontario institutions have been removed from the list of designated learning institutions."])]
    groups = cluster(news)
    check_(sorted(len(g) for g in groups) == [1, 2], "one piece of news on two pages is one article",
           [len(g) for g in groups])
    news[1]["after_read_at"] = "2026-09-30T05:00:00"
    check_(len(cluster(news)) == 3, "the same words on a different day are a separate article")

    hours = [{"summary": "The prefecture's Tuesday opening hours change on 8 September."},
             {"summary": "Allo Service Public telephone hours are updated."}]
    check_(admin_only(hours), "a change that only moves opening hours is not news")
    check_(not admin_only([{"summary": "Opening hours change, and the visa fee rises to 99 euros."}]),
           "hours plus a fee change is still news")
    check_(not admin_only([{"summary": "The salary threshold rises to 41,700 pounds."}]), "a rule change is news")
    ebola3 = [{"id": str(i), "jurisdiction": "CA", "after_read_at": "2026-08-29T05:00:00", "source_url": f"https://c/{i}",
               "summary": t} for i, t in enumerate([
                   "Canada extends temporary Ebola measures on the study permit route.",
                   "Temporary Ebola travel measures are extended until September 2026.",
                   "Canada extends temporary Ebola travel measures for international students."])]
    check_(len(cluster(ebola3)) == 1, "the three Ebola notes of 29 August are one story", len(cluster(ebola3)))
    check_(same_story("Canada extends Ebola measures for students",
                      "Canada extends temporary Ebola measures until November 27 for study permit applicants"),
           "a change matching a filed headline that day is the same story")

    check_(article_id(["b", "a"]) == article_id(["a", "b"]), "an article's id does not depend on change order")
    check_(slugify("UK raises the Skilled Worker salary threshold to £41,700!") ==
           "uk-raises-the-skilled-worker-salary-threshold-to-41-700", "slugs are plain", slugify(parsed["headline"]))

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
