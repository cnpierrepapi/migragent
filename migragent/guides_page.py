"""Guide pages: the index by country, and one guide with its citations and affiliate boxes.

Every paragraph carries numbered citations. Each number opens the requirement
it rests on: what it says, the government's own sentence, and the page it came
from. Affiliate boxes appear only for topics the editor has a real link for,
and say they are affiliate links.
"""
from __future__ import annotations

import html
from typing import Any

from .guides import TOPICS
from .masthead import MASTHEAD
from .registry import JURISDICTIONS
from .result_page import HEAD
from .seo import SITE, breadcrumbs, meta
from .signup import STYLE as SIGNUP_STYLE


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _country(code: str) -> str:
    return JURISDICTIONS.get(code, {}).get("name", code)


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding-bottom: 80px }
  main { max-width: 1100px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  .kicker { font: 500 .72rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); margin: 0 0 12px }
  .kicker b { color: var(--primary); font-weight: 500 }
  h1 { font-size: clamp(1.9rem, 4.2vw, 2.9rem); line-height: 1.08; margin: 0 0 12px }
  .dek { font: italic 1.2rem/1.55 var(--font-serif); margin: 0 0 16px }
  .stamp { font: .72rem/1.7 var(--font-mono); color: var(--ink-soft); border-top: 1px solid var(--ink);
           border-bottom: 1px solid var(--rule); padding: 8px 0; margin-bottom: 24px }
  .stamp b { color: var(--accent); font-weight: 500 }
  .guide { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 48px }
  .body h2 { font-size: 1.4rem; margin: 30px 0 10px; padding-top: 10px; border-top: 1px solid var(--rule) }
  .body p { font: 1.08rem/1.72 var(--font-serif); margin: 0 0 14px }
  sup.c a { font: 500 .68rem var(--font-mono); color: var(--primary); text-decoration: none; margin-left: 2px }
  ul.check { list-style: none; padding: 0; margin: 0 }
  ul.check li { font: 1.04rem/1.6 var(--font-serif); padding: 8px 0 8px 28px; position: relative; border-bottom: 1px dotted var(--rule) }
  ul.check li::before { content: "\\2610"; position: absolute; left: 0; color: var(--primary) }
  details.faq { border-bottom: 1px solid var(--rule); padding: 10px 0 }
  details.faq summary { cursor: pointer; font: 600 1.04rem/1.5 var(--font-serif) }
  details.faq p { margin: 8px 0 0 }
  .aff { border: 1px solid var(--accent); background: var(--paper-raised); padding: 14px 16px; margin: 0 0 14px }
  .aff b { display: block; font: 500 .66rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase; color: var(--accent) }
  .aff a.name { font: 640 1.05rem var(--font-display); color: var(--ink); text-decoration: none }
  .aff p { font: .92rem/1.5 var(--font-serif); margin: 4px 0 0 }
  .aff small { display: block; font: .64rem var(--font-mono); color: var(--ink-soft); margin-top: 6px }
  .side h3 { font: 500 .72rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase;
             border-bottom: 1px solid var(--ink); padding-bottom: 6px; margin: 0 0 10px }
  ol.cites { padding-left: 22px; font: .78rem/1.6 var(--font-mono) }
  ol.cites li { padding: 6px 0; border-bottom: 1px dotted var(--rule); overflow-wrap: anywhere }
  ol.cites q { display: block; color: var(--ink-soft); quotes: none; margin-top: 3px }
  .src { font: .74rem/1.6 var(--font-mono); overflow-wrap: anywhere }
  .disclaim { font: italic .92rem/1.6 var(--font-serif); color: var(--ink-soft); margin-top: 24px }
  .idx h2 { font-size: 1.35rem; margin: 30px 0 6px; padding-top: 10px; border-top: 1px solid var(--ink) }
  .idx a.g { display: block; padding: 10px 0; border-bottom: 1px solid var(--rule); text-decoration: none; color: var(--ink) }
  .idx a.g b { font: 640 1.1rem var(--font-display); font-variation-settings: "opsz" 36, "SOFT" 0, "WONK" 0 }
  .idx a.g span { display: block; font: .95rem/1.5 var(--font-serif); color: var(--ink-soft) }
  @media (max-width: 900px) { .guide { grid-template-columns: 1fr; gap: 10px } }
'''


def _page(title: str, description: str, path: str, body: str, ld=None, kind: str = "website") -> str:
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
{meta(title=title, description=description, path=path, ld=ld, kind=kind)}
<style>{STYLE}{SIGNUP_STYLE}</style></head>
<body>{MASTHEAD}<main>{body}</main></body></html>'''


def index_html(guides: list[dict[str, Any]], signup: str = "") -> str:
    by: dict[str, list[dict[str, Any]]] = {}
    for g in guides:
        by.setdefault(g.get("jurisdiction", ""), []).append(g)
    blocks = "".join(
        f'<h2>{_e(_country(code))}</h2>' + "".join(
            f'<a class="g" href="/guides/{_e(g["slug"])}"><b>{_e(g["title"])}</b><span>{_e(g.get("dek"))}</span></a>'
            for g in gs)
        for code, gs in sorted(by.items(), key=lambda kv: _country(kv[0])))
    body = f'''<div class="idx"><h1>Guides</h1>
  <p class="dek">Each guide explains one official immigration page: who it's for, what you need to show, what it
  costs. Every line links to the government's own sentence.</p>
  {blocks or "<p>The first guides are being written.</p>"}</div>
  <div id="alerts" style="max-width:760px">{signup}</div>'''
    return _page("Immigration guides, cited line by line", "Plain-English guides to official visa and study "
                 "routes in 13 countries, built only from the government's own wording.", "/guides", body,
                 ld=[breadcrumbs(("The wire", "/"), ("Guides", "/guides"))])


def _cite_marks(cites: list[str], order: dict[str, int]) -> str:
    return "".join(f'<sup class="c"><a href="#c{order[c]}">[{order[c]}]</a></sup>' for c in cites if c in order)


def _affiliate_boxes(topics: list[str], country: str, affs: list[dict[str, Any]]) -> str:
    out = []
    for t in topics:
        for a in affs:
            if a.get("topic") != t:
                continue
            if a.get("countries") and country not in a["countries"]:
                continue
            out.append(f'<div class="aff"><b>{_e(TOPICS.get(t, t))}</b>'
                       f'<a class="name" href="{_e(a.get("url"))}" rel="sponsored noopener" target="_blank">{_e(a.get("name"))}</a>'
                       f'<p>{_e(a.get("blurb"))}</p><small>Affiliate link: we may earn a commission, at no cost to you.</small></div>')
            break
    return "".join(out)


def guide_html(g: dict[str, Any], affs: list[dict[str, Any]], signup: str = "") -> str:
    order: dict[str, int] = {}
    for c in [c for s in g.get("sections") or [] for p in s["paragraphs"] for c in p["cites"]] + \
             [c for it in (g.get("checklist") or []) + (g.get("faq") or []) for c in it["cites"]]:
        order.setdefault(c, len(order) + 1)
    cites = g.get("cites") or {}
    country = _country(g.get("jurisdiction", ""))
    sections = "".join(f'<h2>{_e(s["heading"])}</h2>' + "".join(
        f'<p>{_e(p["text"])}{_cite_marks(p["cites"], order)}</p>' for p in s["paragraphs"]) for s in g.get("sections") or [])
    checklist = ("<h2>Checklist</h2><ul class=\"check\">" + "".join(
        f'<li>{_e(c["item"])}{_cite_marks(c["cites"], order)}</li>' for c in g["checklist"]) + "</ul>") if g.get("checklist") else ""
    faq = ("<h2>Questions people ask</h2>" + "".join(
        f'<details class="faq"><summary>{_e(f["q"])}</summary><p>{_e(f["a"])}{_cite_marks(f["cites"], order)}</p></details>'
        for f in g["faq"])) if g.get("faq") else ""
    cite_list = "".join(f'<li id="c{n}">{_e((cites.get(cid) or {}).get("text"))}<q>"{_e((cites.get(cid) or {}).get("quote"))}"</q></li>'
                        for cid, n in sorted(order.items(), key=lambda kv: kv[1]))
    path = f"/guides/{g['slug']}"
    r = g.get("report") or {}
    body = f'''<div class="guide"><div>
  <p class="kicker"><b>{_e(country)}</b> · {_e(g.get("lane"))} · guide</p>
  <h1>{_e(g.get("title"))}</h1>
  <p class="dek">{_e(g.get("dek"))}</p>
  <p class="stamp"><b>MIGRAGENT</b> wrote this from {len(order)} requirements on the official page, each checked against the
  government's own wording. Updated {_e((g.get("updated_at") or "")[:10])}.
  Source: <a href="{_e(g.get("source_url"))}" target="_blank" rel="noopener">{_e(g.get("source_url"))}</a></p>
  <div class="body">{sections}{checklist}{faq}
    <p class="disclaim">This explains what one official page says. It is not legal advice, and the page itself is the
    authority. Rules change; the <a href="/articles">wire</a> reports it when they do.</p>
    <div id="alerts">{signup}</div>
  </div>
</div>
<aside class="side">
  {_affiliate_boxes(g.get("topics") or [], g.get("jurisdiction", ""), affs)}
  <h3>Where each line comes from</h3><ol class="cites">{cite_list}</ol>
  <p class="src">All from <a href="{_e(g.get("source_url"))}" target="_blank" rel="noopener">the official page</a>.
  {r.get("lines_dropped", 0)} lines the writer proposed were dropped because they cited nothing on it.</p>
</aside></div>'''
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
        for f in g.get("faq") or []]}
    article_ld = {"@context": "https://schema.org", "@type": "Article", "headline": g.get("title"),
                  "description": g.get("dek"), "url": SITE + path, "mainEntityOfPage": SITE + path,
                  "dateModified": g.get("updated_at"), "datePublished": g.get("created_at"),
                  "author": {"@type": "Organization", "name": "MIGRAGENT"},
                  "publisher": {"@type": "Organization", "name": "MIGRAGENT"}, "isBasedOn": g.get("source_url")}
    ld = [article_ld, breadcrumbs(("Guides", "/guides"), (g.get("title", ""), path))] + ([faq_ld] if g.get("faq") else [])
    return _page(g.get("title", ""), g.get("dek", ""), path, body, ld=ld, kind="article")
