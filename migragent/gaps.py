"""What a course does not tell us, and where to go and ask.

THE RULE
--------
A course is shown if we know anything about it at all. Not if we know the fee,
not if we know the intake, not if the row is complete: if it exists and we read
it, it is offered. Every field we could not read becomes a question with a link
to the school's own contact page attached.

WHY, BECAUSE THIS IS THE OPPOSITE OF WHAT SOFTWARE USUALLY DOES
----------------------------------------------------------------
The instinct is to hide incomplete rows, because a card with three blanks looks
unfinished and a card with everything filled in looks professional. That instinct
optimises for how the product looks and pays for it with what the person can do.

A course we know the name and level of, at a school on the official register, is
genuinely useful to somebody even with no fee attached. They can go and ask. What
is not useful is being shown nothing and concluding there is nothing, which is
what hiding produces and which is indistinguishable, from the outside, from us
having nothing to say.

This product already refuses to invent a fee. The gap is going to exist. The only
question is whether the gap is an apology or a next step, and a link to the
admissions office is a next step.

WHY THE LINK GOES TO THE SCHOOL AND NOT TO US
-----------------------------------------------
We do not know the answer. The school does. Routing somebody through a form we
own so we can capture their email first, and then telling them to email the
school anyway, would be charging them a toll for a road we did not build.

WHAT IT NEVER SAYS
------------------
It never says "fee not available" as though the fee does not exist, and it never
shows a blurred or greyed placeholder implying we are withholding it. A missing
fee and a withheld intake date are different things and the person can tell them
apart: `entitlements.py` handles the second and says plainly that a subscription
reveals it. This module handles the first and says plainly that we do not know.
"""
from __future__ import annotations

from typing import Any

# The fields worth asking a school about, in the order a person cares. Each is
# the field name, the label, and the question to put in front of the link.
ASKABLE = (
    ("fee_international", "Tuition",
     "What does this cost for an international student?"),
    ("intake", "Intake",
     "When does this course start, and when do applications close?"),
    ("entry_requirements", "Entry requirements",
     "What do I need to already have to apply?"),
    ("duration", "Length", "How long is this course?"),
)


def missing(course: dict[str, Any]) -> list[dict[str, str]]:
    """The fields this course does not carry, as questions to ask.

    A field withheld by the paywall is NOT missing and never appears here. The
    person has not been told the intake because they have not subscribed, which
    is a different sentence from us not knowing it, and merging the two would
    tell somebody to email a school about something we are sitting on.
    """
    withheld = bool(course.get("intake_withheld"))
    out: list[dict[str, str]] = []
    for field, label, question in ASKABLE:
        if course.get(field):
            continue
        if field == "intake" and withheld:
            continue
        out.append({"field": field, "label": label, "question": question})
    return out


def ask_url(course: dict[str, Any], institution: dict[str, Any] | None = None) -> str:
    """Where to send somebody with a question about this course.

    In order of how likely it is to reach a person who knows:

      the school's contact page   found on the shallow pass
      the course's own page       it carries the department's details often
                                  enough, and it is certainly about this course
      the school's home page      always something

    Never an empty link. A CTA that goes nowhere is worse than no CTA, because
    somebody clicks it and learns that the product is broken rather than that
    the school is worth emailing.
    """
    institution = institution or {}
    for candidate in (institution.get("contact_url"),
                      course.get("detail_url"),
                      course.get("source_url"),
                      institution.get("website")):
        if candidate:
            return str(candidate)
    return ""


def completeness(course: dict[str, Any]) -> tuple[int, int]:
    """How many of the askable fields this course carries, out of how many.

    For ordering only, and gently: a course we know more about is more useful to
    show first. It is never a filter and never a score on a screen. A school
    whose website is hard to read is not a worse school.
    """
    have = sum(1 for field, _l, _q in ASKABLE if course.get(field))
    return have, len(ASKABLE)


def with_gaps(courses: list[dict[str, Any]],
              institutions: dict[str, dict[str, Any]] | None = None
              ) -> list[dict[str, Any]]:
    """Every course, none dropped, each carrying its own questions and link.

    The list is sorted by how much we know, most first, so the fullest cards lead
    and the thinnest are still there underneath rather than cut. Nothing is
    removed by this function, which is the entire point of it.
    """
    institutions = institutions or {}
    out: list[dict[str, Any]] = []
    for course in courses:
        row = dict(course)
        school = institutions.get(course.get("institution", ""), {})
        row["gaps"] = missing(course)
        row["ask_url"] = ask_url(course, school)
        row["known"], row["askable"] = completeness(course)
        out.append(row)

    out.sort(key=lambda r: (-r["known"], r.get("title", "")))
    return out
