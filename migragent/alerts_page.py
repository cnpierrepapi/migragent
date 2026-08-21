"""The screen where the watch actually pays off.

WHAT IS ON IT AND WHY IN THIS ORDER
-----------------------------------
Newest first, and nothing else. No filters, no tabs, no unread badge you have to
clear. Opening the page is the acknowledgement, the same way opening a letter is.

Every row says three things: what happened, when it was observed, and where that
came from. The third one is not decoration. An alert that says "the salary floor
went up" and cannot show you the page it read is a rumour, and a rumour about
somebody's visa is worse than silence.

Where the sentence was written by a model rather than measured, the row says so
in the line under it, in the same place a requirement names its source. That
distinction is the product's whole discipline and it does not get quieter on the
screen people will read most often.

THE EMPTY STATE IS NOT AN APOLOGY
---------------------------------
Nothing happening is the normal state of an immigration case and it is good news
most days. The empty state says when the watch last looked, so an empty page is
evidence that something is running rather than a suspicion that it is not.
"""
from __future__ import annotations

import html
from typing import Any

from .alerts import KIND_LABELS
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 52px 24px 96px }
  main { max-width: 800px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 32px }
  .brand svg { width: 28px; height: 28px }
  .brand span { font-family: var(--font-display); font-size: 1.25rem; color: var(--ink) }
  h1 { font-size: clamp(1.8rem, 4.5vw, 2.4rem); margin: 0 0 12px; line-height: 1.1 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 28px; max-width: 62ch }

  .state { display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
           border: 1px solid var(--rule); background: var(--paper-raised);
           border-radius: var(--radius); padding: 15px 18px; margin-bottom: 30px }
  .state .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent) }
  .state .dot.off { background: var(--rule) }
  .state p { margin: 0; flex: 1 1 260px; font-size: .93rem; line-height: 1.5 }
  .state .when { display: block; font-family: var(--font-mono); font-size: .71rem;
                 color: var(--ink-soft); margin-top: 3px }
  .btn { padding: 10px 18px; border-radius: var(--radius); border: 0; cursor: pointer;
         background: var(--primary); color: var(--paper); font: 600 .88rem var(--font-body) }
  .btn.quiet { background: transparent; color: var(--ink); border: 1px solid var(--rule) }

  .alert { border: 1px solid var(--rule); background: var(--paper-raised);
           border-radius: var(--radius); padding: 18px 20px; margin-bottom: 10px;
           display: flex; gap: 14px; align-items: flex-start }
  .alert.new { border-left: 3px solid var(--accent) }
  .alert .mark { flex: 0 0 auto; width: 24px; height: 24px; margin-top: 2px;
                 color: var(--primary) }
  .alert.job .mark { color: var(--accent) }
  .kind { font-family: var(--font-mono); font-size: .66rem; letter-spacing: .09em;
          text-transform: uppercase; color: var(--ink-soft); display: block;
          margin-bottom: 5px }
  .alert h3 { font: 600 1.03rem/1.45 var(--font-body); margin: 0 0 6px }
  .detail { margin: 0 0 10px; color: var(--ink-soft); font-size: .92rem; line-height: 1.5 }
  .evidence { font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft);
              line-height: 1.65; border-top: 1px solid var(--rule); padding-top: 9px }
  .evidence a { color: var(--link); word-break: break-all }
  .evidence b { color: var(--ink); font-weight: 500 }

  .none { border: 1px dashed var(--rule); border-radius: var(--radius);
          padding: 30px 24px; color: var(--ink-soft); line-height: 1.7 }
  .back { display: inline-block; margin-top: 34px; font-size: .9rem }
'''

MARKS = {
    "rule": ('<svg class="mark" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
             'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
             '<rect x="4" y="3" width="18" height="20" rx="2.5"/>'
             '<path d="M8 9h10M8 13h10M8 17h6"/></svg>'),
    "opening": ('<svg class="mark" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
                'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M14 22H5V4h9"/><path d="M14 4v18"/><path d="M18 9l4 4-4 4"/>'
                '<path d="M22 13h-7"/></svg>'),
    "job": ('<svg class="mark" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="3" y="8" width="20" height="14" rx="2.5"/>'
            '<path d="M9 8V6a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M3 14h20"/></svg>'),
}


def _row(alert: dict[str, Any], was_unseen: bool) -> str:
    kind = alert.get("kind", "rule")
    url = alert.get("url", "")
    evidence = alert.get("evidence", "")
    by = alert.get("evidence_by", "")

    lines = []
    if evidence:
        lines.append(_e(evidence))
    if by:
        lines.append(f"<b>Source:</b> {_e(by)}")
    if url:
        lines.append(f'<a href="{_e(url)}" rel="noopener noreferrer" '
                     f'target="_blank">{_e(url)}</a>')
    observed = (alert.get("observed_at") or "")[:10]
    if observed:
        lines.append(f"Observed {_e(observed)}")

    detail = (f'<p class="detail">{_e(alert.get("detail"))}</p>'
              if alert.get("detail") else "")

    return (f'<article class="alert {kind}{" new" if was_unseen else ""}">'
            f'{MARKS.get(kind, MARKS["rule"])}'
            f'<div><span class="kind">{_e(KIND_LABELS.get(kind, kind))}</span>'
            f'<h3>{_e(alert.get("headline"))}</h3>{detail}'
            f'<div class="evidence">{"<br>".join(lines)}</div></div></article>')


def alerts_html(rows: list[dict[str, Any]], watch: Any, place: str) -> str:
    """`watch` may be None: somebody can reach this page before turning it on."""
    watching = bool(watch and getattr(watch, "active", False))
    checked = (getattr(watch, "checked_at", None) or "") if watch else ""
    since = (getattr(watch, "started_at", "") or "")[:10] if watch else ""

    if watching:
        when = (f"Last looked {_e(checked[:16].replace('T', ' '))} UTC."
                if checked else "It has not run yet; the first pass is tonight.")
        state = (f'<div class="state"><span class="dot"></span>'
                 f'<p>Your agent is watching {_e(place)} for you.'
                 f'<span class="when">Watching since {_e(since)}. {when}</span></p>'
                 f'<form method="post" action="/watch/off">'
                 f'<button class="btn quiet" type="submit">Stop watching</button>'
                 f'</form></div>')
    else:
        state = ('<div class="state"><span class="dot off"></span>'
                 '<p>Your agent is not watching yet.'
                 '<span class="when">Turn it on and it checks the official pages '
                 'every day, then tells you what moved.</span></p>'
                 '<form method="post" action="/watch">'
                 '<button class="btn" type="submit">Watch this for me</button>'
                 '</form></div>')

    if rows:
        body = "".join(_row(r, not r.get("seen_at")) for r in rows)
    elif watching:
        body = ('<div class="none">Nothing has moved since your agent started '
                'watching. That is the usual answer and it is a good one: it means '
                'the rules your guide is built on still say what they said. '
                'You will see something here the day they do not.</div>')
    else:
        body = ('<div class="none">Nothing here yet, because nothing is watching '
                'yet.</div>')

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>What moved</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>What moved</h1>
  <p class="sub">Rules that changed, doors that opened, and jobs you qualify for &mdash;
  found by reading the official pages, not by anybody telling us.</p>
  {state}
  {body}
  <a class="back" href="/guide">&larr; Back to your guide</a>
</main></body></html>'''
