"""Check $MIGRA voting, without a chain or a database.

    python -m tools.test_governance
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from eth_account import Account  # noqa: E402
from eth_account.messages import encode_defunct  # noqa: E402

from migragent import governance as gov  # noqa: E402


class Snap:
    def __init__(self, d):
        self._d = d
        self.exists = d is not None

    def to_dict(self):
        return dict(self._d or {})


class Doc:
    def __init__(self, store, coll, key):
        self.s, self.c, self.k = store, coll, key

    def get(self):
        return Snap(self.s.setdefault(self.c, {}).get(self.k))

    def set(self, d):
        self.s.setdefault(self.c, {})[self.k] = dict(d)

    def update(self, d):
        self.s[self.c][self.k].update(d)


class Query:
    def __init__(self, rows):
        self.rows = rows

    def stream(self):
        return [Snap(r) for r in self.rows]


class Coll:
    def __init__(self, store, name):
        self.s, self.n = store, name

    def document(self, k):
        return Doc(self.s, self.n, k)

    def where(self, filter):  # noqa: A002
        rows = [r for r in self.s.get(self.n, {}).values() if r.get(filter.field_path) == filter.value]
        return Query(rows)

    def stream(self):
        return [Snap(r) for r in self.s.get(self.n, {}).values()]


class DB:
    def __init__(self):
        self.store = {}

    def collection(self, n):
        return Coll(self.store, n)


def sign(acct, pid, opt, wallet=None):
    return acct.sign_message(encode_defunct(text=gov.message(pid, opt, wallet or acct.address))).signature.hex()


def main() -> int:
    results = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    db = DB()
    alice, bob, carol = Account.create(), Account.create(), Account.create()
    holdings = {alice.address.lower(): 600 * 10**18, bob.address.lower(): 400 * 10**18, carol.address.lower(): 0}
    gov.balance = lambda w: holdings.get(w.lower(), 0)

    pid = gov.create(db, "Which country next?", "Pick one.", ["Netherlands", "Japan"], 7)
    check(gov.cast(db, pid, "Netherlands", alice.address, sign(alice, pid, "Netherlands")) == "", "a holder can vote")
    check(gov.cast(db, pid, "Japan", bob.address, sign(bob, pid, "Japan")) == "", "a second holder can vote")
    check("doesn't belong" in gov.cast(db, pid, "Japan", alice.address, sign(bob, pid, "Japan", alice.address)),
          "someone else's signature cannot vote for a wallet")
    check("doesn't belong" in gov.cast(db, pid, "Japan", alice.address, sign(alice, pid, "Netherlands")),
          "a signature for one option cannot be replayed onto another")
    check("holds no $MIGRA" in gov.cast(db, pid, "Japan", carol.address, sign(carol, pid, "Japan")),
          "an empty wallet has no vote")
    check("isn't one of the options" in gov.cast(db, pid, "Mars", alice.address, sign(alice, pid, "Mars")),
          "an option that wasn't offered is refused")

    t = gov.tally(db, db.store[gov.PROPOSALS][pid])
    check(t["weights"]["Netherlands"] == str(600 * 10**18) and not t["final"], "the open tally is provisional", t["voters"])

    # Alice moves her tokens to Carol mid-vote; Carol votes Japan with the same tokens.
    holdings[carol.address.lower()], holdings[alice.address.lower()] = 600 * 10**18, 0
    check(gov.cast(db, pid, "Japan", carol.address, sign(carol, pid, "Japan")) == "", "the receiving wallet can vote")
    db.store[gov.PROPOSALS][pid]["closes_at"] = "2000-01-01T00:00:00+00:00"   # close it
    final = gov.tally(db, db.store[gov.PROPOSALS][pid])
    check(final["final"] and final["weights"]["Japan"] == str(1000 * 10**18) and final["weights"]["Netherlands"] == "0",
          "at the close, moved tokens count once, in the wallet that holds them", final["weights"])
    check(db.store[gov.PROPOSALS][pid]["status"] == "closed", "a closed vote stores its final result")
    check("has closed" in gov.cast(db, pid, "Japan", bob.address, sign(bob, pid, "Japan")), "a closed vote takes no more votes")

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
