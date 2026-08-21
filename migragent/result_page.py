"""What comes back: the guide, the ways through the gaps, and the short form.

Three things on one page, in the order somebody needs them.

The score sits at the top because it frames everything under it, and it is
labelled with what it is rather than left to be read as a verdict. Then the ways
through what is missing, each carrying the page it was read from. Then the
questions, which exist only because the documents did not answer them.
"""
from __future__ import annotations

import html
from typing import Any

from .upload_page import LABELS


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


HEAD = '''<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/brand/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/brand/tokens.css">'''

LOGO = ('<svg viewBox="0 0 64 64"><path d="M10 36 V8 L32 28 L54 8 V36" fill="none" '
        'stroke="currentColor" stroke-width="9" stroke-linecap="round" '
        'stroke-linejoin="round"/><path d="M19 50 Q32 61 45 50" fill="none" '
        'stroke="currentColor" stroke-width="7.5" stroke-linecap="round"/></svg>')


def result_html(case, coverage: dict, result: dict, documents: list) -> str:
    score = int(coverage.get("score", 0))
    covered = int(coverage.get("covered", 0))
    of = int(coverage.get("document_requirements", 0))
    action_only = int(coverage.get("action_only", 0))
    unverified = int(coverage.get("unverified", 0))

    doc_rows = "".join(
        f'<li><b>{_e(LABELS.get(d.kind, d.kind))}</b>'
        f'<span>{_e(d.filename)} &middot; {len(d.fields)} fields, '
        f'{len(d.verified_fields)} verified'
        f'{"" if d.text_layer else " &middot; no text layer, so unverified"}</span></li>'
        for d in documents) or '<li class="none">You did not upload anything, so this guide is the general one for this lane.</li>'

    route_blocks = []
    for route in result.get("routes", []):
        options = route.get("options", [])
        if options:
            items = "".join(
                f'''<div class="opt">
                  <b>{_e(o.get("name"))}</b>
                  <p>{_e(o.get("what_it_is"))}</p>
                  <div class="facts">
                    {f'<span>Cost <b>{_e(o.get("cost"))}</b></span>' if o.get("cost") else ""}
                    {f'<span>Takes <b>{_e(o.get("lead_time"))}</b></span>' if o.get("lead_time") else ""}
                    {f'<span>Accepted by <b>{_e(o.get("accepted_by"))}</b></span>' if o.get("accepted_by") else ""}
                  </div>
                  <a class="src" href="{_e(o.get("source_url"))}">{_e(o.get("source_url"))}</a>
                  <span class="read">read {_e((o.get("read_at") or "")[:10])}</span>
                </div>''' for o in options)
        else:
            items = (f'<p class="none">{_e(route.get("no_route_reason"))}. '
                     f'That is a hole in what we have read, not a claim that there is no way '
                     f'through, and it goes to open questions.</p>')
        route_blocks.append(f'''
      <section class="route">
        <h3>{_e(route.get("requirement_text"))}</h3>
        {items}
      </section>''')

    form = result.get("form", {})
    questions = form.get("questions", [])
    q_rows = "".join(f'''
      <div class="q">
        <label for="{_e(q.get("key"))}">{_e(q.get("prompt"))}</label>
        <span class="why">{_e(q.get("why"))} &middot; settles {len(q.get("settles", []))} requirement(s)</span>
        {'<div class="yn"><label><input type="radio" name="' + _e(q.get("key")) + '" value="yes"> Yes</label><label><input type="radio" name="' + _e(q.get("key")) + '" value="no"> No</label><label><input type="radio" name="' + _e(q.get("key")) + '" value="unsure"> Not sure</label></div>'
         if q.get("answer_type") == "yes_no" else
         '<input type="' + ("date" if q.get("answer_type") == "date" else "text") + '" id="' + _e(q.get("key")) + '" name="' + _e(q.get("key")) + '">'}
      </div>''' for q in questions)

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Your guide</title>
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; padding: 52px 24px 96px }}
  main {{ max-width: 780px; margin: 0 auto }}
  a {{ color: var(--link) }}
  .brand {{ display: flex; align-items: center; gap: 11px; color: var(--primary); margin-bottom: 32px }}
  .brand svg {{ width: 28px; height: 28px }}
  .brand span {{ font-family: var(--font-display); font-size: 1.25rem; color: var(--ink) }}
  h1 {{ font-size: clamp(1.9rem, 5vw, 2.6rem); margin: 0 0 12px; line-height: 1.08 }}
  .sub {{ color: var(--ink-soft); line-height: 1.65; margin: 0 0 8px; max-width: 62ch }}
  h2 {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .14em; font-family: var(--font-body);
        font-weight: 600; color: var(--ink-soft); margin: 46px 0 14px; padding-bottom: 8px;
        border-bottom: 1px solid var(--rule) }}
  h3 {{ font: 600 1.02rem/1.45 var(--font-body); margin: 0 0 12px }}
  ul {{ list-style: none; margin: 0; padding: 0 }}
  li {{ padding: 11px 14px; border: 1px solid var(--rule); border-radius: var(--radius-sm);
        margin-bottom: 6px; background: var(--paper-raised) }}
  li span {{ display: block; font-family: var(--font-mono); font-size: .72rem;
             color: var(--ink-soft); margin-top: 3px }}
  .scorebox {{ display: flex; gap: 24px; align-items: center; flex-wrap: wrap;
               background: var(--paper-raised); border: 1px solid var(--rule);
               border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow) }}
  .big {{ font: var(--display-wght) 3.2rem var(--font-display); font-variant-numeric: tabular-nums; line-height: 1 }}
  .big small {{ font-size: 1.1rem; color: var(--ink-soft) }}
  .meter {{ flex: 1; min-width: 210px }}
  .track {{ height: 9px; background: var(--paper); border: 1px solid var(--rule);
            border-radius: 100px; overflow: hidden }}
  .fill {{ height: 100%; width: {score}%; background: var(--primary) }}
  .lbl {{ font-family: var(--font-mono); font-size: .74rem; color: var(--ink-soft); margin-top: 8px }}
  .cta {{ display: inline-block; padding: 13px 28px; border-radius: var(--radius);
          background: var(--primary); color: var(--paper-raised); text-decoration: none;
          font: 600 .95rem var(--font-body) }}
  .route {{ background: var(--paper-raised); border: 1px solid var(--rule);
            border-left: 3px solid var(--primary); border-radius: var(--radius);
            padding: 20px 22px; margin-bottom: 12px }}
  .opt {{ border-top: 1px solid var(--rule); padding: 13px 0 4px }}
  .opt:first-of-type {{ border-top: 0; padding-top: 0 }}
  .opt p {{ margin: 5px 0 8px; color: var(--ink-soft); line-height: 1.55 }}
  .facts {{ display: flex; gap: 16px; flex-wrap: wrap; font: .82rem var(--font-body);
            color: var(--ink-soft); margin-bottom: 7px }}
  .src {{ font-family: var(--font-mono); font-size: .72rem; word-break: break-all }}
  .read {{ font-family: var(--font-mono); font-size: .7rem; color: var(--ink-soft); margin-left: 8px }}
  .none {{ color: var(--ink-soft); line-height: 1.6 }}
  .q {{ background: var(--paper-raised); border: 1px solid var(--rule); border-radius: var(--radius);
        padding: 17px 19px; margin-bottom: 8px }}
  .q label {{ font-weight: 500; display: block; line-height: 1.5 }}
  .q .why {{ display: block; font-family: var(--font-mono); font-size: .7rem;
             color: var(--ink-soft); margin: 5px 0 10px }}
  .q input[type=text], .q input[type=date] {{ width: 100%; padding: 9px 11px;
    border: 1px solid var(--rule); border-radius: var(--radius-sm);
    background: var(--paper); color: var(--ink); font: .92rem var(--font-body) }}
  .yn {{ display: flex; gap: 18px; font: .9rem var(--font-body) }}
  .yn label {{ font-weight: 400 }}
  .declared {{ border-left: 2px solid var(--accent); padding-left: 12px; margin-top: 14px }}
</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Your guide is ready</h1>
  <p class="sub">Built from {result.get("requirement_count", 0)} requirements read across
  {result.get("source_count", 0)} official pages. Every line in it carries the page it came from and
  the date that page was read. This is not legal advice.</p>

  <div class="scorebox" style="margin-top:24px">
    <div class="big">{score}<small>%</small></div>
    <div class="meter">
      <div class="track"><div class="fill"></div></div>
      <div class="lbl">{covered} of {of} requirements your documents answer
        &nbsp;·&nbsp; {action_only} are actions or fees no document covers
        {f"&nbsp;·&nbsp; {unverified} unverified" if unverified else ""}</div>
    </div>
    <a class="cta" href="/guide?jurisdiction={_e(case.jurisdiction)}&lane={_e(case.lane)}">Open the guide</a>
  </div>
  <p class="sub" style="margin-top:10px;font-size:.9rem">That is the share of requirements a
  document could answer which yours do. It is not a prediction about your application.</p>

  <h2>What you gave us</h2>
  <ul>{doc_rows}</ul>

  <h2>Ways through what is missing</h2>
  {"".join(route_blocks) or '<p class="none">Nothing was missing, or nothing had a route we could evidence.</p>'}

  <h2>The questions only you can answer</h2>
  <p class="sub">{len(questions)} questions, and they exist because your documents did not answer
  them. An answer here is recorded as <b>declared</b> rather than evidenced, and it is shown that
  way in the guide. A field read off a passport carries a quote from the passport; an answer typed
  here carries the typing.</p>
  <form method="post" action="/answers">{q_rows}
    <button class="cta" style="border:0;cursor:pointer;margin-top:12px" type="submit">Save my answers</button>
  </form>

  <h2>Keep it true after today</h2>
  <p class="sub">A guide is only worth what it was worth on the day it was read. Turn the watch
  on and the agent re-reads these pages every day: if a rule moves, if a door opens, or if a job
  you qualify for is posted, it is waiting for you on <a href="/alerts">what moved</a>. It is off
  until you say so, and off again the moment you say so.</p>
  <form method="post" action="/watch">
    <button class="cta" style="border:0;cursor:pointer;margin-top:4px" type="submit">Watch this
    for me</button>
  </form>

  <h2>Your data</h2>
  <p class="sub">The files themselves were never kept. This case is deleted 30 days after you last
  touch it, and you can delete it now. <a href="/dashboard">Your dashboard</a> &middot; <a href="/data">What happens to your documents</a>.</p>
</main></body></html>
'''
