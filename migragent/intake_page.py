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

SHARED_CSS = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 52px 24px 96px }
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
  .go { padding: 15px 40px; border: 0; border-radius: var(--radius); background: var(--primary);
        color: var(--paper-raised); font: 600 1rem var(--font-body); cursor: pointer }
  .go:disabled { opacity: .45; cursor: not-allowed }
  .go:hover:enabled { background: var(--primary-hot) }
'''


def intake_html(coverage_by_lane: dict, total_sources: int) -> str:
    """One page: what you want, and what you already have."""
    places = []
    for code, meta in JURISDICTIONS.items():
        states = {lane: coverage_by_lane.get((code, lane), ("uncovered", "")) for lane in ("study", "work")}
        any_ready = any(s[0] == "ready" for s in states.values())
        note = ("ready" if any_ready else
                "watched, not read yet" if any(s[0] == "watched" for s in states.values())
                else "not covered yet")
        disabled = "" if any_ready else " disabled"
        places.append(f'''
        <label class="choice">
          <input type="radio" name="place" value="{_e(code)}"{disabled} required>
          <span><b>{_e(meta["name"])}</b><em>{_e(note)}</em></span>
        </label>''')

    return f'''<!doctype html>
<html lang="en" data-theme="light"><head>{HEAD}<title>MIGRAGENT</title>
<style>{SHARED_CSS}
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
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  <h1>Nothing is stated<br>without a source.</h1>
  <p class="sub">Answer two questions, add whatever paperwork you already have, and an agent goes
  and reads the official pages. What comes back is a guide you can save as a PDF, with the source
  and the date on every line.</p>

  <form id="f" method="post" action="/begin">
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
      <p class="sub" style="margin-top:10px;font-size:.88rem">Somewhere greyed out means no
      official source could be read for it yet. It says so rather than handing you a thinner
      guide without mentioning it.</p>
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
