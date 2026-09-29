"""$MIGRA as the credit: a wallet, a deposit, and a month of timing.

WHAT THIS REPLACES
------------------
`entitlements.is_subscriber` returned False for everybody because there was no
way to pay. This is the way to pay. The thing being sold has not changed, it is
still timing, and the line in entitlements.py is still the only line. What
changed is that somebody can now be on the other side of it.

THE TOKEN
---------
$MIGRA is launched on orbio.so, which puts it on Robinhood Chain (chain id 4663)
as an ordinary ERC-20 paired with $ORBIO. Nothing here depends on Orbio's own
contracts or API: a transfer of an ERC-20 to an address is the whole interface,
and every public RPC for the chain can prove one happened.

The token address does not exist until launch. Until MIGRAGENT_MIGRA_TOKEN and
MIGRAGENT_MIGRA_TREASURY are both set, `settings().live` is False, every paid
check answers False, and the subscribe page says payments are not open. There is
no placeholder address, because a placeholder is where somebody's tokens go to
die.

HOW A CREDIT IS MADE
--------------------
1. The browser connects a wallet and signs a sign-in message (EIP-4361 shaped)
   that this server wrote, with a nonce this server issued and will only accept
   once. The recovered address is linked to the case. Nothing is trusted from
   the browser except the signature.
2. The wallet sends $MIGRA to the treasury with a plain `transfer`. The browser
   hands back the transaction hash.
3. The server reads the receipt itself. It counts only Transfer events emitted
   by the token contract, from the linked wallet, to the treasury, in a
   successful transaction with enough confirmations. The hash is written as the
   id of a deposit record in the same Firestore transaction that raises the
   balance, so a hash can be credited once and only once.

The credit is the token, one for one, in the token's own base units. There is no
exchange rate to manage and no second currency to explain.

HOW A CREDIT IS SPENT
---------------------
`unlock` takes a month's price off the balance and extends `paid_until` by
thirty days from whichever is later, now or the current end. Paying early never
loses days.

A month costs whichever is more: MIGRAGENT_MIGRA_PER_MONTH tokens (1,000), or
MIGRAGENT_MIGRA_USD_PER_MONTH dollars' worth ($3.49). It is always shown in
$MIGRA, never in dollars.

The dollar leg reads Orbio's own price for the token: ORBIO per token from the
bonding curve, times ORBIO's price in micro-dollars, both integers, so nothing
rounds a cheap token down to zero. The published `priceMicroUsd` field is not
used because it is rounded to a whole micro-dollar, which for a token worth
seven and a bit micro-dollars is a ten percent error.

The floor is what makes a price feed safe to use here. Pumping the token to
make a month cheaper stops working at 1,000 tokens, and pushing the price down
only makes a month dearer for the person doing it.

The price is quoted when the page is drawn and held for thirty minutes, so a
curve that moves while the transfer confirms cannot leave somebody who sent
exactly what they were asked for a few tokens short.

WHAT IS KEPT, AND FOR HOW LONG
------------------------------
The wallet's balance, deposits and spends are kept after a case is deleted. They
are a record of money paid, keyed by a public address that is already on a
public chain, and deleting them would delete somebody's prepaid month. What the
delete path does remove is the link between the case and the wallet, so the
wallet no longer says anything about the person's documents.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

CHAIN_ID = 4663
CHAIN_NAME = "Robinhood Chain"
DEFAULT_RPC = "https://rpc.mainnet.chain.robinhood.com"
EXPLORER = "https://robinhoodchain.blockscout.com"

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

MONTH = timedelta(days=30)

# A nonce that is never used should not sit in the database forever, and one
# that is used late is more likely stolen than slow.
NONCE_TTL = timedelta(minutes=10)

from .cases import NONCES, WALLET_LINKS  # noqa: E402  deleted with the case

from .cases import QUOTES  # noqa: E402  deleted with the case

WALLETS = "migra_wallets"
DEPOSITS = "migra_deposits"
LEDGER = "migra_ledger"

_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


class CreditError(Exception):
    """Something the person can be told, in words, on the page."""


def is_address(value: str) -> bool:
    return bool(value and _ADDRESS.match(value))


def is_tx_hash(value: str) -> bool:
    return bool(value and _TX_HASH.match(value))


@dataclass(frozen=True)
class Settings:
    token: str
    treasury: str
    rpc: str
    per_month: int          # whole tokens, the floor
    confirmations: int
    decimals: int           # 18 unless the environment says otherwise
    usd_micro: int = 0      # the dollar leg, in millionths of a dollar

    @property
    def live(self) -> bool:
        return is_address(self.token) and is_address(self.treasury) and self.per_month > 0

    @property
    def floor_units(self) -> int:
        return self.per_month * 10 ** self.decimals


def settings() -> Settings:
    """Read on every call, so a deploy that sets the address needs no code."""
    return Settings(
        token=os.environ.get("MIGRAGENT_MIGRA_TOKEN", "").strip().lower(),
        treasury=os.environ.get("MIGRAGENT_MIGRA_TREASURY", "").strip().lower(),
        rpc=os.environ.get("MIGRAGENT_CHAIN_RPC", DEFAULT_RPC).strip(),
        per_month=int(os.environ.get("MIGRAGENT_MIGRA_PER_MONTH", "0") or 0),
        confirmations=int(os.environ.get("MIGRAGENT_MIGRA_CONFIRMATIONS", "3") or 3),
        decimals=int(os.environ.get("MIGRAGENT_MIGRA_DECIMALS", "18") or 18),
        usd_micro=_micro(os.environ.get("MIGRAGENT_MIGRA_USD_PER_MONTH", "0")),
    )


def _micro(dollars: str) -> int:
    from decimal import Decimal, InvalidOperation

    try:
        return max(0, int(Decimal(dollars.strip() or "0") * 1_000_000))
    except InvalidOperation:
        return 0


# --- price -------------------------------------------------------------------

ORBIO_AGENT_API = "https://www.orbio.so/api/protocol/agents/"
QUOTE_TTL = timedelta(minutes=30)
_PRICE_FRESH = 60          # seconds before asking Orbio again
_PRICE_STALE = 3600        # seconds a last-known price is still good enough
_price_cache: dict[str, tuple[float, int, int]] = {}


def usd_units(usd_micro: int, orbio_per_token_wei: int, orbio_micro_usd: int,
              decimals: int) -> int:
    """Base units of the token worth `usd_micro`, rounded up.

    One token costs orbio_per_token_wei / 1e18 ORBIO, and one ORBIO costs
    orbio_micro_usd micro-dollars. Kept in integers end to end.
    """
    denom = orbio_per_token_wei * orbio_micro_usd
    if denom <= 0:
        raise CreditError("price")
    num = usd_micro * 10 ** decimals * 10 ** 18
    return -(-num // denom)


def fetch_orbio_price(token: str, timeout: float = 10.0) -> tuple[int, int]:
    """(ORBIO wei per token, ORBIO micro-dollars) from Orbio's public read."""
    req = urllib.request.Request(ORBIO_AGENT_API + token,
                                 headers={"User-Agent": "migragent/credits"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    per_token = int((data.get("price") or {}).get("orbioPerToken") or 0)
    orbio_usd = int(data.get("orbioMicroUsd") or 0)
    if per_token <= 0 or orbio_usd <= 0:
        raise CreditError("price")
    return per_token, orbio_usd


def month_price(cfg: Settings, fetch=fetch_orbio_price, clock=None) -> int:
    """What a month costs right now, in base units. The larger of the two legs.

    Raises CreditError("price") only when Orbio has not answered for an hour and
    there is no last-known price, so a month is never sold at the floor just
    because the dollar leg could not be read.
    """
    import time

    floor = cfg.floor_units
    if cfg.usd_micro <= 0:
        return floor
    now = (clock or time.time)()
    cached = _price_cache.get(cfg.token)
    if not cached or now - cached[0] > _PRICE_FRESH:
        try:
            per_token, orbio_usd = fetch(cfg.token)
            cached = (now, per_token, orbio_usd)
            _price_cache[cfg.token] = cached
        except (OSError, ValueError, CreditError):
            if not cached or now - cached[0] > _PRICE_STALE:
                raise CreditError("price") from None
    # Whole tokens, rounded up, so the wallet asks for the same round number the
    # page shows.
    one = 10 ** cfg.decimals
    usd_leg = -(-usd_units(cfg.usd_micro, cached[1], cached[2], cfg.decimals) // one) * one
    return max(floor, usd_leg)


def format_units(units: int, decimals: int, places: int = 4) -> str:
    """Base units as a human number, without float rounding.

    places=0 rounds up to a whole token, for prices: asking for 1,234 when the
    real number is 1,233.2 costs the payer under a token and never leaves them
    short.
    """
    if places == 0:
        return f"{-(-int(units) // 10 ** decimals):,}"
    whole, frac = divmod(int(units), 10 ** decimals)
    frac_s = str(frac).rjust(decimals, "0").rstrip("0")[:places]
    return f"{whole:,}" + (f".{frac_s}" if frac_s else "")


# --- sign-in ---------------------------------------------------------------

def sign_in_message(domain: str, address: str, nonce: str, issued_at: str) -> str:
    """The text the wallet signs. Written here, never taken from the browser."""
    return (
        f"{domain} wants you to sign in with your Ethereum account:\n"
        f"{address}\n\n"
        "Link this wallet to your MIGRAGENT case so $MIGRA you send can pay for it. "
        "This does not send a transaction or cost gas.\n\n"
        f"URI: https://{domain}\n"
        "Version: 1\n"
        f"Chain ID: {CHAIN_ID}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}"
    )


def recover_signer(message: str, signature: str) -> str:
    """The address that signed `message`, lowercased, or '' if it cannot be read."""
    from eth_account import Account
    from eth_account.messages import encode_defunct

    try:
        return Account.recover_message(encode_defunct(text=message),
                                       signature=signature).lower()
    except Exception:  # noqa: BLE001
        return ""


# --- the chain ---------------------------------------------------------------

class Chain:
    """The two JSON-RPC calls this needs, and nothing else."""

    def __init__(self, rpc: str, timeout: float = 15.0) -> None:
        self._rpc = rpc
        self._timeout = timeout

    def call(self, method: str, params: list[Any]) -> Any:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                           "params": params}).encode()
        req = urllib.request.Request(self._rpc, data=body, headers={
            "Content-Type": "application/json", "User-Agent": "migragent/credits"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            out = json.loads(resp.read())
        if out.get("error"):
            raise CreditError(f"The chain refused the request: {out['error'].get('message', '')}")
        return out.get("result")

    def receipt(self, tx_hash: str) -> dict[str, Any] | None:
        return self.call("eth_getTransactionReceipt", [tx_hash])

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)


def _topic_address(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def transferred(receipt: dict[str, Any], token: str, sender: str, treasury: str) -> int:
    """Base units of `token` moved from `sender` to `treasury` in this receipt.

    Only Transfer events emitted by the token contract itself count. Any other
    contract can emit an event with the same shape and the same topics, and a
    check that read the topics without checking who emitted them would credit a
    fake token as $MIGRA.
    """
    token, sender, treasury = token.lower(), sender.lower(), treasury.lower()
    total = 0
    for log in receipt.get("logs") or []:
        topics = [t.lower() for t in (log.get("topics") or [])]
        if (str(log.get("address", "")).lower() != token or len(topics) != 3
                or topics[0] != TRANSFER_TOPIC):
            continue
        if _topic_address(topics[1]) != sender or _topic_address(topics[2]) != treasury:
            continue
        total += int(log.get("data") or "0x0", 16)
    return total


def check_deposit(chain: Chain, cfg: Settings, tx_hash: str, wallet: str) -> tuple[int, int]:
    """(base units credited, block number), or a CreditError saying why not."""
    receipt = chain.receipt(tx_hash)
    if not receipt:
        raise CreditError("pending")
    if int(receipt.get("status", "0x0"), 16) != 1:
        raise CreditError("That transaction failed on chain, so nothing was sent.")

    block = int(receipt["blockNumber"], 16)
    if chain.block_number() - block + 1 < cfg.confirmations:
        raise CreditError("pending")

    amount = transferred(receipt, cfg.token, wallet, cfg.treasury)
    if amount <= 0:
        raise CreditError("That transaction did not send $MIGRA from your linked "
                          "wallet to the MIGRAGENT treasury.")
    return amount, block


# --- the ledger ----------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


@dataclass
class Balance:
    wallet: str
    balance: int = 0            # base units
    paid_until: str = ""

    def active(self, now: datetime | None = None) -> bool:
        until = _parse(self.paid_until)
        return bool(until and until > (now or _now()))


class Credits:
    """Wallet links, balances, deposits and spends, all in Firestore.

    Balances are stored as decimal strings. An 18-decimal token overflows a
    64-bit integer at about nine tokens, and Firestore integers are 64-bit.
    """

    def __init__(self, client) -> None:
        self._db = client

    # links

    def wallet_for(self, case_id: str) -> str:
        if not case_id:
            return ""
        snap = self._db.collection(WALLET_LINKS).document(case_id).get()
        return (snap.to_dict() or {}).get("wallet", "") if snap.exists else ""

    def unlink(self, case_id: str) -> int:
        ref = self._db.collection(WALLET_LINKS).document(case_id)
        if ref.get().exists:
            ref.delete()
            return 1
        return 0

    # sign-in

    def issue_nonce(self, case_id: str, domain: str, address: str) -> str:
        nonce = secrets.token_hex(12)
        issued = _iso(_now())
        message = sign_in_message(domain, address, nonce, issued)
        self._db.collection(NONCES).document(case_id).set({
            "case_id": case_id, "address": address.lower(), "message": message,
            "issued_at": issued})
        return message

    def verify(self, case_id: str, address: str, signature: str) -> str:
        """Link the wallet if the signature is good. One nonce, one use."""
        ref = self._db.collection(NONCES).document(case_id)
        snap = ref.get()
        if not snap.exists:
            raise CreditError("Start the sign-in again; that one has expired.")
        pending = snap.to_dict() or {}
        ref.delete()

        issued = _parse(pending.get("issued_at", ""))
        if not issued or _now() - issued > NONCE_TTL:
            raise CreditError("Start the sign-in again; that one has expired.")
        if pending.get("address") != address.lower():
            raise CreditError("The wallet that signed is not the one that asked.")

        signer = recover_signer(pending.get("message", ""), signature)
        if not signer or signer != address.lower():
            raise CreditError("That signature does not belong to this wallet.")

        self._db.collection(WALLET_LINKS).document(case_id).set({
            "case_id": case_id, "wallet": signer, "linked_at": _iso(_now())})
        return signer

    # balances

    def account(self, wallet: str) -> Balance:
        if not wallet:
            return Balance(wallet="")
        snap = self._db.collection(WALLETS).document(wallet).get()
        data = (snap.to_dict() or {}) if snap.exists else {}
        return Balance(wallet=wallet, balance=int(data.get("balance", "0") or 0),
                       paid_until=data.get("paid_until", ""))

    def credit(self, wallet: str, tx_hash: str, amount: int, block: int) -> Balance:
        """Credit a verified deposit exactly once."""
        from google.cloud import firestore

        tx_hash = tx_hash.lower()
        dep_ref = self._db.collection(DEPOSITS).document(tx_hash)
        wal_ref = self._db.collection(WALLETS).document(wallet)

        @firestore.transactional
        def apply(txn) -> Balance:
            if dep_ref.get(transaction=txn).exists:
                raise CreditError("That transaction has already been credited.")
            snap = wal_ref.get(transaction=txn)
            data = (snap.to_dict() or {}) if snap.exists else {}
            balance = int(data.get("balance", "0") or 0) + amount
            now = _iso(_now())
            txn.set(dep_ref, {"wallet": wallet, "amount": str(amount),
                              "block": block, "at": now})
            txn.set(wal_ref, {"wallet": wallet, "balance": str(balance),
                              "updated_at": now}, merge=True)
            txn.set(self._db.collection(LEDGER).document(), {
                "wallet": wallet, "kind": "deposit", "amount": str(amount),
                "tx_hash": tx_hash, "at": now})
            return Balance(wallet=wallet, balance=balance,
                           paid_until=data.get("paid_until", ""))

        return apply(self._db.transaction())

    # quotes

    def quote(self, case_id: str, units: int) -> None:
        """Hold today's price for this case while the transfer confirms."""
        self._db.collection(QUOTES).document(case_id).set({
            "case_id": case_id, "units": str(units), "at": _iso(_now())})

    def price_for(self, case_id: str, current: int) -> int:
        """The held quote if it is recent and lower, otherwise the current price."""
        snap = self._db.collection(QUOTES).document(case_id).get()
        if not snap.exists:
            return current
        data = snap.to_dict() or {}
        at = _parse(data.get("at", ""))
        if not at or _now() - at > QUOTE_TTL:
            return current
        return min(current, int(data.get("units", "0") or 0) or current)

    def unlock(self, wallet: str, price: int) -> Balance:
        """Spend `price` base units on thirty more days."""
        from google.cloud import firestore

        wal_ref = self._db.collection(WALLETS).document(wallet)

        @firestore.transactional
        def apply(txn) -> Balance:
            snap = wal_ref.get(transaction=txn)
            data = (snap.to_dict() or {}) if snap.exists else {}
            balance = int(data.get("balance", "0") or 0)
            if balance < price:
                raise CreditError("Not enough $MIGRA credit for a month yet.")
            now = _now()
            current = _parse(data.get("paid_until", ""))
            until = max(now, current) if current else now
            until = _iso(until + MONTH)
            txn.set(wal_ref, {"wallet": wallet, "balance": str(balance - price),
                              "paid_until": until, "updated_at": _iso(now)}, merge=True)
            txn.set(self._db.collection(LEDGER).document(), {
                "wallet": wallet, "kind": "unlock", "amount": str(price),
                "paid_until": until, "at": _iso(now)})
            return Balance(wallet=wallet, balance=balance - price, paid_until=until)

        return apply(self._db.transaction())

    def active_for_case(self, case_id: str) -> bool:
        if not settings().live:
            return False
        return self.account(self.wallet_for(case_id)).active()
