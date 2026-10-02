"""What the agent is doing, for the front page, from rows the job already wrote.

WHAT THIS IS
------------
The reading job has always written down every round: pages fetched, pages that
did not move and so cost nothing, pages that moved, requirements kept, and since
1 Oct 2026 what Orbio carried and charged. Changes are written with the one
sentence the model gave about what a difference means. That record lived on
/rounds, which nobody finds.

This turns it into a feed and a handful of figures that the front page polls.
Nothing here is computed for show: every line is one row, and every figure is a
sum of rows or a balance the worker read from Orbio and wrote down. The web
service never holds the Orbio key.

The feed builder is a pure function of the rows, so `tools/test_live.py` can
check it without a database.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

TOKEN = "0xdebc1c4ea1689a7507568ecfeacb42599b493b60"
ORBIO_AGENT = "https://www.orbio.so/api/protocol/agents/" + TOKEN
ORBIO_PAGE = "https://www.orbio.so/launchpad/" + TOKEN

# What Cloud Scheduler starts, in UTC. Mirrors the table on /rounds.
SCHEDULE = (("03:17", "retention sweep"), ("04:40", "watch round"), ("05:40", "articles"))

CACHE_SECONDS = 30
_cache: dict[str, Any] = {"at": 0.0, "state": None}
_token_cache: dict[str, Any] = {"at": 0.0, "value": None}

def _name(code: str) -> str:
    from .registry import JURISDICTIONS

    return JURISDICTIONS.get(code, {}).get("name", code)


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _money(usd: float) -> str:
    return f"${usd:.4f}" if usd < 1 else f"${usd:,.2f}"


def next_run(now: datetime) -> dict[str, str]:
    for hhmm, what in SCHEDULE:
        h, m = map(int, hhmm.split(":"))
        at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if at > now:
            return {"at": at.isoformat(), "what": what}
    h, m = map(int, SCHEDULE[0][0].split(":"))
    at = (now + timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)
    return {"at": at.isoformat(), "what": SCHEDULE[0][1]}


def round_line(r: dict[str, Any]) -> dict[str, Any]:
    """One round as one feed line, in words, with what it cost."""
    place = f"{_name(r.get('jurisdiction', ''))} {r.get('lane', '')}"
    fetched, unchanged, changed = r.get("fetched", 0), r.get("unchanged", 0), r.get("changed", 0)
    kept = r.get("kept", 0)
    if r.get("mode") == "watch":
        parts = [f"re-read {fetched} pages"]
        if unchanged:
            parts.append(f"{unchanged} unchanged ($0)")
        if changed:
            parts.append(f"{changed} moved")
    else:
        parts = [f"read {fetched} pages"]
    if kept:
        parts.append(f"{kept} requirements kept")
    if r.get("failed"):
        parts.append(f"{r['failed']} failed")
    calls, usd = r.get("orbio_calls", 0), float(r.get("orbio_usd") or 0)
    if calls:
        cost = f"{_money(usd)} from its own budget"
    else:
        cost = ""
    return {"at": r.get("finished_at") or r.get("started_at", ""),
            "role": "WATCH" if r.get("mode") == "watch" else "READ",
            "text": f"{place}: " + ", ".join(parts), "cost": cost}


def change_line(c: dict[str, Any]) -> dict[str, Any]:
    place = f"{_name(c.get('jurisdiction', ''))} {c.get('lane', '')}"
    host = urlparse(c.get("source_url", "")).netloc.replace("www.", "")
    what = c.get("summary") or f"{c.get('added', 0)} lines added, {c.get('removed', 0)} removed"
    return {"at": c.get("after_read_at", ""), "role": "CHANGE",
            "text": f"{place}, {host}: {what}", "cost": "", "url": c.get("source_url", "")}


def build_state(*, rounds: list[dict[str, Any]], changes: list[dict[str, Any]],
                orbio: dict[str, Any] | None, token: dict[str, Any] | None,
                requirements: int, now: datetime) -> dict[str, Any]:
    today = now.date().isoformat()
    todays = [r for r in rounds if (r.get("started_at") or "")[:10] == today]
    last = max((r.get("finished_at") or r.get("started_at") or "" for r in rounds), default="")

    # None, not zero, when no round today recorded a cost at all: rounds from
    # before 1 Oct 2026 carry no Orbio fields, and $0 would be a false figure.
    costed = [r for r in todays if "orbio_usd" in r]
    spent_today = sum(float(r.get("orbio_usd") or 0) for r in costed) if costed else None
    week_ago = (now - timedelta(days=7)).isoformat()
    by_day: dict[str, float] = {}
    for r in rounds:
        if (r.get("started_at") or "") >= week_ago and r.get("orbio_usd"):
            day = r["started_at"][:10]
            by_day[day] = by_day.get(day, 0.0) + float(r["orbio_usd"])

    available = None
    runway = None
    if orbio and orbio.get("available") not in (None, ""):
        try:
            available = float(orbio["available"])
            daily = sum(by_day.values()) / len(by_day) if by_day else 0.0
            runway = int(available / daily) if daily > 0 else None
        except (TypeError, ValueError):
            available = None

    # Only changes the model said alter what is required. A page whose wording
    # moved and whose rules did not is counted on the card, not listed.
    material = [c for c in changes if c.get("material")]
    feed = [round_line(r) for r in rounds[:40]] + [change_line(c) for c in material[:20]]
    feed = [f for f in feed if f["at"]]
    feed.sort(key=lambda f: f["at"], reverse=True)

    last_dt = _parse(last)
    working = bool(last_dt and now - last_dt < timedelta(minutes=10))
    return {
        "now": now.isoformat(),
        "status": {"phase": "READING" if working else "IDLE", "last_round_at": last,
                   "next": next_run(now)},
        "stats": {
            "pages_today": sum(r.get("fetched", 0) for r in todays),
            "unchanged_today": sum(r.get("unchanged", 0) for r in todays),
            "moved_today": sum(r.get("changed", 0) for r in todays),
            "changes_week": sum(1 for c in changes if (c.get("after_read_at") or "") >= week_ago),
            "rule_changes_week": sum(1 for c in changes if c.get("material")
                                     and (c.get("after_read_at") or "") >= week_ago),
            "requirements": requirements,
        },
        "orbio": {"available": available, "used": (orbio or {}).get("used"),
                  "at": (orbio or {}).get("at"), "spent_today": None if spent_today is None else round(spent_today, 6),
                  "runway_days": runway, "page": ORBIO_PAGE},
        "token": token,
        "feed": feed[:40],
    }


def token_figures() -> dict[str, Any] | None:
    """$MIGRA's market cap and curve progress from Orbio's public read. Cached."""
    if time.time() - _token_cache["at"] < 120 and _token_cache["value"] is not None:
        return _token_cache["value"]
    try:
        req = urllib.request.Request(ORBIO_AGENT, headers={"User-Agent": "migragent"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            d = json.load(resp)
        value = {"market_cap_usd": int((d.get("price") or {}).get("marketCapMicroUsd") or 0) / 1e6,
                 "graduation_pct": int((d.get("curve") or {}).get("progressBps") or 0) / 100,
                 "ca": TOKEN, "page": ORBIO_PAGE}
    except (OSError, ValueError):
        value = _token_cache["value"]
    _token_cache.update(at=time.time(), value=value)
    return value


def state(db, requirements: int) -> dict[str, Any]:
    """The front page's figures, at most CACHE_SECONDS old."""
    if _cache["state"] is not None and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["state"]
    from google.cloud import firestore

    rounds = [d.to_dict() for d in db.collection("rounds")
              .order_by("started_at", direction=firestore.Query.DESCENDING).limit(80).stream()]
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    changes = [d.to_dict() for d in db.collection("changes")
               .where(filter=firestore.FieldFilter("after_read_at", ">=", week_ago))
               .order_by("after_read_at", direction=firestore.Query.DESCENDING).limit(40).stream()]
    snap = db.collection("agent_state").document("orbio").get()
    built = build_state(rounds=rounds, changes=changes,
                        orbio=snap.to_dict() if snap.exists else None,
                        token=token_figures(), requirements=requirements,
                        now=datetime.now(timezone.utc))
    _cache.update(at=time.time(), state=built)
    return built
