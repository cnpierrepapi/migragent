"""Which countries are open to *this* person, worked out from their documents.

THE INVERSION
-------------
Every build until now asked somebody to pick a country and then told them what it
would take. That is backwards, and it is backwards in the way that matters: a
person who does not already know that Canada is short of welders cannot choose
Canada for being short of welders. Asking them to pick first makes them do the
research the product exists to do.

So nothing is picked first. They say what they do, they upload what they have,
and the countries that appear are the ones whose own published lists say they
want somebody like them. A country a person is not eligible for is never shown,
because showing it means either a wasted week or a refusal with a fee attached.

WHAT MAKES A COUNTRY ELIGIBLE
-----------------------------
Work: the country publishes a shortage list, and something the CV states matches
something on it. The match carries the government's own sentence naming the
occupation, so the reason a country appeared can always be shown.

Study: the country has a school on its own register that teaches the level the
transcripts point at, with an intake open for the coming year. That needs school
course data, and where it is missing this returns nothing for that country
rather than guessing. A country that appears because we could not check is worse
than a country that does not appear.

WHAT THIS IS NOT
----------------
It is not a prediction that an application will succeed. It is a statement that
the country has published something that fits, which is a much smaller claim and
the only one the evidence supports. Nothing here scores a person.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .listings import _words


@dataclass
class Reason:
    """Why one country appeared, in a form that can be shown to the person.

    `quote` is the government's own sentence. It is not optional: a country that
    cannot say in its own words why it wants this person does not qualify, and
    an eligibility with no quote is a recommendation, which is a different and
    much larger claim than this product makes.
    """

    matched: str
    quote: str
    source_url: str = ""
    because: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Eligible:
    """One country a person can actually go to, and the evidence that they can."""

    jurisdiction: str
    lane: str
    reasons: list[Reason] = field(default_factory=list)

    # How much has been read for this country and lane. Carried so the page can
    # be honest about a country that qualifies on a thin corpus, rather than
    # showing it beside one with six hundred requirements as though they were
    # the same offer.
    requirements: int = 0
    postings: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"jurisdiction": self.jurisdiction, "lane": self.lane,
                "requirements": self.requirements, "postings": self.postings,
                "reasons": [r.to_dict() for r in self.reasons]}


def work_countries(roles: list[str],
                   shortages_by_country: dict[str, list[dict[str, Any]]],
                   requirements: dict[str, int] | None = None,
                   postings: dict[str, int] | None = None) -> list[Eligible]:
    """Countries whose published shortage list matches something this CV says.

    The matching is the same dull word overlap `listings.matched_for` uses, and
    for the same reason: a model deciding that a pipefitter is basically a welder
    would be making a claim about somebody's career that nobody asked it to make,
    and the person would have no way to see where it came from. Overlap can be
    shown, and it is: every reason carries the role from the CV that produced it.
    """
    requirements = requirements or {}
    postings = postings or {}
    role_words = [(role, _words(role)) for role in roles if role and role.strip()]
    out: list[Eligible] = []

    for jurisdiction, occupations in sorted(shortages_by_country.items()):
        reasons: list[Reason] = []
        seen: set[str] = set()

        for occupation in occupations:
            title = occupation.get("title") or ""
            against = _words(title)
            best_role, best = None, 0
            for role, words in role_words:
                shared = len(words & against)
                if shared > best:
                    best_role, best = role, shared
            if not best or title.lower() in seen:
                continue
            seen.add(title.lower())
            reasons.append(Reason(
                matched=title,
                quote=occupation.get("quote", ""),
                source_url=occupation.get("source_url", ""),
                because=best_role or "",
            ))

        if not reasons:
            continue
        # Strongest first, so the reason shown at the top of a country card is
        # the one that most nearly describes what the person actually does.
        reasons.sort(key=lambda r: -len(_words(r.matched) & _words(r.because)))
        out.append(Eligible(
            jurisdiction=jurisdiction, lane="work", reasons=reasons,
            requirements=requirements.get(jurisdiction, 0),
            postings=postings.get(jurisdiction, 0),
        ))

    return out


def study_countries(level: str, subjects: list[str],
                    courses_by_country: dict[str, list[dict[str, Any]]],
                    requirements: dict[str, int] | None = None) -> list[Eligible]:
    """Countries with a school teaching this level and subject, intake open.

    Two gates, both from data a school or a government published:

      the level      a transcript pointing at a bachelor's does not produce a
                     country whose matching courses are all doctorates
      the subject    word overlap again, against the course title

    THE INTAKE IS NOT A GATE, and that is a deliberate reversal.

    It was one: a course whose next intake was not open did not appear. That
    made the whole study path collapse to nothing, because course index pages
    list names and put dates on the individual course pages, so almost no course
    carried an intake at all. The effect was a person being told there is
    nowhere for them to go, when what had actually happened is that we had not
    read a date yet. Absence of a date is not a closed door.

    Intake dates are also the thing somebody subscribes for: they arrive with
    the alerts, which is what the subscription is. Using them to decide who sees
    a country at all would mean withholding the existence of an option to sell
    the timing of it, and that is not a trade this product makes. Everybody sees
    every country they qualify for. Paying tells you when to move.

    A country with no course data still returns nothing rather than everything.
    That is the difference between "we checked and there is nothing" and "we did
    not check", and only the first is worth putting in front of somebody.
    """
    requirements = requirements or {}
    subject_words = [(s, _words(s)) for s in subjects if s and s.strip()]
    out: list[Eligible] = []

    for jurisdiction, courses in sorted(courses_by_country.items()):
        reasons: list[Reason] = []
        seen: set[str] = set()

        for course in courses:
            if level and (course.get("level") or "") != level:
                continue

            title = course.get("title") or ""
            against = _words(title)
            best_subject, best = None, 0
            for subject, words in subject_words:
                shared = len(words & against)
                if shared > best:
                    best_subject, best = subject, shared
            # No subject stated is not a failure. Somebody whose transcripts say
            # what they studied and not what they want next is the normal case,
            # and every course at the right level is genuinely an option for
            # them.
            if subject_words and not best:
                continue

            key = f"{course.get('institution', '')}|{title}".lower()
            if key in seen:
                continue
            seen.add(key)
            reasons.append(Reason(
                matched=f"{title} at {course.get('institution', '')}".strip(),
                quote=course.get("quote", ""),
                source_url=course.get("source_url", ""),
                because=best_subject or level,
            ))

        if not reasons:
            continue
        reasons.sort(key=lambda r: -len(_words(r.matched) & _words(r.because)))
        out.append(Eligible(
            jurisdiction=jurisdiction, lane="study", reasons=reasons,
            requirements=requirements.get(jurisdiction, 0),
        ))

    return out


# What a transcript points at next. A bachelor's in hand points at a master's,
# and this is the ladder rather than a judgement about the person.
NEXT_LEVEL = {
    "secondary": "bachelors",
    "bachelors": "masters",
    "masters": "doctorate",
    "doctorate": "doctorate",
}

LEVEL_NAMES = {
    "bachelors": "a bachelor's degree",
    "masters": "a master's degree",
    "doctorate": "a doctorate or professional doctorate",
}


def next_level(highest_held: str) -> str:
    """The level somebody with this qualification is most likely applying for.

    Most likely, and not certainly: somebody with a master's may well want a
    second one, and somebody with a bachelor's may want a conversion course. So
    this decides what to show first and never decides what somebody may have.
    The screen that uses it says which level it assumed and lets it be changed
    in one tap.
    """
    return NEXT_LEVEL.get((highest_held or "").lower().strip(), "bachelors")
