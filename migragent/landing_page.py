"""The landing page: what this is, for somebody who has never heard of it.

WHAT THE PRODUCT ACTUALLY IS, HAVING GOT THIS WRONG THREE TIMES
---------------------------------------------------------------
Version one led with "nothing is stated without a source". That is a sentence
about our internal discipline, and nobody arrives caring about our discipline.

Version two led with the guide. Closer, and still only half of it: a guide is a
document, and a document is a thing you read once and then have to keep checking
yourself, which is exactly the labour this is supposed to remove.

The product is an agent that keeps working after you close the tab. You tell it
who you are and where you want to go, it carves a route out of the official
rules for your case, and then it stays on watch: when a rule moves, when an
intake opens, when a job in a shortage occupation you actually qualify for is
posted, it tells you. The guide is the first thing it gives you. The alerts are
why you keep it.

So this page is ordered that way. The hero says what it does. The second beat is
the watch, because that is the part nobody else does. The evidence discipline
comes after, as the reason the alerts are worth opening, which is where it
belongs rather than at the top.

THE FORM IS NOT HERE
--------------------
This page sells; `/start` does the work. Every call to action points there.

DARK, DELIBERATELY
------------------
The tokens carry two faces and this page asks for the mature one. Note that in
dark `--primary` is a pale blue, so anything painting text on it uses
`var(--paper)` and never `#fff`, or the label disappears into its own background.
That is why this could not be the light page with one attribute changed.
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
  .wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px }

  .top { display: flex; align-items: center; justify-content: space-between;
         padding: 22px 0 8px }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary) }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.16rem; color: var(--ink);
                letter-spacing: .02em }

  /* On dark, --primary is pale. White on pale blue is unreadable, so the label
     takes the page colour instead. */
  .cta { display: inline-flex; align-items: center; gap: 8px; padding: 13px 24px;
         border-radius: var(--radius); background: var(--primary); color: var(--paper);
         text-decoration: none; font: 600 .95rem var(--font-body); border: 0; cursor: pointer;
         transition: background var(--motion-fast) var(--ease) }
  .cta.small { padding: 9px 16px; font-size: .88rem }
  .cta.ghost { background: transparent; color: var(--ink); border: 1px solid var(--rule) }
  .cta.ghost:hover { border-color: var(--primary); background: var(--paper-raised) }
  .cta:hover { background: var(--primary-hot) }

  .hero { display: grid; grid-template-columns: 1.02fr 1fr; gap: 48px; align-items: center;
          padding: 44px 0 60px }
  .kicker { font-family: var(--font-mono); font-size: .72rem; letter-spacing: .1em;
            text-transform: uppercase; color: var(--accent); margin: 0 0 16px }
  .hero h1 { font-family: var(--font-display); font-size: clamp(2.2rem, 4.7vw, 3.6rem);
             line-height: 1.05; margin: 0 0 18px; letter-spacing: var(--display-tracking);
             text-wrap: balance }
  .hero h1 em { font-style: normal; color: var(--primary) }
  .hero p { font-size: 1.09rem; line-height: 1.62; color: var(--ink-soft); margin: 0 0 26px;
            max-width: 48ch }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center }
  .under { font-family: var(--font-mono); font-size: .73rem; color: var(--ink-soft);
           margin-top: 18px }

  .shot { display: block; width: 100%; object-fit: cover; border-radius: var(--radius);
          background: var(--paper-raised) }
  /* Photographs shot in daylight sit on a near-black page like open windows. A
     hair of contrast and a border settles them into it rather than letting them
     glare out of it. */
  .figures .shot, .step .shot, .split .shot { box-shadow: var(--shadow);
          border: 1px solid var(--rule); filter: saturate(.94) contrast(1.03) }

  .strip { border-block: 1px solid var(--rule); background: var(--paper-raised) }
  .strip .wrap { display: flex; gap: 30px; flex-wrap: wrap; justify-content: space-between;
                 padding-block: 20px }
  .stat b { font-family: var(--font-display); font-size: 1.55rem; display: block;
            font-variant-numeric: tabular-nums; line-height: 1.1 }
  .stat span { font-family: var(--font-mono); font-size: .71rem; color: var(--ink-soft) }

  section { padding: 68px 0 }
  h2 { font-family: var(--font-display); font-size: clamp(1.55rem, 3vw, 2.2rem); margin: 0 0 12px;
       line-height: 1.13; text-wrap: balance }
  h2 em { font-style: normal; color: var(--primary) }
  .lede { color: var(--ink-soft); line-height: 1.62; margin: 0 0 32px; max-width: 62ch;
          font-size: 1.02rem }

  .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px }
  .step .shot { aspect-ratio: 4 / 3; margin-bottom: 15px }
  .step b { display: block; font: 600 1.03rem var(--font-body); margin-bottom: 6px }
  .step p { margin: 0; color: var(--ink-soft); line-height: 1.56; font-size: .95rem }
  .step em { font-style: normal; font-family: var(--font-mono); font-size: .69rem;
             color: var(--accent); display: block; margin-bottom: 8px; letter-spacing: .08em;
             text-transform: uppercase }

  .split { display: grid; grid-template-columns: 1fr 1fr; gap: 46px; align-items: center }
  .split .shot { aspect-ratio: 5 / 4 }

  .routes { display: grid; grid-template-columns: 1fr 1fr; gap: 22px }
  .route { border: 1px solid var(--rule); border-radius: var(--radius); overflow: hidden;
           background: var(--paper-raised) }
  .route .shot { border-radius: 0; border: 0; aspect-ratio: 16 / 9 }
  .route div { padding: 20px 22px 24px }
  .route b { display: block; font-family: var(--font-display); font-size: 1.2rem;
             margin-bottom: 7px }
  .route p { margin: 0; color: var(--ink-soft); line-height: 1.55; font-size: .95rem }

  .places { display: flex; gap: 10px; flex-wrap: wrap }
  .place { border: 1px solid var(--rule); border-radius: var(--radius-sm);
           background: var(--paper-raised); padding: 13px 16px; min-width: 172px }
  .place b { display: block; font-weight: 600 }
  .place span { font-family: var(--font-mono); font-size: .71rem; color: var(--ink-soft) }
  /* Places nothing has been read for are named in one line below the grid rather
     than given a greyed-out card each. A faded card is a promise with a shape,
     and this product does not make promises with a shape. */
  .later { font-family: var(--font-mono); font-size: .73rem; color: var(--ink-soft);
           margin-top: 16px; line-height: 1.7 }

  .end { text-align: center; padding: 80px 0 96px; border-top: 1px solid var(--rule) }
  .end h2 { margin-bottom: 14px }
  .end .lede { margin: 0 auto 28px }

  footer { border-top: 1px solid var(--rule); padding: 26px 0 44px;
           font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft);
           line-height: 1.8 }
  footer a { color: var(--link) }

  @media (prefers-reduced-motion: reduce) { .figures video { display: none } }
  @media (max-width: 900px) {
    .hero { grid-template-columns: 1fr; gap: 30px; padding-top: 26px }
    .steps, .routes { grid-template-columns: 1fr }
    .split { grid-template-columns: 1fr; gap: 28px }
    section { padding: 48px 0 }
  }
'''

# THE MOTION ON THIS PAGE
# -----------------------
# There is one animated thing and it is the alert feed, because the watch is the
# claim this page makes and a still picture of three rows does not say "these
# arrive". Rows enter on a stagger and the loop restarts, which is what the thing
# actually does: it is quiet, and then it is not.
#
# CSS and SVG only. No library, no canvas, nothing that needs JavaScript to have
# loaded before the page means anything.
FEED = '''
  .feed { border: 1px solid var(--rule); border-radius: var(--radius);
          background: var(--paper-raised); padding: 8px 20px 14px; box-shadow: var(--shadow) }
  .feed .head { display: flex; align-items: center; gap: 9px; padding: 12px 0 10px;
                border-bottom: 1px solid var(--rule); font-family: var(--font-mono);
                font-size: .71rem; color: var(--ink-soft); letter-spacing: .06em }
  .feed .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent);
               animation: pulse 2.6s var(--ease) infinite }
  @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .25 } }

  .alert { display: flex; gap: 13px; align-items: flex-start; padding: 15px 0;
           border-bottom: 1px solid var(--rule); opacity: 0;
           animation: arrive 9s var(--ease) infinite }
  .alert:last-child { border-bottom: 0 }
  .alert:nth-of-type(1) { animation-delay: .4s }
  .alert:nth-of-type(2) { animation-delay: 2.2s }
  .alert:nth-of-type(3) { animation-delay: 4.0s }
  @keyframes arrive {
    0%   { opacity: 0; transform: translateY(9px) }
    7%   { opacity: 1; transform: none }
    88%  { opacity: 1; transform: none }
    100% { opacity: 0; transform: none }
  }

  .alert .mark { flex: 0 0 auto; width: 26px; height: 26px; margin-top: 1px;
                 color: var(--primary) }
  .alert.job .mark { color: var(--accent) }
  .alert .tag { font-family: var(--font-mono); font-size: .66rem; letter-spacing: .09em;
                text-transform: uppercase; color: var(--ink-soft); display: block;
                margin-bottom: 4px }
  .alert .txt { font-size: .98rem; line-height: 1.5; display: block }
  .alert q { display: block; font-family: var(--font-mono); font-size: .73rem;
             color: var(--ink-soft); margin-top: 5px; quotes: none }

  @media (prefers-reduced-motion: reduce) {
    .alert { animation: none; opacity: 1 }
    .feed .dot { animation: none }
  }
'''

# The evidence block. It shows the product refusing something rather than
# producing something, which is the opposite of what every other entry will show.
REFUSAL = '''
  .refuse { background: var(--paper-raised); border: 1px solid var(--rule);
            border-radius: var(--radius); padding: 24px 26px 20px }
  .refuse .line { display: flex; gap: 12px; align-items: flex-start; padding: 13px 0;
                  border-bottom: 1px solid var(--rule); font-size: .97rem; line-height: 1.5 }
  .refuse .line:last-child { border-bottom: 0 }
  .refuse .mark { flex: 0 0 auto; width: 20px; height: 20px; margin-top: 2px }
  .refuse .kept .mark { color: var(--primary) }
  .refuse .cut .mark { color: var(--warn) }
  .refuse .mark circle { fill: none }
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
        'stroke="currentColor" stroke-width="1.5"/><path d="M6 10.4l2.6 2.6L14 7.6" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>')
CROSS = ('<svg class="mark" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="9" '
         'stroke="currentColor" stroke-width="1.5"/><path d="M7 7l6 6M13 7l-6 6" fill="none" '
         'stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')

# Three marks for three kinds of alert: a page that moved, a door that opened, a
# job that appeared. Drawn rather than fetched, so they cost nothing, carry no
# licence, and match the type.
MOVED = ('<svg class="mark" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
         'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         '<rect x="4" y="3" width="18" height="20" rx="2.5"/><path d="M8 9h10M8 13h10M8 17h6"/>'
         '</svg>')
OPENED = ('<svg class="mark" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
          'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          '<path d="M14 22H5V4h9"/><path d="M14 4v18"/><path d="M18 9l4 4-4 4"/>'
          '<path d="M22 13h-7"/></svg>')
POSTED = ('<svg class="mark" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
          'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          '<rect x="3" y="8" width="20" height="14" rx="2.5"/>'
          '<path d="M9 8V6a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M3 14h20"/></svg>')


def landing_html(live: int, sources: int, lanes_open: int,
                 places: list[tuple[str, str, str]],
                 openings: int = 0, waiting: int = 0) -> str:
    """`places` is (name, note, offered), so the page never invents coverage.

    `openings` is how many postings have actually been ingested. It is passed in
    rather than typed into the template, and where it is zero the stat is
    replaced instead of printing a nought beside a sentence about opportunities.
    """
    # `places` is (name, what it is open for, note). Only countries where the
    # whole path works reach this page: study needs courses to point at, work
    # needs a job board we can read. Everything else lives on /coverage, with
    # its real numbers, rather than being listed here as a promise.
    place_cards = "".join(
        f'<div class="place"><b>{_e(name)}</b>'
        f'<span>{_e(opens)}</span><span>{_e(note)}</span></div>'
        for name, opens, note in places)

    later_line = (f'<p class="later">{waiting} more countries are being read. '
                  f'A country appears here when we can take you all the way, '
                  f'not when we have started.</p>' if waiting else "")

    openings_stat = (f'<div class="stat"><b>{openings:,}</b>'
                     f'<span>live postings matched against cases</span></div>'
                     if openings else
                     '<div class="stat"><b>Daily</b>'
                     '<span>re-read, so it cannot go stale</span></div>')

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}
<title>MIGRAGENT: the agent that keeps watch on your move</title>
<meta name="description" content="Upload what you have. MIGRAGENT reads the official
immigration rules, works out which countries fit you, and tells you when a rule changes, an
intake opens, or a job you qualify for is posted.">
<meta name="theme-color" content="#080B12">
<style>{CSS}{FEED}{REFUSAL}</style></head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
      <a class="cta small" href="/start">Start free</a>
    </div>

    <div class="hero">
      <div>
        <p class="kicker">Your immigration agent</p>
        <h1>Tell it what you want. <em>It does the reading.</em></h1>
        <p>Upload what you already have. It works out which countries fit you and what each
        one takes, then keeps checking after you close the tab.</p>
        <div class="row">
          <a class="cta" href="/start">Start free</a>
          <a class="cta ghost" href="#watch">What it tells you</a>
        </div>
        <p class="under">No account. Your documents are never kept.</p>
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
    <div class="stat"><b>{sources:,}</b><span>government pages under watch</span></div>
    <div class="stat"><b>{lanes_open}</b><span>routes you can take today</span></div>
    {openings_stat}
  </div></div>

  <div class="wrap">
    <section id="watch">
      <h2>The useful part happens <em>after</em> you leave.</h2>
      <p class="lede">A checklist is a photograph. It was true the day it was written. Then the
      salary floor moves, the intake opens on a Tuesday with no announcement, and the job that
      would have carried your visa is gone in nine days. So it keeps reading while you get on
      with your life.</p>
      <div class="split">
        <div class="feed" role="img"
             aria-label="Example alerts: a salary threshold change, an intake opening, and a matching job posting">
          <div class="head"><span class="dot"></span> YOUR AGENT &middot; TODAY</div>

          <div class="alert">{MOVED}<div>
            <span class="tag">A rule moved</span>
            <span class="txt">The Skilled Worker salary floor went up. Your offer is
            &pound;900 short now.</span>
            <q>read on gov.uk this morning &middot; both versions kept</q></div></div>

          <div class="alert">{OPENED}<div>
            <span class="tag">A door opened</span>
            <span class="txt">January applications just opened at the two schools on your
            shortlist.</span>
            <q>register updated &middot; deadline in 41 days</q></div></div>

          <div class="alert job">{POSTED}<div>
            <span class="tag">A job you qualify for</span>
            <span class="txt">Three welding jobs went up. Your ticket and your skills
            already match.</span>
            <q>Job Bank &middot; employer-submitted &middot; posted yesterday</q></div></div>
        </div>
        <div>
          {_picture("08-window-seat-cloud",
                    "The view through an aeroplane window onto bright cloud")}
        </div>
      </div>
    </section>

    <section id="how">
      <h2>You do three things. It does the rest.</h2>
      <p class="lede">Nothing to search, nothing to compare, nothing to go and find. Moving
      country already turns you into a part-time researcher. That is the job we are taking
      off you.</p>
      <div class="steps">
        <div class="step">
          {_picture("03-folder-and-hands", "Hands holding a folder of papers while waiting")}
          <em>Step one</em>
          <b>Say what you want</b>
          <p>Study or work. Then drop in whatever paperwork you have. A phone photo is fine,
          and none at all is fine too.</p>
        </div>
        <div class="step">
          {_picture("06-consulate-waiting-daylight", "A calm official waiting area in daylight")}
          <em>Step two</em>
          <b>It works out your route</b>
          <p>The steps for your case, in order. Documents, money, waiting times. Every line
          carries the sentence it came from.</p>
        </div>
        <div class="step">
          {_picture("07-keys-new-flat", "A hand setting keys down in an empty sunlit flat")}
          <em>Step three</em>
          <b>It keeps watching</b>
          <p>Rules that change, intakes that open, jobs you qualify for. You hear about them
          when they happen, not when you remember to look.</p>
        </div>
      </div>
    </section>

    <section>
      <h2>Both reasons for going.</h2>
      <p class="lede">Study and work are different rulebooks with different registers and
      different deadlines. You pick. It knows which one it is reading.</p>
      <div class="routes">
        <div class="route">
          {_picture("05-campus-courtyard-daylight",
                    "A university courtyard in bright daylight", "16 / 9")}
          <div>
            <b>To study</b>
            <p>What the visa needs, what money you have to show, and which schools the
            government's own register says can actually take you. Plus a nudge when the next
            intake opens.</p>
          </div>
        </div>
        <div class="route">
          {_picture("04-new-city-street-morning",
                    "A person walking a wide unfamiliar city street at dawn", "16 / 9")}
          <div>
            <b>To work</b>
            <p>The route, the salary floor, the sponsorship rules. Then real postings in
            occupations that country has said out loud it is short of, matched against what
            you can prove you can do.</p>
          </div>
        </div>
      </div>
    </section>

    <section>
      <h2>It would rather say nothing than say something wrong.</h2>
      <p class="lede">Every line carries the sentence it came from, on the government's own
      page, with the date it was read. If it cannot show you the sentence, it throws the line
      away before you see it. That is why the alerts are worth opening.</p>
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
      <p class="lede">Two countries, all the way through. We would rather open one
      properly than list ten we cannot finish.</p>
      <div class="places">{place_cards}</div>
      {later_line}
      <p style="margin-top:22px">
        <a class="cta ghost" href="/coverage">See everything we have read</a></p>
    </section>
  </div>

  <div class="wrap end">
    <h2>Find out what it would take.</h2>
    <p class="lede">Two taps and an upload. You can stop there. No account, no card.</p>
    <a class="cta" href="/start">Start free</a>
  </div>

  <div class="wrap"><footer>
    MIGRAGENT reads official government pages and cites them.
    It is not a law firm and does not give immigration advice.
    <a href="/data">What happens to your documents</a> &middot;
    <a href="/architecture">How it is built</a> &middot;
    <a href="/rounds">What the reading job did</a>
  </footer></div>
</body></html>'''
