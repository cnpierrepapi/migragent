"""Folding a string so two of them can be compared fairly.

Whitespace, smart quotes and dashes vary between what a model returns and what a
page holds. Comparing them raw fails a true match on a curly apostrophe, which
throws away good data and makes a check look stricter than it is.

Two folds, because two callers want different things:

  fold      keeps case and accents. The quote check in extract.py uses this,
            because "Debe" and "debe" are different words in Spanish and a
            requirement's quote has to match the page as written.

  fold_ci   also lowercases. CV claims, document fields and posting requirements
            are matched case-insensitively, because "Welder" on a CV should meet
            "welder" in a job advert.
"""
from __future__ import annotations

import re
import unicodedata

_SWAPS = (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'),
          ("–", "-"), ("—", "-"), (" ", " "))


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for a, b in _SWAPS:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def fold_ci(s: str) -> str:
    return fold(s).lower()
