"""Assembling the guide a person receives.

Plain code. A model wrote the wording of each requirement when the page was
read, and the check on that already happened in extract.py. Nothing here calls a
model, because ordering steps and totalling costs are not tasks that benefit
from one, and every number on the page should be arithmetic somebody can repeat.

The shape is fixed and the two halves are not negotiable:

  the steps      what this page says you must do, each with its link and the
                 date it was read
  open questions what no source could be found for, at the back, named as such

A guide with an empty open questions section is not a better guide, it is a less
honest one, so the section is always printed even when it is empty and says so.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

JURISDICTION_NAMES = {
    "UK": "the United Kingdom", "US": "the United States", "CA": "Canada",
    "AU": "Australia", "FR": "France", "ES": "Spain",
    "AE": "the United Arab Emirates",
}

CATEGORY_HEADINGS = {
    "eligibility": "Whether you qualify",
    "document": "Documents you must have",
    "requirement": "What you must do",
    "cost": "What it costs",
    "timing": "How long it takes",
}


def _pretty_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %B %Y")
    except (ValueError, TypeError):
        return iso or "an unrecorded date"


@dataclass
class Guide:
    jurisdiction: str
    lane: str
    generated_at: str
    requirements: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[dict[str, Any]] = field(default_factory=list)
    sources_read: int = 0
    total_sources: int = 0

    @property
    def title(self) -> str:
        place = JURISDICTION_NAMES.get(self.jurisdiction, self.jurisdiction)
        what = "study" if self.lane == "study" else "work"
        return f"Applying to {what} in {place}"

    @property
    def source_urls(self) -> list[str]:
        return sorted({r.get("source_url", "") for r in self.requirements if r.get("source_url")})

    def by_category(self) -> list[tuple[str, list[dict[str, Any]]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for req in self.requirements:
            grouped.setdefault(req.get("category", "requirement"), []).append(req)
        return [(CATEGORY_HEADINGS.get(cat, cat.title()), grouped[cat])
                for cat in CATEGORY_HEADINGS if cat in grouped]


def build(jurisdiction: str, lane: str, requirements: list[dict[str, Any]],
          open_questions: list[dict[str, Any]], total_sources: int) -> Guide:
    return Guide(
        jurisdiction=jurisdiction,
        lane=lane,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        requirements=requirements,
        open_questions=open_questions,
        sources_read=len({r.get("source_url") for r in requirements}),
        total_sources=total_sources,
    )


def _e(text: Any) -> str:
    return html.escape(str(text or ""))


def to_html(guide: Guide) -> str:
    """The guide as a page, and as the thing a browser prints to PDF.

    Printing is the delivery mechanism rather than a separate renderer, so what
    somebody saves is the document they were looking at. A second renderer would
    be a second place for the two to disagree.
    """
    steps: list[str] = []
    number = 0
    for heading, items in guide.by_category():
        steps.append(f'<h2>{_e(heading)}</h2>')
        for req in items:
            number += 1
            facts = []
            if req.get("cost"):
                facts.append(f'<span>Cost <b>{_e(req["cost"])}</b></span>')
            if req.get("duration"):
                facts.append(f'<span>Takes <b>{_e(req["duration"])}</b></span>')
            if req.get("depends_on"):
                facts.append(f'<span>First <b>{_e(req["depends_on"])}</b></span>')
            facts_html = f'<div class="facts">{"".join(facts)}</div>' if facts else ""

            provenance = req.get("provenance", "official")
            label = "Official source" if provenance == "official" else "Course portal"

            steps.append(f'''
    <section class="req">
      <h3><span class="n">{number}</span>{_e(req.get("text"))}</h3>
      {facts_html}
      <blockquote>{_e(req.get("quote"))}</blockquote>
      <p class="cite">
        <span class="tag">{_e(label)}</span>
        <a class="source" href="{_e(req.get("source_url"))}">{_e(req.get("source_url"))}</a>
        <span class="read-on">read on {_e(_pretty_date(req.get("read_at", "")))}</span>
      </p>
    </section>''')

    if guide.open_questions:
        questions = "".join(
            f'<li>{_e(q.get("question"))}<span class="from">raised by '
            f'<a href="{_e(q.get("source_url"))}">{_e(q.get("source_url"))}</a></span></li>'
            for q in guide.open_questions
        )
        open_block = f'<ul class="oq">{questions}</ul>'
    else:
        open_block = ('<p class="none">No open questions were recorded for this lane. That is '
                      'not a promise that nothing is missing, only that nothing was flagged '
                      'by the pages that were read.</p>')

    return f'''<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(guide.title)}</title>
<link rel="icon" href="/brand/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/brand/tokens.css">
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; padding: 56px 28px 96px; }}
  main {{ max-width: 780px; margin: 0 auto }}
  .mark {{ display: flex; align-items: center; gap: 12px; color: var(--primary); margin-bottom: 36px }}
  .mark svg {{ width: 30px; height: 30px }}
  .mark span {{ font-family: var(--font-display); font-size: 1.35rem; color: var(--ink);
                letter-spacing: .02em }}
  h1 {{ font-size: clamp(2rem, 5vw, 2.9rem); line-height: 1.06; margin: 0 0 12px }}
  .sub {{ color: var(--ink-soft); font-size: 1.02rem; line-height: 1.6; margin: 0 0 8px; max-width: 60ch }}
  .counts {{ font-family: var(--font-mono); font-size: .8rem; color: var(--ink-soft);
             padding: 14px 0 0; border-top: 1px solid var(--rule); margin-top: 28px }}
  h2 {{ font-size: .82rem; text-transform: uppercase; letter-spacing: .14em;
        font-family: var(--font-body); font-weight: 600; color: var(--ink-soft);
        margin: 48px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--rule) }}
  .req {{ background: var(--paper-raised); border: 1px solid var(--rule);
          border-left: 3px solid var(--primary); border-radius: var(--radius);
          padding: 20px 22px; margin: 0 0 12px; box-shadow: var(--shadow);
          break-inside: avoid }}
  .req h3 {{ margin: 0 0 10px; font: 600 1.04rem/1.45 var(--font-body); color: var(--ink);
             display: flex; gap: 12px; align-items: baseline }}
  .n {{ font-family: var(--font-mono); font-size: .78rem; color: var(--primary); flex: none }}
  .facts {{ display: flex; flex-wrap: wrap; gap: 18px; margin: 0 0 10px;
            font: .84rem var(--font-body); color: var(--ink-soft) }}
  .facts b {{ color: var(--ink); font-variant-numeric: tabular-nums }}
  blockquote {{ margin: 0 0 12px; padding: 10px 14px; background: var(--paper);
                border-radius: var(--radius-sm); font-size: .9rem; line-height: 1.6;
                color: var(--ink-soft); border: 1px solid var(--rule) }}
  .cite {{ margin: 0; display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline }}
  .tag {{ font: 500 .7rem var(--font-body); text-transform: uppercase; letter-spacing: .08em;
          color: var(--primary); border: 1px solid var(--rule); border-radius: 100px;
          padding: 2px 9px }}
  .oq {{ margin: 0; padding: 0; list-style: none }}
  .oq li {{ border-left: 2px solid var(--warn); padding: 4px 0 4px 16px; margin-bottom: 14px;
            line-height: 1.6; color: var(--ink) }}
  .from {{ display: block; font-family: var(--font-mono); font-size: .72rem;
           color: var(--ink-soft); margin-top: 4px }}
  .from a {{ color: var(--link) }}
  .none {{ color: var(--ink-soft); line-height: 1.6 }}
  footer {{ margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--rule);
            color: var(--ink-soft); font-size: .84rem; line-height: 1.65 }}
  @media print {{
    body {{ padding: 0; background: #fff }}
    .req {{ box-shadow: none }}
    a {{ color: inherit }}
  }}
</style>
</head>
<body>
<main>
  <div class="mark">
    <svg viewBox="0 0 64 64"><path d="M10 36 V8 L32 28 L54 8 V36" fill="none" stroke="currentColor" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 50 Q32 61 45 50" fill="none" stroke="currentColor" stroke-width="7.5" stroke-linecap="round"/></svg>
    <span>MIGRAGENT</span>
  </div>

  <h1>{_e(guide.title)}</h1>
  <p class="sub">Every requirement below carries the official page it came from and the date that
  page was read. Nothing is stated without a source. Anything that could not be sourced is at the
  back, under open questions, rather than guessed at.</p>
  <p class="sub">This is not legal advice. It reports what official sources say.</p>

  <div class="counts">
    {len(guide.requirements)} requirements &nbsp;·&nbsp;
    {guide.sources_read} pages cited &nbsp;·&nbsp;
    {guide.total_sources} sources in the registry &nbsp;·&nbsp;
    built {_e(_pretty_date(guide.generated_at))}
  </div>

  {"".join(steps) if steps else '<h2>What you must do</h2><p class="none">No requirements have been extracted for this lane yet. Rather than fill the space, this says so.</p>'}

  <h2>Open questions</h2>
  {open_block}

  <footer>
    Generated by MIGRAGENT on {_e(_pretty_date(guide.generated_at))}. Rules change. Every line above
    is what the linked page said on the date shown next to it, and not what it says today.
  </footer>
</main>
</body>
</html>
'''
