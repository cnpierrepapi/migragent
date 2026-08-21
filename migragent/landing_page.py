"""The landing page: what this is, for somebody who has never heard of it.

WHAT THIS PAGE IS ABOUT, HAVING GOT IT WRONG TWICE
--------------------------------------------------
It is not about sources. Sources are how the product keeps its promise, not the
promise. The promise is that somebody who wants to move, study or work in another
country can stop guessing: an agent goes and reads the official rules every day
and hands them what they actually need to do, in order, with what it costs and
what changed.

The first version of this page led with "nothing is stated without a source",
which is a sentence about our internal discipline. A person deciding whether to
move to Canada does not arrive caring about our discipline. They arrive wanting
to know if they can go, what it takes, and whether the thing they read last month
is still true.

It also has to look like what it is. The earlier art direction was a table, some
paper and a plant: calm, well lit, and it could have been an accounting product.
Nothing on the page said anybody was leaving anywhere.

THE FORM IS NOT HERE
--------------------
This page sells; `/start` does the work. Every call to action points there.

LIGHT, DELIBERATELY
-------------------
An earlier hero filled four fifths of the first screen with a dark scrim over a
video, and the page read as dark mode whether or not the theme said so. The photo
sits beside the words now rather than under them, so the first screen is the
colour of the paper it is printed on.
"""
from __future__ import annotations

import html
from typing import Any

from .intake_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


def _picture(stem: str, alt: str, ratio: str = "4 / 3", lazy: bool = True) -> str:
    """One image, at the two widths that exist.

    Both files are always written by tools/prepare_images.py, including when the
    source is smaller than the larger label, because a srcset that names a file
    which is not there shows nothing at all. That is how the first version of
    this page shipped with a broken image on every large screen.
    """
    base = f"/brand/images/web/{stem}"
    return (f'<img class="shot" style="aspect-ratio:{ratio}" src="{base}-800.webp" '
            f'srcset="{base}-800.webp 800w, {base}-1600.webp 1600w" '
            f'sizes="(max-width: 900px) 100vw, 620px" alt="{_e(alt)}" '
            f'{"loading=\"lazy\" " if lazy else ""}decoding="async">')


CSS = '''
  * { box-sizing: border-box }
  body { margin: 0; background: var(--paper); color: var(--ink);
         font-family: var(--font-body) }
  a { color: inherit }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px }

  .top { display: flex; align-items: center; justify-content: space-between;
         padding: 20px 0 8px }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary) }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.16rem; color: var(--ink) }

  .cta { display: inline-flex; align-items: center; gap: 8px; padding: 12px 22px;
         border-radius: var(--radius); background: var(--primary); color: #fff;
         text-decoration: none; font: 600 .95rem var(--font-body); border: 0; cursor: pointer }
  .cta.small { padding: 9px 16px; font-size: .88rem }
  .cta.ghost { background: transparent; color: var(--ink); border: 1px solid var(--rule) }
  .cta:hover { background: var(--primary-hot) }

  .hero { display: grid; grid-template-columns: 1.05fr 1fr; gap: 46px; align-items: center;
          padding: 40px 0 56px }
  .hero h1 { font-family: var(--font-display); font-size: clamp(2.2rem, 4.6vw, 3.5rem);
             line-height: 1.04; margin: 0 0 18px; letter-spacing: var(--display-tracking);
             text-wrap: balance }
  .hero p { font-size: 1.1rem; line-height: 1.62; color: var(--ink-soft); margin: 0 0 26px;
            max-width: 46ch }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center }
  .under { font-family: var(--font-mono); font-size: .74rem; color: var(--ink-soft);
           margin-top: 16px }

  .shot { display: block; width: 100%; object-fit: cover; border-radius: var(--radius);
          background: var(--rule) }

  .figures { position: relative }
  .figures .shot { box-shadow: var(--shadow) }

  .strip { border-block: 1px solid var(--rule); background: var(--paper-raised) }
  .strip .wrap { display: flex; gap: 34px; flex-wrap: wrap; justify-content: space-between;
                 padding-block: 18px }
  .stat b { font-family: var(--font-display); font-size: 1.5rem; display: block;
            font-variant-numeric: tabular-nums; line-height: 1.1 }
  .stat span { font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }

  section { padding: 62px 0 }
  h2 { font-family: var(--font-display); font-size: clamp(1.5rem, 3vw, 2.1rem); margin: 0 0 10px;
       line-height: 1.12 }
  .lede { color: var(--ink-soft); line-height: 1.6; margin: 0 0 30px; max-width: 60ch }

  .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px }
  .step .shot { aspect-ratio: 4 / 3; margin-bottom: 14px }
  .step b { display: block; font: 600 1.02rem var(--font-body); margin-bottom: 6px }
  .step p { margin: 0; color: var(--ink-soft); line-height: 1.55; font-size: .95rem }
  .step em { font-style: normal; font-family: var(--font-mono); font-size: .7rem;
             color: var(--primary); display: block; margin-bottom: 8px }

  .places { display: flex; gap: 10px; flex-wrap: wrap }
  .place { border: 1px solid var(--rule); border-radius: var(--radius-sm);
           background: var(--paper-raised); padding: 13px 16px; min-width: 168px }
  .place b { display: block; font-weight: 600 }
  .place span { font-family: var(--font-mono); font-size: .71rem; color: var(--ink-soft) }
  .place.soon { opacity: .55 }

  .end { text-align: center; padding: 76px 0 92px; border-top: 1px solid var(--rule) }
  .end h2 { margin-bottom: 14px }
  .end .lede { margin: 0 auto 26px }

  footer { border-top: 1px solid var(--rule); padding: 24px 0 40px;
           font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }
  footer a { color: var(--link) }

  @media (prefers-reduced-motion: reduce) { .figures video { display: none } }
  @media (max-width: 900px) {
    .hero { grid-template-columns: 1fr; gap: 30px; padding-top: 24px }
    .steps { grid-template-columns: 1fr }
  }
'''

# The one piece of motion on the page, and it shows the product refusing
# something rather than producing something. Every other entry will show a thing
# being generated; almost none will show a thing being rejected.
REFUSAL = '''
  .refuse { background: var(--paper-raised); border: 1px solid var(--rule);
            border-radius: var(--radius); padding: 26px 26px 22px; max-width: 660px }
  .refuse .line { display: flex; gap: 12px; align-items: flex-start; padding: 12px 0;
                  border-bottom: 1px solid var(--rule); font-size: .97rem; line-height: 1.5 }
  .refuse .line:last-child { border-bottom: 0 }
  .refuse .mark { flex: 0 0 auto; width: 20px; height: 20px; margin-top: 2px }
  .refuse .kept .mark circle { fill: rgba(22,70,125,.10); stroke: var(--primary) }
  .refuse .cut .mark circle { fill: rgba(166,58,34,.10); stroke: var(--warn) }
  .refuse q { display: block; font-family: var(--font-mono); font-size: .74rem;
              color: var(--ink-soft); margin-top: 5px; quotes: none }
  .refuse .cut .txt { position: relative; color: var(--ink-soft) }
  .refuse .cut .txt::after { content: ""; position: absolute; left: 0; top: .62em; height: 1.5px;
                             background: var(--warn); width: 0;
                             animation: strike 5.5s var(--ease) infinite }
  .refuse .why { font-family: var(--font-mono); font-size: .72rem; color: var(--warn);
                 opacity: 0; animation: showwhy 5.5s var(--ease) infinite; margin-top: 6px }
  @keyframes strike { 0%,42% { width: 0 } 58%,100% { width: 100% } }
  @keyframes showwhy { 0%,56% { opacity: 0 } 70%,100% { opacity: 1 } }
  @media (prefers-reduced-motion: reduce) {
    .refuse .cut .txt::after { animation: none; width: 100% }
    .refuse .why { animation: none; opacity: 1 }
  }
'''

TICK = ('<svg class="mark" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="9" '
        'stroke-width="1.5"/><path d="M6 10.4l2.6 2.6L14 7.6" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
CROSS = ('<svg class="mark" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="9" '
         'stroke-width="1.5"/><path d="M7 7l6 6M13 7l-6 6" fill="none" stroke="currentColor" '
         'stroke-width="1.8" stroke-linecap="round"/></svg>')


def landing_html(live: int, sources: int, lanes_open: int,
                 places: list[tuple[str, str, bool]]) -> str:
    """`places` is (name, note, offered), so the page never invents coverage."""
    place_cards = "".join(
        f'<div class="place{"" if offered else " soon"}"><b>{_e(name)}</b>'
        f'<span>{_e(note)}</span></div>'
        for name, note, offered in places)

    return f'''<!doctype html>
<html lang="en" data-theme="light"><head>{HEAD}
<title>MIGRAGENT: everything you need to move, kept current</title>
<meta name="description" content="An agent reads the official immigration rules every day and
tells you what you need to study or work abroad: the steps, the documents, the cost, and what
changed.">
<style>{CSS}{REFUSAL}</style></head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
      <a class="cta small" href="/start">Start free</a>
    </div>

    <div class="hero">
      <div>
        <h1>Everything you need to move, kept current.</h1>
        <p>Studying or working in another country means a hundred rules that change without
        telling you. An agent reads the official pages every day and gives you the steps, the
        documents, the money and the deadlines for your case.</p>
        <div class="row">
          <a class="cta" href="/start">Start free</a>
          <a class="cta ghost" href="#how">See how it works</a>
        </div>
        <p class="under">No account needed. Nothing you upload is kept.</p>
      </div>
      <div class="figures">
        <video class="shot" style="aspect-ratio:5 / 4" autoplay muted loop playsinline
               preload="metadata" poster="/brand/images/web/01-departure-hall-morning-800.webp"
               aria-label="A traveller crossing a bright airport departure hall">
          <!-- mp4 first, deliberately. VP9 came out larger than h264 on this
               clip, and a browser takes the first source it can play, so
               listing webm first was handing most people the heavier file. -->
          <source src="/brand/video/hero.mp4" type="video/mp4">
          <source src="/brand/video/hero.webm" type="video/webm">
        </video>
        <noscript>{_picture("01-departure-hall-morning",
                  "A traveller crossing a bright airport departure hall", "5 / 4", lazy=False)}</noscript>
      </div>
    </div>
  </div>

  <div class="strip"><div class="wrap">
    <div class="stat"><b>{live:,}</b><span>requirements read from official pages</span></div>
    <div class="stat"><b>{sources:,}</b><span>government pages watched</span></div>
    <div class="stat"><b>{lanes_open}</b><span>routes you can take today</span></div>
    <div class="stat"><b>Daily</b><span>re-read, so it does not go stale</span></div>
  </div></div>

  <div class="wrap">
    <section id="how">
      <h2>It does the reading. You do the deciding.</h2>
      <p class="lede">Three steps, and the middle one is the part nobody has time for.</p>
      <div class="steps">
        <div class="step">
          {_picture("03-folder-and-hands", "Hands holding a folder of papers while waiting")}
          <em>Step one</em>
          <b>Say what you want</b>
          <p>Where you are going and whether it is study or work. Add whatever paperwork you
          already have, or none at all.</p>
        </div>
        <div class="step">
          {_picture("06-consulate-waiting-daylight", "A calm official waiting area in daylight")}
          <em>Step two</em>
          <b>The agent reads the rules</b>
          <p>It goes to the government's own pages, reads them, and re-reads them every day so a
          change in the fee or the salary floor reaches you rather than surprising you.</p>
        </div>
        <div class="step">
          {_picture("07-keys-new-flat", "A hand setting keys down in an empty sunlit flat")}
          <em>Step three</em>
          <b>Get your plan</b>
          <p>The steps in order, the documents you still need, what it costs, and jobs that match
          what you can actually do.</p>
        </div>
      </div>
    </section>

    <section>
      <h2>It would rather tell you nothing than tell you wrong.</h2>
      <p class="lede">Every line it gives you carries the sentence it came from, on the
      government's own page, with the date it was read. Anything it cannot show you a sentence
      for is thrown away before you ever see it.</p>
      <div class="refuse">
        <div class="line kept">{TICK}<div><span class="txt">You must have a confirmed job offer
          before you apply.</span>
          <q>"You must have a confirmed job offer before you apply for your visa."</q></div></div>
        <div class="line kept">{TICK}<div><span class="txt">You must be paid at least
          &pound;41,700 a year, or the going rate for the job.</span>
          <q>"the 'standard' salary rate of at least &pound;41,700 per year"</q></div></div>
        <div class="line cut">{CROSS}<div><span class="txt">You must provide six months of bank
          statements.</span>
          <div class="why">Refused: no sentence on the page says this.</div></div></div>
      </div>
    </section>

    <section>
      <h2>Where you can go today</h2>
      <p class="lede">Each place says how much has actually been read for it. Where that number
      is small, it says so, rather than pretending.</p>
      <div class="places">{place_cards}</div>
    </section>
  </div>

  <div class="wrap end">
    <h2>Find out what it would take.</h2>
    <p class="lede">Two questions, and you can stop there. No account, no card.</p>
    <a class="cta" href="/start">Start free</a>
  </div>

  <div class="wrap"><footer>
    MIGRAGENT reads official government pages and cites them.
    It is not a law firm and does not give immigration advice.
    <a href="/data">What happens to your documents</a>
  </footer></div>
</body></html>'''
