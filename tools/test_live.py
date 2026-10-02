"""Check the front page's live state, without a database.

    python -m tools.test_live

migragent/live.py claims every feed line is one row and every figure a sum of
rows or a balance Orbio reported. These checks feed it rows and read back what
it says.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from migragent.live import build_state, next_run, round_line  # noqa: E402

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

ROUNDS = [
    {"jurisdiction": "AE", "lane": "work", "mode": "watch", "started_at": "2026-10-01T04:45:00+00:00",
     "finished_at": "2026-10-01T04:47:30+00:00", "fetched": 14, "unchanged": 6, "changed": 8, "kept": 5,
     "orbio_calls": 9, "orbio_usd": 0.0812},
    {"jurisdiction": "FR", "lane": "work", "mode": "watch", "started_at": "2026-10-01T04:45:00+00:00",
     "finished_at": "2026-10-01T04:45:26+00:00", "fetched": 19, "unchanged": 19, "changed": 0},
    {"jurisdiction": "ES", "lane": "study", "mode": "watch", "started_at": "2026-09-30T04:45:00+00:00",
     "finished_at": "2026-09-30T04:46:00+00:00", "fetched": 2, "unchanged": 0, "changed": 2,
     "orbio_calls": 3, "orbio_usd": 0.3},
]
CHANGES = [{"jurisdiction": "AE", "lane": "work", "source_url": "https://www.mohre.gov.ae/en/x",
            "after_read_at": "2026-10-01T04:46:00+00:00", "summary": "The salary floor rose.",
            "added": 3, "removed": 1, "material": True},
           {"jurisdiction": "AE", "lane": "work", "source_url": "https://u.ae/y",
            "after_read_at": "2026-10-01T04:46:30+00:00", "summary": "no change to what is required.",
            "material": False}]


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    s = build_state(rounds=ROUNDS, changes=CHANGES, orbio={"available": "4.39537", "used": "0.39",
                    "at": "2026-10-01T05:00:00+00:00"}, token=None, requirements=2478, now=NOW)
    st = s["stats"]
    check(st["pages_today"] == 33 and st["unchanged_today"] == 25 and st["moved_today"] == 8,
          "today's figures sum only today's rounds", st)
    check(abs(s["orbio"]["spent_today"] - 0.0812) < 1e-9, "spent today is today's Orbio cost only",
          s["orbio"]["spent_today"])
    check(s["orbio"]["runway_days"] == int(4.39537 / ((0.0812 + 0.3) / 2)),
          "runway is balance over the average spending day", s["orbio"]["runway_days"])
    check(s["stats"]["changes_week"] == 2 and s["stats"]["rule_changes_week"] == 1 and s["stats"]["requirements"] == 2478, "changes and requirements")

    fr = round_line(ROUNDS[1])
    check("France work" in fr["text"] and "19 unchanged ($0)" in fr["text"] and fr["cost"] == "",
          "a round where nothing moved says it cost nothing", fr)
    ae = round_line(ROUNDS[0])
    check("8 moved" in ae["text"] and ae["cost"] == "$0.0812 from its own budget",
          "a round Orbio paid for shows what it paid", ae["cost"])
    check(s["feed"][0]["role"] == "WATCH" and s["feed"][1]["role"] == "CHANGE",
          "the feed is newest first and mixes rounds and changes",
          [f["role"] for f in s["feed"]])
    check("The salary floor rose." in s["feed"][1]["text"] and "mohre.gov.ae" in s["feed"][1]["text"],
          "a change line carries what it means and where", s["feed"][1]["text"])

    check(not any("no change to what is required" in f["text"] for f in s["feed"]),
          "rewording that changed no rule is counted, not listed")
    old = build_state(rounds=[{k: v for k, v in ROUNDS[1].items()}], changes=[], orbio=None,
                      token=None, requirements=0, now=NOW)
    check(old["orbio"]["spent_today"] is None,
          "rounds with no cost record give a dash, not $0")
    empty = build_state(rounds=[], changes=[], orbio=None, token=None, requirements=0, now=NOW)
    check(empty["orbio"]["available"] is None and empty["orbio"]["runway_days"] is None
          and empty["feed"] == [], "no rows and no balance give dashes, not zeros")
    check(empty["status"]["phase"] == "IDLE", "nothing recent reads as idle")
    check(s["status"]["phase"] == "IDLE", "a round four hours ago is not 'reading'")

    n = next_run(NOW)
    check(n["what"] == "retention sweep" and n["at"].startswith("2026-10-02T03:17"),
          "after the last job, the next run is tomorrow's first", n)
    check(next_run(datetime(2026, 10, 1, 4, 50, tzinfo=timezone.utc))["what"] == "job listings",
          "between jobs, the next one is the next in the table")

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
