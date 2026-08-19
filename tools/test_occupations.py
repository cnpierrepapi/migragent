"""Prove the shortage list reader rejects a job the page does not name.

    python -m tools.test_occupations

The first real run kept 144 occupations and dropped none. That is a good result
and it is also no evidence at all that the guard works, because a check that
never fires and a check that always passes look identical from the outside. D21
is the entry in the defect log about exactly this, and it was found the same way.

So the reader is given a page whose text we control, and five answers a model
could plausibly return. Nothing here touches the network or the model.

The third case is the one that matters and it is new here. A requirement is
checked by finding its quote on the page. An occupation needs a second check,
because a shortage list is a list of names: a model can return a span that really
is on the page and attach a job title to it that is not, and the quote check
alone would wave it through. So the occupation has to appear inside its own
evidence.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent import occupations as occ  # noqa: E402
from migragent.fetcher import Fetched  # noqa: E402
from migragent.occupations import ShortageReader  # noqa: E402

PAGE = (b"<html><body><p>The following occupations are on the list: "
        b"5223 Welders and related machine operators, and 3413 Nursing assistants. "
        b"Salary floor 30,960.</p></body></html>")

PAGE_OBJ = Fetched(url="https://example.gov/list", outcome="fetched",
                   read_at="2026-08-19T00:00:00+00:00", status=200, body=PAGE)

CASES = [
    ("a real occupation with a real quote", True, {
        "occupations": [{"title": "Welders and related machine operators",
                         "quote": "5223 Welders and related machine operators"}]}),
    ("an occupation that is not on the page", False, {
        "occupations": [{"title": "Astronaut",
                         "quote": "5223 Astronauts and related machine operators"}]}),
    ("a real quote with an unrelated occupation attached", False, {
        "occupations": [{"title": "Astronaut",
                         "quote": "5223 Welders and related machine operators"}]}),
    ("a real line with the code changed", False, {
        "occupations": [{"title": "Nursing assistants",
                         "quote": "3999 Nursing assistants"}]}),
    ("two real fragments stitched together", False, {
        "occupations": [{"title": "Welders",
                         "quote": "5223 Welders and 3413 Nursing assistants"}]}),
]


def main() -> int:
    original = occ.call_json
    failures = 0
    try:
        for name, should_keep, payload in CASES:
            occ.call_json = (lambda _p: (lambda **_kw: _p))(payload)
            reader = ShortageReader.__new__(ShortageReader)
            reader._project = reader._model = reader._location = reader._credentials = None
            result = reader.read(PAGE_OBJ, "XX", "en")

            kept = result.kept > 0
            ok = kept == should_keep
            failures += 0 if ok else 1
            verdict = "PASS" if ok else "FAIL"
            what = "kept" if kept else "rejected"
            why = result.dropped[0]["why"] if result.dropped else ""
            print(f"  {verdict}  {name:<50} {what:<9} {why}")
    finally:
        occ.call_json = original

    print(f"\n{len(CASES) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
