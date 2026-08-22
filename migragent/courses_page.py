"""The courses this person can apply to, and what we could not find out.

WHAT THIS SCREEN IS
-------------------
The end of the study path. They said what they wanted, uploaded what they had,
and picked from the countries their own documents opened. This is the answer:
the courses at their level, in their subject, at schools on the official
register, with the school's own words behind each one.

THREE RULES IT FOLLOWS, ALL OF THEM SET ELSEWHERE
--------------------------------------------------
**Nothing is hidden for being incomplete.** A course with no fee still appears,
with a question pointed at the school. migragent/gaps.py owns that, and this
screen is the first thing to lean on it: only 146 of 3,938 courses carry a fee,
so a screen that showed complete rows would show almost nothing.

**Intake dates are the subscription.** A free case sees the course and a line
saying when it starts is what the subscription buys. That is not the same as a
gap and is never phrased as one, because we know the answer and are not saying
it. migragent/entitlements.py owns that line.

**The best-offer country is chosen and never shown.** migragent/rubric.py ranks
what they picked and the screen leads with the winner, silently. A person is
never told a country scored 71 and another scored 49; they are shown the one we
would start with, and the rest underneath, in an order.

WHY THE ORDER IS NOT A RANKING ANYBODY SEES
--------------------------------------------
Printing the score would dress an editorial choice as a finding. We know how
many permit holders a school takes and roughly how much its town costs; we do
not know what somebody's life is like. So the order carries the opinion, and the
page carries the evidence.
"""
from __future__ import annotations

import html
from typing import Any

from .entitlements import PRICE_LABEL
from .registry import JURISDICTIONS
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 44px 24px 96px }
  main { max-width: 860px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 28px }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }
  h1 { font-family: var(--font-display); font-size: clamp(1.8rem, 4.4vw, 2.5rem);
       margin: 0 0 12px; line-height: 1.08 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 30px; max-width: 64ch }

  h2 { font-size: .78rem; text-transform: uppercase; letter-spacing: .14em;
       font-family: var(--font-body); font-weight: 600; color: var(--ink-soft);
       margin: 40px 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--rule) }
  h2 .count { text-transform: none; letter-spacing: 0; float: right; font-weight: 400 }

  .course { border: 1px solid var(--rule); background: var(--paper-raised);
            border-radius: var(--radius); padding: 18px 20px; margin-bottom: 10px }
  .course h3 { font: 600 1.05rem/1.4 var(--font-body); margin: 0 0 4px }
  .school { font-family: var(--font-mono); font-size: .73rem; color: var(--ink-soft);
            margin-bottom: 10px }
  .facts { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px }
  .fact { border: 1px solid var(--rule); border-radius: var(--radius-sm);
          padding: 5px 10px; font-size: .82rem; background: var(--paper) }
  .fact b { font-weight: 600 }
  .fact.locked { border-style: dashed; color: var(--ink-soft) }
  .fact.locked a { color: var(--accent); text-decoration: none }

  .asks { border-top: 1px solid var(--rule); padding-top: 10px; margin-top: 4px }
  .asks p { margin: 0 0 6px; font-family: var(--font-mono); font-size: .72rem;
            color: var(--ink-soft); line-height: 1.6 }
  .asks a { color: var(--link) }
  .src { font-family: var(--font-mono); font-size: .69rem; color: var(--ink-soft);
         word-break: break-all; margin-top: 8px; display: block }

  .sell { border: 1px solid var(--accent); border-radius: var(--radius);
          background: var(--paper-raised); padding: 22px 24px; margin: 34px 0 }
  .sell b { display: block; font-family: var(--font-display); font-size: 1.25rem;
            margin-bottom: 8px }
  .sell p { margin: 0 0 16px; color: var(--ink-soft); line-height: 1.6; max-width: 60ch }
  .cta { display: inline-flex; padding: 12px 24px; border-radius: var(--radius);
         background: var(--primary); color: var(--paper); text-decoration: none;
         font: 600 .92rem var(--font-body) }
  .none { border: 1px dashed var(--rule); border-radius: var(--radius); padding: 26px;
          color: var(--ink-soft); line-height: 1.7 }
'''


def _fact(label: str, value: str) -> str:
    return f'<span class="fact">{label} <b>{_e(value)}</b></span>'


def _course(row: dict[str, Any], subscriber: bool) -> str:
    facts = []
    if row.get("duration"):
        facts.append(_fact("Length", row["duration"][:34]))
    if row.get("fee_international"):
        facts.append(_fact("International fee", row["fee_international"][:34]))

    if row.get("intake"):
        facts.append(_fact("Starts", row["intake"][:34]))
    elif row.get("intake_withheld"):
        # We hold this and are not showing it. Said plainly, and never mixed in
        # with the things we simply do not know.
        facts.append('<span class="fact locked">Start date '
                     f'<a href="/subscribe">{_e(PRICE_LABEL)}</a></span>')

    asks = ""
    if row.get("gaps"):
        lines = "".join(
            f'<p>{_e(g["question"])} '
            f'<a href="{_e(row.get("ask_url"))}" target="_blank" '
            f'rel="noopener noreferrer">Ask {_e(row.get("institution"))}</a></p>'
            for g in row["gaps"][:3])
        asks = f'<div class="asks">{lines}</div>'

    entry = (f'<p class="sub" style="margin:0 0 10px;font-size:.9rem">'
             f'{_e(row["entry_requirements"][:200])}</p>'
             if row.get("entry_requirements") else "")

    return (f'<article class="course">'
            f'<h3>{_e(row.get("title"))}</h3>'
            f'<div class="school">{_e(row.get("institution"))}</div>'
            f'{entry}'
            f'<div class="facts">{"".join(facts)}</div>'
            f'{asks}'
            f'<a class="src" href="{_e(row.get("source_url"))}" target="_blank" '
            f'rel="noopener noreferrer">{_e(row.get("source_url"))}</a>'
            f'</article>')


def courses_html(*, by_country: list[tuple[str, list[dict[str, Any]]]],
                 level: str, subjects: list[str], subscriber: bool) -> str:
    """`by_country` is already in rubric order; the score itself never arrives here."""
    what = (f"{_e(level)} courses in {_e(', '.join(subjects))}"
            if subjects else f"{_e(level)} courses")

    if not by_country:
        body = ('<div class="none">Nothing matched yet. That is about how much we have '
                'read, not about what is out there. '
                '<a href="/start/level">Change what you are looking for</a>.</div>')
    else:
        blocks = []
        for code, rows in by_country:
            name = JURISDICTIONS.get(code, {}).get("name", code)
            blocks.append(
                f'<h2>{_e(name)}<span class="count">{len(rows)} courses</span></h2>'
                + "".join(_course(r, subscriber) for r in rows[:25]))
        body = "".join(blocks)

    sell = "" if subscriber else f'''
      <div class="sell">
        <b>Know the moment a door opens.</b>
        <p>Start dates and application windows move, and they move without an
        announcement. {PRICE_LABEL} puts every intake date on this page and tells you
        when a new one opens at a school you are looking at.</p>
        <a class="cta" href="/subscribe">See what it covers</a>
      </div>'''

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Courses you can apply to</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Courses you can apply to</h1>
  <p class="sub">{what}, at schools on the official register in the countries you chose.
  Each one links to the page it was read from. Where a school does not publish
  something, we say so and point you at the people who know.</p>
  {sell}
  {body}
  <p style="margin-top:34px"><a href="/dashboard">Your dashboard</a> &middot;
  <a href="/start/level">Change level or subject</a></p>
</main></body></html>'''
