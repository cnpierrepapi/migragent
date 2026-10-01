"""The wire: the article list, and one article with its report.

Every article is assembled from claims that survived the quote check in
migragent/articles.py, so this file only lays them out. It adds no claim of its
own. Each line carries its quote and a numbered link to the page that says it,
and the report under the article shows both reads of every page, what was
checked, what was dropped and why, and what it cost.
"""
from __future__ import annotations

import html
from typing import Any

from .masthead import MASTHEAD
from .registry import JURISDICTIONS
from .result_page import HEAD


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _country(code: str) -> str:
    return JURISDICTIONS.get(code, {}).get("name", code)


def _when(iso: str) -> str:
    """'29 Sep 2026, 04:46 UTC' from an ISO time; the date alone if no time."""
    if not iso:
        return ""
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return dt.strftime("%d %b %Y, %H:%M UTC") if "T" in iso else dt.strftime("%d %b %Y")


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 0 0 90px }
  main { max-width: 1160px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  .kicker { font: 500 .72rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase;
            color: var(--accent); margin: 0 0 14px }
  .kicker b { color: var(--primary); font-weight: 500 }

  /* index */
  .wire-head { display: flex; justify-content: space-between; align-items: baseline; gap: 20px;
               border-bottom: 1px solid var(--ink); padding-bottom: 10px; margin-bottom: 4px }
  .wire-head h1 { font-size: clamp(1.6rem, 3.4vw, 2.3rem); margin: 0 }
  .wire-head p { font: .74rem var(--font-mono); color: var(--ink-soft); margin: 0; text-align: right }
  .filing { display: grid; grid-template-columns: 150px 1fr; gap: 26px; padding: 26px 0;
            border-bottom: 1px solid var(--rule) }
  .filing .meta { font: .72rem var(--font-mono); color: var(--ink-soft); line-height: 1.7 }
  .filing .meta b { display: block; color: var(--ink); font-weight: 500 }
  .filing h2 { font-size: clamp(1.25rem, 2.4vw, 1.65rem); line-height: 1.18; margin: 0 0 8px }
  .filing h2 a { color: var(--ink); text-decoration: none }
  .filing h2 a:hover { color: var(--primary) }
  .filing .dek { font: 1.04rem/1.6 var(--font-serif); color: var(--ink); margin: 0 0 10px }
  .filing .for { font: .78rem/1.6 var(--font-mono); color: var(--ink-soft); margin: 0 }
  .filing .for b { color: var(--accent); font-weight: 500 }
  .empty { font: 1.05rem/1.7 var(--font-serif); padding: 40px 0; color: var(--ink-soft) }

  /* article */
  .story { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 56px }
  .story h1 { font-size: clamp(2rem, 4.6vw, 3.1rem); line-height: 1.06; margin: 0 0 16px }
  .story .dek { font: italic 1.3rem/1.5 var(--font-serif); color: var(--ink); margin: 0 0 18px }
  .byline { font: .74rem/1.7 var(--font-mono); color: var(--ink-soft); border-top: 1px solid var(--ink);
            border-bottom: 1px solid var(--rule); padding: 9px 0; margin-bottom: 30px }
  .byline b { color: var(--accent); font-weight: 500 }
  .body h2 { font-size: 1.35rem; margin: 38px 0 12px; padding-top: 12px; border-top: 1px solid var(--rule) }
  .body h2.lead { font-size: 1.7rem; color: var(--primary); border-top: 3px solid var(--primary) }
  .body p, .body li { font: 1.08rem/1.7 var(--font-serif) }
  .body ul { padding-left: 0; list-style: none; margin: 0 }
  .claim { padding: 14px 0; border-bottom: 1px dotted var(--rule) }
  .claim:last-child { border-bottom: 0 }
  .claim .group { display: block; font: 600 1.12rem/1.45 var(--font-serif); color: var(--ink) }
  .claim .why { display: block; margin-top: 4px }
  .claim q { display: block; margin-top: 8px; padding-left: 14px; border-left: 2px solid var(--accent);
             font: .82rem/1.65 var(--font-mono); color: var(--ink-soft); quotes: none }
  .claim sup a { font: 500 .7rem var(--font-mono); text-decoration: none; color: var(--primary);
                 margin-left: 4px }
  .conds { margin: 10px 0 0 0 !important; padding: 0 0 0 14px !important; border-left: 1px solid var(--rule) }
  .conds li { padding: 6px 0; font: 1rem/1.55 var(--font-serif) }
  .conds li span::before { content: "92  "; color: var(--primary); font-family: var(--font-mono) }
  .conds q { margin-top: 4px }
  .claim .date { font: 500 .8rem var(--font-mono); color: var(--primary) }
  .gaps li { padding: 6px 0 6px 22px; position: relative }
  .gaps li::before { content: "?"; position: absolute; left: 0; font: 600 .9rem var(--font-mono);
                     color: var(--warn) }
  .check { margin: 40px 0 0; border: 1px solid var(--ink); padding: 20px 22px; background: var(--paper-raised) }
  .check p { margin: 0 0 12px; font: 1.02rem/1.6 var(--font-serif) }
  .cta { display: inline-block; padding: 11px 20px; background: var(--primary); color: var(--paper);
         text-decoration: none; font: 600 .9rem var(--font-body); border-radius: var(--radius) }
  .side { font: .74rem/1.7 var(--font-mono); color: var(--ink-soft) }
  .side h3 { font: 500 .72rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase;
             color: var(--ink); border-bottom: 1px solid var(--ink); padding-bottom: 6px; margin: 0 0 10px }
  .side .src { padding: 8px 0; border-bottom: 1px solid var(--rule); overflow-wrap: anywhere }
  .side .src b { color: var(--primary); font-weight: 500 }

  /* report */
  .report { margin-top: 54px; border-top: 3px double var(--ink); padding-top: 18px;
            font: .76rem/1.75 var(--font-mono); color: var(--ink) }
  .report h2 { font: 500 .8rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase;
               margin: 0 0 4px; color: var(--accent) }
  .report > p { color: var(--ink-soft); margin: 0 0 18px; max-width: 80ch }
  .report table { width: 100%; border-collapse: collapse; margin-bottom: 18px }
  .report th { text-align: left; font-weight: 500; color: var(--ink-soft); padding: 6px 12px 6px 0;
               border-bottom: 1px solid var(--ink); white-space: nowrap }
  .report td:first-child { white-space: nowrap; width: 40px; color: var(--primary) }
  .report td { padding: 7px 12px 7px 0; border-bottom: 1px solid var(--rule); vertical-align: top;
               overflow-wrap: anywhere }
  .report .figs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; border: 1px solid var(--rule);
                  margin-bottom: 18px }
  .report .figs div { padding: 10px 14px; border-right: 1px solid var(--rule) }
  .report .figs div:last-child { border-right: 0 }
  .report .figs b { display: block; font: 600 1.25rem var(--font-display); color: var(--ink) }
  .disclaim { font: italic .9rem/1.6 var(--font-serif); color: var(--ink-soft); margin-top: 24px }
  @media (max-width: 900px) {
    .story { grid-template-columns: 1fr; gap: 10px }
    .filing { grid-template-columns: 1fr; gap: 8px }
    .report .figs { grid-template-columns: repeat(2, 1fr) }
    .report .figs div:nth-child(2) { border-right: 0 }
    .report table, .report tbody, .report tr, .report td { display: block }
    .report thead { display: none }
    .report td { border-bottom: 0; padding: 2px 0 }
    .report tr { border-bottom: 1px solid var(--rule); padding: 8px 0 }
  }
'''


def _page(title: str, body: str, description: str = "") -> str:
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
<title>{_e(title)}</title>
<meta name="description" content="{_e(description)}">
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>{body}</main></body></html>'''


def _groups_line(article: dict[str, Any], n: int = 3) -> str:
    groups = [g.get("group", "") for g in article.get("who_for") or []][:n]
    more = len(article.get("who_for") or []) - len(groups)
    tail = f" and {more} more" if more > 0 else ""
    return "; ".join(groups) + tail


def index_html(articles: list[dict[str, Any]]) -> str:
    rows = []
    for a in articles:
        r = a.get("report") or {}
        rows.append(f'''<article class="filing">
  <div class="meta"><b>{_e(_country(a.get("jurisdiction", "")))}</b>{_e(a.get("lane", ""))}<br>
    {_e(_when(a.get("observed_on", "")))}<br>{len(r.get("sources") or [])} official {"page" if len(r.get("sources") or []) == 1 else "pages"}<br>
    {r.get("quotes_kept", 0)} quotes checked</div>
  <div><h2><a href="/articles/{_e(a.get("slug"))}">{_e(a.get("headline"))}</a></h2>
    <p class="dek">{_e(a.get("dek"))}</p>
    <p class="for"><b>For:</b> {_e(_groups_line(a))}</p></div>
</article>''')
    listing = "".join(rows) or ('<p class="empty">Nothing filed yet. An article appears here the '
                                'morning an official page changes a rule.</p>')
    body = f'''
<div class="wire-head"><h1>The wire</h1>
  <p>Every article is a rule change the agent caught on an official page.<br>
  Each one carries its report.</p></div>
{listing}'''
    return _page("The wire, MIGRAGENT", body,
                 "Rule changes on official immigration pages, written up by an agent, each with its report.")


def _sup(item: dict[str, Any], sources: list[dict[str, Any]]) -> str:
    i = int(item.get("source") or 0)
    if not (1 <= i <= len(sources)):
        return ""
    return f'<sup><a href="{_e(sources[i - 1]["url"])}" target="_blank" rel="noopener">[{i}]</a></sup>'


def _claims(items: list[dict[str, Any]], sources: list[dict[str, Any]], head: str, lead: bool = False) -> str:
    if not items:
        return ""
    out = []
    for it in items:
        main = it.get("group") or it.get("text") or it.get("what") or ""
        date = f'<span class="date">{_e(it["date"])}</span> ' if it.get("date") else ""
        why = f'<span class="why">{_e(it["why"])}</span>' if it.get("why") else ""
        conds = "".join(f'<li><span>{_e(c.get("text"))}{_sup(c, sources)}</span><q>{_e(c.get("quote"))}</q></li>'
                        for c in it.get("conditions") or [])
        cond_block = f'<ul class="conds">{conds}</ul>' if conds else ""
        out.append(f'<li class="claim"><span class="group">{date}{_e(main)}{_sup(it, sources)}</span>{why}'
                   f'<q>{_e(it.get("quote"))}</q>{cond_block}</li>')
    cls = ' class="lead"' if lead else ""
    return f'<h2{cls}>{head}</h2><ul>{"".join(out)}</ul>'


def _voice_line(v: dict[str, Any]) -> str:
    """What the voice check did to the agent's own words. Quotes are never touched."""
    if not v:
        return "not recorded for this article"
    parts = [f"{v.get('fields', 0)} written fields checked against the house rules"]
    if v.get("rewritten"):
        parts.append("headline or dek rewritten once to meet them")
    if v.get("dropped_why"):
        parts.append(f"{v['dropped_why']} explanation(s) dropped; their quotes stand")
    remaining = v.get("remaining") or []
    parts.append("nothing left that breaks them" if not remaining
                 else "still breaking them: " + "; ".join(remaining))
    return ". ".join(parts) + "."


def article_html(a: dict[str, Any]) -> str:
    r = a.get("report") or {}
    sources = r.get("sources") or []
    country = _country(a.get("jurisdiction", ""))
    dropped = r.get("dropped") or []

    gaps = "".join(f"<li>{_e(g)}</li>" for g in a.get("not_said") or [])
    gaps_block = (f'<h2>What the page does not say</h2><ul class="gaps">{gaps}</ul>' if gaps else "")

    side = "".join(f'<div class="src"><b>[{i}]</b> <a href="{_e(s["url"])}" target="_blank" '
                   f'rel="noopener">{_e(s["url"])}</a><br>read {_e(_when(s.get("after_read_at", "")))}</div>'
                   for i, s in enumerate(sources, 1))

    src_rows = "".join(
        f'<tr><td>[{i}]</td><td><a href="{_e(s["url"])}" target="_blank" rel="noopener">{_e(s["url"])}</a></td>'
        f'<td>{_e(_when(s.get("before_read_at", "")))}</td><td>{_e(_when(s.get("after_read_at", "")))}</td>'
        f'<td>+{s.get("lines_added", 0)} / -{s.get("lines_removed", 0)}</td>'
        f'<td>{_e(s.get("change_summary") or "")}</td></tr>' for i, s in enumerate(sources, 1))
    snap_rows = "".join(f'<tr><td>[{i}]</td><td>{_e(s.get("before_snapshot") or "none stored")}</td>'
                        f'<td>{_e(s.get("after_snapshot") or "none stored")}</td></tr>'
                        for i, s in enumerate(sources, 1))
    drop_rows = "".join(f'<tr><td>{_e(d.get("section", "").replace("_", " "))}</td><td>{_e(d.get("claim"))}</td>'
                        f'<td>{_e(d.get("quote", ""))}</td><td>{_e(d.get("why"))}</td></tr>' for d in dropped)
    drop_table = (f'<table><thead><tr><th>Section</th><th>Claim the model proposed</th><th>Quote it gave</th>'
                  f'<th>Why it was dropped</th></tr></thead><tbody>{drop_rows}</tbody></table>'
                  if dropped else "<p>Nothing was dropped. Every claim the model proposed was found on the page.</p>")
    unreadable = "".join(f"<li>{_e(u)}</li>" for u in r.get("unreadable") or [])
    unreadable_block = (f"<p>Changed, but could not be read back, so nothing from them is in this article:</p>"
                        f"<ul>{unreadable}</ul>" if unreadable else "")
    cost = r.get("cost_usd") or 0
    served = r.get("served_by") or ""
    served_line = (f"Orbio, paid from $MIGRA fees, ${cost:.4f}" if served == "orbio"
                   else "Vertex AI, Google Cloud" if served == "vertex" else "not recorded")

    body = f'''
<div class="story"><div>
  <p class="kicker"><b>{_e(country)}</b> · {_e(a.get("lane", ""))} · filed by the agent · {_e(_when(a.get("observed_on", "")))}</p>
  <h1>{_e(a.get("headline"))}</h1>
  <p class="dek">{_e(a.get("dek"))}</p>
  <p class="byline"><b>MIGRAGENT</b> read {len(sources)} official {"page" if len(sources) == 1 else "pages"} before and after the change.
  {r.get("quotes_kept", 0)} of {r.get("quotes_checked", 0)} claims were found word for word on the page; {len(dropped)} {"was" if len(dropped) == 1 else "were"} dropped.
  <a href="#report">Read the report</a>.</p>
  <div class="body">
    {_claims(a.get("what_changed") or [], sources, "What changed")}
    {_claims(a.get("who_for") or [], sources, "Who this is for", lead=True)}
    {_claims(a.get("who_not_for") or [], sources, "Who it is not for")}
    {_claims(a.get("dates") or [], sources, "Dates")}
    {_claims(a.get("what_to_do") or [], sources, "What the page tells you to do")}
    {gaps_block}
    <div class="check"><p>Whether this touches you depends on your documents, not on a headline.
    Upload what you have and MIGRAGENT will tell you which routes you qualify for, and watch them.</p>
    <a class="cta" href="/start">Check where you qualify</a></div>
    <p class="disclaim">This reports what an official page says and when it said it. It is not legal advice.
    The page is the authority; follow the links.</p>
  </div>
</div>
<aside class="side"><h3>Sources</h3>{side}</aside></div>

<section class="report" id="report">
  <h2>Report</h2>
  <p>How this article was made. The model proposed every claim; each one was kept only if its quote was found
  word for word on the page as it reads now. The article above is built from the claims that were kept, and
  nothing else.</p>
  <div class="figs">
    <div><b>{len(sources)}</b>official pages</div>
    <div><b>{r.get("quotes_checked", 0)}</b>claims checked</div>
    <div><b>{r.get("quotes_kept", 0)}</b>found on the page</div>
    <div><b>{len(dropped)}</b>dropped</div>
  </div>
  <table><thead><tr><th></th><th>Page</th><th>Read before</th><th>Read after</th><th>Lines</th><th>What the change note said</th></tr></thead>
  <tbody>{src_rows}</tbody></table>
  {unreadable_block}
  <p>Both reads of every page are stored exactly as they arrived, with a digest of the bytes. The store is
  MIGRAGENT's own and is not public; the links above open each page as it reads today.</p>
  <table><thead><tr><th></th><th>Stored read, before</th><th>Stored read, after</th></tr></thead>
  <tbody>{snap_rows}</tbody></table>
  {drop_table}
  <table><tbody>
    <tr><td>Written by</td><td>{_e(r.get("model"))}, through {_e(served_line)}</td></tr>
    <tr><td>Written at</td><td>{_e(_when(r.get("generated_at", "")))}</td></tr>
    <tr><td>Change records</td><td>{_e(", ".join(r.get("change_ids") or []))}</td></tr>
    <tr><td>House voice</td><td>{_e(_voice_line(r.get("voice") or {}))}</td></tr>
  </tbody></table>
</section>'''
    return _page(f"{a.get('headline')}, MIGRAGENT", body, a.get("dek", ""))
