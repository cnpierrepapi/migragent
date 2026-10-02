"""The desk: where a person adds what the crawl cannot reach.

Two jobs. File something by hand (a page behind a login, a PDF, an
announcement, a site whose robots.txt keeps the crawler out) and it goes
through the same quote check and voice as everything else, with a report that
says a person submitted it. Or add a page to the crawl list, and the watcher
reads it from the next round on.

Also: hide an article from the wire without deleting it, and see what the
writer refused to publish and why. Not indexed, and useless without the key.
"""
from __future__ import annotations

import html
from typing import Any

from .masthead import LOGO
from .registry import JURISDICTIONS
from .result_page import HEAD


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 0 0 80px }
  main { max-width: 1100px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  .bar { display: flex; justify-content: space-between; align-items: center; border-bottom: 3px double var(--ink);
         padding: 18px 0 12px; margin-bottom: 26px }
  .bar a.name { display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--ink);
                font: 700 1.4rem var(--font-display) }
  .bar svg { width: 24px; height: 24px; color: var(--primary) }
  .bar span.tag { font: 500 .7rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase; color: var(--accent) }
  h1 { font-size: 1.9rem; margin: 0 0 6px }
  h2 { font-size: 1.25rem; margin: 30px 0 10px; padding-top: 10px; border-top: 1px solid var(--ink) }
  .msg { border-left: 3px solid var(--accent); padding: 8px 14px; background: var(--paper-raised);
         font: .85rem var(--font-mono); margin: 0 0 18px; overflow-wrap: anywhere }
  .cols { display: grid; grid-template-columns: 1.4fr 1fr; gap: 28px }
  form.box { border: 1px solid var(--ink); background: var(--paper-raised); padding: 18px 20px }
  label { display: block; font: 500 .72rem var(--font-mono); text-transform: uppercase; letter-spacing: .06em;
          color: var(--ink-soft); margin: 12px 0 4px }
  input[type=text], input[type=url], input[type=date], input[type=password], select, textarea {
    width: 100%; padding: 9px 10px; border: 1px solid var(--rule); background: var(--paper); color: var(--ink);
    font: .92rem var(--font-body); border-radius: var(--radius-sm) }
  textarea { min-height: 200px; font: .82rem/1.5 var(--font-mono) }
  .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px }
  button, .btn { margin-top: 14px; padding: 10px 18px; border: 0; background: var(--primary); color: var(--paper);
                 font: 600 .88rem var(--font-body); border-radius: var(--radius); cursor: pointer }
  button.ghost { background: transparent; color: var(--ink); border: 1px solid var(--ink); margin: 0;
                 padding: 4px 10px; font-size: .74rem }
  .hint { font: .72rem/1.6 var(--font-mono); color: var(--ink-soft); margin: 8px 0 0 }
  table { width: 100%; border-collapse: collapse; font: .78rem/1.5 var(--font-mono) }
  th { text-align: left; font-weight: 500; color: var(--ink-soft); border-bottom: 1px solid var(--ink); padding: 6px 10px 6px 0 }
  td { border-bottom: 1px solid var(--rule); padding: 7px 10px 7px 0; vertical-align: top; overflow-wrap: anywhere }
  td.h { font: .95rem/1.4 var(--font-serif) }
  .off { color: var(--ink-soft); text-decoration: line-through }
  .st-published { color: var(--accent) } .st-failed, .st-not { color: var(--warn) }
  .login { max-width: 420px; margin: 60px auto }
  @media (max-width: 860px) { .cols, .row { grid-template-columns: 1fr } }
'''


def _shell(title: str, body: str) -> str:
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
<meta name="robots" content="noindex, nofollow">
<title>{_e(title)}</title><style>{STYLE}</style></head>
<body><main>
  <div class="bar"><a class="name" href="/">{LOGO}MIGRAGENT</a><span class="tag">Editor</span></div>
  {body}
</main></body></html>'''


def login_html(message: str = "", disabled: bool = False) -> str:
    if disabled:
        return _shell("Editor", '<div class="login"><h1>The editor is not set up</h1>'
                      '<p class="hint">No admin key is configured on this service, so nobody can sign in.</p></div>')
    msg = f'<p class="msg">{_e(message)}</p>' if message else ""
    return _shell("Editor", f'''<div class="login"><h1>Editor</h1>{msg}
  <form class="box" method="post" action="/admin/login" autocomplete="off">
    <label for="key">Admin key</label><input id="key" type="password" name="key" required autofocus>
    <button type="submit">Sign in</button>
    <p class="hint">Five wrong keys from one address locks it out for fifteen minutes.</p>
  </form></div>''')


def _country_options() -> str:
    return "".join(f'<option value="{c}">{_e(m["name"])}</option>' for c, m in JURISDICTIONS.items())


def desk_html(csrf: str, submissions: list[dict[str, Any]], articles: list[dict[str, Any]],
              skips: list[dict[str, Any]], stats: dict[str, Any], message: str = "",
              guides: list[dict[str, Any]] | None = None, affiliates: list[dict[str, Any]] | None = None,
              signups: dict[str, int] | None = None, reservations: list[dict[str, Any]] | None = None) -> str:
    msg = f'<p class="msg">{_e(message)}</p>' if message else ""
    countries = _country_options()
    lanes = '<option value="work">Work</option><option value="study">Study</option>'
    t = stats["totals"]

    sub_rows = "".join(
        f'<tr><td>{_e((s.get("submitted_at") or "")[:16].replace("T", " "))}</td>'
        f'<td>{_e(s.get("jurisdiction"))} · {_e(s.get("lane"))}</td>'
        f'<td><a href="{_e(s.get("url"))}" target="_blank" rel="noopener">{_e(s.get("title") or s.get("url"))}</a></td>'
        f'<td class="st-{_e((s.get("status") or "").split()[0])}">{_e(s.get("status"))}'
        f'{(" · <a href=" + chr(34) + "/articles/" + _e(s["article_slug"]) + chr(34) + ">read</a>") if s.get("article_slug") else ""}'
        f'{("<br>" + _e(s["outcome"])) if s.get("outcome") else ""}</td></tr>' for s in submissions) \
        or '<tr><td colspan="4">Nothing filed by hand yet.</td></tr>'

    art_rows = "".join(
        f'<tr><td>{_e(a.get("observed_on"))}</td><td>{_e(a.get("jurisdiction"))}</td>'
        f'<td class="h{" off" if a.get("hidden") else ""}"><a href="/articles/{_e(a.get("slug"))}">{_e(a.get("headline"))}</a></td>'
        f'<td>{_e(a.get("origin") or "crawl")}</td>'
        f'<td><form method="post" action="/admin/article/{_e(a.get("id"))}/{"show" if a.get("hidden") else "hide"}">'
        f'<input type="hidden" name="csrf" value="{_e(csrf)}">'
        f'<button class="ghost" type="submit">{"Put back" if a.get("hidden") else "Hide"}</button></form></td></tr>'
        for a in articles) or '<tr><td colspan="5">No articles yet.</td></tr>'

    skip_rows = "".join(
        f'<tr><td>{_e((s.get("at") or "")[:10])}</td>'
        f'<td>{_e(", ".join(x.get("url", "") for x in (s.get("report") or {}).get("sources") or []) or ", ".join((s.get("report") or {}).get("unreadable") or []))}</td>'
        f'<td>{_e(s.get("why"))}</td></tr>' for s in skips) or '<tr><td colspan="3">Nothing refused.</td></tr>'

    body = f'''
  <h1>Editor</h1>
  <p class="hint">{t["pages"]:,} pages on file in {t["countries"]} countries, {t["daily"]} read every morning.
  {t["articles"]:,} articles on the wire. <a href="/sources">Every page</a></p>
  {msg}
  <div class="cols">
    <form class="box" method="post" action="/admin/filing" enctype="multipart/form-data">
      <h2 style="margin-top:0;border:0;padding:0">File something by hand</h2>
      <p class="hint">For what the crawl can't reach: a page behind a login, a PDF, an announcement, a site that
      blocks bots. It goes through the same quote check as everything else. Every claim must quote what you give
      it, and the report says a person submitted it.</p>
      <input type="hidden" name="csrf" value="{_e(csrf)}">
      <label>Official source URL</label><input type="url" name="url" required placeholder="https://">
      <div class="row">
        <div><label>Country</label><select name="jurisdiction">{countries}</select></div>
        <div><label>Lane</label><select name="lane">{lanes}</select></div>
        <div><label>Date it was published</label><input type="date" name="observed_on"></div>
      </div>
      <label>Title, for your own list</label><input type="text" name="title" maxlength="200">
      <label>The text, pasted from the source</label><textarea name="text" placeholder="Paste the official wording here."></textarea>
      <label>Or a file: PDF, or a photo or screenshot</label><input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg,.webp">
      <label>Note, stays private</label><input type="text" name="note" maxlength="500">
      <button type="submit">Write it up</button>
      <p class="hint">Takes up to a minute. Paste the text as it appears on the official source; the quote check
      runs against exactly what you give it.</p>
    </form>
    <form class="box" method="post" action="/admin/source">
      <h2 style="margin-top:0;border:0;padding:0">Add a page to the crawl</h2>
      <p class="hint">An official page the agent should read every morning from now on. It is read on that country's
      next round, and only if the site's robots.txt allows it.</p>
      <input type="hidden" name="csrf" value="{_e(csrf)}">
      <label>Page URL</label><input type="url" name="url" required placeholder="https://">
      <div class="row" style="grid-template-columns:1fr 1fr">
        <div><label>Country</label><select name="jurisdiction">{countries}</select></div>
        <div><label>Lane</label><select name="lane">{lanes}</select></div>
      </div>
      <label>Title</label><input type="text" name="title" maxlength="200">
      <button type="submit">Add to the crawl</button>
    </form>
  </div>

  <h2>Filed by hand</h2>
  <table><thead><tr><th>When</th><th>Where</th><th>Source</th><th>Outcome</th></tr></thead><tbody>{sub_rows}</tbody></table>

  <h2>On the wire</h2>
  <table><thead><tr><th>Changed</th><th>Country</th><th>Headline</th><th>From</th><th></th></tr></thead><tbody>{art_rows}</tbody></table>

  <h2>Refused by the writer</h2>
  <table><thead><tr><th>When</th><th>Pages</th><th>Why</th></tr></thead><tbody>{skip_rows}</tbody></table>

  <form method="post" action="/admin/logout"><button class="ghost" type="submit" style="margin-top:30px">Sign out</button></form>'''
    body += _business(csrf, guides or [], affiliates or [], signups or {}, reservations or [])
    return _shell("Editor, MIGRAGENT", body)


def _business(csrf: str, guides: list[dict[str, Any]], affiliates: list[dict[str, Any]],
              signups: dict[str, int], reservations: list[dict[str, Any]]) -> str:
    """Guides, affiliate links, and the two numbers the business test rests on."""
    from .guides import TOPICS
    from .signup import ROLES

    total = sum(signups.values())
    roles = " · ".join(f"{_e(name)}: {signups.get(key, 0)}" for key, name in ROLES)
    paid = sum(1 for r in reservations if r.get("status") == "paid")
    res_rows = "".join(
        f'<tr><td>{_e((r.get("at") or "")[:16].replace("T", " "))}</td><td>{_e(r.get("email"))}</td>'
        f'<td>{_e(r.get("name"))}</td><td>{_e(r.get("plan"))}</td><td class="st-{_e(r.get("status"))}">{_e(r.get("status"))}</td>'
        f'<td>{_e(r.get("reference"))}</td></tr>' for r in reservations) or '<tr><td colspan="6">None yet.</td></tr>'
    topics = "".join(f'<option value="{k}">{_e(v)}</option>' for k, v in TOPICS.items())
    aff_rows = "".join(
        f'<tr><td>{_e(TOPICS.get(a.get("topic"), a.get("topic")))}</td><td><a href="{_e(a.get("url"))}" rel="noopener" '
        f'target="_blank">{_e(a.get("name"))}</a></td><td>{_e(", ".join(a.get("countries") or []) or "all")}</td>'
        f'<td><form method="post" action="/admin/affiliate/{_e(a.get("id"))}/remove"><input type="hidden" name="csrf" '
        f'value="{_e(csrf)}"><button class="ghost" type="submit">Remove</button></form></td></tr>'
        for a in affiliates) or '<tr><td colspan="4">No affiliate links yet. Guides show no boxes until you add one.</td></tr>'
    guide_rows = "".join(
        f'<tr><td>{_e(g.get("jurisdiction"))}</td><td class="h{" off" if g.get("hidden") else ""}">'
        f'<a href="/guides/{_e(g.get("slug"))}">{_e(g.get("title"))}</a></td><td>{_e((g.get("updated_at") or "")[:10])}</td>'
        f'<td>{_e(", ".join(g.get("topics") or []))}</td>'
        f'<td><form method="post" action="/admin/guide/{_e(g.get("id"))}/{"show" if g.get("hidden") else "hide"}">'
        f'<input type="hidden" name="csrf" value="{_e(csrf)}"><button class="ghost" type="submit">'
        f'{"Put back" if g.get("hidden") else "Hide"}</button></form></td></tr>'
        for g in guides) or '<tr><td colspan="5">No guides yet. They are written on Sundays, or when you run the guides job.</td></tr>'
    return f'''
  <h2>The business test</h2>
  <p class="hint">Alerts signups: <b>{total}</b>. {roles}</p>
  <p class="hint">Desk reservations: <b>{len(reservations)}</b>, of which <b>{paid}</b> paid the deposit.
  Refunds are made in the Paystack dashboard.</p>
  <table><thead><tr><th>When</th><th>Email</th><th>Name</th><th>Plan</th><th>Status</th><th>Reference</th></tr></thead>
  <tbody>{res_rows}</tbody></table>

  <h2>Affiliate links</h2>
  <form class="box" method="post" action="/admin/affiliate" style="margin-bottom:14px">
    <input type="hidden" name="csrf" value="{_e(csrf)}">
    <div class="row">
      <div><label>Topic</label><select name="topic">{topics}</select></div>
      <div><label>Name shown</label><input type="text" name="name" required maxlength="80"></div>
      <div><label>Countries (codes, blank for all)</label><input type="text" name="countries" placeholder="UK, CA"></div>
    </div>
    <label>Your affiliate URL</label><input type="url" name="url" required placeholder="https://">
    <label>One line about it</label><input type="text" name="blurb" maxlength="160">
    <button type="submit">Add link</button>
    <p class="hint">Shown on guides that need this topic, labelled as an affiliate link.</p>
  </form>
  <table><thead><tr><th>Topic</th><th>Link</th><th>Countries</th><th></th></tr></thead><tbody>{aff_rows}</tbody></table>

  <h2>Guides</h2>
  <table><thead><tr><th>Country</th><th>Guide</th><th>Updated</th><th>Topics</th><th></th></tr></thead><tbody>{guide_rows}</tbody></table>'''
