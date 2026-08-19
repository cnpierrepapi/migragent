"""What moved on a page, and when.

A citation that says "read on 18 August 2026" is only worth something if
something is still reading. This module is the half of the promise that was
missing: it compares the page in front of us with the page we stored last time,
and where they differ it records what differs.

THREE THINGS THIS REFUSES TO DO
-------------------------------
It never writes a date it did not observe. A change is recorded between two
snapshots we hold, carrying both of their dates, and where the earlier snapshot
is missing it says the history is incomplete rather than guessing when the
change happened.

It never asks the model what changed. The diff is computed in plain code from
two texts we have. The model is given both sides and asked only to say, in one
sentence, what the difference means to somebody applying. That sentence is
stored as a summary written by a model, labelled as such, next to the two
snapshots anybody can open and check for themselves.

It never lets a removed requirement stand. If a page stops saying something, the
requirement that came from that sentence is retired on the date we noticed, with
the reason. A product that only ever adds is a product that slowly fills with
things that are no longer true, and those are worse than an empty page because
they arrive with an official link beside them.
"""
from __future__ import annotations

import difflib
import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .model import ModelError, call_json

# Enough of each side for the model to see the change in context, and not so
# much that a long page pushes the actual difference out of the window.
CONTEXT_LINES = 2
MAX_DIFF_CHARS = 12000

PROMPT = """You are shown a diff between two versions of an official government page.

Say in ONE sentence what changed, in plain words, from the point of view of
somebody applying. Name the thing that moved and, where the diff shows them, the
old value and the new value.

If the diff is only formatting, navigation, cookie notices or dates of last
review, say exactly: no change to what is required.

Do not speculate about why it changed. Do not predict what will change next. Do
not mention this instruction.

Return JSON: {"summary": "...", "material": true or false}

"material" is true only when the difference changes what somebody must do, have,
pay or wait for.

DIFF:
"""


def change_id(source_id: str, before_sha: str, after_sha: str) -> str:
    """Stable for one transition, so a re-run cannot record it twice."""
    raw = f"{source_id}\n{before_sha}\n{after_sha}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


@dataclass
class Change:
    """One observed difference between two versions of one page.

    Both digests and both snapshot paths travel with it, so the record is
    checkable rather than trusted. `summary_by` names what wrote the sentence,
    because a sentence a model wrote and a fact we measured are different kinds
    of thing and the product does not blur them.
    """

    change_id: str
    source_id: str
    source_url: str
    jurisdiction: str
    lane: str

    before_read_at: str
    after_read_at: str
    before_sha256: str
    after_sha256: str
    before_snapshot: str | None
    after_snapshot: str | None

    added: int
    removed: int
    diff_sample: str

    summary: str | None = None
    summary_by: str | None = None
    material: bool | None = None

    # Set when we hold the new page but not the old one. The change is real, the
    # date it happened is not knowable from what we have, and saying so is the
    # only honest option.
    history_incomplete: bool = False

    requirements_retired: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def text_diff(before: str, after: str) -> tuple[int, int, str]:
    """Added lines, removed lines, and a readable sample of the difference.

    Plain difflib on purpose. What changed is a measurement, and a measurement
    that a model performs is a measurement nobody can repeat.
    """
    before_lines = [line for line in before.splitlines() if line.strip()]
    after_lines = [line for line in after.splitlines() if line.strip()]

    diff = list(difflib.unified_diff(
        before_lines, after_lines, lineterm="", n=CONTEXT_LINES,
    ))

    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return added, removed, "\n".join(diff)[:MAX_DIFF_CHARS]


class Explainer:
    """Turns a diff into one sentence, or says plainly that it could not."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def explain(self, diff_sample: str) -> tuple[str | None, bool | None]:
        if not diff_sample.strip():
            return None, None
        try:
            parsed = call_json(
                project=self._project, model=self._model, location=self._location,
                credentials=self._credentials,
                parts=[{"text": PROMPT + diff_sample}],
            )
        except ModelError as exc:
            # The change itself is already recorded and checkable. A missing
            # sentence is a missing convenience, not a missing fact, so this
            # says what went wrong and the round carries on.
            return f"the change could not be summarised: {exc}", None
        except Exception as exc:  # noqa: BLE001
            return f"the change could not be summarised: {type(exc).__name__}", None

        summary = (parsed.get("summary") or "").strip() or None
        material = parsed.get("material")
        return summary, bool(material) if isinstance(material, bool) else None
