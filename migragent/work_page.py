"""The two screens after the guide: what your CV matched, and the board.

WHY THERE IS NO SEARCH ON EITHER OF THEM
----------------------------------------
A person drops a CV on the page. What comes back is what that CV matched, each
row carrying the line in their own CV that put it there. There is no box to type
in, no filters, no browse. Rule 39.

That is not a missing feature. A search box would mean showing somebody every
job in the country and asking them to guess which ones they have a chance at,
which is the thing every other job site already does badly. What this product
knows that they do not is what a government said it is short of, and what their
own document says they can do.

EVERY NUMBER SAYS WHAT IT IS
----------------------------
The fit score sits next to the sentence that limits it, not above a footnote.
Drafts are labelled drafts on the face of the card. An item moves only when a
person moves it.
"""
from __future__ import annotations

import html
from typing import Any

from .board import COLUMNS, COLUMN_NAMES
from .fit import CAVEAT
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 52px 24px 96px }
  main { max-width: 900px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary); margin-bottom: 32px }
  .brand svg { width: 28px; height: 28px }
  .brand span { font-family: var(--font-display); font-size: 1.25rem; color: var(--ink) }
  h1 { font-size: clamp(1.8rem, 4.5vw, 2.4rem); margin: 0 0 12px; line-height: 1.1 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 8px; max-width: 64ch }
  h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .14em;
       font-family: var(--font-body); font-weight: 600; color: var(--ink-soft);
       margin: 44px 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--rule) }
  .job { background: var(--paper-raised); border: 1px solid var(--rule);
         border-radius: var(--radius); padding: 18px 20px; margin-bottom: 10px }
  .job h3 { font: 600 1.05rem/1.4 var(--font-body); margin: 0 0 4px }
  .meta { display: flex; gap: 14px; flex-wrap: wrap; font: .84rem var(--font-body);
          color: var(--ink-soft); margin-bottom: 10px }
  .why { font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft);
         margin-bottom: 12px }
  .why b { color: var(--ink) }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center }
  .cta { display: inline-block; padding: 10px 20px; border-radius: var(--radius);
         background: var(--primary); color: var(--paper-raised); text-decoration: none;
         font: 600 .88rem var(--font-body); border: 0; cursor: pointer }
  .cta.quiet { background: transparent; color: var(--ink); border: 1px solid var(--rule) }
  .cta[disabled] { opacity: .55; cursor: default }
  .score { font: var(--display-wght) 1.6rem var(--font-display);
           font-variant-numeric: tabular-nums }
  .score small { font-size: .8rem; color: var(--ink-soft); font-family: var(--font-body) }
  .caveat { font-size: .82rem; color: var(--ink-soft); line-height: 1.55; margin: 8px 0 0;
            max-width: 60ch }
  .asks { margin: 12px 0 0; padding: 0; list-style: none }
  .asks li { padding: 9px 12px; border: 1px solid var(--rule); border-radius: var(--radius-sm);
             margin-bottom: 5px; background: var(--paper) }
  .asks .met { border-left: 3px solid var(--primary) }
  .asks .gap { border-left: 3px solid var(--warn) }
  .asks q { display: block; font-family: var(--font-mono); font-size: .72rem;
            color: var(--ink-soft); margin-top: 4px }
  .none { color: var(--ink-soft); line-height: 1.65; background: var(--paper-raised);
          border: 1px dashed var(--rule); border-radius: var(--radius); padding: 22px 24px }
  .drop { border: 2px dashed var(--rule); border-radius: var(--radius); padding: 34px 24px;
          text-align: center; background: var(--paper-raised) }
  .drop.over { border-color: var(--primary) }
  .drop p { margin: 0 0 6px; color: var(--ink-soft) }
  .cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px }
  @media (max-width: 720px) { .cols { grid-template-columns: 1fr } }
  .col h3 { font: 600 .78rem/1.4 var(--font-body); text-transform: uppercase;
            letter-spacing: .12em; color: var(--ink-soft); margin: 0 0 10px }
  .card { background: var(--paper-raised); border: 1px solid var(--rule);
          border-radius: var(--radius); padding: 14px 16px; margin-bottom: 8px }
  .card b { display: block; font: 600 .95rem/1.4 var(--font-body) }
  .card .meta { font-size: .78rem; margin: 4px 0 8px }
  .piece { border-top: 1px solid var(--rule); padding-top: 8px; margin-top: 8px;
           font-size: .84rem; color: var(--ink-soft) }
  .draft { display: inline-block; font-family: var(--font-mono); font-size: .66rem;
           text-transform: uppercase; letter-spacing: .1em; color: var(--warn);
           border: 1px solid var(--warn); border-radius: 100px; padding: 1px 7px;
           margin-left: 6px }
  form.inline { display: inline }
'''


def _brand() -> str:
    return f'<div class="brand">{LOGO}<span>MIGRAGENT</span></div>'


def jobs_html(cv, listings: list[dict[str, Any]], fits: dict[str, dict],
              place: str) -> str:
    """What this person's CV matched, and nothing else."""
    if cv is None:
        body = f'''
        <h1>Work that matches what you already do</h1>
        <p class="sub">Drop your CV here. We read it, and show you jobs in {_e(place)} that
        governments have said they are short of and that your CV actually matches. Nothing else,
        and no searching.</p>
        <form class="drop" id="drop" method="post" action="/cv" enctype="multipart/form-data">
          <p>Drop your CV here, or</p>
          <label class="cta" for="cv">Choose a file<input id="cv" name="cv" type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.heic" hidden></label>
          <p class="caveat">A PDF, or a photo of your CV. We read it, keep what it says, and
          never keep the file. A photo has no text to check against, so what we read from it is
          marked unverified.</p>
        </form>
        <script>
          var d = document.getElementById('drop'), i = document.getElementById('cv');
          i.addEventListener('change', function () {{ if (i.files.length) d.submit(); }});
          ['dragenter', 'dragover'].forEach(function (e) {{
            d.addEventListener(e, function (ev) {{ ev.preventDefault(); d.classList.add('over'); }});
          }});
          ['dragleave', 'drop'].forEach(function (e) {{
            d.addEventListener(e, function (ev) {{ ev.preventDefault(); d.classList.remove('over'); }});
          }});
          d.addEventListener('drop', function (ev) {{
            if (ev.dataTransfer.files.length) {{ i.files = ev.dataTransfer.files; d.submit(); }}
          }});
        </script>'''
        return _page("Work", body)

    roles = ", ".join(c.value for c in cv.of_kind("role")[:4]) or "nothing we could read"
    unverified = "" if cv.text_layer else (
        '<p class="caveat">Your CV had no text layer, so nothing in it could be checked '
        'against the document. Everything below is marked unverified.</p>')

    if not listings:
        rows = ('<div class="none">Nothing on the boards we read matches your CV yet. '
                'We only read government job services, and only for occupations a government '
                'has published as short. This page fills itself when that changes.</div>')
    else:
        rows = "".join(_job(row, fits.get(row.get("listing_id", ""))) for row in listings)

    body = f'''
      <h1>{len(listings)} job{"" if len(listings) == 1 else "s"} matched your CV</h1>
      <p class="sub">From government job services only, for occupations {_e(place)} has published
      as short. Each one is here because of a line in your own CV.</p>
      <p class="why">Read from your CV: <b>{_e(roles)}</b></p>
      {unverified}
      <h2>What matched</h2>
      {rows}'''
    return _page("Work that matched", body)


def _job(row: dict[str, Any], fit: dict | None) -> str:
    listing_id = _e(row.get("listing_id"))
    facts = " ".join(
        f"<span>{_e(v)}</span>" for v in
        (row.get("employer"), row.get("location"), row.get("salary"), row.get("posted_on"))
        if v)

    via = row.get("posted_via")
    origin = (f'<div class="why">On {_e(row.get("board"))}, gathered from '
              f'<b>{_e(via)}</b></div>' if via and via != "Job Bank" else
              f'<div class="why">Posted on <b>{_e(row.get("board"))}</b></div>')

    if fit is None:
        action = f'''<form class="inline" method="post" action="/fit">
            <input type="hidden" name="listing" value="{listing_id}">
            <button class="cta" type="submit">See how you fit</button></form>'''
        breakdown = ""
    else:
        action = f'''<span class="score">{int(fit.get("score", 0))}%<small> fit</small></span>
          <form class="inline" method="post" action="/interested">
            <input type="hidden" name="listing" value="{listing_id}">
            <button class="cta" type="submit">I'm interested</button></form>'''
        breakdown = _breakdown(fit)

    return f'''<div class="job">
      <h3>{_e(row.get("title"))}</h3>
      <div class="meta">{facts}</div>
      <div class="why">Matched because your CV says <b>{_e(row.get("matched_because"))}</b></div>
      {origin}
      <div class="row">{action}
        <a class="cta quiet" href="{_e(row.get("url"))}" rel="nofollow noopener"
           target="_blank">Read the posting</a></div>
      {breakdown}
    </div>'''


def _breakdown(fit: dict) -> str:
    if fit.get("error"):
        return f'<p class="caveat">This posting could not be scored: {_e(fit["error"])}</p>'

    items = []
    for match in fit.get("matches", []):
        met = bool(match.get("met"))
        evidence = match.get("evidence")
        mark = "met" if met else "gap"
        if met:
            tail = (f'Your CV: <b>{_e(evidence)}</b>'
                    + ("" if match.get("evidence_verified")
                       else " <span class=\"draft\">unverified</span>"))
        else:
            tail = _e(match.get("note") or "Nothing in your CV shows this")
        items.append(f'<li class="{mark}"><b>{_e(match.get("asks_for"))}</b>'
                     f'<q>{_e(match.get("quote"))}</q><div class="why">{tail}</div></li>')

    return (f'<ul class="asks">{"".join(items)}</ul>'
            f'<p class="caveat">{_e(CAVEAT)} '
            f'It asks for {int(fit.get("asked", 0))} things and your CV shows '
            f'{int(fit.get("met", 0))} of them.</p>')


def board_html(columns: dict[str, list]) -> str:
    """The board. Nothing on it moved by itself."""
    total = sum(len(items) for items in columns.values())
    if not total:
        body = '''
          <h1>Your board</h1>
          <p class="sub">When you say you are interested in a job, it lands here with the work
          the application needs: your CV rewritten for that listing, a cover letter drafted, and
          the people worth speaking to.</p>
          <div class="none">Nothing here yet.
            <a href="/work">See what your CV matched</a>.</div>'''
        return _page("Your board", body)

    cols = []
    for column in COLUMNS:
        cards = "".join(_card(item, column) for item in columns.get(column, []))
        cols.append(f'<div class="col"><h3>{_e(COLUMN_NAMES[column])} '
                    f'({len(columns.get(column, []))})</h3>{cards}</div>')

    body = f'''
      <h1>Your board</h1>
      <p class="sub">{total} application{"" if total == 1 else "s"}. You send them, and you move
      them. Nothing here moves on its own, and everything written for you is a draft you should
      read before it goes anywhere.</p>
      <div class="cols">{"".join(cols)}</div>'''
    return _page("Your board", body)


def _card(item, column: str) -> str:
    pieces = "".join(
        f'<div class="piece">{_e(p.title)}'
        f'{"<span class=\"draft\">draft</span>" if p.is_draft else ""}</div>'
        for p in item.pieces) or '<div class="piece">Nothing prepared yet</div>'

    moves = []
    for target in COLUMNS:
        if target == column:
            continue
        moves.append(f'''<form class="inline" method="post" action="/board/move">
            <input type="hidden" name="item" value="{_e(item.item_id)}">
            <input type="hidden" name="column" value="{target}">
            <button class="cta quiet" type="submit">{_e(COLUMN_NAMES[target])}</button></form>''')

    fit = (f'<span class="score">{item.fit_score}%<small> fit</small></span>'
           if item.fit_score is not None else "")

    return f'''<div class="card">
      <b>{_e(item.title)}</b>
      <div class="meta">{_e(item.employer)} {_e(item.location)}</div>
      {fit}
      {pieces}
      <div class="row" style="margin-top:10px">{"".join(moves)}</div>
    </div>'''


def _page(title: str, body: str) -> str:
    return (f'<!doctype html>\n<html lang="en" data-theme="light"><head>{HEAD}'
            f'<title>{_e(title)}</title>\n<style>{STYLE}</style></head>\n<body><main>'
            f'{_brand()}{body}</main></body></html>')
