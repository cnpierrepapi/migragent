"""Building a CV for somebody who does not have one.

WHY THIS EXISTS
---------------
The work path opens with "upload your CV", and a large share of the people this
product is for do not have one. Not because they have not worked: because the
document is a convention of a labour market they have not been in yet. A welder
with nine years on site in Lagos may have a trade certificate, two references and
no two-page PDF, and telling that person to come back when they have one is
telling them to solve the problem they came here with.

So they answer questions instead, and the answers become the same `CV` object an
uploaded file produces. Everything downstream — the country filter, the shortage
match, the fit score, the country clones — works on it without knowing which way
it arrived.

THE ONE THING THAT IS DIFFERENT, AND IT IS NOT WHAT IT LOOKS LIKE
-----------------------------------------------------------------
An uploaded CV is read by a model, and `verified` on a claim means the model did
not invent it: the quote was found in the document's own text. That check exists
because a model that has read ten thousand CVs will happily award somebody
Python and stakeholder management for being a project manager.

Here there is no model between the person and the claim. They typed it. The text
they typed *is* the document, so every quote is trivially present in it, and
`verified` is true in the same sense and for a better reason. Nothing was
inferred by anything.

What this must never do is add. Not a duty that "obviously" goes with a job
title, not a skill implied by a certificate, not a language implied by a
country. If they did not type it, it is not here. That is the same rule as
everywhere else and it is easier to keep, because nothing here is guessing.

WHAT IT REFUSES
---------------
An empty CV. Somebody who types nothing gets told they have typed nothing rather
than getting an empty document that then matches no country and looks like the
product failing.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .cv import CV, Claim
from .clock import now_iso

# What the form asks for, in the order it asks. Each entry is the claim kind it
# produces, the label, and whether more than one may be given.
#
# Five fields, and the shortest set that can still drive the country filter: the
# roles do the shortage matching, and the rest is what a country's CV convention
# will ask for once the clone runs.
FIELDS = (
    ("role", "What do you do?",
     "Job titles you have held. One per line.", True),
    ("skill", "What can you do?",
     "Machines, tools, systems, languages you work in. One per line.", True),
    ("qualification", "What have you finished?",
     "Certificates, diplomas, degrees. One per line.", True),
    ("licence", "What are you licensed or registered to do?",
     "Trade tickets, professional registrations, driving categories. One per line.", True),
    ("language", "What languages do you speak?",
     "One per line. Add the level if you know it.", True),
)

MAX_LINES = 25
MAX_LINE = 200


def _lines(raw: str) -> list[str]:
    """One entry per line, trimmed, deduplicated, capped.

    Deduplication is case-insensitive and keeps the first spelling, because
    somebody who types "Welder" and "welder" meant one thing, and showing them
    two would look like the form doubling their work back at them.
    """
    out: list[str] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        value = re.sub(r"\s+", " ", line).strip(" ,;·-•\t")[:MAX_LINE]
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        out.append(value)
        if len(out) >= MAX_LINES:
            break
    return out


def build(answers: dict[str, str], name: str = "") -> CV:
    """Turn what somebody typed into the same CV object an upload produces.

    `answers` is keyed by claim kind, each value being the raw text of one box.
    Anything not in FIELDS is ignored rather than stored, so a posted form
    carrying an extra key cannot invent a claim kind.
    """
    now = now_iso()
    claims: list[Claim] = []

    for kind, _label, _hint, _many in FIELDS:
        for value in _lines(answers.get(kind, "")):
            claims.append(Claim(
                kind=kind,
                value=value,
                # The quote is the line they typed, which is the whole of the
                # document. Not a flourish: the number guard in drafts.py checks
                # generated text against the numbers in these quotes, so a year
                # typed here is a year a draft is allowed to use.
                quote=value,
                verified=True,
            ))

    return CV(
        filename=(f"{name.strip()}, written here" if name.strip()
                  else "Written here, not uploaded"),
        read_at=now,
        text_layer=True,
        claims=claims,
    )


def is_empty(cv: CV) -> bool:
    return not cv.claims


def missing_for_matching(cv: CV) -> str:
    """What is still needed before this CV can find a country, in one sentence.

    The country filter matches on roles. A CV of five skills and no job title
    will produce nothing, and the person will read that as the product having no
    countries for them rather than as a form they half filled in.
    """
    if not cv.claims:
        return "Nothing has been filled in yet."
    if not cv.of_kind("role"):
        return ("Add at least one job title. Countries publish the occupations "
                "they are short of, and a job title is what those lists are "
                "matched against.")
    return ""
