"""$MIGRA: what the token does for the reporter.

Nothing is sold on this page. Until 2 October 2026 $MIGRA paid for a month of
intake dates on somebody's case; the case product is gone, and so is that
checkout. What is left is the part that was always true: $MIGRA launched on
Orbio's agent launchpad, its trading fees become AI balance, and that balance
pays for the reading the wire is built from. The figures here are the desk's
figures, from /api/state, so the page cannot claim more than the job recorded.
"""
from __future__ import annotations

from .live import ORBIO_PAGE, TOKEN
from .masthead import MASTHEAD
from .result_page import HEAD
from .seo import meta, organization, website, breadcrumbs

DEPLOYER = "0x49CD0F898530eA9CbEC73e62efB359F2758478a1"
FAKE = "0x9b7b5e41466b6aa1e21f1077ce5d1db69a2eff90"

STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding-bottom: 80px }
  main { max-width: 860px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  h1 { font-size: clamp(2rem, 4.4vw, 3rem); margin: 0 0 12px }
  .lede { font: italic 1.25rem/1.55 var(--font-serif); margin: 0 0 24px }
  p { font: 1.08rem/1.7 var(--font-serif) }
  h2 { font-size: 1.35rem; margin: 34px 0 8px; padding-top: 12px; border-top: 1px solid var(--ink) }
  .figs { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--ink);
          border-bottom: 3px double var(--ink); margin: 6px 0 26px }
  .figs div { padding: 14px 14px 14px 0; border-right: 1px solid var(--rule); min-width: 0 }
  .figs div:last-child { border-right: 0 }
  .figs b { display: block; font: 640 1.6rem var(--font-display); overflow-wrap: anywhere }
  .figs .paid b { color: var(--accent) }
  .figs span { font: .68rem var(--font-mono); color: var(--ink-soft) }
  .ca { font: .9rem var(--font-mono); background: var(--paper-raised); border: 1px solid var(--ink);
        padding: 14px 16px; overflow-wrap: anywhere }
  .ca b { display: block; font: 500 .66rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase;
          color: var(--accent); margin-bottom: 4px }
  .warn { border-left: 3px solid var(--warn); padding: 4px 0 4px 16px; margin: 18px 0 }
  .warn code { font: .82rem var(--font-mono); overflow-wrap: anywhere }
  ol.flow { counter-reset: s; list-style: none; padding: 0; margin: 0 }
  ol.flow li { counter-increment: s; padding: 10px 0 10px 40px; position: relative; font: 1.04rem/1.6 var(--font-serif);
               border-bottom: 1px dotted var(--rule) }
  ol.flow li::before { content: counter(s); position: absolute; left: 0; top: 10px; font: 600 .9rem var(--font-mono);
                       color: var(--primary) }
  .cta { display: inline-block; padding: 12px 22px; background: var(--primary); color: var(--paper);
         text-decoration: none; font: 600 .92rem var(--font-body); border-radius: var(--radius) }
  .small { font: .74rem/1.7 var(--font-mono); color: var(--ink-soft) }
  @media (max-width: 700px) { .figs { grid-template-columns: repeat(2, 1fr) }
    .figs div:nth-child(even) { border-right: 0 } }
'''

SCRIPT = '''<script>
(() => {
  const $ = (id) => document.getElementById(id);
  const money = (n) => n == null ? "-" : (n < 1 ? "$" + n.toFixed(4) : "$" + n.toFixed(2));
  fetch("/api/state").then((r) => r.json()).then((s) => {
    const o = s.orbio || {}, t = s.token;
    $("m-balance").textContent = money(o.available);
    $("m-spent").textContent = money(o.spent_today);
    $("m-runway").textContent = o.runway_days == null ? "-" : o.runway_days + " days";
    if (t) { $("m-mcap").textContent = "$" + (t.market_cap_usd / 1000).toFixed(1) + "K";
             $("m-grad").textContent = t.graduation_pct + "% to graduation"; }
  }).catch(() => {});
})();
</script>'''


def migra_html() -> str:
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
{meta(title="$MIGRA pays for the reading", path="/migra", description="How $MIGRA's trading fees pay for the AI that reads official immigration rules and writes the wire. Contract, deployer and live figures.")}
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>
  <h1>$MIGRA pays for the reading</h1>
  <p class="lede">The agent that writes this wire runs on AI it pays for itself. $MIGRA is how.</p>

  <div class="figs">
    <div class="paid"><b id="m-balance">-</b><span>AI balance, from $MIGRA fees</span></div>
    <div><b id="m-spent">-</b><span>spent by the agent today</span></div>
    <div><b id="m-runway">-</b><span>runway at this week's pace</span></div>
    <div><b id="m-mcap">-</b><span id="m-grad">market cap</span></div>
  </div>

  <h2>How it works</h2>
  <ol class="flow">
    <li>$MIGRA launched on Orbio's agent launchpad, paired with $ORBIO.</li>
    <li>Every trade pays a creator fee. Orbio splits it: half is staked for the agent, 45% becomes AI balance
    it can spend, 5% goes to the launchpad.</li>
    <li>Every morning the agent re-reads the official pages it holds. A page that didn't move costs nothing.
    One that did is read again by Gemini, through Orbio, out of that balance.</li>
    <li>When a page changes a rule, the agent writes it up for the wire, also paid from the balance.</li>
  </ol>
  <p>So trading the token pays for the work the token is about. When the balance runs dry the agent falls back
  to Google Cloud and carries on, so the wire never stops. It just stops being paid for by $MIGRA until more
  fees come in.</p>

  <h2>The contract</h2>
  <div class="ca"><b>$MIGRA on Robinhood Chain</b>{TOKEN}</div>
  <p class="small">Deployed by {DEPLOYER}. That address is the agent's own wallet, and it's where the fees land.</p>
  <div class="warn"><p>There is a fake. Someone launched a "migragent" token on Orbio that links this site to look
  real. It is <code>{FAKE}</code>, from a different deployer. Check the deployer before you buy anything.</p></div>
  <p><a class="cta" href="{ORBIO_PAGE}" target="_blank" rel="noopener">$MIGRA on Orbio</a></p>
  <p class="small">Nothing here is financial advice. The token pays for AI usage; it is not a share in anything.</p>
</main>{SCRIPT}</body></html>'''
