"""Check the $MIGRA credit rules, without Firestore and without spending anything.

    python -m tools.test_credits

migragent/credits.py makes claims that decide whether somebody gets credited
for money: that a signature from one wallet cannot link another, that a
Transfer event from any contract but the token is ignored, that a transfer to
anywhere but the treasury is ignored, and that an unconfirmed transaction is a
wait rather than a credit. Rule 3: each gets a check before it gets a sentence.

The ledger's once-only credit lives in a Firestore transaction and is not
exercised here. Run it against a scratch project, never the live one.

Pass --live to also read the real Robinhood Chain RPC, which proves the default
endpoint answers and the receipt shape is the one parsed here.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")

from eth_account import Account as EthAccount  # noqa: E402
from eth_account.messages import encode_defunct  # noqa: E402

from migragent import credits  # noqa: E402
from migragent.credits import (TRANSFER_TOPIC, Balance, Chain, CreditError,  # noqa: E402
                               Settings, check_deposit, format_units,
                               recover_signer, sign_in_message, transferred)

TOKEN = "0x" + "11" * 20
TREASURY = "0x" + "22" * 20
OTHER = "0x" + "33" * 20


def topic(addr: str) -> str:
    return "0x" + "0" * 24 + addr[2:].lower()


def log(emitter: str, frm: str, to: str, amount: int) -> dict:
    return {"address": emitter, "topics": [TRANSFER_TOPIC, topic(frm), topic(to)],
            "data": hex(amount)}


class FakeChain(Chain):
    def __init__(self, receipt, head: int) -> None:
        self._receipt, self._head = receipt, head

    def receipt(self, tx_hash):
        return self._receipt

    def block_number(self):
        return self._head


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    # --- sign-in -------------------------------------------------------------
    me = EthAccount.create()
    them = EthAccount.create()
    msg = sign_in_message("migragent.onenept.com", me.address, "abc123",
                          "2026-09-29T00:00:00+00:00")
    sig = me.sign_message(encode_defunct(text=msg)).signature.hex()
    check(recover_signer(msg, sig) == me.address.lower(),
          "a wallet's own signature recovers to that wallet")
    check(recover_signer(msg, sig) != them.address.lower(),
          "and not to anybody else")
    check(recover_signer(msg.replace("abc123", "zzz999"), sig) != me.address.lower(),
          "a signature over a different nonce does not recover to the signer")
    check(recover_signer(msg, "0xdeadbeef") == "",
          "garbage in place of a signature is refused, not raised")
    check("Chain ID: 4663" in msg and "Nonce: abc123" in msg,
          "the signed message names the chain and the nonce")

    # --- which transfers count -------------------------------------------------
    sender = me.address.lower()
    receipt = {"status": "0x1", "blockNumber": hex(100), "logs": [
        log(TOKEN, sender, TREASURY, 5 * 10**18),
        log(OTHER, sender, TREASURY, 999 * 10**18),      # a fake token, same event
        log(TOKEN, sender, OTHER, 7 * 10**18),           # right token, wrong place
        log(TOKEN, them.address, TREASURY, 9 * 10**18),  # somebody else's payment
        log(TOKEN.upper().replace("0X", "0x"), sender, TREASURY, 1 * 10**18),
    ]}
    got = transferred(receipt, TOKEN, sender, TREASURY)
    check(got == 6 * 10**18,
          "only the token's own transfers, from the wallet, to the treasury, are summed",
          f"got {got}")

    cfg = Settings(token=TOKEN, treasury=TREASURY, rpc="", per_month=100,
                   confirmations=3, decimals=18)
    check(cfg.live and cfg.price_units == 100 * 10**18, "settings go live with both addresses")
    check(not Settings("", TREASURY, "", 100, 3, 18).live, "no token address, not live")
    check(not Settings(TOKEN, "0xnope", "", 100, 3, 18).live, "a malformed treasury, not live")

    amount, block = check_deposit(FakeChain(receipt, head=102), cfg, "0x" + "a" * 64, sender)
    check(amount == 6 * 10**18 and block == 100, "a confirmed deposit is credited in full")

    def refused(chain, who=sender) -> str:
        try:
            check_deposit(chain, cfg, "0x" + "a" * 64, who)
        except CreditError as exc:
            return str(exc)
        return ""

    check(refused(FakeChain(receipt, head=101)) == "pending",
          "two confirmations of three is a wait, not a credit")
    check(refused(FakeChain(None, head=200)) == "pending",
          "an unmined transaction is a wait")
    check("failed" in refused(FakeChain({**receipt, "status": "0x0"}, head=200)),
          "a reverted transaction is refused")
    check("did not send" in refused(FakeChain(receipt, head=200), who=OTHER),
          "a wallet that sent nothing in this transaction gets nothing")

    # --- display and the paid gate -----------------------------------------------
    check(format_units(1234567 * 10**17, 18) == "123,456.7", "units format without float error",
          format_units(1234567 * 10**17, 18))
    check(format_units(0, 18) == "0", "zero formats as zero")
    check(Balance("0x1", paid_until="2999-01-01T00:00:00+00:00").active(),
          "a month that has not ended is active")
    check(not Balance("0x1", paid_until="2000-01-01T00:00:00+00:00").active(),
          "a month that ended is not")
    check(not Balance("0x1").active(), "never paid is not active")

    from migragent.entitlements import is_subscriber
    check(is_subscriber(None) is False and is_subscriber(object()) is False,
          "with no case or no database, nobody is a subscriber")

    from migragent.subscribe_page import subscribe_html
    closed = subscribe_html(wallet={"live": False})
    check("isn't launched yet" in closed and 'action="/subscribe"' in closed
          and "Connect wallet" not in closed,
          "before launch the page says so and offers no checkout")
    open_ = subscribe_html(has_case=True, wallet={
        "live": True, "token": TOKEN, "treasury": TREASURY, "per_month": 100,
        "price_units": str(100 * 10**18), "wallet": "", "balance": "0"})
    check("Connect wallet" in open_ and "Send 100 $MIGRA" in open_,
          "after launch the page offers the wallet")
    hostile = subscribe_html(has_case=True, wallet={
        "live": True, "token": "</script><script>alert(1)</script>", "treasury": TREASURY,
        "per_month": 1, "price_units": "1"})
    check("</script><script>alert(1)" not in hostile,
          "nothing in the config can close the script tag")

    # --- the real chain ----------------------------------------------------------
    if "--live" in sys.argv:
        chain = Chain(os.environ.get("MIGRAGENT_CHAIN_RPC", credits.DEFAULT_RPC))
        head = chain.block_number()
        check(head > 0, "the default Robinhood Chain RPC answers", f"head {head}")
        block = chain.call("eth_getBlockByNumber", [hex(head - 5), False])
        txs = block.get("transactions") or []
        if txs:
            r = chain.receipt(txs[0])
            check(r and "logs" in r and "status" in r and "blockNumber" in r,
                  "a real receipt has the fields check_deposit reads", txs[0])

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
