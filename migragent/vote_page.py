"""The vote page: open proposals, how to vote, and every result so far."""
from __future__ import annotations

import html
import json
from typing import Any

from .governance import CHAIN_ID, is_open
from .masthead import MASTHEAD
from .result_page import HEAD
from .seo import meta


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding-bottom: 80px }
  main { max-width: 860px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  h1 { font-size: clamp(1.9rem, 4vw, 2.6rem); margin: 0 0 10px }
  .lede { font: italic 1.15rem/1.55 var(--font-serif); margin: 0 0 22px }
  .prop { border-top: 1px solid var(--ink); padding: 18px 0 8px }
  .prop .k { font: 500 .68rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent) }
  .prop h2 { font-size: 1.35rem; margin: 6px 0 6px }
  .prop p { font: 1.04rem/1.6 var(--font-serif); margin: 0 0 12px }
  .opt { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; padding: 8px 0;
         border-bottom: 1px dotted var(--rule) }
  .bar { height: 6px; background: var(--rule); margin-top: 6px }
  .bar i { display: block; height: 6px; background: var(--primary) }
  .opt span.n { font: .76rem var(--font-mono); color: var(--ink-soft) }
  .opt button { padding: 7px 14px; border: 1px solid var(--ink); background: transparent; color: var(--ink);
                font: 600 .82rem var(--font-body); border-radius: var(--radius-sm); cursor: pointer }
  .fine { font: .72rem/1.7 var(--font-mono); color: var(--ink-soft) }
  #v-status { font: .82rem var(--font-mono); color: var(--accent); min-height: 1.2em }
  #v-status.err { color: var(--warn) }
'''

SCRIPT = '''<script>
(() => {
  const status = (t, err) => { const s = document.getElementById("v-status"); s.textContent = t; s.className = err ? "err" : ""; };
  const msg = (pid, opt, w) => "MIGRAGENT governance vote\\nProposal: " + pid + "\\nOption: " + opt + "\\nWallet: " +
    w.toLowerCase() + "\\nChain ID: " + CHAIN + "\\nThis signature is free and moves no tokens.";
  document.querySelectorAll("button[data-pid]").forEach((b) => b.addEventListener("click", async () => {
    if (!window.ethereum) return status("No wallet found in this browser. MetaMask or Rabby will do.", true);
    try {
      const [w] = await window.ethereum.request({method: "eth_requestAccounts"});
      status("Check your wallet and sign. It's free and moves nothing.");
      const sig = await window.ethereum.request({method: "personal_sign", params: [msg(b.dataset.pid, b.dataset.opt, w), w]});
      const r = await fetch("/migra/vote", {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({proposal: b.dataset.pid, option: b.dataset.opt, wallet: w, signature: sig})});
      const out = await r.json().catch(() => ({}));
      if (!r.ok) return status(out.error || "That didn't go through.", true);
      status("Vote recorded. Reloading the tally..."); setTimeout(() => location.reload(), 900);
    } catch (e) { status(e.message || "Cancelled.", true); }
  }));
})();
</script>'''


def vote_html(items: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    blocks = []
    for p, t in items:
        weights = {k: int(v) for k, v in (t.get("weights") or {}).items()}
        total = sum(weights.values()) or 1
        live = is_open(p)
        opts = "".join(
            f'<div class="opt"><div>{_e(o)}<div class="bar"><i style="width:{100 * weights.get(o, 0) / total:.1f}%"></i></div>'
            f'<span class="n">{weights.get(o, 0) / 1e18:,.0f} $MIGRA · {t.get("voters", {}).get(o, 0)} wallets</span></div>'
            + (f'<button data-pid="{_e(p["id"])}" data-opt="{_e(o)}">Vote</button>' if live else "<span></span>")
            + '</div>' for o in p.get("options", []))
        state = (f'open until {_e(p.get("closes_at", "")[:16].replace("T", " "))} UTC · provisional tally at today\'s balances'
                 if live else f'closed · final tally, weights read at {_e((t.get("counted_at") or "")[:16].replace("T", " "))} UTC')
        blocks.append(f'<div class="prop"><span class="k">{state}</span><h2>{_e(p.get("title"))}</h2>'
                      f'<p>{_e(p.get("question"))}</p>{opts}</div>')
    body = "".join(blocks) or '<p>No votes yet. The first one goes up soon.</p>'
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
{meta(title="$MIGRA governance: vote on what the agent covers", path="/migra/vote",
      description="$MIGRA holders vote on which countries and sources MIGRAGENT reads next. Votes are free signatures, weighted by $MIGRA held when the vote closes.")}
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>
  <h1>Vote on what the agent covers</h1>
  <p class="lede">Hold $MIGRA and you get a say in where the agent reads next: which country, which source,
  which guides come first.</p>
  <p class="fine">Voting is a free signature from your wallet. No transaction, no gas, nothing leaves your wallet.
  Votes are weighted by the $MIGRA you hold when the vote closes, so moving tokens around mid-vote doesn't help.
  One vote per wallet; vote again to change it.</p>
  <p id="v-status"></p>
  {body}
  <p class="fine" style="margin-top:24px">Governance here is small on purpose. The editor puts up the questions and
  acts on the results. It isn't a share in anything, and nothing here is financial advice.</p>
</main><script>const CHAIN = {json.dumps(CHAIN_ID)};</script>{SCRIPT}</body></html>'''
