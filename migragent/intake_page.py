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

There is now an estimated wait on the screen, and it is not that. The difference
is the claim being made. A progress bar says a measured fraction of the work is
finished, and when the fraction is invented the claim is false. An estimate says
"about three minutes", which is a statement about expectation, is labelled as
one, is computed from what runs have really taken, and is ended by the real
completion event rather than by its own clock. It also never sits at zero while
work continues: when it runs out it says it has run out. See migragent/timing.py.
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
<html lang="en" data-theme="dark"><head>{HEAD}<title>MIGRAGENT</title>
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
<body><main class="band">
  <div class="brand" style="padding-top:34px">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Two questions, and we start reading.</h1>
  <p class="sub">Tell us where you are going and whether it is study or work. Add whatever
  paperwork you already have, or none at all. <a href="/">What this is</a>.</p>

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


def working_html(case, file_count: int, estimate=None) -> str:
    """The agent at work. Every line is a step that really ran.

    THE COUNTDOWN, AND WHY IT IS NOT THE THING THIS SCREEN BANS
    -----------------------------------------------------------
    This page has always refused a progress bar, because a bar that fills on a
    schedule claims a measured fraction of the work is done, and an invented
    fraction is an invented citation in a different medium. That still holds and
    the bar is still not here.

    What is here is an estimated wait, which is a different sentence. It says
    "about three minutes", not "62% complete". It is computed from what runs have
    really taken (migragent/timing.py), it is deliberately padded so it leans
    long, and the real `done` event ends it the instant the work finishes
    whatever the clock says.

    It never sits at 0:00 while the work continues. That is the dishonest
    version: a countdown that has run out and is still counting is claiming
    something it cannot know. When it runs out it says so and stops.
    """
    seconds = int(round(getattr(estimate, "seconds", 0) or 0))
    basis = getattr(estimate, "basis", "") or ""
    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Working</title>
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
  .eta {{ display: flex; gap: 18px; align-items: baseline; flex-wrap: wrap;
           border: 1px solid var(--rule); background: var(--paper-raised);
           border-radius: var(--radius); padding: 15px 18px; margin-top: 22px }}
  .eta .left {{ display: flex; align-items: baseline; gap: 9px; flex: 0 0 auto }}
  .eta b {{ font-family: var(--font-mono); font-size: 1.5rem; font-variant-numeric: tabular-nums;
            color: var(--ink); line-height: 1 }}
  .eta span {{ font-family: var(--font-mono); font-size: .71rem; color: var(--ink-soft) }}
  .eta p {{ margin: 0; flex: 1 1 260px; font-family: var(--font-mono); font-size: .71rem;
            color: var(--ink-soft); line-height: 1.65 }}
  .eta.over b, .eta.over span {{ color: var(--warn) }}
  .eta.ready b, .eta.ready span {{ color: var(--primary) }}
  .done {{ margin-top: 30px; display: none }}
  @media (prefers-reduced-motion: reduce) {{ .steps li {{ animation: none; opacity: 1; transform: none }} }}
</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Reading the sources</h1>
  <p class="sub">Every line below is a step that actually ran, with what it actually produced.
  The clock is an estimate of how long to wait, not a measure of how much is done.</p>

  <div class="working">
    <div class="counter" id="n">0</div>
    <div class="cap">steps completed &nbsp;·&nbsp; {file_count} {"file" if file_count == 1 else "files"} to read</div>
  </div>

  <div class="eta" id="eta" data-seconds="{seconds}">
    <div class="left"><b id="clock">{"—" if not seconds else f"{seconds // 60}:{seconds % 60:02d}"}</b>
      <span id="etalabel">estimated wait</span></div>
    <p id="etawhy">{_e(basis)}. It leans long on purpose, and the moment the work
    is finished this stops, whatever it says.</p>
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

  // The estimated wait. It counts down, it never counts past zero, and the real
  // 'done' event stops it wherever it happens to be. See working_html's
  // docstring for why this is not the progress bar this screen refuses.
  var eta = document.getElementById('eta');
  var clock = document.getElementById('clock');
  var etaLabel = document.getElementById('etalabel');
  var etaWhy = document.getElementById('etawhy');
  var left = parseInt(eta.getAttribute('data-seconds'), 10) || 0;
  var ticking = left > 0;

  function paint(secs) {{
    var m = Math.floor(secs / 60), s = secs % 60;
    clock.textContent = m + ':' + (s < 10 ? '0' : '') + s;
  }}

  var timer = ticking && setInterval(function () {{
    left -= 1;
    if (left > 0) {{ paint(left); return; }}
    // Out of time and still working. Say that, rather than sitting at 0:00
    // pretending the estimate still means something.
    clearInterval(timer);
    ticking = false;
    eta.classList.add('over');
    clock.textContent = '—';
    etaLabel.textContent = 'longer than usual';
    etaWhy.textContent = 'This is taking longer than runs like yours normally do. '
      + 'It is still going: every step below is real and they are still arriving.';
  }}, 1000);

  function resolve() {{
    if (timer) clearInterval(timer);
    eta.classList.remove('over');
    eta.classList.add('ready');
    clock.textContent = 'Done';
    etaLabel.textContent = '';
    etaWhy.textContent = 'Finished. The estimate above was an estimate; this is the real thing.';
  }}

  // Built as nodes with textContent rather than assembled as a string of HTML.
  // One of these lines is "Read <the name of the file you uploaded>", and the
  // file name is somebody else's text. Through innerHTML a file called
  // <img src=x onerror=...>.pdf ran on this page. Only on the page of the
  // person who uploaded it, which is the small version of the problem, and it
  // is still the model's own output going into a markup parser on a screen
  // whose whole argument is that nothing here is taken on trust.
  function line(tick, what, detail, took) {{
    var li = document.createElement('li');

    var t = document.createElement('span');
    t.className = 'tick';
    t.textContent = tick;

    var w = document.createElement('div');
    w.className = 'what';
    var b = document.createElement('b');
    b.textContent = what || '';
    w.appendChild(b);
    if (detail) {{
      var d2 = document.createElement('span');
      d2.textContent = detail;
      w.appendChild(d2);
    }}

    var k = document.createElement('div');
    k.className = 'took';
    k.textContent = took || '';

    li.appendChild(t);
    li.appendChild(w);
    li.appendChild(k);
    return li;
  }}

  source.onmessage = function (e) {{
    var d = JSON.parse(e.data);
    if (d.event === 'done') {{
      source.close();
      resolve();
      document.getElementById('done').style.display = 'block';
      return;
    }}
    if (d.event === 'error') {{
      steps.appendChild(line('!', d.what, d.detail || '', ''));
      return;
    }}
    count++;
    n.textContent = count;
    steps.appendChild(line(String(count).padStart(2, '0'), d.what, d.detail || '', d.took || ''));
  }};
  source.onerror = function () {{ source.close(); }};
</script>
</body></html>
'''
