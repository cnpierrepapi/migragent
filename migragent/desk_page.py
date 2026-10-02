"""The Desk: paid alerts for the people whose job is knowing the rules.

WHO IT IS FOR
-------------
Study-abroad agents and immigration advisers. A missed rule change costs them
a commission or a case, and they already pay to stay current (Free Movement is
£26 a month in the UK). Readers who are only curious stay on the free wire.

THE DEPOSIT
-----------
The Desk is not built yet. This page tests whether anybody will pay for it
before it is: ₦5,000 reserves a place, comes off the first month, and is
refunded in full on request. A deposit is the evidence; an email is not.

Payment is Paystack's hosted checkout. The server starts the transaction,
Paystack takes the card, and the server then asks Paystack itself whether the
money arrived before writing "paid". The webhook does the same for anybody who
never comes back to the page. The amount and currency are checked too, so a
tampered callback cannot mark a reservation paid. Without PAYSTACK_SECRET_KEY
the button takes nobody's money and the page says so.
"""
from __future__ import annotations

import html
from typing import Any

from .masthead import MASTHEAD
from .registry import JURISDICTIONS
from .result_page import HEAD
from .seo import meta

RESERVATIONS = "desk_reservations"
DEPOSIT_KOBO = 500_000  # ₦5,000

PLANS = (
    ("solo", "Solo agent", "₦15,000 a month", "One person. Every country you sell."),
    ("agency", "Agency", "₦45,000 a month", "Up to five people, shared alerts, one invoice."),
    ("adviser", "International adviser", "$29 a month", "For lawyers and advisers outside Nigeria."),
)


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding-bottom: 80px }
  main { max-width: 1000px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  h1 { font-size: clamp(2rem, 4.4vw, 3rem); margin: 0 0 10px }
  .lede { font: italic 1.22rem/1.55 var(--font-serif); margin: 0 0 22px; max-width: 60ch }
  p { font: 1.06rem/1.7 var(--font-serif) }
  h2 { font-size: 1.35rem; margin: 34px 0 8px; padding-top: 12px; border-top: 1px solid var(--ink) }
  .plans { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--ink);
           border-bottom: 3px double var(--ink); margin: 10px 0 24px }
  .plan { padding: 16px 18px 16px 0; border-right: 1px solid var(--rule) }
  .plan + .plan { padding-left: 18px }
  .plan:last-child { border-right: 0 }
  .plan b { display: block; font: 640 1.2rem var(--font-display) }
  .plan .price { font: 640 1.6rem var(--font-display); color: var(--primary); margin: 6px 0 }
  .plan span { font: .9rem/1.5 var(--font-serif); color: var(--ink-soft) }
  ul.get { padding-left: 20px; margin: 0 }
  ul.get li { font: 1.04rem/1.6 var(--font-serif); padding: 4px 0 }
  form.reserve { border: 1px solid var(--ink); background: var(--paper-raised); padding: 20px 22px; max-width: 640px }
  form.reserve label { display: block; font: 500 .72rem var(--font-mono); text-transform: uppercase;
                       letter-spacing: .06em; color: var(--ink-soft); margin: 12px 0 4px }
  form.reserve input, form.reserve select { width: 100%; padding: 10px 11px; border: 1px solid var(--rule);
       background: var(--paper); color: var(--ink); font: .95rem var(--font-body); border-radius: var(--radius-sm) }
  form.reserve button { margin-top: 16px; padding: 12px 22px; border: 0; background: var(--primary); color: var(--paper);
       font: 600 .95rem var(--font-body); border-radius: var(--radius); cursor: pointer }
  form.reserve button[disabled] { opacity: .5; cursor: not-allowed }
  .fine { font: .74rem/1.7 var(--font-mono); color: var(--ink-soft) }
  .msg { border-left: 3px solid var(--accent); padding: 8px 14px; background: var(--paper-raised);
         font: .9rem var(--font-mono); margin: 0 0 18px }
  .msg.bad { border-color: var(--warn) }
  @media (max-width: 760px) { .plans { grid-template-columns: 1fr }
    .plan, .plan + .plan { padding: 14px 0; border-right: 0; border-bottom: 1px solid var(--rule) } }
'''


def desk_html(*, live: bool, message: str = "", bad: bool = False) -> str:
    plans = "".join(f'<div class="plan"><b>{_e(n)}</b><div class="price">{_e(p)}</div><span>{_e(d)}</span></div>'
                    for _k, n, p, d in PLANS)
    options = "".join(f'<option value="{k}">{_e(n)}, {_e(p)}</option>' for k, n, p, _d in PLANS)
    msg = f'<p class="msg{" bad" if bad else ""}">{_e(message)}</p>' if message else ""
    button = ('<button type="submit">Reserve with ₦5,000</button>' if live else
              '<button type="submit">Join the waitlist</button>')
    note = ("You go to Paystack to pay, then come back here. The ₦5,000 comes off your first month, "
            "and if you change your mind before then, you get all of it back. Email us and it's done."
            if live else
            "Payments aren't switched on yet, so this takes nobody's money. Leave your email and you're first in line.")
    from .round import OFFERED

    countries = len(OFFERED)  # read every morning; not every country on file
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
{meta(title="The Desk: rule changes for agents and immigration advisers", path="/desk",
      description="Alerts for the countries you sell, a weekly briefing and a searchable archive with the government's own wording. For study-abroad agents and immigration advisers.")}
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>
  <h1>The Desk</h1>
  <p class="lede">For the people whose job is knowing the rules. One missed change can cost you a student or a
  case. This makes sure you hear about it the morning it happens.</p>
  {msg}
  <div class="plans">{plans}</div>

  <h2>What you get</h2>
  <ul class="get">
    <li>An alert the morning a rule changes in a country you sell, with who it affects.</li>
    <li>A weekly briefing of everything that moved across your countries.</li>
    <li>The full archive, searchable, every line with the government's own sentence under it.</li>
    <li>A monthly round-up you can forward to your own clients, with your name on it.</li>
  </ul>
  <p>It reads {countries} countries' official pages every morning, the same reading that writes
  <a href="/articles">the wire</a>. The wire is free and stays free. The Desk is the version that comes to you, sorted for
  your countries, and doesn't make you go looking.</p>

  <h2>Reserve a place</h2>
  <p>The Desk opens to the first agents who reserve. A deposit holds your place.</p>
  <form class="reserve" method="post" action="/desk/reserve">
    <label for="d-email">Email</label><input id="d-email" type="email" name="email" required autocomplete="email">
    <label for="d-name">Your name or agency</label><input id="d-name" type="text" name="name" maxlength="120">
    <label for="d-plan">Plan</label><select id="d-plan" name="plan">{options}</select>
    <div style="position:absolute;left:-9999px"><input type="text" name="website" tabindex="-1" autocomplete="off"></div>
    {button}
    <p class="fine">{note}</p>
  </form>
  <p class="fine">Questions: admin@onenept.com. <a href="/data">What we keep</a>.</p>
</main></body></html>'''


def thanks_html(paid: bool, plan: str = "") -> str:
    name = dict((k, n) for k, n, _p, _d in PLANS).get(plan, "The Desk")
    body = (f"<h1>You're in.</h1><p class=\"lede\">Your ₦5,000 is in and your place on {_e(name)} is held. "
            "We'll email you when the Desk opens, and the deposit comes off your first month. Want it back? "
            "Email admin@onenept.com and it's refunded in full.</p>" if paid else
            "<h1>Not paid yet</h1><p class=\"lede\">Paystack hasn't confirmed this payment. If you were charged, "
            "it can take a minute; refresh this page. If it still says this, email admin@onenept.com with the "
            "reference and we'll sort it out.</p>")
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
<meta name="robots" content="noindex"><title>The Desk | MIGRAGENT</title>
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>{body}<p><a href="/articles">Back to the wire</a></p></main></body></html>'''
