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
somebody's money. A page that opens with a locked feature implies the thing you
already have is a trailer. It is not: the countries, the courses, the
requirements and every source behind them are free and stay free.

So the columns are side by side and the free one is not greyed out.

PAYING IN $MIGRA
----------------
The checkout is a wallet. Connect it, sign a message that proves it is yours,
send $MIGRA to the treasury, and migragent/credits.py reads the transfer on
Robinhood Chain before anything is credited. The page does no checking of its
own: every number it shows came back from the server.

Until the token is launched and its address configured, there is nothing to pay
with, and the page says so and keeps the email box. A page with a convincing
checkout that quietly goes nowhere is the thing this page exists not to be.

`entitlements.is_subscriber` is still the only place that decides who has paid.
"""
from __future__ import annotations

import html
import json
from typing import Any

from .credits import CHAIN_ID, CHAIN_NAME, DEFAULT_RPC, EXPLORER
from .entitlements import PRICE_LABEL
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

  .pay { border: 1px solid var(--accent); border-radius: var(--radius);
         background: var(--paper-raised); padding: 22px 24px; margin: 0 0 26px }
  .pay h2 { font-family: var(--font-display); font-size: 1.2rem; margin: 0 0 8px }
  .pay p { color: var(--ink-soft); line-height: 1.65; margin: 0 0 14px; font-size: .94rem }
  .pay .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 0 0 12px }
  .pay .ghost { background: transparent; color: var(--ink); border: 1px solid var(--rule) }
  .pay input[type=text] { flex: 1 1 320px; padding: 11px 12px; border: 1px solid var(--rule);
         border-radius: var(--radius-sm); background: var(--paper); color: var(--ink);
         font: .82rem var(--font-mono) }
  .pay .status { font-family: var(--font-mono); font-size: .76rem; line-height: 1.7;
                 color: var(--ink-soft); min-height: 1.2em }
  .pay .status.err { color: var(--warn) }
  .pay .good { color: var(--primary) }
  [hidden] { display: none !important }
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


# Plain EIP-1193, no library: two wallet calls and one ABI encoding are not
# worth a bundle. Amounts stay BigInt from the server all the way to the wallet,
# because an 18-decimal amount is past what a JavaScript number holds exactly.
PAY_JS = r"""
(() => {
  const C = window.MIGRA, eth = window.ethereum;
  const $ = (id) => document.getElementById(id);
  const say = (t, err) => { const s = $('status'); s.textContent = t; s.className = 'status' + (err ? ' err' : ''); };
  const post = async (url, body) => {
    const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify(body || {})});
    return {status: r.status, data: await r.json().catch(() => ({}))};
  };
  const refresh = () => location.reload();
  const price = BigInt(C.price || '0');
  if (price > 0n && BigInt(C.balance || '0') >= price) $('spend').hidden = false;

  async function onChain() {
    const hex = '0x' + C.chainId.toString(16);
    try {
      await eth.request({method: 'wallet_switchEthereumChain', params: [{chainId: hex}]});
    } catch (e) {
      if (e.code !== 4902) throw e;
      await eth.request({method: 'wallet_addEthereumChain', params: [{chainId: hex,
        chainName: C.chainName, rpcUrls: [C.rpc], blockExplorerUrls: [C.explorer],
        nativeCurrency: {name: 'Ether', symbol: 'ETH', decimals: 18}}]});
    }
  }

  $('connect').onclick = async () => {
    if (!eth) return say('No wallet found in this browser. MetaMask, Rabby or Coinbase Wallet all work.', true);
    try {
      const [address] = await eth.request({method: 'eth_requestAccounts'});
      const n = await post('/wallet/nonce', {address});
      if (n.status !== 200) return say(n.data.error || 'Could not start the sign-in.', true);
      say('Check your wallet and sign the message.');
      const signature = await eth.request({method: 'personal_sign', params: [n.data.message, address]});
      const v = await post('/wallet/verify', {address, signature});
      if (v.status !== 200) return say(v.data.error || 'That did not verify.', true);
      refresh();
    } catch (e) { say(e.message || 'Cancelled.', true); }
  };

  async function claim(tx) {
    say('Waiting for the transfer to land on chain...');
    for (let i = 0; i < 90; i++) {
      const r = await post('/credits/deposit', {tx_hash: tx});
      if (r.status === 200) {
        if (price > 0n && BigInt(r.data.balance) >= price) {
          const u = await post('/credits/unlock');
          if (u.status !== 200) return say(u.data.error || 'Credited, but the month did not start.', true);
        }
        return refresh();
      }
      if (r.status !== 202) return say(r.data.error || 'That transfer could not be credited.', true);
      await new Promise((ok) => setTimeout(ok, 4000));
    }
    say('Still not confirmed. Paste the hash again in a minute, nothing is lost.', true);
  }

  $('buy').onclick = async () => {
    try {
      await onChain();
      const [from] = await eth.request({method: 'eth_requestAccounts'});
      if (C.wallet && from.toLowerCase() !== C.wallet)
        return say('Switch to the linked wallet, ' + C.wallet + ', or link this one first.', true);
      const pad = (h) => h.replace(/^0x/, '').padStart(64, '0');
      const data = '0xa9059cbb' + pad(C.treasury) + pad(price.toString(16));
      say('Confirm the transfer in your wallet.');
      const tx = await eth.request({method: 'eth_sendTransaction', params: [{from, to: C.token, data}]});
      await claim(tx);
    } catch (e) { say(e.message || 'Cancelled.', true); }
  };

  $('spend').onclick = async () => {
    const u = await post('/credits/unlock');
    if (u.status !== 200) return say(u.data.error || 'That did not go through.', true);
    refresh();
  };

  $('claim').onclick = () => {
    const tx = $('txhash').value.trim();
    if (!/^0x[0-9a-fA-F]{64}$/.test(tx)) return say('That does not look like a transaction hash.', true);
    claim(tx);
  };
})();
"""


def _short(addr: str) -> str:
    return f"{addr[:6]}...{addr[-4:]}" if len(addr) > 12 else addr


def _pay_panel(wallet: dict[str, Any], has_case: bool) -> str:
    if not has_case:
        return ('<div class="pay"><h2>Pay with $MIGRA</h2>'
                '<p>Start a case first, so the month has somewhere to go. '
                '<a href="/start">Start here</a>.</p></div>')

    linked = wallet.get("wallet", "")
    amount = wallet.get("price_label", "")
    until = (wallet.get("paid_until") or "")[:10]
    state = (f'Linked: <b>{_e(_short(linked))}</b>. Credit: '
             f'<b>{_e(wallet.get("balance_label", "0"))} $MIGRA</b>.'
             if linked else "No wallet linked yet.")
    if wallet.get("active"):
        state += f' <span class="good">Paid through {_e(until)}.</span>'

    # Everything the script needs, as JSON the server wrote. "</" is escaped so
    # no value can close the script tag early.
    config = json.dumps({
        "chainId": CHAIN_ID, "chainName": CHAIN_NAME, "rpc": DEFAULT_RPC,
        "explorer": EXPLORER, "token": wallet.get("token", ""),
        "treasury": wallet.get("treasury", ""),
        "price": wallet.get("price_units", "0"),
        "balance": wallet.get("balance", "0"), "wallet": linked}).replace("</", "<\\/")

    hide_if_unlinked = "" if linked else "hidden"
    hide_buy = "" if linked and amount else "hidden"
    ask = (f"Connect a wallet and send {_e(amount)} $MIGRA. The dates show up for 30 "
           "days. Pay early and the days stack, you don't lose any."
           if amount else
           "Can't read the $MIGRA price right now, so there's nothing to pay yet. "
           "Try again in a minute.")
    return f'''<div class="pay" id="pay">
    <h2>Pay with $MIGRA</h2>
    <p>{ask}</p>
    <p class="status" id="acct">{state}</p>
    <div class="row">
      <button class="cta ghost" type="button" id="connect">{"Switch wallet" if linked else "Connect wallet"}</button>
      <button class="cta" type="button" id="buy" {hide_buy}>Send {_e(amount)} $MIGRA for a month</button>
      <button class="cta ghost" type="button" id="spend" hidden>Use my credit for a month</button>
    </div>
    <div class="row" {hide_if_unlinked}>
      <input type="text" id="txhash" placeholder="Sent it from somewhere else? Paste the transaction hash">
      <button class="cta ghost" type="button" id="claim">Check it</button>
    </div>
    <p class="status" id="status"></p>
    <p class="note">Signing only proves the wallet is yours. No gas, nothing moves.
    The payment is read on {CHAIN_NAME} before anything is credited, which takes a
    few blocks. It doesn't renew. It just runs out.</p>
  </div>
  <script>window.MIGRA = {config};</script>
  <script>{PAY_JS}</script>'''


def subscribe_html(lane: str = "study", saved: str = "", email: str = "",
                   has_case: bool = False, wallet: dict[str, Any] | None = None) -> str:
    wallet = wallet or {}
    paid = PAID_WORK if lane == "work" else PAID_STUDY
    headline = ("Know the moment a job you qualify for is posted."
                if lane == "work"
                else "Know the moment a door opens.")

    notice = (f'<p class="note" style="color:var(--primary)">{_e(saved)}</p>'
              if saved else "")

    if wallet.get("live"):
        checkout = _pay_panel(wallet, has_case)
    else:
        checkout = f'''<p class="honest"><b>$MIGRA isn't launched yet, so there's nothing to
  pay with.</b> Leave an address and we'll write once when it is. Better that than
  a checkout that goes nowhere.</p>

  {notice}
  <form method="post" action="/subscribe">
    <input type="email" name="email" required placeholder="you@example.com"
           value="{_e(email)}">
    <input type="hidden" name="lane" value="{_e(lane)}">
    <button class="cta" type="submit">Tell me when it opens</button>
  </form>'''

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
      <div class="price">Paid in $MIGRA on {CHAIN_NAME}. It doesn't renew.</div>
      <ul>{"".join(f"<li>{_e(x)}</li>" for x in paid)}</ul>
    </div>
  </div>

  {checkout}
  <p class="note">Your wallet address gets linked to your case. Delete the case and
  the link goes with it. The payment record stays, because it's money you already
  paid. <a href="/data">What happens to your data</a>.</p>

  <p class="note" style="margin-top:26px"><a href="/dashboard">Back to your dashboard</a></p>
</main></body></html>'''
