"""The search page, and the search box other pages carry."""
from __future__ import annotations

import html
from typing import Any

from .masthead import MASTHEAD
from .result_page import HEAD
from .seo import meta


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


BOX_STYLE = '''
  form.search { display: flex; gap: 8px; margin: 0 0 22px; max-width: 680px }
  form.search input { flex: 1; padding: 11px 12px; border: 1px solid var(--ink); background: var(--paper-raised);
       color: var(--ink); font: 1rem var(--font-body); border-radius: var(--radius-sm) }
  form.search button { padding: 11px 18px; border: 0; background: var(--ink); color: var(--paper);
       font: 600 .9rem var(--font-body); border-radius: var(--radius-sm); cursor: pointer }
'''


def box(q: str = "", placeholder: str = "Search guides and the wire, e.g. Canada study permit") -> str:
    return (f'<form class="search" role="search" method="get" action="/search">'
            f'<input type="search" name="q" value="{_e(q)}" placeholder="{_e(placeholder)}" aria-label="Search" '
            f'id="site-search"><button type="submit">Search</button></form>')


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding-bottom: 80px }
  main { max-width: 900px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  h1 { font-size: clamp(1.8rem, 3.6vw, 2.4rem); margin: 0 0 14px }
  .count { font: .76rem var(--font-mono); color: var(--ink-soft); margin: 0 0 8px }
  .hit { padding: 14px 0; border-bottom: 1px solid var(--rule) }
  .hit .k { font: 500 .66rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent) }
  .hit .k b { color: var(--primary); font-weight: 500 }
  .hit a.t { display: block; font: 640 1.15rem/1.3 var(--font-display); color: var(--ink); text-decoration: none; margin: 3px 0;
             font-variation-settings: "opsz" 36, "SOFT" 0, "WONK" 0 }
  .hit a.t:hover { color: var(--primary) }
  .hit p { font: .98rem/1.55 var(--font-serif); margin: 0; color: var(--ink-soft) }
  .none { font: 1.05rem/1.6 var(--font-serif) }
''' + BOX_STYLE


def search_html(q: str, hits: list[dict[str, Any]]) -> str:
    rows = "".join(
        f'<div class="hit"><span class="k"><b>{_e(h["country"])}</b> · {_e(h["lane"])} · '
        f'{"guide" if h["kind"] == "guide" else "article, " + _e(h["date"])}</span>'
        f'<a class="t" href="{_e(h["url"])}">{_e(h["title"])}</a><p>{_e(h["summary"])}</p></div>' for h in hits)
    if q and not hits:
        rows = ('<p class="none">Nothing matches every word of that. Try fewer words, or a country and a route, '
                'like "Portugal work" or "UK student visa".</p>')
    count = f'<p class="count">{len(hits)} result{"" if len(hits) == 1 else "s"} for "{_e(q)}"</p>' if q else ""
    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
{meta(title=f"Search: {q}" if q else "Search the guides and the wire", path="/search",
      description="Search MIGRAGENT's cited immigration guides and rule-change articles across 13 countries.", noindex=True)}
<style>{STYLE}</style></head>
<body>{MASTHEAD}<main>
  <h1>Search</h1>
  {box(q)}
  {count}{rows}
</main></body></html>'''
