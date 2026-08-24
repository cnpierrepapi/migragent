"""The architecture page, drawn rather than described.

WHY THIS PAGE EXISTS ON THE SITE AND NOT ONLY IN THE REPOSITORY
---------------------------------------------------------------
The same reason `/data` renders `docs/DATA_PROTECTION.md`: the document the
build is held to and the page a reader sees are one file, so they cannot drift
into a promise and a practice. `docs/ARCHITECTURE.md` is that file here.

WHY THE DIAGRAM IS HAND DRAWN SVG
---------------------------------
The markdown carries a mermaid block, which GitHub renders on its own. A browser
does not, and rendering it would mean shipping a diagramming library to draw one
picture that changes a few times a year. So the page swaps that block for an
inline SVG that uses the same design tokens as everything else, which means it
follows the light and dark faces without a second copy of the palette.

The two have to be kept in step by hand. That is a real cost and it is smaller
than the one it avoids.
"""
from __future__ import annotations

import re
from typing import Any

from .data_page import STYLE, render
from .result_page import HEAD, LOGO

MERMAID = re.compile(r"```mermaid.*?```", re.S)
PLACEHOLDER = "@@DIAGRAM@@"


# Boxes are drawn from one helper so the geometry stays in one place. Nothing
# here is clever: it is a grid, and the columns are the three questions a reader
# has, which are where the words come from, what runs, and what I end up seeing.
def _box(x: int, y: int, w: int, h: int, title: str, sub: str = "",
         kind: str = "", top: bool = False) -> str:
    cls = f"n {kind}".strip()
    head = y + 24 if (sub or top) else y + h // 2 + 5
    out = [f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="7"/>',
           f'<text class="t" x="{x + 14}" y="{head}">{title}</text>']
    if sub:
        out.append(f'<text class="s" x="{x + 14}" y="{y + 42}">{sub}</text>')
    return "".join(out)


# Two lines, because one line of "cloud run job, this name, running as that
# identity" ran into the next column and the identity is the half worth keeping.
def _band(x: int, y: int, label: str, who: str = "") -> str:
    out = f'<text class="band" x="{x}" y="{y}">{label}</text>'
    if who:
        out += f'<text class="band" x="{x}" y="{y + 13}">{who}</text>'
    return out


DIAGRAM = f'''
<figure class="diagram">
<svg viewBox="0 0 900 626" role="img"
     aria-label="Government pages, school registers and job boards are read by a
     Cloud Run job, which fetches, checks every quote against the page, and
     stores rows in Firestore. The Cloud Run service reads those rows to build a
     person's guide. Every model call goes through one module.">
  <defs>
    <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
            markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z"/>
    </marker>
  </defs>

  {_band(16, 22, "WHERE THE WORDS COME FROM", "asked, not taken")}
  {_box(16, 44, 190, 52, "Government pages", "robots.txt asked first")}
  {_box(16, 116, 190, 52, "Registers and schools", "official lists, no model")}
  {_box(16, 188, 190, 52, "Government job boards", "an opening, never a rule")}

  {_band(250, 22, "CLOUD RUN JOB &#183; migragent-ingest", "runs as migragent-watcher")}
  {_box(250, 44, 300, 52, "ADK researcher", "picks the next page where structure runs out")}
  {_box(250, 124, 300, 60, "Fetch, then two gates",
        "bytes changed, and then the text really changed")}
  {_box(250, 212, 300, 56, "Quote check",
        "not on the page, not a row", "gate")}
  {_box(250, 300, 300, 132, "Firestore and Cloud Storage", "", "store", top=True)}
  <text class="s" x="264" y="352">requirements, retired ones kept and never repeated</text>
  <text class="s" x="264" y="376">sources registry: a new source is a row, not a deploy</text>
  <text class="s" x="264" y="400">courses, occupations, listings, cases</text>
  <text class="s" x="264" y="424">snapshot archive, append only, watcher reads it back</text>
  {_box(250, 460, 300, 56, "Digest", "who does this actually affect")}

  {_band(620, 22, "CLOUD RUN SERVICE &#183; migragent", "runs as migragent-web")}
  {_box(620, 44, 264, 56, "What you want, what you have", "two taps and an upload")}
  {_box(620, 140, 264, 56, "Countries out of your documents", "never a country list")}
  {_box(620, 236, 264, 56, "Guide, courses, work, alerts", "every line carries its source")}

  {_box(16, 548, 868, 60, "Gemini 3.5 Flash on Vertex, through migragent/model.py",
        "It says what a page means. It never says a requirement exists, and it "
        "never supplies the link or the date: those come off the fetch.", "model")}

  <path class="e" d="M 206 70 L 232 70 L 232 154 L 246 154" marker-end="url(#a)"/>
  <path class="e" d="M 206 142 L 232 142 L 232 154 L 246 154" marker-end="url(#a)"/>
  <path class="e" d="M 206 214 L 232 214 L 232 154 L 246 154" marker-end="url(#a)"/>
  <path class="e" d="M 400 96 L 400 120" marker-end="url(#a)"/>
  <path class="e" d="M 400 184 L 400 208" marker-end="url(#a)"/>
  <path class="e" d="M 400 268 L 400 296" marker-end="url(#a)"/>
  <path class="e" d="M 400 432 L 400 456" marker-end="url(#a)"/>
  <path class="e" d="M 550 366 L 585 366 L 585 168 L 616 168" marker-end="url(#a)"/>
  <path class="e" d="M 550 488 L 624 296" marker-end="url(#a)"/>
  <path class="e" d="M 752 100 L 752 136" marker-end="url(#a)"/>
  <path class="e" d="M 752 196 L 752 232" marker-end="url(#a)"/>
</svg>
<figcaption>The job reads and the service serves. They meet at the rows in the
middle, and nothing reaches a screen that did not pass the quote check.</figcaption>
</figure>
'''


EXTRA = '''
  .diagram { margin: 0 0 26px; padding: 0 }
  .diagram svg { width: 100%; height: auto; display: block }
  .diagram figcaption { font-size: .84rem; color: var(--ink-soft); line-height: 1.6;
                        margin-top: 12px }
  svg .n { fill: var(--paper-raised); stroke: var(--rule) }
  svg .gate { stroke: var(--primary) }
  svg .store { fill: none; stroke-dasharray: 3 3 }
  svg .model { fill: none; stroke: var(--primary) }
  svg .t { font: 600 13px var(--font-body); fill: var(--ink) }
  svg .s { font: 400 11.5px var(--font-body); fill: var(--ink-soft) }
  svg .band { font: 500 9.5px var(--font-mono); letter-spacing: .08em; fill: var(--ink-soft) }
  svg .e { fill: none; stroke: var(--ink-soft); stroke-width: 1.3 }
  svg marker path { fill: var(--ink-soft) }
'''


def architecture_html(markdown: str, updated: str = "", **facts: Any) -> str:
    # The masthead already carries the document's title, so the file's own H1
    # comes off. Rendering both put the same sentence on screen twice.
    text = re.sub(r"\A#\s+.*\n", "", markdown)
    body = render(MERMAID.sub(PLACEHOLDER, text)).replace(
        f"<p>{PLACEHOLDER}</p>", DIAGRAM)
    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}
<title>How MIGRAGENT is put together</title>
<style>{STYLE}{EXTRA}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>

  <div class="masthead">
    <h1>How MIGRAGENT is put together</h1>
    <dl>
      <dt>Runs on</dt><dd>Cloud Run, Firestore, Cloud Storage, Cloud Scheduler, Vertex AI</dd>
      <dt>Agent</dt><dd>ADK, on the researcher, and nowhere else</dd>
      <dt>Source</dt><dd><a href="https://github.com/cnpierrepapi/migragent"
        rel="noopener noreferrer">github.com/cnpierrepapi/migragent</a></dd>
      <dt>Last updated</dt><dd>{updated or "see the repository history"}</dd>
    </dl>
  </div>

  {body}

  <p class="foot">This page renders docs/ARCHITECTURE.md from the repository, so what
  is described here and what the build is held to are the same file. Where a boundary
  is tested, the test is named and you can run it.
  <br><a href="/">MIGRAGENT</a> &middot;
  <a href="/coverage">What we have read</a> &middot;
  <a href="/data">What happens to your documents</a></p>
</main></body></html>'''
