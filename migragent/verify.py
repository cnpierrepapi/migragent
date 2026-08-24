"""A second reader, which is a different model, saying whether the page says it.

WHY THIS EXISTS
---------------
`migragent/ocr.py` already argues this for images: Gemini could transcribe a
document and then check its own claims against its own transcription, and a
hallucinated date would happily verify itself. So Cloud Vision reads the pixels
instead. A different engine, no stake in the answer, and when the two agree the
agreement is worth something.

The same hole is open on text, and it is wider.

The verbatim quote check in `migragent/extract.py` is deterministic and stays
exactly as it is: a quote that is not in the page text means the requirement
never existed. That catches an invented sentence. It does not catch a real
sentence pressed into service as evidence for something it does not say, which
is the subtler failure and the one a fluent model makes.

Nothing independent has ever disagreed with Gemini here. This is that.

WHAT THE SECOND READER IS AND IS NOT
------------------------------------
It is Gemma, on Vertex, and it is given two things: the page text, and the claim.
It does not see the prompt Gemini was given, what Gemini decided, or why. It is
not asked to improve the requirement, rewrite it, or find new ones. It answers
one question, and the question is not "is this true" but "does this page say it".

That distinction is the entire point. A model that has read a thousand
immigration pages knows a study permit usually needs proof of funds. We are not
asking what it knows. We are asking what is on the page in front of it.

WHAT HAPPENS TO A DISAGREEMENT
------------------------------
It goes to open questions, with both readings recorded, and it never reaches the
guide. An open question is a thing this product already knows how to say. A
requirement two models cannot agree on is exactly what that section is for.

WHAT HAPPENS WHEN THE SECOND READER IS DOWN
-------------------------------------------
The requirement stays live and is marked `unverified`.

This is deliberate and it is the opposite of what a strict reading would do. A
second opinion being unavailable is not evidence against the first one. Gemma 4
on Vertex is a public preview and it throttles: the first call made from this
machine came back 429 and the second succeeded. Building a rule where an
unreachable optional model silently deletes verified, quoted, government-sourced
requirements would be a far worse failure than the one this file prevents.

WHY GLOBAL IS PINNED
--------------------
`gemma-4-26b-a4b-it-maas` is served only from the global endpoint. Asking
us-central1 for it returns FAILED_PRECONDITION, not a fallback. The rest of the
product happens to default to global today, so inheriting the location would work
right up until somebody changes that default and the second reader quietly stops
existing. So it is pinned here and does not inherit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .extract import MAX_CHARS as EXTRACTOR_WINDOW, _normalise
from .model import ModelError, call_content

# The second reader. Pinned, not inherited: see the note above.
SECOND_MODEL = "gemma-4-26b-a4b-it-maas"
SECOND_LOCATION = "global"

# How much page goes to the second reader. IMPORTED, not chosen, and this is
# the whole lesson of D40.
#
# It used to be 12,000 against the extractor's 30,000, on the reasoning that a
# yes or no about one sentence is a smaller job than surveying a page, so a
# smaller window would be cheaper on the high-volume path.
#
# That reasoning is fine and the conclusion was wrong, because the two numbers
# are not independent. A reader asked whether a page states a claim, shown less
# of the page than the reader who made the claim, will correctly report that it
# does not, and every one of those correct answers is a false disagreement.
#
# So it is not a smaller number that happens to match today. It is the same
# number, by construction, and it moves when the extractor's does.
MAX_CHARS = EXTRACTOR_WINDOW

PROMPT = """Below is the text of one page from an official government website, \
and one claim somebody has made about what that page says.

Answer one question: does this page state this claim?

Not whether the claim is true. Not whether it is usually true of this kind of \
visa. Only whether this page, in front of you, states it.

Reply with exactly one word on the first line, YES or NO. On the second line, \
give a short reason in one sentence.

PAGE:
{page}

CLAIM: {claim}
QUOTE THE CLAIM RESTS ON: {quote}
"""


def _quote_present(window: str, quote: str) -> bool:
    """Is the sentence the claim rests on inside the text we are handing over?

    Folded the same way `migragent/extract.py` folds a quote before checking it
    against a page, so this agrees with the check that let the requirement exist
    in the first place rather than inventing a second, stricter opinion.
    """
    if not quote:
        return True
    return _normalise(quote) in _normalise(window)


@dataclass
class Verdict:
    """What the second reader said, or why it did not say anything."""

    agreed: bool | None          # None means it never answered
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.agreed is not None

    @property
    def state(self) -> str:
        if self.agreed is None:
            return "unverified"
        return "agreed" if self.agreed else "disputed"


def enabled() -> bool:
    """Off unless switched on. A new reader does not get to be a default."""
    return os.environ.get("MIGRAGENT_SECOND_READ", "").strip().lower() in {"1", "true", "on", "yes"}


class SecondReader:
    """Gemma, asked whether a page says a thing."""

    def __init__(self, project: str, credentials) -> None:
        self._project = project
        self._credentials = credentials

    def check(self, page_text: str, claim: str, quote: str) -> Verdict:
        window = page_text[:MAX_CHARS]

        # The guard that makes D40 unrepeatable. If the sentence the claim rests
        # on is not in the text being handed over, then whatever comes back is
        # not an opinion about the claim, and a NO would be an artefact of the
        # window rather than a judgement about the page. There is nothing to ask.
        #
        # This is belt and braces now that the window is imported, and it stays,
        # because the previous version of this file was also correct on the day
        # it was written.
        if not _quote_present(window, quote):
            return Verdict(None, "the quote is outside the text the second reader was given")

        body = {
            "contents": [{"role": "user", "parts": [{"text": PROMPT.format(
                page=window, claim=claim, quote=quote)}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256},
        }
        try:
            payload = call_content(
                project=self._project, model=SECOND_MODEL, location=SECOND_LOCATION,
                credentials=self._credentials, body=body,
            )
        except ModelError as exc:
            # Unreachable is not disagreement. Say which one it was.
            return Verdict(None, f"the second reader did not answer: {exc}")
        except Exception as exc:  # noqa: BLE001
            return Verdict(None, f"the second reader did not answer: {type(exc).__name__}: {exc}")

        return _read(payload)


def _read(payload: dict) -> Verdict:
    """Turn a response into a verdict, or into an honest absence of one.

    A one word answer is asked for because the second reader is a smaller model
    and JSON from a smaller model is one more thing that can go wrong on a path
    whose whole job is to be more reliable than the path it is checking.
    """
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        return Verdict(None, "the second reader returned no candidates")

    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        return Verdict(None, "the second reader returned an empty answer")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    head = lines[0].upper().strip(".,:;!*_ ")
    reason = lines[1] if len(lines) > 1 else ""

    if head.startswith("YES"):
        return Verdict(True, reason)
    if head.startswith("NO"):
        return Verdict(False, reason or "the second reader said this page does not state it")

    # Neither word. Not a disagreement, just an answer we cannot read, and
    # treating an unreadable answer as a NO would delete requirements on the
    # strength of a formatting slip.
    return Verdict(None, f"the second reader did not answer YES or NO: {text[:120]}")


def review(reader: SecondReader, page_text: str, extraction) -> dict[str, int]:
    """Put every requirement in an extraction past the second reader.

    Mutates the extraction in place, because it is the same extraction: nothing
    new was read and no new requirement can be created here. A second reader can
    only ever move a requirement out of the guide, never into it.

    Returns the counts, because a check nobody can see the score of is a check
    nobody can trust. If `disputed` is always zero, this is theatre and the
    number is how we would find that out.
    """
    kept = []
    counts = {"agreed": 0, "disputed": 0, "unverified": 0}

    for requirement in extraction.requirements:
        verdict = reader.check(page_text, requirement.text, requirement.quote)
        counts[verdict.state] += 1

        if verdict.agreed is False:
            # Out of the guide, into the part of the product that admits doubt.
            extraction.open_questions.append(
                f"Two readers disagree about whether this page says: {requirement.text} "
                f"(the quote it rests on is \"{requirement.quote}\"; "
                f"the second reader said: {verdict.reason})"
            )
            continue

        requirement.second_read = verdict.state
        kept.append(requirement)

    extraction.requirements = kept
    return counts
