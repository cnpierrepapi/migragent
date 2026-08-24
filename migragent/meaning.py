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
