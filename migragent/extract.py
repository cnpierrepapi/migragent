"""Turning a page we have read into requirements we can cite.

THE ONE RULE THIS FILE EXISTS TO ENFORCE
----------------------------------------
A model says what a requirement means. It never says where the requirement came
from, and it never gets to decide that a requirement exists.

The citation is assembled here from the `Fetched` object: the URL that was
actually requested, and the timestamp taken from the clock when the bytes
arrived. Neither value is ever put in a prompt or read back out of a response,
so no arrangement of words from a model can produce a source that was not
fetched.

That handles invented URLs. It does nothing about invented *requirements*, which
is the likelier failure: a model that has read a thousand immigration pages will
happily tell you a study permit needs a police certificate, whether or not this
page says so. So every extracted requirement must carry a **verbatim quote** from
the page, and every quote is checked against the page text before the
requirement is allowed to exist. A quote that is not in the text means the
requirement is dropped, counted, and reported.

That check is the difference between a guide and a plausible-looking list, and it
is the reason `dropped` is returned alongside `requirements` rather than being
swallowed. A run that drops nine of ten needs to say so.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .fetcher import Fetched, decode_body
from .model import call_json

_SCRIPT = re.compile(r"<script\b.*?</script\s*>", re.I | re.S)
_STYLE = re.compile(r"<style\b.*?</style\s*>", re.I | re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|tr|section|article|br)\s*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")

# How much of a page goes to the model. Government pages are mostly navigation
# and footer even after stripping, and the requirement text is near the top.
MAX_CHARS = 30_000


def page_text(page: Fetched) -> str:
    """The visible words of a page, as plain code.

    No model, no readability heuristic guessing which div is "the content". A
    guess about which part of a page matters is the mistake in INHERITED.md, and
    here it would silently decide which requirements are allowed to be found.
    """
    if not page.ok or page.body is None:
        return ""
    html = decode_body(page.body, page.content_type)
    html = _SCRIPT.sub(" ", html)
    html = _STYLE.sub(" ", html)
    html = _COMMENT.sub(" ", html)
    html = _BLOCK_END.sub("\n", html)
    text = _TAG.sub(" ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANKS.sub("\n\n", text).strip()


# Keeps case and accents. Re-exported as _normalise because verify.py,
# lanes.py and researcher.py import it from here.
from .fold import fold as _normalise  # noqa: E402


@dataclass
class Requirement:
    """One thing an applicant must do or have, with the line that proves it."""

    text: str
    quote: str
    category: str = "requirement"
    cost: str | None = None
    duration: str | None = None
    depends_on: str | None = None

    # Assembled from the fetch. Never from the model.
    source_url: str = ""
    read_at: str = ""
    source_language: str = ""
    provenance: str = "official"
    jurisdiction: str = ""
    lane: str = ""

    # What the second reader made of it: agreed, or unverified because it could
    # not be reached. A disputed requirement never becomes one of these, because
    # it never becomes a requirement at all. See migragent/verify.py.
    second_read: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Extraction:
    """What one page produced, including what it failed to produce."""

    source_url: str
    read_at: str
    requirements: list[Requirement] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    model_error: str | None = None

    @property
    def kept(self) -> int:
        return len(self.requirements)


PROMPT = """You are reading one page from an official government website about \
immigration, study or work permits.

List only the requirements this page ITSELF states. A requirement is something \
an applicant must do, have, pay, or prove.

For each one, return:
  "text": the requirement in plain words, one sentence, second person
  "quote": a VERBATIM span copied exactly from the page text below, which states \
this requirement. Copy it character for character. Do not paraphrase, do not \
join two separate sentences, do not correct spelling.
  "category": one of requirement, cost, timing, eligibility, document
  "cost": the amount if the page states one, else null
  "duration": how long it takes if the page states one, else null
  "depends_on": what must happen first if the page says so, else null

Rules you must follow:
- If this page does not state any requirement, return an empty list. An empty \
list is a correct and useful answer.
- Never add a requirement you know from elsewhere. Only what is on this page.
- The "quote" must appear word for word in the page text. It will be checked \
automatically and anything that does not match will be discarded.
- Write "text" in the same language as the page.

Also return "open_questions": things this page refers to but does not state, \
which a reader would still need to know.

Return only JSON: {"requirements": [...], "open_questions": [...]}

PAGE TEXT:
"""


class Extractor:
    """Reads a page with Gemini and keeps only what the page can be shown to say."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _call(self, prompt: str):
        """Delegates to migragent.model, which retries and reports properly.

        Every caller used to carry its own copy of this and none of them
        retried, so one run hitting the quota produced three unrelated
        looking symptoms. See D20.
        """
        return call_json(
            project=self._project, model=self._model,
            location=self._location, credentials=self._credentials,
            parts=[{"text": prompt}],
        )

    def extract(
        self, page: Fetched, jurisdiction: str, lane: str, language: str,
        provenance: str = "official",
    ) -> Extraction:
        # The citation is built here, from the fetch, before the model is even
        # called. It cannot be influenced by anything the model returns.
        result = Extraction(source_url=page.final_url or page.url, read_at=page.read_at)

        text = page_text(page)
        if not text:
            result.model_error = "no readable text on the page"
            return result

        try:
            parsed = self._call(PROMPT + text[:MAX_CHARS])
        except Exception as exc:  # noqa: BLE001
            result.model_error = str(exc)
            return result

        haystack = _normalise(text)
        result.open_questions = [str(q) for q in parsed.get("open_questions", []) if q]

        for item in parsed.get("requirements", []):
            quote = str(item.get("quote") or "").strip()
            statement = str(item.get("text") or "").strip()

            if not quote or not statement:
                result.dropped.append({"text": statement, "why": "no quote given"})
                continue

            # The check. A requirement whose quote is not on the page is a
            # requirement this page did not state, whatever else it may be.
            if _normalise(quote) not in haystack:
                result.dropped.append({
                    "text": statement,
                    "quote": quote,
                    "why": "the quote is not on the page",
                })
                continue

            result.requirements.append(Requirement(
                text=statement,
                quote=quote,
                category=str(item.get("category") or "requirement"),
                cost=item.get("cost") or None,
                duration=item.get("duration") or None,
                depends_on=item.get("depends_on") or None,
                source_url=result.source_url,
                read_at=result.read_at,
                source_language=language,
                provenance=provenance,
                jurisdiction=jurisdiction,
                lane=lane,
            ))

        return result
