"""The dashboard: everything this product has made for one person, in one place.

WHY A DASHBOARD AT ALL, HAVING AVOIDED ONE THIS LONG
-----------------------------------------------------
Until now every screen answered one question and then handed you on: the guide,
the matched jobs, the board, what moved. That was right while the product was a
thing you used once. It stopped being right the moment it started producing
documents on your behalf and watching pages for you overnight, because those
accumulate, and things that accumulate need somewhere to live.

So this is a place to come back to, and it is organised by what somebody
actually comes back for:

    your documents   what has been written for you, including the same CV in
                     each country's shape
    your watch       whether anything is reading on your behalf, and what it
                     has found
    your activity    the applications you started, as a board
    your settings    a name, a picture, and the delete button

WHAT IT REFUSES TO DO
---------------------
It does not show a completion percentage, a streak, or a nudge to finish
anything. This is somebody's immigration case, not a habit tracker, and a
progress ring on it would invent pressure around a thing that is already the
most stressful administrative process most people ever go through.

Every document on it says it is a draft, on its own face, because every one of
them is.
"""
from __future__ import annotations

import html
from typing import Any

from .board import COLUMN_NAMES, COLUMNS
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 44px 24px 96px }
  main { max-width: 1000px; margin: 0 auto }
  a { color: var(--link) }
  .top { display: flex; align-items: center; justify-content: space-between; gap: 16px;
         flex-wrap: wrap; margin-bottom: 34px }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary) }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }

  .who { display: flex; align-items: center; gap: 14px }
  .face { width: 52px; height: 52px; border-radius: 50%; object-fit: cover;
          border: 1px solid var(--rule); background: var(--paper-raised); flex: 0 0 auto }
  .face.blank { display: grid; place-items: center; font-family: var(--font-display);
                font-size: 1.1rem; color: var(--ink-soft) }
  .who b { display: block; font: 600 1.05rem var(--font-body) }
  .who span { font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }

  h1 { font-family: var(--font-display); font-size: clamp(1.7rem, 4vw, 2.3rem);
       margin: 0 0 8px; line-height: 1.1 }
  .sub { color: var(--ink-soft); line-height: 1.6; margin: 0 0 30px; max-width: 62ch }

  section { margin-bottom: 46px }
  h2 { font-size: .78rem; text-transform: uppercase; letter-spacing: .14em;
       font-family: var(--font-body); font-weight: 600; color: var(--ink-soft);
       margin: 0 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--rule) }

  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); gap: 12px }
  .card { border: 1px solid var(--rule); background: var(--paper-raised);
          border-radius: var(--radius); padding: 16px 17px; display: flex;
          flex-direction: column; gap: 7px }
  .card b { font: 600 .98rem var(--font-body) }
  .card p { margin: 0; color: var(--ink-soft); font-size: .87rem; line-height: 1.5 }
  .card .tag { font-family: var(--font-mono); font-size: .65rem; letter-spacing: .08em;
               text-transform: uppercase; color: var(--accent) }
  .card a.open { margin-top: auto; padding-top: 8px; font-size: .87rem }

  .btn { display: inline-flex; align-items: center; gap: 8px; padding: 11px 20px;
         border-radius: var(--radius); background: var(--primary); color: var(--paper);
         text-decoration: none; font: 600 .89rem var(--font-body); border: 0; cursor: pointer }
  .btn.quiet { background: transparent; color: var(--ink); border: 1px solid var(--rule) }
  .btn.danger { background: transparent; color: var(--warn); border: 1px solid var(--warn) }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center }

  .state { display: flex; align-items: center; gap: 13px; flex-wrap: wrap;
           border: 1px solid var(--rule); background: var(--paper-raised);
           border-radius: var(--radius); padding: 17px 19px }
  .state .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent) }
  .state .dot.off { background: var(--rule) }
  .state p { margin: 0; flex: 1 1 300px; font-size: .93rem; line-height: 1.55 }
  .state .when { display: block; font-family: var(--font-mono); font-size: .71rem;
                 color: var(--ink-soft); margin-top: 4px }

  .lanes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px }
  .lane { background: var(--paper-raised); border: 1px solid var(--rule);
          border-radius: var(--radius); padding: 13px }
  .lane h3 { font: 600 .74rem var(--font-body); text-transform: uppercase;
             letter-spacing: .1em; color: var(--ink-soft); margin: 0 0 10px }
  .job { border: 1px solid var(--rule); border-radius: var(--radius-sm);
         padding: 11px 12px; margin-bottom: 8px; background: var(--paper) }
  .job b { display: block; font: 600 .89rem/1.4 var(--font-body); margin-bottom: 3px }
  .job span { font-family: var(--font-mono); font-size: .68rem; color: var(--ink-soft) }
  .lane .none { font-family: var(--font-mono); font-size: .7rem; color: var(--ink-soft);
                padding: 6px 2px }

  .settings { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; align-items: start }
  label.field { display: block; margin-bottom: 14px }
  label.field span { display: block; font: 600 .85rem var(--font-body); margin-bottom: 6px }
  input[type=text], input[type=email] { width: 100%; padding: 11px 13px;
         border: 1px solid var(--rule); border-radius: var(--radius-sm);
         background: var(--paper); color: var(--ink); font: .95rem var(--font-body) }
  input:focus { outline: 0; border-color: var(--primary); box-shadow: var(--ring) }
  .hint { font-family: var(--font-mono); font-size: .7rem; color: var(--ink-soft);
          line-height: 1.65; margin: 6px 0 0 }
  .none-yet { border: 1px dashed var(--rule); border-radius: var(--radius);
              padding: 24px; color: var(--ink-soft); line-height: 1.65; font-size: .93rem }

  @media (max-width: 800px) {
    .lanes, .settings { grid-template-columns: 1fr }
  }
'''


def _face(profile: Any) -> str:
    if getattr(profile, "avatar", ""):
        return (f'<img class="face" src="{_e(profile.avatar)}" alt="" '
                f'width="52" height="52">')
    initials = getattr(profile, "initials", "") or "?"
    return f'<div class="face blank">{_e(initials)}</div>'


def _document_cards(clones: list[dict], has_guide: bool, pieces: list[dict],
                    place: str) -> str:
    cards: list[str] = []

    if has_guide:
        cards.append(
            '<div class="card"><span class="tag">Your guide</span>'
            f'<b>What it takes for {_e(place)}</b>'
            '<p>Every step, with the sentence from the government page it came from '
            'and the date it was read.</p>'
            '<a class="open" href="/guide">Open the guide &rarr;</a></div>')

    for clone in clones:
        cards.append(
            '<div class="card"><span class="tag">Draft &middot; your CV</span>'
            f'<b>{_e(clone.get("title"))}</b>'
            '<p>The same CV you gave us, laid out the way employers there expect '
            'it. Nothing was added.</p>'
            f'<a class="open" href="/cv/{_e(clone.get("jurisdiction"))}">Read it &rarr;</a></div>')

    for piece in pieces:
        cards.append(
            f'<div class="card"><span class="tag">Draft &middot; {_e(piece.get("kind", "").replace("_", " "))}</span>'
            f'<b>{_e(piece.get("title"))}</b>'
            f'<p>{_e((piece.get("for") or "")[:110])}</p>'
            '<a class="open" href="/board">Open on the board &rarr;</a></div>')

    if not cards:
        return ('<div class="none-yet">Nothing has been written for you yet. '
                'A guide is built as soon as you finish the questions, and a CV is '
                'shaped for each country the moment you add one. '
                '<a href="/start">Pick up where you left off</a>.</div>')
    return f'<div class="cards">{"".join(cards)}</div>'


def _board(columns: dict[str, list]) -> str:
    lanes = []
    for column in COLUMNS:
        items = columns.get(column, [])
        cards = "".join(
            f'<div class="job"><b>{_e(getattr(i, "title", ""))}</b>'
            f'<span>{_e(getattr(i, "employer", "") or "")}'
            f'{" &middot; " + _e(getattr(i, "location", "")) if getattr(i, "location", "") else ""}'
            f'</span></div>'
            for i in items)
        lanes.append(
            f'<div class="lane"><h3>{_e(COLUMN_NAMES.get(column, column))} '
            f'({len(items)})</h3>'
            f'{cards or "<div class=\'none\'>nothing here yet</div>"}</div>')
    return f'<div class="lanes">{"".join(lanes)}</div>'


def dashboard_html(*, profile: Any, place: str, clones: list[dict],
                   pieces: list[dict], has_guide: bool, watch: Any,
                   unseen: int, columns: dict[str, list],
                   has_cv: bool, saved: str = "", error: str = "") -> str:
    watching = bool(watch and getattr(watch, "active", False))
    checked = (getattr(watch, "checked_at", None) or "") if watch else ""

    if watching:
        when = (f"Last looked {_e(checked[:16].replace('T', ' '))} UTC."
                if checked else "The first pass runs tonight.")
        unseen_line = (f" <b>{unseen} new.</b>" if unseen else "")
        watch_block = (
            f'<div class="state"><span class="dot"></span>'
            f'<p>Your agent is watching {_e(place)} for you.{unseen_line}'
            f'<span class="when">{when}</span></p>'
            f'<a class="btn" href="/alerts">See what moved</a>'
            f'<form method="post" action="/watch/off">'
            f'<button class="btn quiet" type="submit">Turn off</button></form></div>')
    else:
        watch_block = (
            '<div class="state"><span class="dot off"></span>'
            '<p>Nothing is watching yet.'
            '<span class="when">Turn it on and the agent re-reads the official pages '
            'every day, then tells you when a rule moves, an intake opens, or a job '
            'you qualify for is posted.</span></p>'
            '<form method="post" action="/watch">'
            '<button class="btn" type="submit">Set up alerts</button></form></div>')

    cv_block = (
        '<a class="btn quiet" href="/cv/new">Edit your CV</a>' if has_cv
        else '<a class="btn" href="/cv/new">Create a CV</a>')

    notice = ""
    if saved:
        notice = f'<p class="hint" style="color:var(--primary)">{_e(saved)}</p>'
    elif error:
        notice = f'<p class="hint" style="color:var(--warn)">{_e(error)}</p>'

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Your dashboard</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="top">
    <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
    <div class="who">{_face(profile)}
      <div><b>{_e(getattr(profile, "name", "") or "Your case")}</b>
      <span>{_e(place)} &middot; kept 30 days after you last touch it</span></div>
    </div>
  </div>

  <h1>Everything we have made for you.</h1>
  <p class="sub">Your documents, what the agent is watching, and the applications you
  started. Everything here is a draft you read before anybody else does.</p>

  <section>
    <h2>Your documents</h2>
    {_document_cards(clones, has_guide, pieces, place)}
    <div class="row" style="margin-top:14px">{cv_block}
      <a class="btn quiet" href="/work">Jobs you matched</a></div>
  </section>

  <section>
    <h2>Your alerts</h2>
    {watch_block}
  </section>

  <section>
    <h2>Your activity</h2>
    {_board(columns)}
    <p class="hint">Nothing moves between these columns on its own. You move it.</p>
  </section>

  <section>
    <h2>Settings</h2>
    {notice}
    <div class="settings">
      <form method="post" action="/profile" enctype="multipart/form-data">
        <label class="field"><span>Your name</span>
          <input type="text" name="name" value="{_e(getattr(profile, "name", ""))}"
                 maxlength="80" placeholder="What should we call you?"></label>
        <label class="field"><span>Where to reach you</span>
          <input type="email" name="email" value="{_e(getattr(profile, "email", ""))}"
                 placeholder="Optional"></label>
        <p class="hint">Nothing is sent anywhere yet. There is no mail sender in this
        product, and this address sits unused until there is one.</p>

        <label class="field"><span>Profile picture</span>
          <input type="file" id="pic" accept="image/*"></label>
        <input type="hidden" name="avatar" id="avatar">
        <p class="hint"><b>Your picture is kept.</b> It is the one thing here that is,
        because it exists to be shown back to you. It is resized to 256 pixels in your
        own browser before it is sent, so the full photograph never leaves your
        machine, and it is deleted with everything else.</p>

        <div class="row" style="margin-top:16px">
          <button class="btn" type="submit">Save</button>
          <a class="btn quiet" href="/data">What happens to your documents</a>
        </div>
      </form>

      <div>
        <p class="hint" style="margin-bottom:14px">Your case is deleted 30 days after you
        last touch it. You can delete it now, and it takes the guide, the drafts, the CV,
        the board, the watch and every alert with it.</p>
        <form method="post" action="/delete"
              onsubmit="return confirm('Delete everything? This cannot be undone.')">
          <button class="btn danger" type="submit">Delete my case</button>
        </form>
      </div>
    </div>
  </section>
</main>
<script>
  // The picture is resized here and never uploaded at full size. A canvas at 256
  // square, centre-cropped, out as WebP. The server checks all of this again;
  // this half exists so the original never travels at all.
  var pic = document.getElementById('pic');
  var field = document.getElementById('avatar');
  if (pic) pic.onchange = function () {{
    var file = pic.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (e) {{
      var img = new Image();
      img.onload = function () {{
        var size = 256;
        var canvas = document.createElement('canvas');
        canvas.width = size; canvas.height = size;
        var side = Math.min(img.width, img.height);
        canvas.getContext('2d').drawImage(
          img, (img.width - side) / 2, (img.height - side) / 2, side, side,
          0, 0, size, size);
        field.value = canvas.toDataURL('image/webp', 0.85);
      }};
      img.src = e.target.result;
    }};
    reader.readAsDataURL(file);
  }};
</script>
</body></html>'''
