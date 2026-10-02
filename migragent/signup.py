"""Alerts signup: the one thing a reader can give MIGRAGENT, and only if they want to.

An email, a role, and the countries they care about. Nothing else. The role is
the point for now: it tells us who actually reads the wire (agents, lawyers,
HR, people planning a move), which is the test the business model rests on.

No email has been sent yet, and the box says so. There is no sender built;
signing up puts somebody on the list for when alerts start. Each row carries a
token, and /alerts/leave with it deletes the row outright.
"""
from __future__ import annotations

import hashlib
import html
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from .registry import JURISDICTIONS

SUBSCRIBERS = "subscribers"

ROLES = (
    ("agent", "Study-abroad or recruitment agent"),
    ("adviser", "Immigration lawyer or adviser"),
    ("hr", "HR or global mobility"),
    ("university", "University or college"),
    ("mover", "Planning a move myself"),
    ("other", "Something else"),
)

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,24}$", re.I)


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def doc_id(email: str) -> str:
    """One row per address, whatever case it was typed in."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]


def save(db, form, path: str) -> tuple[bool, str]:
    """(ok, token or reason). The honeypot field is for bots; a person never sees it."""
    if (form.get("website") or "").strip():
        return False, "bot"
    email = (form.get("email") or "").strip()
    if not _EMAIL.match(email):
        return False, "That email address doesn't look right."
    role = form.get("role", "")
    if role not in dict(ROLES):
        return False, "Pick what describes you."
    countries = [c for c in form.getlist("country") if c in JURISDICTIONS] or ["ALL"]
    ref = db.collection(SUBSCRIBERS).document(doc_id(email))
    existing = ref.get()
    token = (existing.to_dict() or {}).get("leave_token") if existing.exists else None
    token = token or secrets.token_urlsafe(18)
    ref.set({"email": email.lower(), "role": role, "countries": countries, "signed_up_on": path[:200],
             "leave_token": token, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "consent": "alerts about rule changes in the countries chosen; delete any time"}, merge=True)
    return True, token


def leave(db, token: str) -> bool:
    if not token or len(token) > 64:
        return False
    from google.cloud import firestore

    found = False
    for d in db.collection(SUBSCRIBERS).where(filter=firestore.FieldFilter("leave_token", "==", token)).limit(1).stream():
        d.reference.delete()
        found = True
    return found


STYLE = '''
  .alerts-box { border: 1px solid var(--ink); background: var(--paper-raised); padding: 18px 20px; margin: 36px 0 0 }
  .alerts-box h3 { font: 640 1.25rem var(--font-display); margin: 0 0 6px;
                   font-variation-settings: "opsz" 36, "SOFT" 0, "WONK" 0 }
  .alerts-box p { font: 1rem/1.6 var(--font-serif); margin: 0 0 12px }
  .alerts-box .r { display: flex; gap: 10px; flex-wrap: wrap }
  .alerts-box input[type=email], .alerts-box select { flex: 1 1 220px; padding: 10px 11px; border: 1px solid var(--rule);
       background: var(--paper); color: var(--ink); font: .95rem var(--font-body); border-radius: var(--radius-sm) }
  .alerts-box details { margin: 10px 0 0; font: .78rem var(--font-mono); color: var(--ink-soft) }
  .alerts-box details label { display: inline-block; margin: 6px 14px 0 0; color: var(--ink) }
  .alerts-box button { padding: 10px 18px; border: 0; background: var(--primary); color: var(--paper);
       font: 600 .92rem var(--font-body); border-radius: var(--radius); cursor: pointer }
  .alerts-box .fine { font: .72rem/1.6 var(--font-mono); color: var(--ink-soft); margin: 10px 0 0 }
  .alerts-box .hp { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden }
  .alerts-box .done { color: var(--accent); font: .85rem var(--font-mono) }
'''


def box(path: str, country: str = "", message: str = "", leave_token: str = "") -> str:
    """The signup box. `country` pre-ticks the article's own country."""
    if leave_token:
        return (f'<div class="alerts-box"><p class="done">You\'re on the list. Changed your mind? '
                f'<a href="/alerts/leave?t={_e(leave_token)}">Take me off it</a>, any time.</p></div>')
    roles = "".join(f'<option value="{k}">{_e(v)}</option>' for k, v in ROLES)
    ticks = "".join(f'<label><input type="checkbox" name="country" value="{c}"{" checked" if c == country else ""}> '
                    f'{_e(m["name"])}</label>' for c, m in JURISDICTIONS.items())
    msg = f'<p class="done" style="color:var(--warn)">{_e(message)}</p>' if message else ""
    return f'''<form class="alerts-box" method="post" action="/alerts/signup">
  <h3>Get the rule changes for your countries</h3>
  <p>When a page in a country you follow changes a rule, you get the article. Nothing else.</p>
  {msg}
  <input type="hidden" name="path" value="{_e(path)}">
  <div class="hp"><label>Leave this empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
  <div class="r">
    <input type="email" name="email" required placeholder="you@example.com" autocomplete="email" aria-label="Email">
    <select name="role" required aria-label="What describes you"><option value="">What describes you?</option>{roles}</select>
    <button type="submit">Sign me up</button>
  </div>
  <details{" open" if country else ""}><summary>Countries (leave all empty for every country)</summary>{ticks}</details>
  <p class="fine">Alerts start going out soon; signing up puts you on the first list. Your email is used for this
  and nothing else, and every alert will have a one-click way off. <a href="/data">What we keep</a>.</p>
</form>'''
