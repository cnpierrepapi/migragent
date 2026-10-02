"""What the agent reads: every country, every page, from the registry itself.

A reporter that will not say where it gets its information is asking to be
taken on trust. This page lists every official page MIGRAGENT holds, which
countries it re-reads every morning, which pages a government's robots.txt
keeps it out of, and what each country has produced: requirements read, rule
changes caught, articles filed. All of it is counted live from the rows.
"""
from __future__ import annotations

import html
from typing import Any

from .masthead import MASTHEAD
from .result_page import HEAD


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding-bottom: 80px }
  main { max-width: 1160px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  h1 { font-size: clamp(1.8rem, 3.8vw, 2.6rem); margin: 0 0 10px }
  .lede { font: 1.12rem/1.65 var(--font-serif); max-width: 66ch; margin: 0 0 26px }
  .totals { display: grid; grid-template-columns: repeat(5, 1fr); border-top: 1px solid var(--ink);
            border-bottom: 3px double var(--ink); margin-bottom: 30px }
  .totals div { padding: 14px 16px 14px 0; border-right: 1px solid var(--rule) }
  .totals div:last-child { border-right: 0 }
  .totals b { display: block; font: 640 1.7rem var(--font-display) }
  .totals span { font: .68rem var(--font-mono); color: var(--ink-soft) }
  .wrap-table { overflow-x: auto }
  table { width: 100%; border-collapse: collapse; font: .82rem var(--font-mono) }
  th { text-align: left; font-weight: 500; color: var(--ink-soft); border-bottom: 1px solid var(--ink);
       padding: 8px 12px 8px 0; white-space: nowrap }
  td { border-bottom: 1px solid var(--rule); padding: 9px 12px 9px 0; white-space: nowrap }
  td.name { font: 600 .98rem var(--font-serif); white-space: normal }
  .yes { color: var(--accent) }
  .no { color: var(--ink-soft) }
  h2 { font-size: 1.35rem; margin: 40px 0 6px; padding-top: 12px; border-top: 1px solid var(--ink) }
  details { border-bottom: 1px solid var(--rule); padding: 10px 0 }
  summary { cursor: pointer; font: 600 1.02rem var(--font-serif) }
  summary span { font: .72rem var(--font-mono); color: var(--ink-soft); margin-left: 8px }
  ul.urls { list-style: none; margin: 10px 0 4px; padding: 0; font: .74rem/1.7 var(--font-mono) }
  ul.urls li { overflow-wrap: anywhere; padding: 2px 0 }
  ul.urls em { font-style: normal; color: var(--primary); margin-right: 6px }
  ul.urls small { color: var(--ink-soft) }
  .note { font: italic .98rem/1.6 var(--font-serif); color: var(--ink-soft); max-width: 70ch }
  @media (max-width: 700px) { .totals { grid-template-columns: repeat(2, 1fr) }
    .totals div:nth-child(even) { border-right: 0 } }
'''


def sources_html(stats: dict[str, Any]) -> str:
    rows, t = stats["rows"], stats["totals"]
    table = "".join(
        f'<tr><td class="name">{_e(r["name"])}</td>'
        f'<td class="{"yes" if r["daily"] else "no"}">{"every morning" if r["daily"] else "on file"}</td>'
        f'<td>{r["pages"]:,}</td><td>{r["study"]:,} / {r["work"]:,}</td>'
        f'<td>{r["requirements"]:,}</td><td>{r["rules"]:,}</td><td>{r["articles"]:,}</td>'
        f'<td>{_e((r["last_read"] or "never")[:10])}</td>'
        f'<td>{r["blocked"] or ""}</td></tr>' for r in rows if r["pages"] or r["daily"])

    lists = []
    for r in rows:
        if not r["urls"]:
            continue
        items = "".join(
            f'<li><em>{_e(p.get("lane"))}</em><a href="{_e(p.get("url"))}" rel="noopener" target="_blank">'
            f'{_e(p.get("url"))}</a> <small>{"robots says no" if p.get("robots_allowed") is False else "read " + _e((p.get("last_read_at") or "never")[:10])}'
            f'{" · added by the desk" if p.get("discovered_via") == "desk" else ""}'
            f'{" · job board" if p.get("kind") == "job_board" else ""}</small></li>'
            for p in r["urls"])
        lists.append(f'<details><summary>{_e(r["name"])}<span>{r["pages"]:,} pages · '
                     f'{"read every morning" if r["daily"] else "on file, not in the daily round"}</span></summary>'
                     f'<ul class="urls">{items}</ul></details>')

    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
<title>Sources, MIGRAGENT</title>
<meta name="description" content="Every official immigration page MIGRAGENT reads, by country.">
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>
  <h1>Where it reads</h1>
  <p class="lede">Every article on the wire comes from one of these pages. They are official government
  sites, read straight from the source. The agent goes back to the ones in the daily round every morning
  and writes up anything that changes a rule.</p>
  <div class="totals">
    <div><b>{t["pages"]:,}</b><span>official pages on file</span></div>
    <div><b>{t["countries"]}</b><span>countries</span></div>
    <div><b>{t["daily"]}</b><span>read every morning</span></div>
    <div><b>{t["rules"]:,}</b><span>rule changes caught</span></div>
    <div><b>{t["articles"]:,}</b><span>articles filed</span></div>
  </div>
  <div class="wrap-table"><table>
    <thead><tr><th>Country</th><th>Read</th><th>Pages</th><th>Study / work</th><th>Requirements</th>
      <th>Rule changes</th><th>Articles</th><th>Last read</th><th>Blocked</th></tr></thead>
    <tbody>{table}</tbody></table></div>
  <p class="note">"Blocked" means the government's robots.txt asks crawlers to stay out, so the agent does.
  Pages it can't crawl can still reach the wire through the desk, and an article that came that way says so
  in its report.</p>
  <h2>Every page</h2>
  {"".join(lists)}
</main></body></html>'''
