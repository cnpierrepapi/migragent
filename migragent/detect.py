"""Working out what a document is from the words on it.

A second opinion on the document type, in plain code, with no model involved.

WHY A SECOND OPINION
--------------------
The model already says what kind of document it read. It is usually right. The
trouble is that when it is wrong there is nothing to notice, and a misread type
is quiet damage: an offer letter filed as a transcript matches the wrong
requirements, and the score moves for a reason nobody can see.

So the words get a vote too. Every kind of document carries vocabulary it cannot
avoid using. A passport says "date of expiry" and "issuing authority". An IELTS
result says "band score" and "listening". A bank statement says "closing
balance". Those words are on the page or they are not, and counting them is
arithmetic anybody can repeat.

**Where the two agree, that is worth saying. Where they disagree, that is worth
showing.** Neither is allowed to silently overrule the other.

AND YES, THIS IS A HEURISTIC OVER NAMES
---------------------------------------
`docs/INHERITED.md` records a heuristic over names as a real failure, and rule 2
in `docs/DECISIONS.md` bans it from deciding what a requirement is. This is a
different job with a different cost.

Deciding a requirement exists on the strength of a matched word puts a false
claim in front of somebody with a government link next to it. Deciding a file is
probably a passport puts a label on a card, next to the model's label, with both
shown when they differ. Getting it wrong costs a visible disagreement rather than
an invisible fabrication.

It also never runs alone: with no text layer there are no words to count, and it
says so instead of guessing.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# Words each kind of document has trouble avoiding. Weight 2 means the phrase is
# close to unique to that document; weight 1 means it is suggestive.
SIGNALS: dict[str, list[tuple[str, int]]] = {
    "passport": [
        ("passport", 2), ("issuing authority", 2), ("date of expiry", 1),
        ("place of birth", 1), ("nationality", 1), ("holder", 1),
        ("machine readable", 2), ("type p", 2), ("passport no", 2),
    ],
    "national_id": [
        ("identity card", 2), ("national identity", 2), ("id number", 1),
        ("carte nationale", 2), ("documento nacional", 2),
    ],
    "degree_certificate": [
        ("has been awarded", 2), ("degree of", 2), ("bachelor of", 2),
        ("master of", 2), ("doctor of philosophy", 2), ("conferred", 2),
        ("graduated", 1), ("with honours", 1), ("diploma", 1),
    ],
    "transcript": [
        ("transcript", 2), ("academic record", 2), ("credit hours", 2),
        ("grade point average", 2), ("gpa", 1), ("semester", 1),
        ("module", 1), ("marks obtained", 2),
    ],
    "english_test": [
        ("ielts", 2), ("toefl", 2), ("pte academic", 2), ("duolingo english test", 2),
        ("band score", 2), ("overall band", 2), ("listening", 1), ("reading", 1),
        ("writing", 1), ("speaking", 1), ("test report form", 2),
        ("secure english language test", 2),
    ],
    "language_test_other": [
        ("tef", 2), ("tcf", 2), ("delf", 2), ("dele", 2), ("goethe", 2),
        ("niveau", 1), ("compr", 1),
    ],
    "professional_registration": [
        ("registration number", 2), ("licence to practise", 2),
        ("license to practice", 2), ("regulatory body", 2), ("register of", 1),
        ("good standing", 2), ("practising certificate", 2),
    ],
    "employment_letter": [
        ("to whom it may concern", 1), ("employed", 2), ("employment", 1),
        ("job title", 1), ("annual salary", 2), ("full-time", 1),
        ("date of joining", 2), ("hr manager", 1), ("human resources", 1),
    ],
    "bank_statement": [
        ("closing balance", 2), ("opening balance", 2), ("account number", 1),
        ("sort code", 2), ("iban", 2), ("statement period", 2),
        ("available balance", 2), ("transaction", 1), ("withdrawal", 1),
        ("deposit", 1),
    ],
    "police_certificate": [
        ("police certificate", 2), ("criminal record", 2), ("no conviction", 2),
        ("police clearance", 2), ("certificate of good conduct", 2),
        ("disclosure", 1), ("acro", 2),
    ],
    "medical_exam": [
        ("panel physician", 2), ("medical examination", 2), ("chest x-ray", 2),
        ("immunisation", 2), ("immunization", 2), ("tuberculosis", 2),
        ("vaccination", 1), ("clinic", 1),
    ],
    "birth_certificate": [
        ("certificate of birth", 2), ("birth certificate", 2),
        ("registrar of births", 2), ("mother", 1), ("father", 1),
        ("date of birth", 1), ("place of birth", 1),
    ],
    "marriage_certificate": [
        ("certificate of marriage", 2), ("marriage certificate", 2),
        ("solemnized", 2), ("solemnised", 2), ("spouse", 1), ("bride", 2),
        ("groom", 2),
    ],
    "offer_letter": [
        ("letter of acceptance", 2), ("offer of admission", 2),
        ("we are pleased to offer", 2), ("unconditional offer", 2),
        ("conditional offer", 2), ("designated learning institution", 2),
        ("cas number", 2), ("confirmation of acceptance", 2),
        ("tuition fee", 1), ("programme", 1), ("registrar", 1),
    ],
}

# Below this, the words are not saying anything and the detector says so rather
# than naming whichever kind happened to score 3.
MIN_SCORE = 4
# A win this narrow is a coin toss dressed as a result.
MIN_MARGIN = 2


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", text)


@dataclass
class Detection:
    """What the words suggest, and how strongly."""

    kind: str | None
    score: int
    runner_up: str | None
    runner_up_score: int
    matched: list[str]
    reason: str

    @property
    def confident(self) -> bool:
        return self.kind is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "score": self.score,
            "runner_up": self.runner_up,
            "runner_up_score": self.runner_up_score,
            "matched": self.matched[:12],
            "reason": self.reason,
        }


def detect(text: str) -> Detection:
    """Guess the document kind from its vocabulary alone."""
    if not text or len(text.strip()) < 40:
        return Detection(None, 0, None, 0, [],
                         "there is no text layer to read, so the words cannot vote")

    haystack = _normalise(text)
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}

    for kind, signals in SIGNALS.items():
        total = 0
        found: list[str] = []
        for phrase, weight in signals:
            if phrase in haystack:
                total += weight
                found.append(phrase)
        if total:
            scores[kind] = total
            hits[kind] = found

    if not scores:
        return Detection(None, 0, None, 0, [],
                         "none of the words this looks for are on the page")

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best, best_score = ranked[0]
    second, second_score = (ranked[1] if len(ranked) > 1 else (None, 0))

    if best_score < MIN_SCORE:
        return Detection(None, best_score, second, second_score, hits[best],
                         f"the strongest match only scored {best_score}, "
                         f"which is not enough to name a kind")
    if best_score - second_score < MIN_MARGIN:
        return Detection(None, best_score, second, second_score, hits[best],
                         f"{best} and {second} scored {best_score} and "
                         f"{second_score}, too close to call")

    return Detection(best, best_score, second, second_score, hits[best],
                     f"scored {best_score} on {len(hits[best])} phrases")


def agreement(model_kind: str, detected: Detection) -> tuple[str, str]:
    """Compare the two opinions and say what to show.

    Returns (state, sentence). The model's answer is never silently replaced,
    because a disagreement is information and hiding it would waste the only
    thing this file is for.
    """
    if detected.kind is None:
        return "unchecked", f"The words could not be checked: {detected.reason}."
    if detected.kind == model_kind:
        return "agreed", (f"The words agree: {detected.reason}, "
                          f"including {', '.join(detected.matched[:3])}.")
    return "disagreed", (
        f"Read as {model_kind}, but the words look more like {detected.kind} "
        f"({detected.reason}). Both are shown because neither gets to overrule "
        f"the other quietly."
    )
