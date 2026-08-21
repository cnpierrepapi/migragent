"""The screen for somebody who does not have a CV.

WHY IT IS FIVE BOXES AND NOT A WIZARD
--------------------------------------
A wizard would be six screens, a progress bar and a back button, to collect what
fits on one page. The reason products build wizards for this is to make a long
form feel short, and the honest fix for a long form is a shorter form.

So: five questions, all optional except the first, all free text, one per line.
No date pickers, no "add another" buttons, no dropdown of standardised job
titles. Somebody typing "Welder, Lagos Steel Works, 2021 to 2024" has given us
more than a form with three fields would have, and the country matching only
needs the words.

WHAT THE PAGE PROMISES AND KEEPS
--------------------------------
Nothing is added to what they type. The page says so, and it is true all the way
down: `cv_builder.build` copies each line into a claim whose quote is that same
line, and the drafts written later are checked against those quotes. There is no
model between the person and their own CV here.
"""
from __future__ import annotations

import html
from typing import Any

from .cv_builder import FIELDS
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 46px 24px 96px }
  main { max-width: 720px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 30px }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }
  h1 { font-family: var(--font-display); font-size: clamp(1.8rem, 4.4vw, 2.4rem);
       margin: 0 0 10px; line-height: 1.1 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 30px; max-width: 60ch }

  label.field { display: block; margin-bottom: 26px }
  label.field b { display: block; font: 600 1.02rem var(--font-body); margin-bottom: 4px }
  label.field em { display: block; font-style: normal; font-family: var(--font-mono);
                   font-size: .71rem; color: var(--ink-soft); margin-bottom: 9px }
  textarea { width: 100%; min-height: 96px; padding: 13px 14px; resize: vertical;
             border: 1px solid var(--rule); border-radius: var(--radius-sm);
             background: var(--paper-raised); color: var(--ink);
             font: .96rem/1.6 var(--font-body) }
  textarea:focus { outline: 0; border-color: var(--primary); box-shadow: var(--ring) }

  .btn { display: inline-flex; align-items: center; padding: 13px 26px;
         border-radius: var(--radius); background: var(--primary); color: var(--paper);
         text-decoration: none; font: 600 .95rem var(--font-body); border: 0; cursor: pointer }
  .btn.quiet { background: transparent; color: var(--ink); border: 1px solid var(--rule) }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 8px }
  .note { border-left: 2px solid var(--primary); padding: 2px 0 2px 14px;
          color: var(--ink-soft); line-height: 1.7; font-size: .9rem; margin: 0 0 30px }
  .warn { color: var(--warn); font-family: var(--font-mono); font-size: .75rem;
          margin: 0 0 20px }
'''


def clone_html(clone: dict[str, Any]) -> str:
    """One country's CV, as plain monospaced text somebody can select and copy.

    Not a rendered document, and deliberately. Producing a styled PDF here would
    invite somebody to send it as it is, and every one of these is a draft with
    labelled gaps still in it. Plain text says "take this into your own editor",
    which is what should happen.
    """
    body = clone.get("body") or ""
    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}
<title>{_e(clone.get("title"))}</title>
<style>{STYLE}
  pre {{ white-space: pre-wrap; font: .88rem/1.7 var(--font-mono); color: var(--ink);
         background: var(--paper-raised); border: 1px solid var(--rule);
         border-radius: var(--radius); padding: 22px 24px; margin: 0 0 22px }}
</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>{_e(clone.get("title"))}</h1>
  <p class="note">{_e(clone.get("note"))}</p>
  <pre>{_e(body) or "This one came back empty. Try building it again."}</pre>
  <div class="row">
    <a class="btn quiet" href="/dashboard">Back to your dashboard</a>
    <a class="btn quiet" href="/cv/new">Edit what it is built from</a>
  </div>
</main></body></html>'''


def cv_builder_html(answers: dict[str, str] | None = None,
                    name: str = "", error: str = "",
                    editing: bool = False) -> str:
    answers = answers or {}

    boxes = "".join(
        f'<label class="field"><b>{_e(label)}</b><em>{_e(hint)}</em>'
        f'<textarea name="{_e(kind)}" rows="4" '
        f'placeholder="">{_e(answers.get(kind, ""))}</textarea></label>'
        for kind, label, hint, _many in FIELDS)

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}
<title>{"Edit your CV" if editing else "Create a CV"}</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>{"Your CV" if editing else "Let us write it with you."}</h1>
  <p class="sub">You do not need a CV to use this. Answer what you can and we will
  shape it into one, then into a Canadian one, a British one and a Europass one,
  because those are three different documents and employers there expect their own.</p>

  <p class="note"><b>Nothing is added to what you type.</b> Not a skill that goes with
  the job title, not a duty, not a language. If it is not in a box below, it will not
  appear in anything written for you.</p>

  {f'<p class="warn">{_e(error)}</p>' if error else ""}

  <form method="post" action="/cv/new">
    <label class="field"><b>What is your name?</b>
      <em>Optional. It goes at the top of the CV.</em>
      <input type="text" name="name" value="{_e(name)}" maxlength="80"
             style="width:100%;padding:13px 14px;border:1px solid var(--rule);
                    border-radius:var(--radius-sm);background:var(--paper-raised);
                    color:var(--ink);font:.96rem var(--font-body)"></label>
    {boxes}
    <div class="row">
      <button class="btn" type="submit">{"Save my CV" if editing else "Build my CV"}</button>
      <a class="btn quiet" href="/dashboard">Back to your dashboard</a>
    </div>
  </form>
</main></body></html>'''
