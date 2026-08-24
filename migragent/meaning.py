"""Did the words change, or did the meaning change? D23, one storey up.

WHAT THIS IS FOR
----------------
D23 was a watcher that reported 95 of 143 pages as changed when not one word had
moved. The fix was a text gate: read the stored version, diff the words, and if
not one line moved then nothing moved, whatever the bytes say.

That gate is still crude in one direction. ANY line that moved counts as a
change, so a page that swaps "you must" for "applicants must" triggers a full
re-extraction and writes a change row, and the person watching that lane is told
immigration policy moved when a civil servant fixed a sentence.

D23's own warning applies to itself: a watcher that cries change every day
teaches the person receiving it to ignore it, and the day something real moves
they ignore that too.

WHICH WAY THIS IS ALLOWED TO BE WRONG
-------------------------------------
This is the whole design and everything below follows from it.

Calling a real change cosmetic means a rule moved and nobody was told. That is
the product's central promise breaking silently, which is the worst thing that
can happen here.

Calling a rewording substantive means one wasted re-extraction and one
notification that says less than it promised. That is the behaviour we have
today, and it is merely annoying.

So the two errors are not comparable and the gate is not balanced. It says
cosmetic only when it is very sure, and everything it cannot settle stays a
change. An unreachable embedding model means substantive, not silence.

THE MODALITY GUARD, AND WHY SIMILARITY ALONE CANNOT DO THIS JOB
---------------------------------------------------------------
Measured against the real model on 18 labelled pairs across English, Spanish and
French, the two populations OVERLAP. Highest real change 0.9788, lowest genuine
rewording 0.9201. There is no threshold that separates them, and that is not a
tuning problem, it is the shape of the tool.

With figures and modality compared first, the highest real change the similarity
score is left to judge drops to 0.9302, and the threshold sits 0.0398 clear of
it. On that set: 10 real changes out of 10 correctly called changes, and 5
rewordings out of 8 correctly called wording. The other 3 cost a re-extraction
each, which is the error we are choosing to make.

That is 18 hand written pairs, not a sample of the corpus. It is enough to show
the threshold alone was unsafe. It is not enough to call this measured, and the
first real watch round with this on should be read as calibration.

Every one of the three worst cases was a modal verb:

    must be issued      -> may be issued          0.9784   EN
    Vous devez fournir  -> Vous pouvez fournir    0.9788   FR
    Debe presentar      -> Puede presentar        0.9762   ES

An embedding scores those as near-identical because "must" and "may" occupy the
same slots in a sentence. On an immigration page that pair is the entire
difference between an obligation and an option. Negation is nearly as bad:
"est renouvelable" to "n'est pas renouvelable" came back at 0.9700, sitting
exactly on the threshold.

So modality gets the same treatment as figures: compared directly, before
similarity, and no score may overrule it. A rewording that swaps "must" for
"has to" now reads as substantive and costs a re-extraction. That is the cheap
error, and it is the one we choose.

THE NUMBER GUARD, WHICH THE MODEL CANNOT OVERRULE
--------------------------------------------------
Immigration pages are mostly numbers that matter: fees, days, ages, income
thresholds, validity periods. A change from 490 euros to 590 euros is a small
edit distance and, to an embedding, two nearly identical sentences.

So before similarity is considered at all, the digits are compared directly. If
the numbers on the page changed, the page changed, and no similarity score is
allowed to say otherwise. The model gets an opinion only about wording, never
about figures.

WHY THE MULTILINGUAL MODEL
--------------------------
`text-multilingual-embedding-002`. The corpus is 16 lanes and most of it is not
English: a monolingual model would be guessing on the Spanish and French pages,
which is where the long, frequently reworded documentation lists live.

Measured on two real Spanish sentences before this was written:

    "Debe presentar un certificado de antecedentes penales."
    "Deberá aportar un certificado de antecedentes penales."      0.9878
    "La tasa es de 80 euros."                                     0.6154

A rewording and a different requirement sit 0.37 apart, so the threshold does
not have to be a fine judgement.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .model import ModelError, _post

MODEL = "text-multilingual-embedding-002"
LOCATION = "us-central1"

# How alike two versions must be before a difference is called wording. Set high
# and deliberately not tuned to the edge of the measurement: reworded Spanish
# came back at 0.9878 and a different requirement at 0.6154, so anything in the
# wide middle stays a change. Moving this number down is a decision to tell
# people about fewer changes, and should be made with evidence, not to reduce
# noise.
SAME_MEANING = 0.97

# Digits that carry meaning. Years attached to nothing and list numbering are
# noise, but this deliberately does not try to be clever about which is which:
# every number is compared, because a guard that decides some numbers do not
# count is a guard with a hole in it.
_NUMBER = re.compile(r"\d[\d.,]*")

# Words that carry obligation, permission or negation, mapped to WHICH of those
# three they carry rather than compared as tokens. Compared like figures, for the
# reason in the docstring.
#
# Classes rather than words, because "debe" and "deberá" are the same obligation
# and comparing the tokens called that a change. What must be caught is a shift
# BETWEEN classes: obligation becoming permission, or a negation appearing. That
# survives the folding and the false alarms do not.
#
# Deliberately across languages in one table rather than switched on the lane: a
# page can carry two languages, and a guard that only works when it has been told
# which one it is reading is a guard that fails quietly.
_MODALITY_CLASSES = {
    "obligation": (
        "must shall required requires obligatory "
        "debe debes debera deberan deberá deberán obligatorio obligatoria "
        "doit doivent devez dois obligatoire "
        "muss mussen müssen deve devono devera deverá"
    ),
    "permission": (
        "may can optional "
        "puede pueden podra podran podrá podrán opcional "
        "peut peuvent pouvez facultatif "
        "darf durfen dürfen kann konnen können puo può possono podem"
    ),
    "negation": (
        "not no never cannot "
        "nunca "
        "ne n pas jamais "
        "nicht kein keine non nao não"
    ),
}

# cannot is both a permission and its refusal, and must fold to both or a page
# swapping "cannot" for "can" reads as unchanged.
_BOTH = {"cannot"}

_MODALITY_LOOKUP: dict[str, list[str]] = {}
for _klass, _words in _MODALITY_CLASSES.items():
    for _word in _words.split():
        _MODALITY_LOOKUP.setdefault(_word, []).append(_klass)
for _word in _BOTH:
    _MODALITY_LOOKUP[_word] = ["negation", "permission"]

_MODALITY = re.compile(r"\b(" + "|".join(sorted(_MODALITY_LOOKUP, key=len, reverse=True)) + r")\b", re.I)

MAX_CHARS = 8_000


@dataclass
class Meaning:
    """Whether a diff moved the meaning, and how that was decided."""

    substantive: bool
    similarity: float | None = None
    reason: str = ""

    @property
    def cosmetic(self) -> bool:
        return not self.substantive


def modality_in(text: str) -> list[str]:
    """Which of obligation, permission and negation this text carries, as a multiset.

    A multiset and not a set: "may work" becoming "may not work" adds a negation
    without removing the permission, and a set would call that unchanged.
    """
    found: list[str] = []
    for match in _MODALITY.finditer(text):
        found.extend(_MODALITY_LOOKUP[match.group(0).lower()])
    return sorted(found)


def numbers_in(text: str) -> list[str]:
    """Every figure in a piece of text, normalised so 1.270 and 1,270 agree."""
    out = []
    for raw in _NUMBER.findall(text):
        cleaned = raw.rstrip(".,").replace(".", "").replace(",", "")
        if cleaned:
            out.append(cleaned)
    return sorted(out)


class Embedder:
    """One call to the embedding model, through the same retry loop as the rest."""

    def __init__(self, project: str, credentials) -> None:
        self._project = project
        self._credentials = credentials

    def embed(self, texts: list[str]) -> list[list[float]]:
        url = (f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{self._project}"
               f"/locations/{LOCATION}/publishers/google/models/{MODEL}:predict")
        body = {"instances": [{"content": t[:MAX_CHARS]} for t in texts]}
        payload = _post(url, json.dumps(body).encode(), self._credentials)
        return [p["embeddings"]["values"] for p in payload["predictions"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def changed_lines(diff: str) -> tuple[str, str]:
    """The removed side and the added side of a unified diff, as two blocks."""
    removed, added = [], []
    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            removed.append(line[1:].strip())
        elif line.startswith("+"):
            added.append(line[1:].strip())
    return "\n".join(removed), "\n".join(added)


def assess(diff: str, embedder: Embedder | None) -> Meaning:
    """Did this diff move the meaning?

    Every path that is not a confident "only the wording moved" returns
    substantive, including every failure.
    """
    removed, added = changed_lines(diff)

    # Content appeared or disappeared. Not a rewording by definition.
    if not removed or not added:
        return Meaning(True, None, "text was added or removed, not reworded")

    before_numbers, after_numbers = numbers_in(removed), numbers_in(added)
    if before_numbers != after_numbers:
        return Meaning(True, None,
                       f"the figures changed: {before_numbers} became {after_numbers}")

    before_modality, after_modality = modality_in(removed), modality_in(added)
    if before_modality != after_modality:
        return Meaning(True, None,
                       "obligation or negation changed: "
                       f"{before_modality} became {after_modality}")

    if embedder is None:
        return Meaning(True, None, "no embedder, so every difference is a change")

    try:
        vectors = embedder.embed([removed, added])
    except ModelError as exc:
        return Meaning(True, None, f"the embedder did not answer, so this stays a change: {exc}")
    except Exception as exc:  # noqa: BLE001
        return Meaning(True, None,
                       f"the embedder did not answer, so this stays a change: {type(exc).__name__}")

    if len(vectors) != 2:
        return Meaning(True, None, "the embedder returned the wrong number of vectors")

    score = _cosine(vectors[0], vectors[1])
    if score >= SAME_MEANING:
        return Meaning(False, score, f"the wording moved and the meaning did not ({score:.4f})")
    return Meaning(True, score, f"the meaning moved ({score:.4f})")
