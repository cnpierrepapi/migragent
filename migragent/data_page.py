"""The data protection notice, rendered rather than dumped.

WHY THE PAGE AND THE DOCUMENT ARE ONE FILE
-------------------------------------------
`docs/DATA_PROTECTION.md` is what the build is held to. This renders that same
file, so the notice a person reads and the standard the code is checked against
cannot drift into a promise and a practice.

It used to be served as raw markdown inside a `<pre>`, so the reader saw the
hashes and the asterisks. Same words, worse impression, and on a page about
whether you can trust us with a passport the impression is part of the content.

WHY THE MARKDOWN IS PARSED HERE INSTEAD OF WITH A LIBRARY
-----------------------------------------------------------
The file is ours. It uses six constructs and no more: headings, bold, inline
code, list items, tables, and horizontal rules. A parser for six things is fifty
lines and no dependency. Pulling in a markdown library to render one file we
write ourselves would be adding a supply chain to save an afternoon.

Everything is escaped before any tag is added, so a stray angle bracket in the
document renders as an angle bracket.
"""
from __future__ import annotations

import html
import re
from typing import Any

from .result_page import HEAD, LOGO

# The registered entity. A data protection notice that does not say who is
# holding the data is not a notice, it is a blog post.
CONTROLLER = "Onenept Studios Inc."
CONTACT = "admin@onenept.com"


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


def _inline(text: str) -> str:
    """Bold, inline code and links, after escaping."""
    out = _e(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                 r'<a href="\2" rel="noopener noreferrer">\1</a>', out)
    return out


def render(markdown: str) -> str:
    """Six constructs, in one pass, with the table state kept as we go."""
    lines = markdown.splitlines()
    out: list[str] = []
    in_table = False
    in_list = False
    # Prose lines are gathered until the paragraph ends, because the source wraps
    # at roughly 100 characters and bold runs across those wraps. Rendering line
    # by line left a literal "**" on screen wherever it did.
    para: list[str] = []
    # A bullet wraps in the source too, and the wrapped half used to close the
    # list and come out as its own paragraph, flush left, under the list it
    # belonged to. On the page about what happens to a passport, three bullets
    # about who may read what were broken in exactly that way.
    item: list[str] = []

    def close_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    def close_item() -> None:
        if item:
            out.append(f"<li>{_inline(' '.join(item))}</li>")
            item.clear()

    def close_list() -> None:
        nonlocal in_list
        close_item()
        if in_list:
            out.append("</ul>")
            in_list = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    for raw in lines:
        line = raw.rstrip()

        if not line.strip():
            close_para()
            close_list()
            close_table()
            continue

        if line.startswith("---") and set(line.strip()) == {"-"}:
            close_para()
            close_list()
            close_table()
            out.append("<hr>")
            continue

        if line.startswith("#"):
            close_para()
            close_list()
            close_table()
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{min(level, 4)}>{_inline(line.lstrip('# ').strip())}"
                       f"</h{min(level, 4)}>")
            continue

        # A table row. The separator row of dashes and pipes is the header rule.
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue  # the |---|---| rule
            close_para()
            close_list()
            if not in_table:
                out.append("<table><thead><tr>"
                           + "".join(f"<th>{_inline(c)}</th>" for c in cells)
                           + "</tr></thead><tbody>")
                in_table = True
                continue
            out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells)
                       + "</tr>")
            continue
        close_table()

        if line.lstrip().startswith(("- ", "* ")):
            close_para()
            close_item()
            if not in_list:
                out.append("<ul>")
                in_list = True
            item.append(line.lstrip()[2:])
            continue

        # An indented line under a bullet is the rest of that bullet.
        if in_list and raw[:1].isspace():
            item.append(line.strip())
            continue
        close_list()

        if line.startswith("> "):
            close_para()
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
            continue

        para.append(line.strip())

    close_para()
    close_list()
    close_table()
    return "\n".join(out)


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 44px 24px 96px }
  main { max-width: 780px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 30px }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }

  .masthead { border: 1px solid var(--rule); border-radius: var(--radius);
              background: var(--paper-raised); padding: 24px 26px; margin-bottom: 40px }
  .masthead h1 { font-family: var(--font-display); font-size: clamp(1.6rem, 3.6vw, 2.1rem);
                 margin: 0 0 14px; line-height: 1.15 }
  .masthead dl { display: grid; grid-template-columns: max-content 1fr; gap: 8px 20px;
                 margin: 0; font-size: .9rem }
  .masthead dt { font-family: var(--font-mono); font-size: .71rem; letter-spacing: .06em;
                 text-transform: uppercase; color: var(--ink-soft); padding-top: 2px }
  .masthead dd { margin: 0; color: var(--ink) }

  h2 { font-family: var(--font-display); font-size: 1.32rem; margin: 44px 0 12px;
       line-height: 1.2; padding-bottom: 9px; border-bottom: 1px solid var(--rule) }
  h3 { font: 600 1.02rem var(--font-body); margin: 30px 0 8px }
  h4 { font: 600 .94rem var(--font-body); margin: 22px 0 6px; color: var(--ink-soft) }
  p { line-height: 1.72; margin: 0 0 14px; color: var(--ink) }
  ul { margin: 0 0 16px; padding-left: 20px }
  li { line-height: 1.7; margin-bottom: 7px }
  strong { font-weight: 600 }
  code { font-family: var(--font-mono); font-size: .84em; background: var(--paper-raised);
         border: 1px solid var(--rule); border-radius: 4px; padding: 1px 5px }
  hr { border: 0; border-top: 1px solid var(--rule); margin: 38px 0 }
  blockquote { border-left: 2px solid var(--primary); margin: 0 0 16px;
               padding: 2px 0 2px 16px; color: var(--ink-soft); line-height: 1.7 }

  table { width: 100%; border-collapse: collapse; margin: 0 0 20px; font-size: .92rem }
  th { text-align: left; font: 600 .71rem var(--font-body); text-transform: uppercase;
       letter-spacing: .1em; color: var(--ink-soft); padding: 0 12px 9px 0;
       border-bottom: 1px solid var(--rule) }
  td { padding: 11px 12px 11px 0; border-bottom: 1px solid var(--rule);
       vertical-align: top; line-height: 1.6 }

  .foot { margin-top: 48px; padding-top: 20px; border-top: 1px solid var(--rule);
          font-family: var(--font-mono); font-size: .73rem; color: var(--ink-soft);
          line-height: 1.8 }
'''


def data_html(markdown: str, updated: str = "") -> str:
    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}
<title>Data protection notice</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>

  <div class="masthead">
    <h1>Data protection notice</h1>
    <dl>
      <dt>Controller</dt><dd>{_e(CONTROLLER)}</dd>
      <dt>Service</dt><dd>MIGRAGENT, at migragent.onenept.com</dd>
      <dt>Contact</dt><dd><a href="mailto:{_e(CONTACT)}">{_e(CONTACT)}</a></dd>
      <dt>Last updated</dt><dd>{_e(updated or "see the repository history")}</dd>
      <dt>Scope</dt><dd>Documents and personal data submitted to this service</dd>
    </dl>
  </div>

  {render(markdown)}

  <p class="foot">This notice describes the behaviour of the software as built, and each
  claim in it is stated as true in code, tested, or not yet implemented. It is not a
  statement of compliance with any particular regime. Where a claim is tested, the test
  is named so it can be run.
  <br>{_e(CONTROLLER)} &middot; <a href="/">MIGRAGENT</a> &middot;
  <a href="/coverage">What we have read</a> &middot;
  <a href="/architecture">How it is built</a></p>
</main></body></html>'''
