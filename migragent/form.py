"""The form generated for one case.

Not an intake form. By the time this is built we already know the lane, we have
read the requirements, and we know which of them the uploads answered. So this
asks only what is still unknown, which is a much shorter and much less annoying
form than the one a person would have filled in at the start.

WHAT AN ANSWER HERE IS WORTH
----------------------------
Less than a document, and the product says so everywhere it appears.

A field read off a passport carries a quote from the passport. An answer typed
into this form carries nothing but the typing. Both are useful and they are not
the same thing, so an answered question is recorded as **declared** and never as
evidenced, it is shown as declared in the guide, and it is counted separately in
the score.

Collapsing that distinction would be the easiest way to make the number go up and
the fastest way to make it worthless.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

ANSWER_TYPES = ("yes_no", "date", "text", "amount", "choice")

# A question may not claim to settle more than this share of what is open.
#
# Measured, not guessed. Against 92 open Canada study requirements the generator
# produced "Do you agree to follow all application procedures and comply with all
# study permit conditions while in Canada?", claiming to settle 32 of them. That
# is not a question, it is a checkbox, and a yes would have moved the score by a
# third of the lane on the strength of somebody agreeing to behave.
#
# A real question is about one thing. A question covering a third of an
# application is covering nothing.
MAX_SETTLED_SHARE = 0.15
MIN_SETTLED_CAP = 6


@dataclass
class Question:
    """One thing we still need to know, and what it would settle."""

    key: str
    prompt: str
    answer_type: str = "text"
    choices: list[str] = field(default_factory=list)
    settles: list[str] = field(default_factory=list)
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseForm:
    case_id: str
    generated_at: str
    questions: list[Question] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "generated_at": self.generated_at,
            "questions": [q.to_dict() for q in self.questions],
            "dropped": self.dropped,
        }


PROMPT = """A person is applying, and we already know which requirements their \
uploaded documents answer. Below are the requirements still unanswered.

Write the SHORTEST set of questions that would tell us where they stand on these. \
Group requirements that one question settles: if six requirements are all about \
proof of funds, that is one question, not six.

UNANSWERED REQUIREMENTS (id, then text):
{gaps}

Return JSON:
{{"questions": [
  {{"key": "short_snake_case_key",
    "prompt": "the question, second person, plain words, one sentence",
    "answer_type": "one of yes_no, date, text, amount, choice",
    "choices": ["only for choice, else empty"],
    "settles": ["<requirement ids this question would settle>"],
    "why": "one short sentence on what this tells us"}}
]}}

Rules:
- Every id in "settles" MUST come from the list above. Anything else is discarded.
- At most 12 questions. Fewer is better.
- Never ask for a document. Documents are uploaded, not typed.
- Never ask something the requirements above do not actually turn on."""


class FormBuilder:
    """Turns the remaining gaps into the shortest form that would close them."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _call(self, prompt: str) -> dict[str, Any]:
        import urllib.request

        import google.auth.transport.requests

        self._credentials.refresh(google.auth.transport.requests.Request())
        url = (f"https://aiplatform.googleapis.com/v1/projects/{self._project}"
               f"/locations/{self._location}/publishers/google/models/{self._model}"
               f":generateContent")
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._credentials.token}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.load(response)
        parts = payload["candidates"][0]["content"]["parts"]
        return json.loads("".join(p.get("text", "") for p in parts))

    def build(self, case_id: str, generated_at: str,
              gaps: list[dict[str, str]]) -> CaseForm:
        form = CaseForm(case_id=case_id, generated_at=generated_at)
        if not gaps:
            return form

        valid = {g.get("requirement_id", "") for g in gaps}
        cap = max(MIN_SETTLED_CAP, int(len(valid) * MAX_SETTLED_SHARE))
        listing = "\n".join(
            f'- {g.get("requirement_id","")}: {g.get("text","")}' for g in gaps[:150])

        try:
            parsed = self._call(PROMPT.format(gaps=listing))
        except Exception as exc:  # noqa: BLE001
            form.dropped.append({"why": f"{type(exc).__name__}: {exc}"})
            return form

        seen: set[str] = set()
        for item in parsed.get("questions", []):
            key = str(item.get("key") or "").strip()
            prompt = str(item.get("prompt") or "").strip()
            if not key or not prompt or key in seen:
                continue

            settles = [s for s in (item.get("settles") or []) if s in valid]
            if not settles:
                # A question that settles nothing we are actually missing is a
                # question asked for its own sake, and the promise of this form
                # is that it only asks what is still open.
                form.dropped.append({
                    "key": key,
                    "why": "settles no requirement that is actually unanswered",
                })
                continue

            if len(settles) > cap:
                form.dropped.append({
                    "key": key,
                    "why": (f"claims to settle {len(settles)} of {len(valid)} open "
                            f"requirements, over the cap of {cap}. A question that "
                            f"broad is a checkbox, not a question"),
                })
                continue

            answer_type = item.get("answer_type")
            form.questions.append(Question(
                key=key,
                prompt=prompt,
                answer_type=answer_type if answer_type in ANSWER_TYPES else "text",
                choices=[str(c) for c in (item.get("choices") or [])][:8],
                settles=settles,
                why=str(item.get("why") or ""),
            ))
            seen.add(key)

        return form
