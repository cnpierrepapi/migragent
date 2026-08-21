"""Which of these did we not have yesterday?

WHY THIS EXISTS
---------------
The product's second promise is that it tells you when something opens: a school
added to the register you need to be on, an occupation a country has just
admitted it is short of, a posting that went up this morning.

None of that is observable from a collection of rows that only ever says what is
true now. `merge=True` writes are idempotent by design, which is what makes the
pipeline safe to re-run and also what makes every row look equally old. A row
added today and a row added in June are indistinguishable, so "what is new" can
only be answered by asking, before writing, which ids are not there yet.

Listings learned this first, in its own `record`, keeping `first_seen_at` off the
merge payload so a second sighting could not reset it to today. This is the same
idea taken out of that file so the register and the shortage list can use it too.

WHAT IT COSTS, AND WHY IT IS WORTH IT
-------------------------------------
One existence read per row per round, batched. For the Canadian register that is
about 1,400 reads a day. The alternative is a `first_seen_at` that resets on
every merge, which is not a cheaper version of this: it is a date that lies, and
the alert built on it would say a school opened its doors today when it has been
on the register for two years.

WHAT IT DOES NOT DO
-------------------
It does not write anything, and it does not decide what "new" means. It answers
one question about ids and hands the answer back, because whether a new row is
worth telling somebody about is a judgement that belongs where the judgement is.
"""
from __future__ import annotations

from typing import Iterable

# Firestore's get_all takes a list; a very long one is a single large request.
# Three hundred keeps each round trip small enough to retry cheaply.
CHUNK = 300


def unseen_ids(db, collection: str, ids: Iterable[str]) -> set[str]:
    """Of these document ids, which do not exist yet.

    Reads only the document's existence, not its contents: `field_paths=["_"]`
    asks for a field nothing writes, so each snapshot comes back knowing whether
    it is there and carrying nothing else.

    A failure here returns the empty set rather than raising. Getting this wrong
    in the cautious direction means a genuinely new row is not announced, which
    is a missed alert. Getting it wrong the other way means announcing rows that
    have been there for months as though they arrived overnight, which is the
    kind of false alarm that teaches somebody to ignore the next one.
    """
    ids = [i for i in ids if i]
    if not ids:
        return set()

    unseen: set[str] = set()
    try:
        for start in range(0, len(ids), CHUNK):
            batch = ids[start:start + CHUNK]
            refs = [db.collection(collection).document(i) for i in batch]
            present = {snap.id for snap in db.get_all(refs, field_paths=["_"])
                       if snap.exists}
            unseen.update(i for i in batch if i not in present)
    except Exception:  # noqa: BLE001
        return set()
    return unseen
