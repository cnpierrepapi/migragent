"""Take the other route's requirements out of a lane's guide.

    python -m tools.fix_lane_mismatch --dry-run
    python -m tools.fix_lane_mismatch

WHAT WENT WRONG
---------------
The walk gives every page it discovers the lane of the entry page that found it.
That is right almost everywhere, because a government puts its student pages
under a student section. It is wrong when one lane's section links directly to
another lane's front door, which gov.uk does in both directions: the Student visa
page links Skilled Worker and Skilled Worker links Student visa.

So the UK study corpus held eleven Skilled Worker requirements tagged study, and
the UK work corpus held twelve Student visa requirements tagged work. Every one
of them is a true sentence, quoted correctly from the page it came from, linked
and dated correctly. They are simply answers to the other question, which is D29
and which had been recorded as a near miss in Italy before it turned out to have
already happened here.

The quote check cannot see this. Nothing is invented. That is the whole point of
writing it down.

WHAT THIS DOES
--------------
A page that sits at, or underneath, another lane's hand seeded entry page is
about that other lane. That is the only rule applied here, it is narrow on
purpose, and it needs no judgment: those entry pages were chosen by hand.

Requirements from such a page are retired rather than deleted, because the
evidence that the page said it is worth keeping, and the row is marked
`other_lane` so it stays in the registry, stays counted, and is not read again
under the wrong question. It is already held under its correct lane, so nothing
is lost.

This does not fix the general case. A page that is about the other route and
does not sit under its entry page will still be missed, and the real answer to
that is the agent in Build 4 choosing pages for a stated question rather than a
walk labelling whatever it reaches.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone  # noqa: E402

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.corpus import Corpus  # noqa: E402
from migragent.registry import Registry  # noqa: E402
from tools.seed_registry import CANDIDATES  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WRITER, PROJECT))
    registry, corpus = Registry(db), Corpus(db)

    entries: dict[str, list[tuple[str, str]]] = {}
    for jurisdiction, lane, url, _title, _language in CANDIDATES:
        entries.setdefault(jurisdiction, []).append((lane, url.rstrip("/")))

    rows = [d.to_dict() for d in db.collection("sources").stream()]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    marked = retired = 0
    for row in rows:
        if row.get("blocked"):
            continue
        jurisdiction, lane = row.get("jurisdiction"), row.get("lane")
        url = (row.get("url") or "").rstrip("/")

        belongs_to = None
        for other_lane, entry in entries.get(jurisdiction, []):
            if other_lane != lane and (url == entry or url.startswith(entry + "/")):
                belongs_to = other_lane
                break
        if belongs_to is None:
            continue

        source_id = row.get("source_id")
        live = corpus.live_ids_for_source(source_id)
        why = (f"this page is the {belongs_to} route, reached from the {lane} entry page. "
               f"It is held in the registry under {jurisdiction} {belongs_to}.")

        print(f"  {jurisdiction} {lane:<5} -> {belongs_to:<5}  {len(live):>3} live  {url[-64:]}")

        if dry_run:
            marked += 1
            retired += len(live)
            continue

        if live:
            retired += corpus.retire(live, now, "this page is about a different route")
        source = registry.get(source_id)
        if source is not None:
            source.blocked = "other_lane"
            source.blocked_reason = why
            registry.put(source)
            marked += 1

    print(f"\n{marked} source(s) marked other_lane, {retired} requirement(s) retired")
    if dry_run:
        print("dry run, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
