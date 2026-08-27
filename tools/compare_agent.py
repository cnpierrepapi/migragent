"""Compare what the agent reads against what the walk read, on the same lane.

    python -m tools.compare_agent UK work
    python -m tools.compare_agent CA study --write

Build 4 ends with the daily round run by an agent. Before that happens, the
agent has to be shown to be better than the thing it replaces, on more than the
one entry page it was first tried on. Switching a pipeline over on one good
anecdote is the failure this project keeps catching in other people's work.

WHAT IS COMPARED
----------------
The walk's side is already in the corpus: every requirement extracted from a
source at depth 0 or 1 in this lane, which is exactly what the guide may cite.
The agent's side is produced live, from the same entry page, choosing its own
pages as it goes. Nothing is written unless `--write` is passed.

WHAT IS MEASURED, AND WHY THESE
-------------------------------
  requirements   the raw count, which is the least interesting number here
  concrete       the share carrying a digit. A guide that says "you must pay the
                 application fee" is worse than one that says "£719", and that
                 difference is the whole reason the agent looked promising on
                 gov.uk. It is measurable, so it gets measured rather than
                 admired.
  costed/timed   requirements the extractor tagged with a cost or a duration
  pages          how many pages each side read to get there, because a better
                 answer that costs five times the reading is a different trade
  only in one    quotes one side found and the other did not, which is where the
                 argument actually lives

A quote is the identity of a requirement here: same sentence from the same
government page, whoever found it.
"""
from __future__ import annotations
import os

import re
import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.registry import JURISDICTIONS, Registry  # noqa: E402
from migragent.researcher import Researcher  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")
MODEL = "gemini-3.5-flash"
MODEL_LOCATION = "global"

_DIGIT = re.compile(r"\d")


def _normalise(quote: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (quote or "").lower()).strip()


def _profile(rows: list[dict]) -> dict:
    total = len(rows)
    if not total:
        return {"requirements": 0, "concrete": 0, "costed": 0, "timed": 0, "share": 0.0}
    concrete = len([r for r in rows if _DIGIT.search(str(r.get("text", "")))])
    return {
        "requirements": total,
        "concrete": concrete,
        "share": round(100 * concrete / total),
        "costed": len([r for r in rows if r.get("cost")]),
        "timed": len([r for r in rows if r.get("duration")]),
    }


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 64

    jurisdiction, lane = sys.argv[1].upper(), sys.argv[2].lower()
    place = JURISDICTIONS.get(jurisdiction, {}).get("name", jurisdiction)

    reader = identity.credentials_for(identity.RESEARCHER, PROJECT)
    db = firestore.Client(project=PROJECT, credentials=reader)
    registry = Registry(db)

    sources = [s for s in registry.for_lane(jurisdiction, lane)
               if s.blocked is None and (s.depth or 0) <= 1]
    entries = [s for s in sources if (s.depth or 0) == 0]
    if not entries:
        print(f"no entry page for {jurisdiction} {lane}")
        return 1
    entry = entries[0]

    ids = {s.source_id for s in sources}
    walked = [d.to_dict() for d in db.collection("requirements")
              .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
              .where(filter=firestore.FieldFilter("lane", "==", lane)).stream()]
    walked = [r for r in walked if not r.get("retired_at") and r.get("source_id") in ids]

    print(f"{jurisdiction} {lane}: the walk holds {len(walked)} live requirements from "
          f"{len({r.get('source_id') for r in walked})} of {len(sources)} pages at depth 0 to 1")
    print(f"the agent starts at {entry.url}\n")

    session = Researcher(project=PROJECT, model=MODEL, location=MODEL_LOCATION,
                         credentials=reader, fetcher=Fetcher(delay_seconds=0.5),
                         on_event=lambda line: print(line, flush=True)).research(
        entry.url, jurisdiction=jurisdiction, lane=lane, place=place,
        language=entry.language, provenance=entry.provenance)

    agent = [r.to_dict() for r in session.requirements]

    print(f"\nthe agent read {len(session.pages_read)} pages in {session.turns} turns, "
          f"refused {len(session.refused)} quotes, stopped because: {session.stopped_because}")

    walk_profile, agent_profile = _profile(walked), _profile(agent)
    print(f"\n{'':<14}{'walk':>10}{'agent':>10}")
    for key in ("requirements", "concrete", "share", "costed", "timed"):
        print(f"  {key:<12}{walk_profile[key]:>10}{agent_profile[key]:>10}")
    print(f"  {'pages read':<12}{len({r.get('source_id') for r in walked}):>10}"
          f"{len(session.pages_read):>10}")

    walk_quotes = {_normalise(r.get("quote")) for r in walked}
    agent_quotes = {_normalise(r.get("quote")) for r in agent}
    shared = walk_quotes & agent_quotes

    print(f"\nsame sentence found by both: {len(shared)}")
    print(f"only the walk: {len(walk_quotes - agent_quotes)}   "
          f"only the agent: {len(agent_quotes - walk_quotes)}")

    only_agent = [r for r in agent if _normalise(r.get("quote")) not in walk_quotes]
    if only_agent:
        print("\nwhat only the agent found:")
        for r in only_agent[:10]:
            print(f"  [{r.get('category')}] {str(r.get('text'))[:88]}")
            print(f"       {str(r.get('source_url'))[-70:]}")

    only_walk = [r for r in walked if _normalise(r.get("quote")) not in agent_quotes]
    if only_walk:
        print(f"\nwhat only the walk found ({len(only_walk)}), first 10:")
        for r in only_walk[:10]:
            print(f"  [{r.get('category')}] {str(r.get('text'))[:88]}")

    print("\npages the agent chose:")
    for url in session.pages_read:
        known = "in the registry" if any(s.url == url for s in sources) else "NEW to the registry"
        print(f"  {known:<20} {url[-66:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
