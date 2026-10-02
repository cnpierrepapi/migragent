"""$MIGRA governance: holders vote on what the agent covers next.

Low stakes on purpose. A proposal is a question the editor puts up ("Which
country should the agent read next?") with a few options. A holder connects a
wallet and signs their choice: a signature, not a transaction, so it costs no
gas and moves nothing. The editor acts on the result.

HOW VOTES ARE WEIGHTED, AND WHY AT THE CLOSE
--------------------------------------------
By $MIGRA held, read from the chain when the vote closes. Weighting at the
moment of voting would let somebody vote, send their tokens to a second wallet,
and vote again with the same tokens. At the close every token is in exactly one
wallet, so it counts once. While a vote is open the page shows a running tally
at current balances, marked provisional.

One vote per wallet per proposal; voting again replaces the earlier choice
until the close. The signed message names the proposal, the option and the
wallet, so a signature cannot be replayed onto a different question.
"""
from __future__ import annotations

import json
import re
import secrets
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

PROPOSALS = "proposals"
VOTES = "votes"
TOKEN = "0xdebc1c4ea1689a7507568ecfeacb42599b493b60"
RPC = "https://rpc.mainnet.chain.robinhood.com"
CHAIN_ID = 4663
_ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def message(proposal_id: str, option: str, wallet: str) -> str:
    """The exact text a holder signs. Written here, never taken from the browser."""
    return (f"MIGRAGENT governance vote\nProposal: {proposal_id}\nOption: {option}\n"
            f"Wallet: {wallet.lower()}\nChain ID: {CHAIN_ID}\nThis signature is free and moves no tokens.")


def recover(text: str, signature: str) -> str:
    from eth_account import Account
    from eth_account.messages import encode_defunct

    try:
        return Account.recover_message(encode_defunct(text=text), signature=signature).lower()
    except Exception:  # noqa: BLE001
        return ""


def balance(wallet: str) -> int:
    """$MIGRA held by a wallet now, in base units. 0 if the chain does not answer."""
    data = "0x70a08231" + wallet[2:].lower().rjust(64, "0")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": TOKEN, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json",
                                                         "User-Agent": "migragent/governance"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(json.load(resp).get("result") or "0x0", 16)
    except Exception:  # noqa: BLE001
        return 0


def create(db, title: str, question: str, options: list[str], days: int) -> str:
    pid = secrets.token_hex(5)
    db.collection(PROPOSALS).document(pid).set({
        "id": pid, "title": title[:120], "question": question[:400],
        "options": [o[:80] for o in options if o][:8], "opens_at": _now().isoformat(timespec="seconds"),
        "closes_at": (_now() + timedelta(days=max(1, min(days, 30)))).isoformat(timespec="seconds"),
        "status": "open", "result": None})
    return pid


def is_open(p: dict[str, Any]) -> bool:
    return p.get("status") == "open" and _now().isoformat() < p.get("closes_at", "")


def cast(db, proposal_id: str, option: str, wallet: str, signature: str) -> str:
    """'' when the vote is recorded, otherwise why not, in words."""
    snap = db.collection(PROPOSALS).document(proposal_id).get()
    if not snap.exists:
        return "That proposal doesn't exist."
    p = snap.to_dict()
    if not is_open(p):
        return "That vote has closed."
    if option not in p.get("options", []):
        return "That isn't one of the options."
    if not _ADDR.match(wallet or ""):
        return "That isn't a wallet address."
    signer = recover(message(proposal_id, option, wallet), signature)
    if signer != wallet.lower():
        return "The signature doesn't belong to that wallet."
    if balance(signer) <= 0:
        return "This wallet holds no $MIGRA, so it has no vote."
    db.collection(VOTES).document(f"{proposal_id}-{signer}").set({
        "proposal": proposal_id, "wallet": signer, "option": option, "signature": signature,
        "at": _now().isoformat(timespec="seconds")})
    return ""


def tally(db, p: dict[str, Any]) -> dict[str, Any]:
    """Weights read from the chain now. Final, and stored, once the vote has closed."""
    from google.cloud import firestore

    if p.get("result"):
        return p["result"]
    votes = [d.to_dict() for d in db.collection(VOTES)
             .where(filter=firestore.FieldFilter("proposal", "==", p["id"])).stream()]
    weights = {o: 0 for o in p.get("options", [])}
    voters = {o: 0 for o in p.get("options", [])}
    for v in votes:
        w = balance(v["wallet"])
        if v["option"] in weights and w > 0:
            weights[v["option"]] += w
            voters[v["option"]] += 1
    result = {"weights": {k: str(v) for k, v in weights.items()}, "voters": voters, "wallets": len(votes),
              "counted_at": _now().isoformat(timespec="seconds"), "final": not is_open(p)}
    if not is_open(p):
        db.collection(PROPOSALS).document(p["id"]).update({"status": "closed", "result": result})
    return result


def proposals(db) -> list[dict[str, Any]]:
    rows = [d.to_dict() for d in db.collection(PROPOSALS).stream()]
    return sorted(rows, key=lambda p: p.get("opens_at", ""), reverse=True)
