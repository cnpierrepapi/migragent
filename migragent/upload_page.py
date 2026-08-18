"""The upload page: what you have, what it covers, and the number.

The score on this page is the share of the lane's document-satisfiable
requirements that the uploads can be shown to address. It is not a prediction
and the page never suggests it is one.

The two moments of motion here are the run and the confetti, which is the whole
budget from docs/BRAND.md. The confetti fires when a real threshold is crossed,
and the page says outright that the line is chosen while the number is computed.
Everything stops under prefers-reduced-motion.
"""
from __future__ import annotations

import html
from typing import Any

LABELS = {
    "passport": "Passport",
    "national_id": "National identity card",
    "degree_certificate": "Degree certificate",
    "transcript": "Academic transcript",
    "english_test": "English test result",
    "language_test_other": "Other language test",
    "professional_registration": "Professional registration",
    "employment_letter": "Employment letter",
    "bank_statement": "Bank statement or proof of funds",
    "police_certificate": "Police certificate",
    "medical_exam": "Medical exam result",
    "birth_certificate": "Birth certificate",
    "marriage_certificate": "Marriage certificate",
    "offer_letter": "Letter of acceptance or job offer",
    "other": "Something else",
}


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


def upload_html(case, worth, uploaded, coverage, requirement_count,
                celebrate_at: int, kinds) -> str:
    score = int(coverage.get("score", 0))
    covered = int(coverage.get("covered", 0))
    of = int(coverage.get("document_requirements", 0))
    action_only = int(coverage.get("action_only", 0))
    unverified = int(coverage.get("unverified", 0))

    wanted = []
    for kind, n in worth:
        if kind == "other":
            continue
        have = [d for d in uploaded if d.kind == kind]
        tick = "have" if have else "want"
        detail = (f"{len(have)} uploaded" if have
                  else (f"{n} requirements mention it" if n else "not mentioned in this lane"))
        wanted.append(f'''
      <li class="doc {tick}">
        <span class="name">{_e(LABELS.get(kind, kind))}</span>
        <span class="why">{_e(detail)}</span>
      </li>''')

    rows = []
    for doc in uploaded:
        marks = []
        if not doc.text_layer:
            marks.append('<span class="mark unver">no text layer, fields unverified</span>')
        if doc.dropped:
            marks.append(f'<span class="mark drop">{len(doc.dropped)} dropped, '
                         f'no quote in the document</span>')
        fields = ", ".join(f"{_e(f.name)}" for f in doc.fields[:8]) or "nothing readable"
        rows.append(f'''
      <li class="up">
        <b>{_e(LABELS.get(doc.kind, doc.kind))}</b>
        <span class="fn">{_e(doc.filename)}</span>
        <span class="fields">{fields}</span>
        {"".join(marks)}
      </li>''')

    matched = coverage.get("matched", [])[:8]
    matched_rows = "".join(
        f'<li><b>{_e(m.get("requirement_text",""))[:110]}</b>'
        f'<span class="via">covered by your {_e(LABELS.get(m.get("document_kind"), m.get("document_kind")))}'
        f' &middot; {_e(m.get("document_field"))}'
        f'{"" if m.get("verified") else " &middot; unverified"}</span></li>'
        for m in matched) or '<li class="none">Nothing matched yet.</li>'

    return f'''<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your documents</title>
<link rel="icon" href="/brand/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/brand/tokens.css">
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; padding: 48px 24px 96px }}
  main {{ max-width: 900px; margin: 0 auto }}
  a {{ color: var(--link) }}
  .mark-logo {{ display: flex; align-items: center; gap: 11px; color: var(--primary); margin-bottom: 32px }}
  .mark-logo svg {{ width: 28px; height: 28px }}
  .mark-logo span {{ font-family: var(--font-display); font-size: 1.25rem; color: var(--ink) }}
  h1 {{ font-size: clamp(1.8rem, 4.5vw, 2.5rem); margin: 0 0 10px; line-height: 1.1 }}
  .sub {{ color: var(--ink-soft); line-height: 1.65; max-width: 60ch; margin: 0 0 8px }}
  h2 {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .14em; font-family: var(--font-body);
        font-weight: 600; color: var(--ink-soft); margin: 40px 0 14px;
        padding-bottom: 8px; border-bottom: 1px solid var(--rule) }}

  .scorebox {{ display: flex; gap: 26px; align-items: center; flex-wrap: wrap;
               background: var(--paper-raised); border: 1px solid var(--rule);
               border-radius: var(--radius); padding: 24px 26px; box-shadow: var(--shadow) }}
  .big {{ font: var(--display-wght) 3.4rem var(--font-display); color: var(--ink);
          font-variant-numeric: tabular-nums; line-height: 1 }}
  .big small {{ font-size: 1.2rem; color: var(--ink-soft) }}
  .meter {{ flex: 1; min-width: 220px }}
  .track {{ height: 10px; background: var(--paper); border: 1px solid var(--rule);
            border-radius: 100px; overflow: hidden }}
  .fill {{ height: 100%; width: {score}%; background: var(--primary);
           transition: width var(--motion) var(--ease) }}
  .meterlabel {{ font-family: var(--font-mono); font-size: .76rem; color: var(--ink-soft); margin-top: 9px }}
  .cta {{ display: inline-block; padding: 13px 30px; border-radius: var(--radius);
          background: var(--primary); color: var(--paper-raised); text-decoration: none;
          font: 600 .95rem var(--font-body); border: 0; cursor: pointer }}
  .cta:hover {{ background: var(--primary-hot) }}

  ul {{ list-style: none; margin: 0; padding: 0 }}
  .doc {{ display: flex; justify-content: space-between; gap: 16px; padding: 11px 14px;
          border: 1px solid var(--rule); border-radius: var(--radius-sm); margin-bottom: 6px;
          background: var(--paper-raised) }}
  .doc.have {{ border-left: 3px solid var(--primary) }}
  .name {{ font-weight: 500 }}
  .why {{ font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }}
  .up {{ padding: 13px 15px; border: 1px solid var(--rule); border-radius: var(--radius-sm);
         margin-bottom: 7px; background: var(--paper-raised); display: grid; gap: 4px }}
  .fn, .fields {{ font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }}
  .mark {{ font: 500 .68rem var(--font-body); text-transform: uppercase; letter-spacing: .07em;
           border-radius: 100px; padding: 2px 9px; justify-self: start }}
  .unver {{ color: var(--warn); border: 1px solid var(--warn) }}
  .drop {{ color: var(--ink-soft); border: 1px solid var(--rule) }}
  .via {{ display: block; font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft); margin-top: 3px }}
  .none {{ color: var(--ink-soft) }}
  #matched li {{ padding: 10px 0; border-bottom: 1px solid var(--rule); line-height: 1.5 }}

  .drop-zone {{ border: 1.5px dashed var(--rule); border-radius: var(--radius); padding: 30px;
                text-align: center; background: var(--paper-raised); cursor: pointer;
                transition: border-color var(--motion-fast) var(--ease) }}
  .drop-zone:hover, .drop-zone.over {{ border-color: var(--primary) }}
  .drop-zone p {{ margin: 0; color: var(--ink-soft) }}
  #log {{ font-family: var(--font-mono); font-size: .76rem; color: var(--ink-soft); margin-top: 12px }}
  #log div {{ padding: 5px 0; border-bottom: 1px solid var(--rule) }}

  .danger {{ background: none; border: 1px solid var(--warn); color: var(--warn);
             border-radius: var(--radius); padding: 10px 18px; font: 500 .85rem var(--font-body);
             cursor: pointer }}
  canvas#confetti {{ position: fixed; inset: 0; pointer-events: none; z-index: 40 }}
  @media (prefers-reduced-motion: reduce) {{ canvas#confetti {{ display: none }} }}
</style>
</head>
<body>
<canvas id="confetti"></canvas>
<main>
  <div class="mark-logo">
    <svg viewBox="0 0 64 64"><path d="M10 36 V8 L32 28 L54 8 V36" fill="none" stroke="currentColor" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 50 Q32 61 45 50" fill="none" stroke="currentColor" stroke-width="7.5" stroke-linecap="round"/></svg>
    <span>MIGRAGENT</span>
  </div>

  <h1>What you already have</h1>
  <p class="sub">Upload what is in your drawer. Nothing is required, and you can take the guide at
  any point. The more the agent can read, the more the guide is about you rather than about
  everybody.</p>
  <p class="sub"><b>The file is not kept.</b> It is read and discarded, and what is stored is the
  fields, not the document. <a href="/data">What happens to your documents</a>.</p>

  <h2>How ready this makes you</h2>
  <div class="scorebox">
    <div class="big" id="score">{score}<small>%</small></div>
    <div class="meter">
      <div class="track"><div class="fill" id="fill"></div></div>
      <div class="meterlabel" id="meterlabel">
        {covered} of {of} requirements your documents can speak to
        &nbsp;·&nbsp; {action_only} are actions or fees, which no document covers
        {f"&nbsp;·&nbsp; {unverified} unverified" if unverified else ""}
      </div>
    </div>
    <a class="cta" href="/guide?jurisdiction={_e(case.jurisdiction)}&lane={_e(case.lane)}">GO</a>
  </div>
  <p class="sub" style="margin-top:12px">This is the share of the {requirement_count} requirements
  read for this lane that your documents address. It is not a prediction of whether an application
  will succeed. The confetti line is set at {celebrate_at}%, which is a chosen line; the number
  itself is counted.</p>

  <h2>Worth digging out, most useful first</h2>
  <p class="sub">Ordered by how many requirements in this lane actually mention each one, counted
  from the sources rather than decided in advance.</p>
  <ul>{"".join(wanted)}</ul>

  <h2>Add a document</h2>
  <div class="drop-zone" id="zone">
    <p>Drop a file here, or click to choose. PDF, PNG, JPG or WEBP.</p>
    <input type="file" id="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp">
  </div>
  <div id="log"></div>

  <h2>What you have uploaded</h2>
  <ul id="uploaded">{"".join(rows) or '<li class="none">Nothing yet.</li>'}</ul>

  <h2>What it covers</h2>
  <ul id="matched">{matched_rows}</ul>

  <h2>Your data</h2>
  <p class="sub">This case is deleted automatically 30 days after you last touch it. You can also
  delete it now, and the button reports exactly what it removed.</p>
  <button class="danger" id="del">Delete everything about this case</button>
  <div id="delresult" class="sub" style="margin-top:10px"></div>
</main>

<script>
(function () {{
  var zone = document.getElementById('zone');
  var input = document.getElementById('file');
  var log = document.getElementById('log');
  var celebrateAt = {celebrate_at};
  var lastScore = {score};

  zone.onclick = function () {{ input.click(); }};
  zone.ondragover = function (e) {{ e.preventDefault(); zone.classList.add('over'); }};
  zone.ondragleave = function () {{ zone.classList.remove('over'); }};
  zone.ondrop = function (e) {{
    e.preventDefault(); zone.classList.remove('over');
    if (e.dataTransfer.files.length) send(e.dataTransfer.files[0]);
  }};
  input.onchange = function () {{ if (input.files.length) send(input.files[0]); }};

  function line(text) {{
    var d = document.createElement('div');
    d.textContent = text;
    log.prepend(d);
    return d;
  }}

  function send(file) {{
    var row = line('reading ' + file.name + ' ...');
    var body = new FormData();
    body.append('file', file);
    fetch('/upload', {{ method: 'POST', body: body }})
      .then(function (r) {{ return r.json().then(function (j) {{ return {{ ok: r.ok, j: j }}; }}); }})
      .then(function (res) {{
        if (!res.ok) {{ row.textContent = file.name + ': ' + (res.j.error || 'could not read it'); return; }}
        var j = res.j;
        var bits = [j.kind, j.fields + ' fields'];
        if (!j.text_layer) bits.push('no text layer, unverified');
        if (j.dropped) bits.push(j.dropped + ' dropped');
        row.textContent = file.name + ': ' + bits.join(' · ');
        setScore(j.score, j.covered, j.of);
        if (j.score >= celebrateAt && lastScore < celebrateAt) confetti();
        lastScore = j.score;
        setTimeout(function () {{ location.reload(); }}, 1200);
      }})
      .catch(function (e) {{ row.textContent = file.name + ': ' + e; }});
  }}

  function setScore(score, covered, of) {{
    document.getElementById('score').innerHTML = score + '<small>%</small>';
    document.getElementById('fill').style.width = score + '%';
    document.getElementById('meterlabel').textContent =
      covered + ' of ' + of + ' requirements your documents can speak to';
  }}

  // The only other animation in the product. It fires when a real threshold is
  // crossed, and not when a file merely arrives.
  function confetti() {{
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var c = document.getElementById('confetti');
    var ctx = c.getContext('2d');
    c.width = innerWidth; c.height = innerHeight;
    var colours = ['#16467D', '#1E5FA8', '#FFC53D', '#55627A'];
    var bits = [];
    for (var i = 0; i < 140; i++) bits.push({{
      x: Math.random() * c.width, y: -20 - Math.random() * c.height * 0.4,
      w: 5 + Math.random() * 6, h: 8 + Math.random() * 8,
      vy: 2 + Math.random() * 3.2, vx: -1.2 + Math.random() * 2.4,
      rot: Math.random() * 6.28, vr: -0.12 + Math.random() * 0.24,
      colour: colours[i % colours.length]
    }});
    var start = Date.now();
    (function frame() {{
      ctx.clearRect(0, 0, c.width, c.height);
      bits.forEach(function (b) {{
        b.x += b.vx; b.y += b.vy; b.rot += b.vr;
        ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.rot);
        ctx.fillStyle = b.colour; ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h);
        ctx.restore();
      }});
      if (Date.now() - start < 2600) requestAnimationFrame(frame);
      else ctx.clearRect(0, 0, c.width, c.height);
    }})();
  }}

  document.getElementById('del').onclick = function () {{
    fetch('/delete', {{ method: 'POST' }})
      .then(function (r) {{ return r.json(); }})
      .then(function (j) {{
        var r = j.removed || {{}};
        document.getElementById('delresult').textContent =
          'Removed ' + (r.documents || 0) + ' documents, ' + (r.coverage || 0) +
          ' coverage record and ' + (r.case || 0) + ' case. Nothing about it is left.';
        document.getElementById('del').disabled = true;
      }});
  }};
}})();
</script>
</body>
</html>
'''
