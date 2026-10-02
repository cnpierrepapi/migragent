"""The front page: the wire, the desk, and the way in.

A NEWSPAPER, BECAUSE THAT IS WHAT IT IS NOW
-------------------------------------------
Earlier versions of this page learned that the product is not the evidence
discipline and not the guide: it is an agent that keeps working after you close
the tab. October 2026 made that visible. The agent reads official immigration
pages every morning and writes up every rule change as an article, with who it
is for and a report that shows its working. So the front page is a front page.

The lead is the strongest recent article, with who it is for. Down the side is
the log: what the agent did today, what it cost, and how long its
$MIGRA-funded balance lasts. Below the fold is how it reports, where it reads,
and what pays for it. Since 2 October 2026 there is no case product: it is a
reporter, and nothing on this page asks anybody for anything.

NOTHING HERE IS A MOCK-UP
-------------------------
The articles come from `articles`, which the agent wrote and the quote check
passed. The desk comes from /api/state, built from rows the reading job wrote.
Where there is nothing yet, the page says so. The old page carried an
illustrated alert feed and a kept-and-dropped demo; both said they were
examples, and both went once the real thing existed.

THE NEWSROOM FACE
-----------------
Paper, ink, wire red for headlines and actions, agent green for anything the
agent says about itself. See the NEWSROOM block in web/brand/tokens.css.
"""
from __future__ import annotations

import html
from typing import Any

from .masthead import MASTHEAD
from .registry import JURISDICTIONS
from .result_page import HEAD


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _country(code: str) -> str:
    return JURISDICTIONS.get(code, {}).get("name", code)


CSS = '''
  * { box-sizing: border-box }
  body { margin: 0 }
  .page { max-width: 1160px; margin: 0 auto; padding: 0 24px }
  a { color: var(--link) }
  .kicker { font: 500 .7rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase;
            color: var(--accent); margin: 0 0 10px }
  .kicker b { color: var(--primary); font-weight: 500 }

  .front { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr) 290px; gap: 0;
           border-bottom: 1px solid var(--ink); padding-bottom: 30px }
  .front > div { padding: 0 24px; border-right: 1px solid var(--rule) }
  .front > div:first-child { padding-left: 0 }
  .front > div:last-child { padding-right: 0; border-right: 0 }

  .lead h1 { font-size: clamp(2rem, 4.4vw, 3.2rem); line-height: 1.04; margin: 0 0 14px }
  .lead h1 a { color: var(--ink); text-decoration: none }
  .lead h1 a:hover { color: var(--primary) }
  .lead .dek { font: italic 1.22rem/1.5 var(--font-serif); margin: 0 0 18px }
  .lead h2 { font: 600 .74rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase;
             color: var(--primary); border-top: 3px solid var(--primary); padding-top: 8px; margin: 0 0 6px }
  .lead ul { list-style: none; margin: 0 0 16px; padding: 0 }
  .lead li { font: 1.04rem/1.55 var(--font-serif); padding: 9px 0; border-bottom: 1px dotted var(--rule) }
  .lead li b { font-weight: 600 }
  .lead li small { font: .74rem/1.6 var(--font-mono); color: var(--accent) }
  .lead .more { font: 500 .8rem var(--font-mono) }
  .lead .stamp { font: .72rem/1.7 var(--font-mono); color: var(--ink-soft); margin-top: 14px }

  .second h3, .desk h3 { font: 500 .7rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase;
             border-bottom: 1px solid var(--ink); padding-bottom: 6px; margin: 0 0 4px;
             display: flex; justify-content: space-between }
  .desk h3 { margin-bottom: 10px }
  .desk h3 span { color: var(--accent) }
  .story { padding: 14px 0; border-bottom: 1px solid var(--rule) }
  .story:last-child { border-bottom: 0 }
  .story h4 { font: 640 1.14rem/1.25 var(--font-display); margin: 4px 0 6px;
              font-variation-settings: "opsz" 36, "SOFT" 0, "WONK" 0 }
  .story .kicker { font: 500 .66rem var(--font-mono); letter-spacing: .08em; text-transform: uppercase;
                   color: var(--accent); margin: 0 }
  .story h4 a { color: var(--ink); text-decoration: none }
  .story h4 a:hover { color: var(--primary) }
  .story p { font: .95rem/1.5 var(--font-serif); margin: 0; color: var(--ink) }
  .story .for { font: .72rem/1.6 var(--font-mono); color: var(--ink-soft); margin-top: 6px }

  .figs { display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid var(--rule) }
  .fig { padding: 10px 0; border-bottom: 1px solid var(--rule); min-width: 0 }
  .fig:nth-child(odd) { padding-right: 10px; border-right: 1px solid var(--rule) }
  .fig:nth-child(even) { padding-left: 10px }
  .fig span { display: block; font: .64rem var(--font-mono); color: var(--ink-soft); text-transform: uppercase;
              letter-spacing: .06em }
  .fig b { display: block; font: 640 1.45rem var(--font-display); margin: 3px 0 1px; color: var(--ink);
           overflow-wrap: anywhere }
  .fig.paid b { color: var(--accent) }
  .fig small { font: .64rem var(--font-mono); color: var(--ink-soft) }
  .log { list-style: none; margin: 12px 0 0; padding: 0; font: .7rem/1.55 var(--font-mono) }
  .log li { padding: 7px 0; border-bottom: 1px dotted var(--rule) }
  .log time { color: var(--ink-soft) }
  .log .role { color: var(--accent); margin: 0 4px }
  .log .role.CHANGE { color: var(--primary) }
  .log .cost { color: var(--accent) }
  .desk .fine { font: .66rem/1.6 var(--font-mono); color: var(--ink-soft); margin-top: 10px }

  .band { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 3px double var(--ink) }
  .band div { padding: 16px 18px; border-right: 1px solid var(--rule) }
  .band div:first-child { padding-left: 0 }
  .band div:last-child { border-right: 0 }
  .band b { display: block; font: 640 1.9rem var(--font-display) }
  .band span { font: .68rem var(--font-mono); color: var(--ink-soft) }

  section { padding: 44px 0 10px }
  section > h2 { font-size: clamp(1.6rem, 3.2vw, 2.3rem); margin: 0 0 8px }
  .lede { font: 1.14rem/1.65 var(--font-serif); max-width: 62ch; margin: 0 0 22px }
  .cols { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--ink) }
  .cols > div { padding: 16px 22px 6px 0; margin-right: 22px; border-right: 1px solid var(--rule) }
  .cols > div:last-child { border-right: 0; margin-right: 0 }
  .cols em { font: 500 .68rem var(--font-mono); letter-spacing: .1em; text-transform: uppercase;
             color: var(--primary); font-style: normal }
  .cols b { display: block; font: 640 1.2rem var(--font-display); margin: 6px 0 6px }
  .cols p { font: 1rem/1.6 var(--font-serif); margin: 0 0 12px }
  .two { display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid var(--ink) }
  .two > div { padding: 16px 22px 6px 0 }
  .two > div + div { padding-left: 22px; border-left: 1px solid var(--rule) }
  .two b { display: block; font: 640 1.3rem var(--font-display); margin-bottom: 6px }
  .two p { font: 1rem/1.6 var(--font-serif); margin: 0 }
  .cta { display: inline-block; padding: 13px 24px; background: var(--primary); color: var(--paper);
         text-decoration: none; font: 600 .95rem var(--font-body); border-radius: var(--radius) }
  .cta.ghost { background: transparent; color: var(--ink); border: 1px solid var(--ink) }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin: 18px 0 8px }
  .under { font: .74rem var(--font-mono); color: var(--ink-soft) }
  .places { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
            border-top: 1px solid var(--ink) }
  .place { padding: 14px 16px 14px 0; border-bottom: 1px solid var(--rule) }
  .place b { display: block; font: 640 1.15rem var(--font-display) }
  .place span { display: block; font: .74rem/1.6 var(--font-mono); color: var(--ink-soft) }
  .later { font: italic .98rem/1.6 var(--font-serif); color: var(--ink-soft); margin-top: 14px }
  .print { border: 1px solid var(--ink); background: var(--paper-raised); padding: 20px 22px; max-width: 760px }
  .print p { font: 1.02rem/1.65 var(--font-serif); margin: 0 0 10px }
  .print code { font: .82rem var(--font-mono); color: var(--accent) }
  .print code.out { color: var(--warn) }
  .end { text-align: center; padding: 56px 0 30px; border-top: 3px double var(--ink); margin-top: 40px }
  .end h2 { font-size: clamp(1.8rem, 3.6vw, 2.6rem); margin: 0 0 10px }
  footer { border-top: 1px solid var(--rule); padding: 20px 0 50px; font: .74rem/1.8 var(--font-mono);
           color: var(--ink-soft) }
  footer a { color: var(--ink-soft) }

  @media (max-width: 1000px) {
    .front { grid-template-columns: 1fr 1fr }
    .front > div.desk { grid-column: 1 / -1; padding: 24px 0 0; border-right: 0;
                        border-top: 1px solid var(--ink); margin-top: 20px }
    .front > div.second { padding-right: 0; border-right: 0 }
  }
  @media (max-width: 700px) {
    .front { grid-template-columns: 1fr }
    .front > div { padding: 0; border-right: 0 }
    .front > div.second { border-top: 1px solid var(--ink); margin-top: 22px; padding-top: 14px }
    .band { grid-template-columns: 1fr 1fr }
    .band div:nth-child(3) { padding-left: 0 }
    .band div:nth-child(2) { border-right: 0 }
    .cols, .two { grid-template-columns: 1fr }
    .cols > div { border-right: 0; margin-right: 0; border-bottom: 1px solid var(--rule) }
    .two > div + div { padding-left: 0; border-left: 0; border-top: 1px solid var(--rule) }
  }
'''

DESK = '''<div class="desk" id="live">
  <h3>The log <span id="lv-phase">-</span></h3>
  <div class="figs">
    <div class="fig paid"><span>Orbio balance</span><b id="lv-balance">-</b><small>from $MIGRA fees</small></div>
    <div class="fig"><span>Spent today</span><b id="lv-spent">-</b><small>by the agent</small></div>
    <div class="fig"><span>Pages read today</span><b id="lv-pages">-</b><small id="lv-unchanged">-</small></div>
    <div class="fig"><span>Pages that moved</span><b id="lv-changes">-</b><small id="lv-rules">this week</small></div>
    <div class="fig"><span>Runway</span><b id="lv-runway">-</b><small>at this week's pace</small></div>
    <div class="fig"><span>$MIGRA</span><b id="lv-mcap">-</b><small id="lv-grad">market cap</small></div>
  </div>
  <ol class="log" id="lv-log"></ol>
  <p class="fine">Every line is a row the reading job wrote. Balance read from Orbio <span id="lv-asof">-</span>.
  Everything it reads is public. <a href="/rounds">Every round</a>.</p>
</div>
<script>
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const money = (n) => n == null ? "-" : (n < 1 ? "$" + n.toFixed(4) : "$" + n.toFixed(2));
  const ago = (iso) => { const s = (Date.now() - Date.parse(iso)) / 1000; if (!isFinite(s)) return "";
    return s < 90 ? "now" : s < 5400 ? Math.round(s / 60) + "m" : s < 129600 ? Math.round(s / 3600) + "h" : Math.round(s / 86400) + "d"; };
  async function poll() {
    let s; try { s = await (await fetch("/api/state", {cache: "no-store"})).json(); } catch (e) { return; }
    const o = s.orbio || {}, st = s.stats || {}, t = s.token;
    $("lv-phase").textContent = s.status.phase === "READING" ? "reading now" : "idle";
    $("lv-balance").textContent = money(o.available);
    $("lv-spent").textContent = money(o.spent_today);
    $("lv-pages").textContent = (st.pages_today ?? "-").toLocaleString();
    $("lv-unchanged").textContent = (st.unchanged_today ?? 0) + " unchanged, $0";
    $("lv-changes").textContent = (st.changes_week ?? "-").toLocaleString();
    $("lv-rules").textContent = (st.rule_changes_week ?? 0) + " changed a rule";
    $("lv-runway").textContent = o.runway_days == null ? "-" : o.runway_days + " days";
    if (t) { $("lv-mcap").textContent = "$" + (t.market_cap_usd / 1000).toFixed(1) + "K";
             $("lv-grad").textContent = t.graduation_pct + "% to graduation"; }
    $("lv-asof").textContent = o.at ? ago(o.at) + " ago" : "after the next round";
    $("lv-log").innerHTML = (s.feed || []).slice(0, 9).map((f) =>
      '<li><time>' + esc(ago(f.at)) + '</time><span class="role ' + esc(f.role) + '">' + esc(f.role) + '</span>' +
      esc(f.text) + (f.cost ? ' <span class="cost">' + esc(f.cost) + '</span>' : '') + '</li>').join("");
  }
  poll(); setInterval(poll, 20000);
})();
</script>'''


def _lead(a: dict[str, Any] | None) -> str:
    if not a:
        return '''<div class="lead">
  <p class="kicker"><b>The wire</b> · waiting for the first filing</p>
  <h1>Rules move. It reads them first.</h1>
  <p class="dek">Every morning the agent re-reads the official immigration pages it holds. When one
  changes a rule, it writes it up here, with who it is for and a report that shows its working.</p>
  <p class="stamp">Nothing has been filed yet.</p></div>'''
    r = a.get("report") or {}
    groups = a.get("who_for") or []
    def _conds(g: dict[str, Any]) -> str:
        cs = (g.get("conditions") or [])[:3]
        return ("<br><small>" + " · ".join(_e(c.get("text")) for c in cs) + "</small>") if cs else ""

    items = "".join(f"<li><b>{_e(g.get('group'))}</b>{(' ' + _e(g.get('why'))) if g.get('why') else ''}"
                    f"{_conds(g)}</li>" for g in groups[:4])
    more = (f"All {len(groups)} groups, with the quotes" if len(groups) > 4 else "Read it, with the quotes")
    return f'''<div class="lead">
  <p class="kicker"><b>{_e(_country(a.get("jurisdiction", "")))}</b> · {_e(a.get("lane", ""))} · filed by the agent</p>
  <h1><a href="/articles/{_e(a["slug"])}">{_e(a.get("headline"))}</a></h1>
  <p class="dek">{_e(a.get("dek"))}</p>
  <h2>Who this is for</h2>
  <ul>{items}</ul>
  <a class="more" href="/articles/{_e(a["slug"])}">{more}</a>
  <p class="stamp">From {len(r.get("sources") or [])} official {"page" if len(r.get("sources") or []) == 1 else "pages"}. {r.get("quotes_kept", 0)} of
  {r.get("quotes_checked", 0)} claims found word for word on the page; the rest were dropped.
  <a href="/articles/{_e(a["slug"])}#report">Report</a></p>
</div>'''


def _second(articles: list[dict[str, Any]]) -> str:
    if not articles:
        return '''<div class="second"><h3>More filings</h3>
  <div class="story"><p>The next rule change the agent catches lands here.</p></div></div>'''
    stories = "".join(f'''<div class="story">
  <p class="kicker"><b>{_e(_country(a.get("jurisdiction", "")))}</b> · {_e(a.get("lane", ""))}</p>
  <h4><a href="/articles/{_e(a["slug"])}">{_e(a.get("headline"))}</a></h4>
  <p>{_e(a.get("dek"))}</p>
  <p class="for">For: {_e("; ".join(g.get("group", "") for g in (a.get("who_for") or [])[:2]))}</p>
</div>''' for a in articles)
    return f'<div class="second"><h3>More filings <a href="/articles">all</a></h3>{stories}</div>'


def weight(a: dict[str, Any]) -> int:
    """How much an article tells its readers: groups, and the conditions on each."""
    groups = a.get("who_for") or []
    return len(groups) * 2 + sum(len(g.get("conditions") or []) for g in groups) + len(a.get("dates") or [])


def lead_first(articles: list[dict[str, Any]], days: int = 3) -> list[dict[str, Any]]:
    """The strongest of the last few days' filings leads; the rest keep date order.

    A paper leads with its biggest story, not its latest. An article whose page
    says almost nothing about who it touches is still filed, just not on top.
    """
    if not articles:
        return []
    newest = max(a.get("observed_on", "") for a in articles)
    from datetime import date, timedelta

    try:
        floor = (date.fromisoformat(newest) - timedelta(days=days)).isoformat()
    except ValueError:
        floor = ""
    recent = [a for a in articles if a.get("observed_on", "") >= floor]
    lead = max(recent, key=lambda a: (weight(a), a.get("observed_on", "")))
    return [lead] + [a for a in articles if a is not lead]


def landing_html(stats: dict[str, Any], articles: list[dict[str, Any]] | None = None) -> str:
    """The front page of the wire. `stats` is app._source_stats(): rows per country and totals."""
    articles = lead_first(articles or [])
    t = stats["totals"]
    reads = "".join(
        f'<div class="place"><b>{_e(r["name"])}</b><span>{r["pages"]:,} official pages'
        f'{" · read every morning" if r["daily"] else " · on file"}</span>'
        f'<span>{r["rules"]:,} rule changes caught · {r["articles"]:,} articles</span></div>'
        for r in stats["rows"] if r["pages"])

    return f'''<!doctype html>
<html lang="en" data-theme="newsroom"><head>{HEAD}
<title>MIGRAGENT, the immigration wire</title>
<meta name="description" content="An AI agent reads official immigration pages every morning and writes
up every rule change: what changed, exactly who it is for, and a report showing its working.">
<meta name="theme-color" content="#F6F3EC">
<style>{CSS}</style></head>
<body>
{MASTHEAD}
<div class="page">
  <div class="front">
    {_lead(articles[0] if articles else None)}
    {_second(articles[1:5])}
    {DESK}
  </div>

  <div class="band">
    <div><b>{t["pages"]:,}</b><span>official pages on file</span></div>
    <div><b>{t["daily"]}</b><span>countries read every morning</span></div>
    <div><b>{t["rules"]:,}</b><span>rule changes caught</span></div>
    <div><b>{t["articles"]:,}</b><span>articles filed</span></div>
  </div>

  <section>
    <p class="kicker"><b>How it reports</b> · an agent, on a beat</p>
    <h2>Rules move without warning. It reads them first.</h2>
    <p class="lede">Immigration rules change on a Tuesday afternoon with no announcement: a salary floor, a
    fee, a list of approved schools. MIGRAGENT is an AI reporter on that beat. Every morning it goes back to the
    official pages it holds, notices what moved, and writes it up.</p>
    <div class="cols">
      <div><em>It reads</em><b>Official pages only</b><p>Government sites, straight from the source. No blogs,
      no forums, no other reporters. <a href="/sources">Every page it reads</a>.</p></div>
      <div><em>It notices</em><b>What actually changed</b><p>A page that didn't move costs nothing and says
      nothing. When one does move, the agent works out whether the rules changed or just the wording.</p></div>
      <div><em>It writes</em><b>Who it's for, exactly</b><p>The route, the occupation, the salary floor, the
      level of study. Every condition the page sets, each with the sentence it came from.</p></div>
    </div>
    <div class="row"><a class="cta" href="/articles">Read the wire</a>
      <a class="cta ghost" href="/rounds">The log</a></div>
  </section>

  <section>
    <h2>How a line gets printed</h2>
    <p class="lede">The agent can propose anything. It can only print what an official page says. Every claim in
    every article has to carry a quote, and the quote is looked up on the page in code before anything goes out.
    A claim whose quote isn't there gets dropped, and the article's report lists it with the reason.</p>
    <div class="print">
      <p><code>kept</code> Care workers must be sponsored by a registered care home. The quote is on the page.</p>
      <p><code class="out">dropped</code> A line about which nationalities get priority. The page never says it,
      so it never reaches you.</p>
      <p>That second kind is why the reports exist. Open any article and scroll to the bottom.</p>
    </div>
  </section>

  <section>
    <h2>Where it reads</h2>
    <p class="lede">{t["pages"]:,} official pages in {t["countries"]} countries. Some sites tell crawlers to keep
    out, and the agent does; what it can't crawl, the desk files by hand, and those articles say so.</p>
    <div class="places">{reads}</div>
    <p style="margin-top:18px"><a class="cta ghost" href="/sources">Every page, by country</a></p>
  </section>

  <section>
    <h2>Paid for by $MIGRA</h2>
    <div class="two">
      <div><b>The agent pays its own way</b><p>$MIGRA's trading fees become AI balance on Orbio, and that
      balance pays for the morning reading and the writing. The log shows what it spent today.</p></div>
      <div><b>And never stops</b><p>When the balance runs dry the agent falls back to Google Cloud and carries
      on. The wire doesn't wait for the market. <a href="/migra">How $MIGRA works</a>.</p></div>
    </div>
  </section>

  <footer>MIGRAGENT is an AI agent that reads official government pages and reports what changed. It is not a
  law firm and does not give immigration advice; the official page is always the authority.
  <a href="/sources">Sources</a> · <a href="/rounds">The log</a> · <a href="/architecture">How it works</a> ·
  <a href="/data">Data</a> · <a href="/migra">$MIGRA</a></footer>
</div>
</body></html>'''
