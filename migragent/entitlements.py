"""What a subscription buys, in one place, so nothing decides it twice.

THE SHAPE OF THE DEAL
---------------------
Free:  every country you qualify for, every course we have read, the guide, the
       documents written for you, and the evidence behind all of it.
Paid:  when things happen. Intake dates, application windows, and the alerts
       that carry them.

The line is timing, not access. Somebody who never pays still learns that they
qualify for a master's in civil engineering at four schools in two countries,
with the schools' own words for it. What they do not get is the calendar.

WHY THE LINE IS THERE AND NOT SOMEWHERE ELSE
----------------------------------------------
Because it is the only line that does not make the free product dishonest.

Gating which countries somebody can see would mean withholding the existence of
an option in order to sell the timing of it. A person would be told there is
nowhere for them to go while we hold a list of places they qualify for. That is
a lie by omission with a price attached, and the study path briefly worked that
way by accident: it hid every country whose courses had no intake date recorded,
which was nearly all of them.

Gating the evidence would be worse. The sources are the product's whole claim to
be believed and they stay in front of everybody.

Timing is a fair thing to charge for. It is genuinely what costs us money to
know: it is the daily re-reading, the watch, and the digest. Nobody is misled by
not having it, and everybody can see that it exists.

HOW IT WORKS TODAY
------------------
There is no billing. `is_subscriber` returns False for everybody, always, and
says so rather than pretending. What matters is that every screen already asks
this module instead of deciding for itself, so the day billing exists there is
one function to change and no screen that quietly forgot.

`redact_intake` is the enforcement. Course rows keep their intake dates in the
database, because the watch needs them to tell a subscriber when something
opens. The redaction happens on the way out, once, here.
"""
from __future__ import annotations

from typing import Any

# What the subscription costs. One tier, and the only one: the product does not
# have a cheaper version that is worse or a dearer one that is the real one.
PRICE_USD = 7
PRICE_LABEL = "$7 a month"

# The fields that are the subscription. Held for everybody, shown to subscribers.
TIMING_FIELDS = ("intake", "intake_open", "intake_date", "application_opens",
                 "application_closes", "deadline")

# What a free user sees in place of a date. A sentence, not a blurred box or a
# fake date: somebody should be able to tell exactly what they are missing and
# decide whether it is worth seven dollars, which a smudge does not allow.
WITHHELD = "with a subscription"


def is_subscriber(case: Any = None) -> bool:
    """Whether this case has paid. Always False, honestly, until billing exists.

    Not a stub that returns True in development. A default of True would mean
    every screen was built and tested against the paid experience and nobody
    would notice the free one was broken until somebody who had not paid used
    it, which is everybody at launch.
    """
    return False


def redact_intake(course: dict[str, Any], subscriber: bool) -> dict[str, Any]:
    """One course, with its timing removed unless it has been paid for.

    Returns a copy. The stored row is never modified: the watch needs the real
    date to tell a subscriber when the intake opens, and a redaction that reached
    the database would delete the thing being sold.
    """
    if subscriber:
        return dict(course)

    out = dict(course)
    withheld = False
    for field in TIMING_FIELDS:
        if out.get(field):
            withheld = True
        out.pop(field, None)
    # Said out loud on the row, so a template does not have to work out whether
    # a missing date means "not published" or "not paid for". Those are very
    # different sentences and only one of them is an offer.
    out["intake_withheld"] = withheld
    return out


def redact_all(courses: list[dict[str, Any]], subscriber: bool) -> list[dict[str, Any]]:
    return [redact_intake(course, subscriber) for course in courses]
