"""Which country to serve first. Internal only; none of this reaches a screen.

WHY THIS IS NOT SHOWN
---------------------
Everywhere else in this product a number on a screen has to carry the sentence
it came from. These numbers cannot, because they are not measurements of the
world: they are our opinion about which of several genuine options to put in
front of somebody first. Printing "Canada 78, United Kingdom 64" would dress an
editorial choice as a finding, and a person would reasonably read it as advice
about their future that we can defend line by line. We cannot.

So the score decides the order of what is served and never appears in the
output. Rule 16 says a number on a screen carries its source; this number stays
off the screen instead.

WHAT IT IS ALLOWED TO USE
-------------------------
Two kinds of input, kept apart:

  measured   things read from data we hold: how many requirements exist for a
             lane, how many live postings match, how well the CV matched, what a
             course costs. These change as the corpus changes.

  weighted   settled policy facts that do not change week to week, written here
             as constants with the reason next to each. A post-study work route
             that leads to permanent residence is genuinely worth more to most
             people than one that does not, and pretending we have no opinion
             about that would just push the opinion into the ordering anyway,
             unwritten and unarguable.

The weights are the honest part: they are visible, they are commented, and they
can be argued with by anybody reading this file. An unwritten preference buried
in a sort key cannot.

WHY COST CAN OVERTURN EVERYTHING
--------------------------------
Canada outranks the United Kingdom on the route weights for most people. It
should still lose when the United Kingdom has a school teaching the same course
for a third of the money, because for most people paying for this themselves,
that difference is larger than every other difference combined. So cost is not a
small tiebreaker term: it is scaled to be able to overturn the route weights on
its own, and that is deliberate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ROUTE WEIGHTS
# -------------
# Settled policy facts, scored 0 to 10, with the reason written next to each.
# These are opinions about what is worth more to a typical person, not claims
# about what a government publishes, which is exactly why they never render.
#
# Anybody may disagree with a number here. That is the point of it being here.

# Does finishing a course or a contract lead anywhere permanent, without leaving?
PR_ROUTE = {
    "CA": 9,   # study or skilled work converts to permanent residence by design
    "AU": 8,   # points-based, and study counts toward it
    "PT": 7,   # a residence route that does not require leaving first
    "DE": 6,   # settlement after a qualifying period on a work permit
    "ES": 5,
    "FR": 5,
    "UK": 4,   # a route exists and is longer, dearer and less certain than it was
    "IT": 4,
    "US": 3,   # the step from a student or work visa to residence is the hard one
    "SA": 1,   # employment does not lead to residence for most people
    "AE": 1,   # long residence, and it remains residence rather than a path
}

# Can a partner come, and can they work when they do? This matters enormously to
# somebody with a family and not at all to somebody without one, which is why it
# is a separate term the caller can turn off rather than folded into the first.
DEPENDANTS = {
    "CA": 9,   # partners of master's and doctoral students may work
    "AU": 7,
    "DE": 6,
    "PT": 6,
    "ES": 5,
    "FR": 5,
    "IT": 4,
    "UK": 3,   # dependants were removed for most taught courses; research keeps them
    "US": 3,
    "AE": 2,
    "SA": 2,
}

# How much of the process a person can do without paying somebody to do it.
SELF_SERVE = {
    "CA": 8, "UK": 8, "AU": 7, "DE": 6, "PT": 6, "FR": 5,
    "ES": 5, "IT": 4, "US": 5, "AE": 4, "SA": 3,
}

# How far each measured term can move the total, so one of them cannot quietly
# dominate. Cost is the largest single term on the study side on purpose: see
# the module docstring.
CAP_CORPUS = 12
CAP_POSTINGS = 14
CAP_MATCH = 16
CAP_COST = 30


@dataclass
class Score:
    """One country's score, and every part of it, for the log rather than a page."""

    jurisdiction: str
    total: float = 0.0
    parts: dict[str, float] = field(default_factory=dict)

    def add(self, name: str, value: float) -> None:
        self.parts[name] = round(value, 2)
        self.total = round(self.total + value, 2)

    def explain(self) -> str:
        """One line for the job log. Never for a template."""
        bits = ", ".join(f"{k} {v}" for k, v in sorted(self.parts.items()))
        return f"{self.jurisdiction} {self.total}: {bits}"


def _capped(value: float, ceiling: float, cap: float) -> float:
    if ceiling <= 0:
        return 0.0
    return min(value / ceiling, 1.0) * cap


def score_work(eligible: list[Any], has_partner: bool = False) -> list[Score]:
    """Rank the countries a work case qualified for.

    The measured half asks a blunt question: can we actually deliver something
    here today. A country with a deep corpus and live postings can be given a
    real guide and a real job to look at; a country with three requirements and
    no board cannot, however good its permanent residence route is. Serving the
    second one first would be preferring our own opinion over the person's
    afternoon.
    """
    if not eligible:
        return []

    most_matches = max(len(e.reasons) for e in eligible) or 1
    most_requirements = max(e.requirements for e in eligible) or 1
    most_postings = max(e.postings for e in eligible) or 1

    scores: list[Score] = []
    for item in eligible:
        score = Score(jurisdiction=item.jurisdiction)
        score.add("pr_route", PR_ROUTE.get(item.jurisdiction, 4))
        score.add("self_serve", SELF_SERVE.get(item.jurisdiction, 5))
        if has_partner:
            score.add("dependants", DEPENDANTS.get(item.jurisdiction, 4))
        score.add("match", _capped(len(item.reasons), most_matches, CAP_MATCH))
        score.add("corpus", _capped(item.requirements, most_requirements, CAP_CORPUS))
        # Whether we can put a real posting in front of them, which is the whole
        # of what the work path promises to end with.
        score.add("postings", _capped(item.postings, most_postings, CAP_POSTINGS))
        scores.append(score)

    scores.sort(key=lambda s: -s.total)
    return scores


def score_study(eligible: list[Any], costs: dict[str, float] | None = None,
                research: bool = False, has_partner: bool = False) -> list[Score]:
    """Rank the countries a study case qualified for.

    `costs` is the cheapest annual tuition we hold for a matching course in each
    country, in one currency. It is the term allowed to overturn the rest, and
    it is scored against the cheapest country in the set rather than against an
    absolute, because what matters to somebody choosing is the difference
    between their options and not the number itself.

    `research` marks a master's by research or a doctorate. It matters because
    the countries that removed dependant rights mostly kept them for research
    degrees, so the same two countries rank differently for the same person
    depending on which kind of course they are heading for. That is a real
    difference and flattening it would produce confidently wrong ordering.
    """
    if not eligible:
        return []

    costs = costs or {}
    most_matches = max(len(e.reasons) for e in eligible) or 1
    most_requirements = max(e.requirements for e in eligible) or 1

    known_costs = [c for c in costs.values() if c and c > 0]
    cheapest = min(known_costs) if known_costs else 0.0

    scores: list[Score] = []
    for item in eligible:
        score = Score(jurisdiction=item.jurisdiction)
        score.add("pr_route", PR_ROUTE.get(item.jurisdiction, 4))
        score.add("self_serve", SELF_SERVE.get(item.jurisdiction, 5))

        if has_partner:
            weight = DEPENDANTS.get(item.jurisdiction, 4)
            # A research degree restores dependant rights in the places that
            # removed them for taught courses, so the gap between countries
            # narrows rather than the score simply rising.
            if research:
                weight = min(10, weight + 4)
            score.add("dependants", weight)

        score.add("match", _capped(len(item.reasons), most_matches, CAP_MATCH))
        score.add("corpus", _capped(item.requirements, most_requirements, CAP_CORPUS))

        # Cost, scaled so a country twice the price of the cheapest loses the
        # whole term. Unknown cost scores nothing rather than scoring well: a
        # country we have no price for must not win on the strength of it.
        mine = costs.get(item.jurisdiction, 0.0)
        if cheapest and mine and mine > 0:
            # The cheapest option in the set takes the whole term; one at twice
            # the price takes none of it. Steep on purpose, because for somebody
            # paying tuition themselves the difference between £12,000 and
            # £30,000 is larger than every other difference on this list
            # combined, and a gentle curve would let route weights quietly
            # decide something that money should decide.
            ratio = cheapest / mine
            score.add("cost", max(0.0, ratio * 2 - 1) * CAP_COST)
        else:
            score.add("cost", 0.0)

        scores.append(score)

    scores.sort(key=lambda s: -s.total)
    return scores


def best(scores: list[Score]) -> str:
    return scores[0].jurisdiction if scores else ""
