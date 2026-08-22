"""The one paid thing, and an honest page about it.

WHAT IS BEING SOLD
------------------
Timing. Not access, not the guide, not the evidence: when things happen. Intake
dates and application windows on the study side, and the alert that fires when a
job in a shortage occupation you match is posted on the work side. Both come
from the same daily reading, which is the thing that actually costs money to
run.

WHY THIS PAGE SAYS WHAT IS FREE FIRST
--------------------------------------
Because the free product is good and hiding that would be a strange way to earn
somebody's seven dollars. A page that opens with a locked feature implies the
thing you already have is a trailer. It is not: the countries, the courses, the
requirements and every source behind them are free and stay free.

So the columns are side by side and the free one is not greyed out.

THERE IS NO CHECKOUT AND THE PAGE SAYS SO
------------------------------------------
No billing exists. The button records interest and says that is what it does. A
page that takes a card and then cannot charge it is fraud; a page with a
convincing checkout that quietly goes nowhere is a worse version of the same
instinct. So: a plain statement, an email box, and no theatre.

`entitlements.is_subscriber` returns False for everybody, and this page is the
only place in the product that asks anybody for money.
"""
from __future__ import annotations

import html
from typing import Any

from .entitlements import PRICE_LABEL, PRICE_USD
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 46px 24px 96px }
  main { max-width: 820px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 30px }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }
  h1 { font-family: var(--font-display); font-size: clamp(1.9rem, 4.6vw, 2.6rem);
       margin: 0 0 12px; line-height: 1.07 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 34px; max-width: 60ch }

  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 32px }
  .col { border: 1px solid var(--rule); border-radius: var(--radius);
         background: var(--paper-raised); padding: 22px 24px }
  .col.paid { border-color: var(--accent) }
  .col h2 { font-family: var(--font-display); font-size: 1.2rem; margin: 0 0 4px }
  .col .price { font-family: var(--font-mono); font-size: .74rem; color: var(--ink-soft);
                margin-bottom: 16px }
  .col ul { list-style: none; margin: 0; padding: 0 }
  .col li { padding: 8px 0 8px 24px; position: relative; line-height: 1.5;
            font-size: .94rem; border-bottom: 1px solid var(--rule) }
  .col li:last-child { border-bottom: 0 }
  .col li::before { content: "\\2713"; position: absolute; left: 0; color: var(--primary) }
  .col.paid li::before { color: var(--accent) }

  .honest { border-left: 2px solid var(--warn); padding: 4px 0 4px 14px; margin: 0 0 26px;
            color: var(--ink-soft); line-height: 1.7; font-size: .93rem }
  form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center }
  input[type=email] { flex: 1 1 260px; padding: 13px 14px; border: 1px solid var(--rule);
         border-radius: var(--radius-sm); background: var(--paper-raised);
         color: var(--ink); font: .96rem var(--font-body) }
  input:focus { outline: 0; border-color: var(--primary); box-shadow: var(--ring) }
  .cta { padding: 13px 26px; border: 0; border-radius: var(--radius);
         background: var(--primary); color: var(--paper);
         font: 600 .95rem var(--font-body); cursor: pointer }
  .note { font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft);
          margin-top: 14px; line-height: 1.7 }
  @media (max-width: 720px) { .cols { grid-template-columns: 1fr } }
'''

FREE = ("Every country your documents qualify you for",
        "Every course we have read, at your level and in your subject",
        "The school's own words behind each one, with a link",
        "Your guide, your CV in three countries' shapes, your board",
        "A question and the school's contact page wherever they do not publish something")

PAID_STUDY = ("Start dates and application windows on every course",
              "An alert when an intake opens at a school you are watching",
              "An alert when a rule that affects your route changes",
              "The daily re-reading that finds all of it")

PAID_WORK = ("An alert when a job you qualify for is posted",
             "An alert when a country adds your occupation to its shortage list",
             "An alert when a rule that affects your route changes",
             "The daily re-reading that finds all of it")


def subscribe_html(lane: str = "study", saved: str = "", email: str = "") -> str:
    paid = PAID_WORK if lane == "work" else PAID_STUDY
    headline = ("Know the moment a job you qualify for is posted."
                if lane == "work"
                else "Know the moment a door opens.")

    notice = (f'<p class="note" style="color:var(--primary)">{_e(saved)}</p>'
              if saved else "")

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>{PRICE_LABEL}</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>{_e(headline)}</h1>
  <p class="sub">Everything you have seen so far is free and stays free. What
  {PRICE_LABEL} buys is timing: the dates, and being told the day they move.</p>

  <div class="cols">
    <div class="col">
      <h2>What you have</h2>
      <div class="price">Free, no account, no card</div>
      <ul>{"".join(f"<li>{_e(x)}</li>" for x in FREE)}</ul>
    </div>
    <div class="col paid">
      <h2>What {PRICE_LABEL} adds</h2>
      <div class="price">{PRICE_USD} dollars a month, cancel whenever</div>
      <ul>{"".join(f"<li>{_e(x)}</li>" for x in paid)}</ul>
    </div>
  </div>

  <p class="honest"><b>Billing is not live yet, so nothing here takes a card.</b>
  Leave an address and we will tell you when it is. We would rather say that than
  show you a checkout that goes nowhere.</p>

  {notice}
  <form method="post" action="/subscribe">
    <input type="email" name="email" required placeholder="you@example.com"
           value="{_e(email)}">
    <input type="hidden" name="lane" value="{_e(lane)}">
    <button class="cta" type="submit">Tell me when it opens</button>
  </form>
  <p class="note">One address, used once, for that one message. It is deleted with
  your case like everything else. <a href="/data">What happens to your data</a>.</p>

  <p class="note" style="margin-top:26px"><a href="/dashboard">Back to your dashboard</a></p>
</main></body></html>'''
