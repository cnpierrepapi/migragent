"""Everything we have read, country by country, including the empty rows.

WHY THIS PAGE EXISTS
--------------------
The front page shows the two countries somebody can actually use today. That is
the right thing to lead with and it hides a real question: what about everywhere
else.

So this is the long answer. Every country in the registry, what has been read
for it, and what that adds up to. A country with nothing shows a zero rather
than being left off, because the honest version of "coming soon" is a number
next to a name.

It is also the page that keeps the front page honest. Two cards and a "more
coming" line could mean anything. One click away there is a table saying Portugal
has 241 work requirements and no register of schools, and that is checkable.
"""
from __future__ import annotations

import html
from typing import Any

from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 44px 24px 96px }
  main { max-width: 880px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 28px }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }
  h1 { font-family: var(--font-display); font-size: clamp(1.8rem, 4.4vw, 2.4rem);
       margin: 0 0 12px; line-height: 1.1 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 30px; max-width: 62ch }

  table { width: 100%; border-collapse: collapse; font-size: .93rem }
  th { text-align: left; font: 600 .72rem var(--font-body); text-transform: uppercase;
       letter-spacing: .12em; color: var(--ink-soft); padding: 0 10px 10px 0;
       border-bottom: 1px solid var(--rule) }
  th.n, td.n { text-align: right; font-variant-numeric: tabular-nums }
  td { padding: 12px 10px 12px 0; border-bottom: 1px solid var(--rule);
       vertical-align: top }
  tr.open td { color: var(--ink) }
  tr.shut td { color: var(--ink-soft) }
  td b { font-weight: 600 }
  .tag { font-family: var(--font-mono); font-size: .68rem; letter-spacing: .06em;
         text-transform: uppercase; padding: 3px 8px; border-radius: 100px;
         border: 1px solid var(--rule); white-space: nowrap }
  .tag.live { color: var(--accent); border-color: var(--accent) }
  .tag.guide { color: var(--ink-soft) }
  .why { font-family: var(--font-mono); font-size: .71rem; color: var(--ink-soft);
         line-height: 1.6; margin-top: 4px; display: block }
  .cta { display: inline-flex; padding: 13px 26px; border-radius: var(--radius);
         background: var(--primary); color: var(--paper); text-decoration: none;
         font: 600 .95rem var(--font-body); margin-top: 30px }
  .note { border-left: 2px solid var(--rule); padding: 2px 0 2px 14px; margin: 30px 0 0;
          color: var(--ink-soft); line-height: 1.7; font-size: .9rem }
'''


def coverage_html(rows: list[dict[str, Any]], totals: dict[str, int]) -> str:
    """`rows` is one dict per country, already ordered with the usable ones first."""
    body = []
    for row in rows:
        live = row["study_ready"] or row["work_ready"]
        offers = []
        if row["study_ready"]:
            offers.append('<span class="tag live">study</span>')
        if row["work_ready"]:
            offers.append('<span class="tag live">work</span>')
        if not offers:
            offers.append('<span class="tag guide">not open yet</span>')

        why = ""
        if not live and (row["study_reqs"] or row["work_reqs"]):
            why = ('<span class="why">Rules read. No register of schools and no job '
                   'board we can read, so there is nothing to point you at yet.</span>')
        elif row["study_ready"] and not row["work_ready"] and row["work_reqs"]:
            why = ('<span class="why">Work rules are read. We cannot read this '
                   'country\'s job board, so we do not offer work here.</span>')
        elif not row["study_reqs"] and not row["work_reqs"]:
            why = '<span class="why">Nothing read yet.</span>'

        body.append(
            f'<tr class="{"open" if live else "shut"}">'
            f'<td><b>{_e(row["name"])}</b>{why}</td>'
            f'<td>{" ".join(offers)}</td>'
            f'<td class="n">{row["study_reqs"]:,}</td>'
            f'<td class="n">{row["work_reqs"]:,}</td>'
            f'<td class="n">{row["schools"]:,}</td>'
            f'<td class="n">{row["schools_read"]:,}</td>'
            f'<td class="n">{row["courses"]:,}</td>'
            f'<td class="n">{row["jobs"]:,}</td>'
            f'</tr>')

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Everything we have read</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Everything we have read</h1>
  <p class="sub">Two countries are open today. Here is every country we hold anything
  for, including the ones with nothing, because a number next to a name is more use
  than the words coming soon.</p>

  <table>
    <thead><tr>
      <th>Country</th><th>Open for</th>
      <th class="n">Study rules</th><th class="n">Work rules</th>
      <th class="n">On the register</th><th class="n">Schools read</th>
      <th class="n">Courses</th><th class="n">Live jobs</th>
    </tr></thead>
    <tbody>{"".join(body)}</tbody>
  </table>

  <p class="note">A country opens for <b>study</b> when we have read its rules and its
  official register of schools, and courses from those schools. It opens for <b>work</b>
  when we have read its rules, its published shortage list, and a job board that will
  let us. The United Kingdom's job board will not say whether it allows crawlers and
  Australia's says no, so neither is open for work and we are not going to pretend
  otherwise.</p>

  <p class="note">Totals: {totals["reqs"]:,} requirements from {totals["sources"]:,}
  official pages. {totals["schools"]:,} schools on the official registers, of which
  {totals["schools_read"]:,} have had their courses read, giving {totals["courses"]:,}
  courses. {totals["jobs"]:,} live job postings.</p>

  <a class="cta" href="/start">Find out what it would take</a>
</main></body></html>'''
