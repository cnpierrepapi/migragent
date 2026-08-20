"""The CV rewritten for one listing, and the cover letter, both as drafts.

THE RULE THAT MATTERS MOST HERE
-------------------------------
A rewrite is the easiest place in this whole product to lie about somebody. Ask
a model to make a CV fit a job and it will help: it will round three years to
five, add a certification the role asks for, and turn "trained four apprentices"
into "led a team of twelve". The person then sends that to an employer under
their own name.

So the only material a rewrite may use is what the CV already claimed, and that
is enforced twice:

1. The prompt is given the claims and nothing else. It never sees the CV text,
   so it cannot lift a half remembered detail out of it.
2. Every number and year in the finished draft is checked against the numbers in
   the person's own claims. Anything that is not there is listed on the draft
   itself, in front of the person, naming exactly what to check.

The second check is the one that counts, because the first is a request and this
one is arithmetic. It is deliberately narrow: numbers are where the damage is,
and a checker that tried to verify every adjective would flag everything and be
switched off within a week.

WHAT IS NOT CLAIMED HERE
------------------------
Layout advice is convention, not law. No government publishes a CV format, and
the ones that publish guidance publish it as guidance. So a draft says which
country it is shaped for and says plainly that the shape is convention. It never
borrows the guide's authority, because the guide's authority comes from citing a
government page and there is no government page behind "put your education last".

Everything here is a draft and says so on its face. The person sends the
application.
"""
from __future__ import annotations

import re
from typing import Any

from .board import Piece
from .cv import CV
from .model import call_json

# Country conventions, as conventions. Short on purpose: the honest version of
# this is a few widely observed habits, not a style guide nobody can source.
CONVENTIONS = {
    "CA": ("Canada", "Two pages at most. No photograph, no date of birth, no marital status. "
                     "Employers expect results with numbers on them."),
    "UK": ("the United Kingdom", "Two pages at most. No photograph, no date of birth. "
                                 "A short personal statement at the top is usual."),
    "FR": ("France", "One or two pages. A photograph is still common and is not required."),
    "ES": ("Spain", "One or two pages. A photograph is common. Language levels are usually "
                    "stated on the CEFR scale."),
    "DE": ("Germany", "A tabular CV in reverse date order. Gaps are expected to be explained."),
    "AE": ("the United Arab Emirates", "Two pages. Nationality and visa status are commonly "
                                       "asked for and it is your choice whether to give them."),
}

CONVENTION_NOTE = ("This shape is convention, not a rule, and no government publishes a required "
                   "CV format. Nothing here is guidance from an official source.")

DRAFT_NOTE = "A draft. Read every line before you send it. You send the application, not us."

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text or "")}


def _claims_block(cv: CV) -> str:
    lines = []
    for claim in cv.claims:
        detail = f" ({claim.detail})" if claim.detail else ""
        mark = "" if claim.verified else "  [unverified: read from a scan]"
        lines.append(f'- {claim.kind}: {claim.value}{detail}{mark}')
    return "\n".join(lines)


def _listing_block(listing: dict[str, Any]) -> str:
    parts = [f"Title: {listing.get('title')}"]
    for key in ("employer", "location", "salary", "matched_occupation"):
        if listing.get(key):
            parts.append(f"{key.replace('_', ' ').title()}: {listing[key]}")
    return "\n".join(parts)


CV_PROMPT = """You are rewriting one person's CV for one specific job.

You may use ONLY the claims listed below. They were read out of the person's own
CV and checked against it. You may reorder them, group them, and put the ones
this job asks for first. You may not add anything else.

Never invent a number. Do not state years of experience, team sizes, percentages
or salaries unless that exact number appears in a claim below. If you are unsure
how long somebody did something, say what the claim says and no more.

Return JSON: {"headline": "...", "summary": "...", "sections": [{"heading": "...", "lines": ["..."]}]}

"summary" is two sentences at most, in the person's own register, saying what
they do and what this job asks for that they have.
"""

LETTER_PROMPT = """You are drafting a cover letter for one person for one job.

You may use ONLY the claims listed below, which were read out of their own CV.
Do not invent numbers, do not claim enthusiasm they have not expressed, and do
not say anything about their visa status, their right to work, or how quickly
they could start. None of that is known here and an employer will ask.

Three short paragraphs at most, plain language, no flattery about the company.

Return JSON: {"letter": "..."}
"""


class Drafter:
    """Writes the drafts a board item carries."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _call(self, prompt: str) -> dict[str, Any]:
        return call_json(project=self._project, model=self._model,
                         location=self._location, credentials=self._credentials,
                         parts=[{"text": prompt}], temperature=0.2)

    def _invented_numbers(self, text: str, cv: CV) -> list[str]:
        """Numbers in the draft that are in no claim the person made.

        Years the person never worked and team sizes they never managed are the
        specific harm this catches. Small numbers are ignored: "three paragraphs"
        and "2 years" collide with ordinary prose, and a checker that cries at
        every "1" is a checker nobody reads.
        """
        theirs = set()
        for claim in cv.claims:
            theirs |= _numbers(claim.value) | _numbers(claim.quote or "") \
                      | _numbers(claim.detail or "")
        return sorted(n for n in _numbers(text) - theirs if len(n) > 1)

    def rewrite_cv(self, cv: CV, listing: dict[str, Any], jurisdiction: str) -> Piece:
        place, convention = CONVENTIONS.get(
            jurisdiction, (jurisdiction, "No convention is recorded for this country here."))

        prompt = (CV_PROMPT
                  + f"\n\nTHE JOB:\n{_listing_block(listing)}"
                  + f"\n\nTHE CLAIMS (all you may use):\n{_claims_block(cv)}"
                  + f"\n\nShaped for {place}. {convention}")

        try:
            parsed = self._call(prompt)
        except Exception as exc:  # noqa: BLE001
            return Piece(kind="cv", title="CV for this job",
                         body="", note=f"This could not be drafted: {exc}")

        body = [str(parsed.get("headline") or "").strip(),
                str(parsed.get("summary") or "").strip(), ""]
        for section in parsed.get("sections", []):
            body.append(str(section.get("heading") or "").upper())
            body += [f"  {str(line).strip()}" for line in section.get("lines", [])]
            body.append("")
        text = "\n".join(line for line in body if line is not None).strip()

        return Piece(kind="cv", title=f"CV for this job, shaped for {place}",
                     body=text, note=self._note(text, cv, convention))

    def cover_letter(self, cv: CV, listing: dict[str, Any], jurisdiction: str) -> Piece:
        prompt = (LETTER_PROMPT
                  + f"\n\nTHE JOB:\n{_listing_block(listing)}"
                  + f"\n\nTHE CLAIMS (all you may use):\n{_claims_block(cv)}")

        try:
            parsed = self._call(prompt)
        except Exception as exc:  # noqa: BLE001
            return Piece(kind="cover_letter", title="Cover letter",
                         body="", note=f"This could not be drafted: {exc}")

        text = str(parsed.get("letter") or "").strip()
        return Piece(kind="cover_letter", title="Cover letter",
                     body=text, note=self._note(text, cv, None))

    def _note(self, text: str, cv: CV, convention: str | None) -> str:
        parts = [DRAFT_NOTE]
        if convention:
            parts.append(CONVENTION_NOTE)
        invented = self._invented_numbers(text, cv)
        if invented:
            parts.append("Check these numbers before you send it, because they are not in "
                         "your CV: " + ", ".join(invented) + ".")
        if any(not c.verified for c in cv.claims):
            parts.append("Some of this came from a scan with no text layer, so it could not be "
                         "checked against your document.")
        return " ".join(parts)
