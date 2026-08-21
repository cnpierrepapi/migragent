"""How long the wait is likely to be, from how long it has actually been.

WHY THIS DOES NOT BREAK THE RULE ON THE WORKING SCREEN
------------------------------------------------------
`migragent/run.py` says, and means, that nothing on the working screen is a timer
pretending to be progress. That rule is about a *progress bar*: a bar that fills
on a schedule is a claim that some measured fraction of the work is finished,
and when the fraction is invented the claim is a lie told in the same shape as
an invented citation.

An estimated wait is a different kind of statement, and an honest one, provided
three things hold:

  it says it is an estimate     not "62% complete", but "about three minutes"
  it is built from measurement  the estimate comes from what runs have really
                                taken, not from a number somebody liked
  the real event ends it        when the run finishes the wait is over that
                                second, whatever the clock said

The third is what the person actually asked for: an estimate deliberately longer
than the work, that resolves the moment the work is done. A countdown that beats
the run and then sits at 0:00 while the spinner turns is the dishonest version,
so it never sits at zero: it says it is taking longer than usual, which is true
and is also the only useful thing to say at that point.

WHY IT LEARNS RATHER THAN BEING A CONSTANT
------------------------------------------
The first measured run took 196 seconds: about 0.6 for the corpus, 77 across four
route lookups at roughly 19 seconds each, and 118 to write the questions. Those
are model calls, and model latency moves week to week. A constant typed in today
is a number that quietly becomes wrong and nobody notices, because nothing
compares it to anything.

So every finished run records what it took, and the estimate is the ninetieth
percentile of comparable runs with a margin on top. It is wrong early, honest
about being an estimate throughout, and gets better the more it is used.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

RUN_TIMES = "run_times"

# The cold start, before this has watched anything. Measured on 21 August 2026:
# one CA work run with no documents, end to end, 196 seconds.
#
# The margin is deliberate and it is the point of the feature. An estimate that
# runs out early makes somebody think the thing has hung; one that resolves early
# is a small pleasant surprise. Asymmetric costs, so the estimate leans long.
BASE_SECONDS = 210.0

# Each uploaded document is one more model call to read it, plus its share of the
# matching pass. Not measured with a large sample yet, which is why the number is
# generous and why it is a named constant rather than buried in an expression.
PER_DOCUMENT_SECONDS = 28.0

# What the margin does to a measured estimate. 1.15 on top of a ninetieth
# percentile means roughly one run in twenty overruns its own estimate, and those
# get the "taking longer than usual" line rather than a lie.
MARGIN = 1.15

# Never promise less than this, whatever the sample says. A ten second estimate
# on a run that occasionally takes forty is worse than no estimate.
FLOOR_SECONDS = 75.0

# Nor more than this. Past a certain point a countdown stops being reassuring and
# starts being a reason to close the tab, and the honest thing is to say it is a
# few minutes rather than to display 14:52.
CEILING_SECONDS = 900.0

# How many past runs to consider. Enough to be stable, few enough that a change
# in model latency shows up within a day rather than being averaged away.
SAMPLE = 40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bucket(documents: int) -> str:
    """Runs are comparable when they read a similar number of documents.

    Buckets rather than an exact count, because nobody has enough runs with
    exactly seven documents to say anything useful about seven documents.
    """
    if documents <= 0:
        return "none"
    if documents <= 2:
        return "few"
    if documents <= 5:
        return "some"
    return "many"


@dataclass
class Estimate:
    """A number of seconds, and the sentence that says where it came from."""

    seconds: float
    basis: str
    measured: bool = False

    @property
    def clock(self) -> str:
        total = int(round(self.seconds))
        return f"{total // 60}:{total % 60:02d}"


class RunTimes:
    """What runs have really taken, and what to tell the next person."""

    COLLECTION = RUN_TIMES

    def __init__(self, client) -> None:
        self._db = client

    def record(self, jurisdiction: str, lane: str, documents: int,
               seconds: float) -> None:
        """One finished run. Failures are not recorded and that is deliberate.

        A run that died after four seconds is not evidence that runs take four
        seconds. Including them would drag every estimate down and make the
        screen promise a wait it cannot keep.
        """
        if seconds <= 0:
            return
        try:
            self._db.collection(RUN_TIMES).add({
                "jurisdiction": jurisdiction,
                "lane": lane,
                "documents": int(documents),
                "bucket": _bucket(documents),
                "seconds": round(float(seconds), 1),
                "at": _now(),
            })
        except Exception:  # noqa: BLE001
            # A timing row is not worth failing a finished run over. The person
            # has their guide; this is bookkeeping for the next person.
            pass

    def estimate(self, lane: str, documents: int) -> Estimate:
        """The wait to show, from comparable runs where there are any."""
        cold = BASE_SECONDS + PER_DOCUMENT_SECONDS * max(0, documents)

        try:
            from google.cloud import firestore

            rows = [
                d.to_dict() for d in self._db.collection(RUN_TIMES)
                .where(filter=firestore.FieldFilter("bucket", "==", _bucket(documents)))
                .limit(SAMPLE).stream()
            ]
        except Exception:  # noqa: BLE001
            rows = []

        times = sorted(float(r.get("seconds", 0)) for r in rows
                       if float(r.get("seconds", 0)) > 0)
        if len(times) < 3:
            # Three is not a sample. Say plainly that this is an estimate rather
            # than dressing two runs up as a measurement.
            return Estimate(
                seconds=_clamp(cold),
                basis="an estimate, before we have enough runs like yours to measure",
                measured=False,
            )

        index = min(len(times) - 1, int(round(0.9 * (len(times) - 1))))
        p90 = times[index]
        return Estimate(
            seconds=_clamp(p90 * MARGIN),
            basis=(f"based on the last {len(times)} runs like yours, which took "
                   f"{int(times[0])} to {int(times[-1])} seconds"),
            measured=True,
        )


def _clamp(seconds: float) -> float:
    return max(FLOOR_SECONDS, min(CEILING_SECONDS, seconds))
