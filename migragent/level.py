"""What somebody's transcripts say they hold, and what that points at next.

WHY THIS IS RULES AND NOT A MODEL CALL
---------------------------------------
The question is small and closed: does this document represent secondary school,
a bachelor's, a master's or a doctorate. The world publishes those names, they
repeat, and a table of them is inspectable in a way a model's opinion is not.

It also has to work on a WASSCE slip, an NECO result, a Nigerian ND or HND, an
Indian B.Tech and a French licence, and the failure mode of a model here is
quiet and specific: it maps an unfamiliar qualification onto the nearest
familiar one and returns "bachelors" for a school certificate with total
confidence. A table returns nothing for a name it does not know, which is the
answer that leads to asking the person rather than guessing at their life.

WHAT IT DOES WITH WHAT IT FINDS
--------------------------------
It reports the HIGHEST level any document evidences, and it says which document
and which words produced that. The screen then shows what it worked out and lets
it be changed in one tap, because "most likely" is not "certainly": somebody
with a master's may want a second one, and somebody with a bachelor's may want a
conversion course. The product decides what to show first and never decides what
somebody may have.

WHY SECONDARY MATTERS MOST HERE
--------------------------------
The largest group of people this is for are finishing secondary school with a
WASSCE or NECO result and applying for a first degree. Getting that group right
matters more than any other row in the table, so those names come first and are
matched most carefully.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Ordered, because the answer is the highest thing found and "highest" needs an
# order. Nothing outside this list is a level.
LEVELS = ("secondary", "bachelors", "masters", "doctorate")

RANK = {name: i for i, name in enumerate(LEVELS)}

# Names as they are actually printed on documents, lowercased. Matched as whole
# words against the qualification text, so "bsc" does not fire inside "bsce" and
# "ba" does not fire inside "basic".
#
# Every entry here is a real award name. Nothing is guessed at from an acronym
# that could be several things: "PGD" is a postgraduate diploma in one country
# and something else in another, so it is absent rather than assumed.
NAMES: dict[str, tuple[str, ...]] = {
    "secondary": (
        # West Africa first, deliberately: this is the largest group of people
        # this product is for, and getting them wrong sends a school leaver to a
        # master's course.
        "wassce", "waec", "west african senior school certificate",
        "senior school certificate", "ssce", "neco",
        "national examinations council", "gce ordinary level", "o level",
        "o'level", "gce advanced level", "a level", "a'level",
        "high school diploma", "secondary school certificate",
        "matriculation certificate", "baccalaureate", "baccalaur", "abitur",
        "kcse", "matric",
    ),
    "bachelors": (
        "bachelor", "bsc", "b sc", "b.sc", "ba", "b a", "b.a", "beng", "b eng",
        "btech", "b tech", "b.tech", "llb", "mbbs", "bcom", "b com",
        "bachelor of science", "bachelor of arts", "first degree",
        # NOT bare "licence" either, for the same reason: a driving licence and
        # a welding licence are both licences, and only in France is a Licence a
        # degree. Missing a French bachelor's costs one tap to correct. Reading a
        # trade licence as a degree sends somebody to the wrong courses and they
        # have no way of knowing why.
        "licenciatura", "laurea", "undergraduate degree",
        # Nigerian polytechnic awards. An HND is not a bachelor's everywhere and
        # is treated as one here because it is the level somebody progresses
        # FROM in the same way, which is the only question being asked.
        "hnd", "higher national diploma",
    ),
    "masters": (
        # NOT bare "master". A great many of the people this product is for hold
        # a Master Electrician or Master Plumber certificate, and reading that as
        # a master's degree would show a tradesperson a list of postgraduate
        # courses. "Master of" and "masters" are degrees; "master" alone is a
        # rank in a trade at least as often.
        "masters", "master s", "master of", "msc", "m sc", "m.sc", "ma", "m a",
        "m.a", "meng", "m eng", "mtech", "m tech", "mba", "llm", "mphil",
        "m phil", "postgraduate degree", "maitrise", "maestria", "magister",
    ),
    "doctorate": (
        "phd", "ph d", "ph.d", "dphil", "doctorate", "doctoral",
        "doctor of philosophy", "dba", "edd", "ed d", "doctorat", "doctorado",
    ),
}

# Which document kinds are worth reading for this at all. A passport says
# nothing about education and a bank statement says nothing about anything here.
KINDS = ("transcript", "degree_certificate", "offer_letter", "other")

# Fields on a read document whose values are worth matching against.
FIELDS = ("qualification", "award", "degree", "programme", "program", "course",
          "certificate", "issuing_authority", "examination", "level")


@dataclass
class Reading:
    """The level found, and exactly what produced it."""

    held: str = ""
    quote: str = ""
    filename: str = ""
    field_name: str = ""
    candidates: list[str] = field(default_factory=list)

    # What they studied, filled in by the caller from subjects_from_documents.
    # Carried here so the screen can show it beside the level it assumed.
    subjects: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.held)

    def to_dict(self) -> dict[str, Any]:
        return {"held": self.held, "quote": self.quote, "filename": self.filename,
                "field_name": self.field_name, "candidates": self.candidates}


def _matches(text: str) -> list[str]:
    """Which levels this string names, if any."""
    lowered = f" {re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()} "
    out = []
    for level, names in NAMES.items():
        for name in names:
            needle = re.sub(r"[^a-z0-9]+", " ", name).strip()
            if f" {needle} " in lowered:
                out.append(level)
                break
    return out


def from_documents(documents: list[Any]) -> Reading:
    """The highest level these documents evidence, with the words that show it.

    Reads the fields the document reader already extracted rather than the
    document, which no longer exists. That is deliberate and it is the same rule
    as everywhere else: the file is gone, the fields survive, and the fields
    carry their own quotes.
    """
    best = Reading()
    seen: list[str] = []

    for doc in documents or []:
        kind = getattr(doc, "kind", "") or ""
        if kind not in KINDS:
            continue

        for f in getattr(doc, "fields", []) or []:
            name = (getattr(f, "name", "") or "").lower()
            value = getattr(f, "value", "") or ""
            if name not in FIELDS and "qualif" not in name and "degree" not in name:
                continue

            for level in _matches(value):
                if level not in seen:
                    seen.append(level)
                if not best.held or RANK[level] > RANK[best.held]:
                    best = Reading(
                        held=level,
                        # The quote is the field's own quote where it has one, so
                        # the screen can show the words off the document rather
                        # than our summary of them.
                        quote=(getattr(f, "quote", "") or value),
                        filename=getattr(doc, "filename", ""),
                        field_name=getattr(f, "name", ""),
                    )

    best.candidates = sorted(seen, key=lambda x: RANK[x])
    return best

# Words that are a qualification, not a field of study. "Bachelor of Science in
# Mechanical Engineering" is about mechanical engineering; the first three words
# are the certificate talking about itself.
_AWARD_WORDS = {
    "bachelor", "bachelors", "master", "masters", "doctor", "doctorate", "phd",
    "bsc", "ba", "beng", "btech", "msc", "ma", "meng", "mtech", "mba", "llb",
    "llm", "hnd", "nd", "diploma", "certificate", "degree", "honours", "honors",
    "science", "arts", "of", "in", "the", "and", "with", "study", "studies",
    "national", "higher", "senior", "school", "examination", "council", "west",
    "african", "general", "advanced", "ordinary", "level",
}

# Subjects a secondary school certificate lists that say nothing about what
# somebody wants to do next. Everybody sits these.
_CORE_SCHOOL_SUBJECTS = {"english", "english language", "mathematics", "maths",
                         "civic education", "general paper"}


def subjects_from_documents(documents: list[Any]) -> list[str]:
    """What this person has studied, as words to match course titles against.

    A degree certificate is the strong signal: "BSc Mechanical Engineering"
    names a field, and somebody with that degree is overwhelmingly likely to be
    looking at that field next. A school certificate is the weak one: it lists
    the subjects everybody sits, and English and Mathematics tell us nothing.

    This is a starting point and never a decision. The screen shows what was
    taken from the documents and lets it be changed, because plenty of people
    move field between qualifications and this must not quietly hide the courses
    they actually came for.
    """
    found: list[str] = []
    seen: set[str] = set()

    for doc in documents or []:
        if (getattr(doc, "kind", "") or "") not in KINDS:
            continue
        for f in getattr(doc, "fields", []) or []:
            name = (getattr(f, "name", "") or "").lower()
            value = (getattr(f, "value", "") or "").strip()
            if not value or len(value) > 90:
                continue
            if name not in FIELDS and "qualif" not in name and "subject" not in name:
                continue

            # Strip the award out and keep the field of study.
            words = [w for w in re.split(r"[^A-Za-z]+", value) if w]
            kept = [w for w in words if w.lower() not in _AWARD_WORDS]
            phrase = " ".join(kept).strip()
            if not phrase or len(phrase) < 3:
                continue
            if phrase.lower() in _CORE_SCHOOL_SUBJECTS:
                continue
            if phrase.lower() in seen:
                continue
            seen.add(phrase.lower())
            found.append(phrase)

    return found[:6]
