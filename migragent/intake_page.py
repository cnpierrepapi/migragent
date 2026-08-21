"""The only form a person fills in, and the screen that shows the agent working.

WHAT CHANGED AND WHY
--------------------
The first version made somebody pick a jurisdiction and a lane off a list of
fourteen rows labelled ready, watched and uncovered. That is our filing system,
not their question. Nobody arrives thinking "CA study"; they arrive thinking "I
want to do a master's in Canada".

So the choices are the question in their words, the lane is derived behind them,
and coverage shows up only where it changes what they can expect.

THE WORKING SCREEN
------------------
Then they watch it work. Every line on that screen is a real step that really
happened, streamed as it completes, with the count it actually produced.

Nothing on it is a timed animation pretending to be progress. That matters more
here than anywhere else in the product: a fake progress bar in front of a person
about to trust a guide with their savings is the same lie as an invented
citation, told in a different medium. If a step takes four seconds the line sits
there for four seconds.
"""
from __future__ import annotations

import html
from typing import Any

from .registry import JURISDICTIONS


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


HEAD = '''<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/brand/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/brand/tokens.css">'''

LOGO = ('<svg viewBox="0 0 64 64"><path d="M10 36 V8 L32 28 L54 8 V36" fill="none" '
        'stroke="currentColor" stroke-width="9" stroke-linecap="round" '
        'stroke-linejoin="round"/><path d="M19 50 Q32 61 45 50" fill="none" '
        'stroke="currentColor" stroke-width="7.5" stroke-linecap="round"/></svg>')

HERO_CSS = '''
  .hero { position: relative; min-height: min(78vh, 620px); display: grid; align-items: end;
          overflow: hidden; background: var(--ink) }
  .hero video, .hero img.bg { position: absolute; inset: 0; width: 100%; height: 100%;
                              object-fit: cover; z-index: 0 }
  /* The scrim exists for contrast, not for mood: white display type over a sunlit
     table fails every contrast check without it. Warm rather than black, so the
     daylight in the picture survives. */
  .hero::after { content: ""; position: absolute; inset: 0; z-index: 1;
                 background: linear-gradient(178deg, rgba(20,14,6,.10) 0%,
                             rgba(20,14,6,.34) 46%, rgba(20,14,6,.72) 100%) }
  .hero-in { position: relative; z-index: 2; max-width: 720px; margin: 0 auto;
             padding: 0 24px 46px; width: 100% }
  .hero h1 { color: #fff; font-size: clamp(2.1rem, 6vw, 3.4rem); line-height: 1.03;
             margin: 0 0 14px; text-wrap: balance }
  .hero p { color: rgba(255,255,255,.92); font-size: 1.06rem; line-height: 1.6;
            margin: 0 0 22px; max-width: 52ch }
  .hero .brand { color: #fff; margin: 0 0 auto; padding-top: 26px }
  .hero .brand span { color: #fff }
  .hero-top { position: absolute; inset: 0 0 auto 0; z-index: 2; max-width: 720px;
              margin: 0 auto; padding: 0 24px; width: 100% }
  .jump { display: inline-flex; align-items: center; gap: 9px; padding: 13px 24px;
          border-radius: var(--radius); background: var(--accent); color: #20160A;
          text-decoration: none; font: 600 .97rem var(--font-body) }
  .band { max-width: 720px; margin: 0 auto; padding: 0 24px }
  .figure { margin: 40px 0 34px; border-radius: var(--radius); overflow: hidden;
            background: var(--paper-raised); border: 1px solid var(--rule) }
  .figure img { display: block; width: 100%; height: clamp(150px, 26vw, 240px);
                object-fit: cover }
  .figure figcaption { padding: 12px 16px; font-family: var(--font-mono); font-size: .73rem;
                       color: var(--ink-soft) }
  @media (prefers-reduced-motion: reduce) { .hero video { display: none } }
'''


SHARED_CSS = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 0 0 96px }
  .wrap { padding: 0 24px }
  main { max-width: 720px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary); margin-bottom: 34px }
  .brand svg { width: 28px; height: 28px }
  .brand span { font-family: var(--font-display); font-size: 1.25rem; color: var(--ink) }
  h1 { font-size: clamp(1.9rem, 5vw, 2.7rem); margin: 0 0 12px; line-height: 1.08 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 8px }
  fieldset { border: 0; padding: 0; margin: 0 0 34px }
  legend { font: 600 1.05rem var(--font-body); color: var(--ink); margin-bottom: 12px; padding: 0 }
  .choices { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)) }
  .choice { position: relative }
  .choice input { position: absolute; opacity: 0; inset: 0; cursor: pointer }
  .choice span { display: block; padding: 15px 17px; border: 1px solid var(--rule);
                 border-radius: var(--radius); background: var(--paper-raised);
                 cursor: pointer; transition: border-color var(--motion-fast) var(--ease) }
  .choice input:checked + span { border-color: var(--primary); box-shadow: var(--ring) }
  .choice input:disabled + span { opacity: .5; cursor: not-allowed }
  .choice b { display: block; font-weight: 600 }
  .choice em { font-style: normal; font-family: var(--font-mono); font-size: .7rem;
               color: var(--ink-soft); display: block; margin-top: 3px }
  /* Thin is a warning and not a refusal, so it is marked and stays choosable.
     The colour is the measured warn tone, which clears contrast on paper; the
     accent never carries text. Rules 16 and 17. */
  .choice.thin em { color: var(--warn) }
  .go { padding: 15px 40px; border: 0; border-radius: var(--radius); background: var(--primary);
        color: var(--paper-raised); font: 600 1rem var(--font-body); cursor: pointer }
  .go:disabled { opacity: .45; cursor: not-allowed }
  .go:hover:enabled { background: var(--primary-hot) }
'''


def intake_html(coverage_by_lane: dict, total_sources: int, live: int = 0) -> str:
    """One page: what you want, and what you already have."""
    # A place is offered when either of its lanes can be answered, and the note
    # says how well rather than whether. "Ready" used to mean extraction had run
    # at least once, so a lane holding three requirements and a lane holding 568
    # looked identical on this screen. The number is now on the page.
    #
    # Only two things are greyed out: a place nothing has been read for, and a
    # place whose government will not tell us its crawling rules. Thin is not
    # greyed out. Somebody who wants the three requirements we can genuinely
    # source should be able to have them, knowing there are three.
    order = {"ready": 0, "thin": 1, "watched": 2, "unavailable": 3, "uncovered": 4}
    places = []
    for code, meta in JURISDICTIONS.items():
        states = [coverage_by_lane.get((code, lane), ("uncovered", ""))
                  for lane in ("study", "work")]
        best = min(states, key=lambda s: order.get(s[0], 9))
        usable = best[0] in ("ready", "thin")

        if best[0] == "ready":
            note = best[1]
        elif best[0] == "thin":
            note = best[1]
        elif best[0] == "watched":
            note = "pages found, none read yet"
        elif best[0] == "unavailable":
            note = "the government will not state its crawling rules"
        else:
            note = "no official source could be read"

        disabled = "" if usable else " disabled"
        classes = "choice" + ("" if best[0] == "ready" else f" {best[0]}")
        places.append(f'''
        <label class="{classes}">
          <input type="radio" name="place" value="{_e(code)}"{disabled} required>
          <span><b>{_e(meta["name"])}</b><em>{_e(note)}</em></span>
        </label>''')

    return f'''<!doctype html>
<html lang="en" data-theme="light"><head>{HEAD}<title>MIGRAGENT</title>
<style>{HERO_CSS}{SHARED_CSS}
  .drop {{ border: 1.5px dashed var(--rule); border-radius: var(--radius); padding: 26px;
           text-align: center; background: var(--paper-raised); cursor: pointer }}
  .drop:hover, .drop.over {{ border-color: var(--primary) }}
  .drop p {{ margin: 0; color: var(--ink-soft) }}
  #files {{ margin: 12px 0 0; padding: 0; list-style: none; font-family: var(--font-mono);
            font-size: .76rem; color: var(--ink-soft) }}
  #files li {{ padding: 7px 0; border-bottom: 1px solid var(--rule) }}
  .counts {{ font-family: var(--font-mono); font-size: .76rem; color: var(--ink-soft);
             border-top: 1px solid var(--rule); margin-top: 26px; padding-top: 13px }}
</style></head>
<body>
  <header class="hero">
    <video autoplay muted loop playsinline preload="none"
           poster="/brand/video/hero.jpg" aria-hidden="true">
      <source src="/brand/video/hero.webm" type="video/webm">
      <source src="/brand/video/hero.mp4" type="video/mp4">
    </video>
    <div class="hero-top"><div class="brand">{LOGO}<span>MIGRAGENT</span></div></div>
    <div class="hero-in">
      <h1>Nothing is stated without a source.</h1>
      <p>Answer two questions, add whatever paperwork you already have, and an agent reads the
      official pages for you. What comes back is a guide with the source and the date on every
      single line, and a PDF you can keep.</p>
      <a class="jump" href="#start">Start with two questions</a>
    </div>
  </header>

<main class="band">
  <figure class="figure">
    <img src="/brand/images/web/02-sorted-stack-daylight-800.webp"
         srcset="/brand/images/web/02-sorted-stack-daylight-800.webp 800w,
                 /brand/images/web/02-sorted-stack-daylight-1600.webp 1600w"
         sizes="(max-width: 760px) 100vw, 720px" alt="" loading="lazy" width="1600" height="900">
    <figcaption>{live:,} requirements read from official pages, each one carrying the sentence it
    came from.</figcaption>
  </figure>

  <form id="f" method="post" action="/begin">
    <span id="start"></span>
    <fieldset style="margin-top:36px">
      <legend>What are you trying to do?</legend>
      <div class="choices">
        <label class="choice"><input type="radio" name="lane" value="study" required>
          <span><b>Study</b><em>a course, a degree, a place at a school</em></span></label>
        <label class="choice"><input type="radio" name="lane" value="work">
          <span><b>Work</b><em>a job, a permit, being licensed to practise</em></span></label>
      </div>
    </fieldset>

    <fieldset>
      <legend>Where?</legend>
      <div class="choices">{"".join(places)}</div>
      <p class="sub" style="margin-top:10px;font-size:.88rem">The number beside a place is how
      many requirements have actually been read from official pages for it. Where that number is
      small it says so, and you can still take the guide. Greyed out means nothing could be read
      there yet, or that the government will not state its crawling rules, and we do not crawl a
      site that will not say what it allows.</p>
    </fieldset>

    <fieldset>
      <legend>What do you already have? <span style="font-weight:400;color:var(--ink-soft)">Optional</span></legend>
      <div class="drop" id="zone">
        <p>Drop files here, or click to choose. PDF, PNG, JPG or WEBP.</p>
        <input type="file" id="picker" multiple hidden accept=".pdf,.png,.jpg,.jpeg,.webp">
      </div>
      <ul id="files"></ul>
      <p class="sub" style="margin-top:10px;font-size:.88rem"><b>The files are not kept.</b> Each is
      read and discarded, and what is stored is the fields, not the document.
      <a href="/data">What happens to your documents</a>.</p>
    </fieldset>

    <button class="go" id="go" type="submit">Build my guide</button>
  </form>

  <div class="counts">{total_sources} official pages in the registry &nbsp;·&nbsp;
  nothing is stated without one</div>
</main>
<script>
  var picker = document.getElementById('picker');
  var zone = document.getElementById('zone');
  var list = document.getElementById('files');
  var form = document.getElementById('f');
  var chosen = [];

  zone.onclick = function () {{ picker.click(); }};
  zone.ondragover = function (e) {{ e.preventDefault(); zone.classList.add('over'); }};
  zone.ondragleave = function () {{ zone.classList.remove('over'); }};
  zone.ondrop = function (e) {{ e.preventDefault(); zone.classList.remove('over'); add(e.dataTransfer.files); }};
  picker.onchange = function () {{ add(picker.files); }};

  function add(files) {{
    for (var i = 0; i < files.length; i++) chosen.push(files[i]);
    list.innerHTML = '';
    chosen.forEach(function (f) {{
      var li = document.createElement('li');
      li.textContent = f.name + '  ·  ' + Math.round(f.size / 1024) + ' KB';
      list.appendChild(li);
    }});
  }}

  form.onsubmit = function (e) {{
    e.preventDefault();
    var go = document.getElementById('go');
    go.disabled = true; go.textContent = 'Starting ...';
    var body = new FormData(form);
    chosen.forEach(function (f) {{ body.append('file', f); }});
    fetch('/begin', {{ method: 'POST', body: body }})
      .then(function (r) {{ return r.json(); }})
      .then(function (j) {{
        if (j.error) {{ go.disabled = false; go.textContent = 'Build my guide'; alert(j.error); return; }}
        location.href = '/working';
      }});
  }};
</script>
</body></html>
'''


def working_html(case, file_count: int) -> str:
    """The agent at work. Every line is a step that really ran."""
    return f'''<!doctype html>
<html lang="en" data-theme="light"><head>{HEAD}<title>Working</title>
<style>{SHARED_CSS}
  .steps {{ list-style: none; margin: 26px 0 0; padding: 0 }}
  .steps li {{ display: grid; grid-template-columns: 22px 1fr auto; gap: 12px; align-items: start;
               padding: 13px 0; border-bottom: 1px solid var(--rule);
               opacity: 0; transform: translateY(5px); animation: land .3s var(--ease) forwards }}
  @keyframes land {{ to {{ opacity: 1; transform: none }} }}
  .tick {{ color: var(--primary); font-family: var(--font-mono); font-size: .8rem }}
  .what {{ line-height: 1.5 }}
  .what b {{ font-weight: 600 }}
  .what span {{ display: block; font-family: var(--font-mono); font-size: .72rem;
                color: var(--ink-soft); margin-top: 3px; word-break: break-all }}
  .took {{ font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft);
           font-variant-numeric: tabular-nums }}
  .counter {{ font: var(--display-wght) 3rem var(--font-display); font-variant-numeric: tabular-nums }}
  .working {{ display: flex; align-items: baseline; gap: 14px }}
  .cap {{ font-family: var(--font-mono); font-size: .78rem; color: var(--ink-soft) }}
  .done {{ margin-top: 30px; display: none }}
  @media (prefers-reduced-motion: reduce) {{ .steps li {{ animation: none; opacity: 1; transform: none }} }}
</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Reading the sources</h1>
  <p class="sub">Every line below is a step that actually ran, with what it actually produced.
  Nothing here is a timer pretending to be progress.</p>

  <div class="working">
    <div class="counter" id="n">0</div>
    <div class="cap">steps completed &nbsp;·&nbsp; {file_count} document{"" if file_count == 1 else "s"} to read</div>
  </div>

  <ul class="steps" id="steps"></ul>

  <div class="done" id="done">
    <a class="go" style="display:inline-block;text-decoration:none" href="/result">See my guide</a>
  </div>
</main>
<script>
  var steps = document.getElementById('steps');
  var n = document.getElementById('n');
  var count = 0;
  var source = new EventSource('/run-stream');

  source.onmessage = function (e) {{
    var d = JSON.parse(e.data);
    if (d.event === 'done') {{
      source.close();
      document.getElementById('done').style.display = 'block';
      return;
    }}
    if (d.event === 'error') {{
      var li = document.createElement('li');
      li.innerHTML = '<span class="tick">!</span><div class="what"><b>' + d.what +
                     '</b><span>' + (d.detail || '') + '</span></div><div class="took"></div>';
      steps.appendChild(li);
      return;
    }}
    count++;
    n.textContent = count;
    var li = document.createElement('li');
    li.innerHTML = '<span class="tick">' + String(count).padStart(2, '0') + '</span>' +
                   '<div class="what"><b>' + d.what + '</b>' +
                   (d.detail ? '<span>' + d.detail + '</span>' : '') + '</div>' +
                   '<div class="took">' + (d.took || '') + '</div>';
    steps.appendChild(li);
  }};
  source.onerror = function () {{ source.close(); }};
</script>
</body></html>
'''
