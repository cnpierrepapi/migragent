"""The three screens that replaced picking a country off a list.

THE ORDER, AND WHY IT IS THIS ORDER
-----------------------------------
    1  what are you trying to do          study, work, or both
    2  what have you got                   a CV, or transcripts
    3  where you can actually go           countries derived from step 2

Every build before this asked for the country first. That is backwards in the
way that matters most: somebody who does not already know that Canada is short
of welders cannot choose Canada for being short of welders, and asking them to
choose makes them do the research this product exists to do for them.

So the country list is not a list of countries. It is a list of the countries
whose own published documents say they want somebody like this person, each one
carrying the sentence that says so. A place they are not eligible for never
appears, because showing it means either a wasted month or a refusal with a fee
attached.

NOTHING ON THESE SCREENS IS A SEARCH BOX
-----------------------------------------
Rule 39, unchanged. There is nothing to type, nothing to filter and nothing to
browse. Two taps and an upload.

WHAT HAPPENS WHEN NOTHING MATCHES
----------------------------------
It says so, plainly, and says what would change it. An empty result here is a
real answer about the world and not a failure of the product, and dressing it up
as "no results found, try adjusting your filters" would be pretending there were
filters to adjust.
"""
from __future__ import annotations

import html
from typing import Any

from .registry import JURISDICTIONS
from .result_page import HEAD, LOGO


def _e(x: Any) -> str:
    return html.escape(str(x or ""))


STYLE = '''
  * { box-sizing: border-box }
  body { margin: 0; padding: 44px 24px 96px }
  main { max-width: 760px; margin: 0 auto }
  a { color: var(--link) }
  .brand { display: flex; align-items: center; gap: 11px; color: var(--primary);
           margin-bottom: 26px }
  .brand svg { width: 26px; height: 26px }
  .brand span { font-family: var(--font-display); font-size: 1.18rem; color: var(--ink) }

  .steps { display: flex; gap: 8px; align-items: center; font-family: var(--font-mono);
           font-size: .68rem; letter-spacing: .08em; text-transform: uppercase;
           color: var(--ink-soft); margin-bottom: 26px; flex-wrap: wrap }
  .steps b { color: var(--ink); font-weight: 500 }
  .steps .on { color: var(--accent) }
  .steps i { font-style: normal; opacity: .4 }

  h1 { font-family: var(--font-display); font-size: clamp(1.8rem, 4.4vw, 2.5rem);
       margin: 0 0 12px; line-height: 1.08 }
  .sub { color: var(--ink-soft); line-height: 1.65; margin: 0 0 30px; max-width: 60ch }

  .picks { display: grid; gap: 11px; margin-bottom: 30px }
  .pick { position: relative }
  .pick input { position: absolute; opacity: 0; inset: 0; cursor: pointer }
  .pick span.box { display: block; padding: 18px 20px; border: 1px solid var(--rule);
                   border-radius: var(--radius); background: var(--paper-raised);
                   cursor: pointer; transition: border-color var(--motion-fast) var(--ease) }
  .pick input:checked + span.box { border-color: var(--primary); box-shadow: var(--ring) }
  .pick b { display: block; font: 600 1.06rem var(--font-body); margin-bottom: 4px }
  .pick em { font-style: normal; color: var(--ink-soft); font-size: .92rem; line-height: 1.5 }

  .why { display: block; font-family: var(--font-mono); font-size: .71rem;
         color: var(--ink-soft); margin-top: 9px; line-height: 1.65;
         border-left: 2px solid var(--rule); padding-left: 11px }
  .why q { quotes: none; color: var(--ink) }
  .counts { font-family: var(--font-mono); font-size: .68rem; color: var(--ink-soft);
            margin-top: 7px }

  .primary { margin: 0 0 30px; padding: 17px 19px; border: 1px solid var(--rule);
             border-radius: var(--radius); background: var(--paper-raised); display: none }
  .primary.show { display: block }
  .primary p { margin: 0 0 12px; font: 600 .97rem var(--font-body) }
  .primary label { display: inline-flex; align-items: center; gap: 7px; margin-right: 18px;
                   font-size: .95rem; cursor: pointer }

  .drop { border: 1.5px dashed var(--rule); border-radius: var(--radius); padding: 30px 24px;
          text-align: center; background: var(--paper-raised); cursor: pointer }
  .drop:hover, .drop.over { border-color: var(--primary) }
  .drop p { margin: 0; color: var(--ink-soft) }
  #files { margin: 12px 0 0; padding: 0; list-style: none; font-family: var(--font-mono);
           font-size: .74rem; color: var(--ink-soft) }
  #files li { padding: 7px 0; border-bottom: 1px solid var(--rule) }

  .go { padding: 15px 38px; border: 0; border-radius: var(--radius); background: var(--primary);
        color: var(--paper); font: 600 1rem var(--font-body); cursor: pointer }
  .go:disabled { opacity: .45; cursor: not-allowed }
  .quiet { display: inline-block; margin-left: 14px; font-size: .92rem }
  .note { border-left: 2px solid var(--primary); padding: 2px 0 2px 14px; margin: 0 0 26px;
          color: var(--ink-soft); line-height: 1.7; font-size: .91rem }
  .none { border: 1px dashed var(--rule); border-radius: var(--radius); padding: 26px;
          color: var(--ink-soft); line-height: 1.7 }
  .level { font-family: var(--font-mono); font-size: .74rem; color: var(--ink-soft);
           margin: 0 0 24px; line-height: 1.7 }
  .level b { color: var(--ink) }
'''


def _crumbs(active: int) -> str:
    names = ("what you want", "what you have", "where you can go")
    out = []
    for i, name in enumerate(names, 1):
        mark = "on" if i == active else ""
        out.append(f'<b class="{mark}">{i}. {name}</b>')
    return '<div class="steps">' + ' <i>&rarr;</i> '.join(out) + '</div>'


def choose_html(live: int, sources: int) -> str:
    """Step one. What are you trying to do, and nothing else on the screen."""
    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Start</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  {_crumbs(1)}
  <h1>What are you trying to do?</h1>
  <p class="sub">One question. We work out where you can go from what you upload next,
  rather than asking you to guess at a list of countries.</p>

  <form method="post" action="/start/lane" id="f">
    <div class="picks">
      <label class="pick"><input type="radio" name="intent" value="study" required>
        <span class="box"><b>Study</b><em>A degree, a diploma, a place at a school.</em></span></label>
      <label class="pick"><input type="radio" name="intent" value="work">
        <span class="box"><b>Work</b><em>A job, a permit, being licensed to practise.</em></span></label>
      <label class="pick"><input type="radio" name="intent" value="both">
        <span class="box"><b>Both</b><em>You would take either, and one of them matters more.</em></span></label>
    </div>

    <div class="primary" id="primary">
      <p>Which matters more to you?</p>
      <label><input type="radio" name="lane" value="study"> Study</label>
      <label><input type="radio" name="lane" value="work"> Work</label>
      <span class="why">We answer that one first and in full. The other follows, on the
      same case, rather than both arriving half done.</span>
    </div>

    <button class="go" type="submit">Continue</button>
  </form>

  <p class="counts" style="margin-top:34px">{live:,} requirements read from
  {sources:,} official pages &nbsp;·&nbsp; nothing is stated without one</p>
</main>
<script>
  var box = document.getElementById('primary');
  document.querySelectorAll('input[name=intent]').forEach(function (r) {{
    r.addEventListener('change', function () {{
      // "Both" is the only answer that needs a second question, so it is the
      // only one that grows the form. Asking everybody which they prefer would
      // be asking most people to answer a question they already answered.
      if (r.value === 'both') {{ box.classList.add('show'); }}
      else {{
        box.classList.remove('show');
        document.querySelectorAll('input[name=lane]').forEach(function (x) {{ x.checked = false; }});
      }}
    }});
  }});
  document.getElementById('f').onsubmit = function (e) {{
    var intent = document.querySelector('input[name=intent]:checked');
    if (intent && intent.value === 'both' && !document.querySelector('input[name=lane]:checked')) {{
      e.preventDefault();
      box.classList.add('show');
    }}
  }};
</script>
</body></html>'''


def documents_html(lane: str, intent: str) -> str:
    """Step two. What have you got, framed as what this particular lane needs."""
    if lane == "work":
        title = "What do you do?"
        sub = ("Upload your CV. We read what it says, then work out which countries have "
               "published a shortage that fits it &mdash; and we lay the same CV out the way "
               "employers in Canada, the United Kingdom and the EU expect to receive it.")
        note = ("<b>No CV?</b> That is normal, and it is not a problem. A great many people "
                "who can do the work a country is short of have never needed the document. "
                "<a href=\"/cv/new\">Answer five questions instead</a> and we will build one.")
        accept = ".pdf,.png,.jpg,.jpeg,.webp"
        hint = "Your CV. A PDF, or a photo of it."
    else:
        title = "What have you finished?"
        sub = ("Upload your transcripts or your national exam results &mdash; a WASSCE or NECO "
               "slip, a degree certificate, whatever you hold. We read them to work out what "
               "you are most likely applying for next, and which countries have a school for it.")
        note = ("Photographs are fine and are what most people have. We read the text off the "
                "picture itself, so what we take from it can still be checked against the "
                "words on your document. We read up to eight at a time. If you have more, "
                "add them after.")
        accept = ".pdf,.png,.jpg,.jpeg,.webp"
        hint = "Transcripts, result slips, certificates. Photos are fine."

    both = ("<p class=\"level\">You chose <b>both</b>. We are answering "
            f"<b>{_e(lane)}</b> first. You can add the other side afterwards without "
            "starting again.</p>" if intent == "both" else "")

    # The work path also writes the CV out for Canada, the UK and Europass after
    # reading it, which is three more model calls the person is waiting through.
    clones = 30 if lane == "work" else 0
    what = ("your CV, then writing it out for three countries" if lane == "work"
            else "what you uploaded")

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>What you have</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  {_crumbs(2)}
  <h1>{title}</h1>
  <p class="sub">{sub}</p>
  {both}
  <p class="note">{note}</p>

  <form id="f" method="post" action="/start/documents" enctype="multipart/form-data">
    <div class="drop" id="zone">
      <p>{hint}<br>Drop files here, or click to choose.</p>
      <input type="file" id="picker" name="file" multiple hidden accept="{accept}">
    </div>
    <ul id="files"></ul>
    <p class="why" style="margin-top:16px"><b>The files are not kept.</b> Each one is read
    and discarded; what is stored is what it said, not the document.
    <a href="/data">What happens to your documents</a>.</p>
    <p style="margin-top:26px">
      <button class="go" id="go" type="submit">Read them</button>
      <a class="quiet" href="/start/places">Skip &mdash; I have nothing to upload</a></p>
  </form>
</main>
<script>
  var picker = document.getElementById('picker');
  var zone = document.getElementById('zone');
  var list = document.getElementById('files');
  zone.onclick = function () {{ picker.click(); }};
  zone.ondragover = function (e) {{ e.preventDefault(); zone.classList.add('over'); }};
  zone.ondragleave = function () {{ zone.classList.remove('over'); }};
  zone.ondrop = function (e) {{
    e.preventDefault(); zone.classList.remove('over');
    picker.files = e.dataTransfer.files; show();
  }};
  picker.onchange = show;
  function show() {{
    list.innerHTML = '';
    for (var i = 0; i < picker.files.length; i++) {{
      var li = document.createElement('li');
      li.textContent = picker.files[i].name + '  ·  ' +
                       Math.round(picker.files[i].size / 1024) + ' KB';
      list.appendChild(li);
    }}
  }}
  // WHAT HAPPENS AFTER SUBMIT, AND WHY IT NEEDS SAYING.
  //
  // This POST reads the file with the model and, on the work path, writes the
  // CV out again in three countries' shapes. That is four model calls and it
  // takes the better part of a minute. Until now the button said "Reading ..."
  // and nothing else moved, so the honest reading of the screen was that it had
  // hung.
  //
  // Same rule as the working screen: an estimate, labelled as one, that leans
  // long and never sits at zero. The page is replaced by the redirect when the
  // work is really done, so the real completion always wins.
  document.getElementById('f').onsubmit = function () {{
    var go = document.getElementById('go');
    go.disabled = true;
    go.textContent = 'Reading ...';

    var picker = document.getElementById('picker');
    var files = picker && picker.files ? picker.files.length : 0;
    // Measured: about 25 seconds a file, plus 30 for the three country CVs on
    // the work path. Padded, because running over looks like a hang and
    // finishing early is a pleasant surprise.
    var left = 20 + (files * 25) + ({clones});

    var note = document.createElement('p');
    note.className = 'why';
    note.style.marginTop = '18px';
    document.getElementById('f').appendChild(note);

    function paint() {{
      var m = Math.floor(left / 60), sec = left % 60;
      note.innerHTML = '<b>' + m + ':' + (sec < 10 ? '0' : '') + sec + '</b> or so. ' +
        'Reading {what}. This is an estimate and it leans long; ' +
        'the page moves on by itself the moment the work is done.';
    }}
    paint();

    var timer = setInterval(function () {{
      left -= 1;
      if (left > 0) {{ paint(); return; }}
      clearInterval(timer);
      note.innerHTML = '<b>Still going.</b> This is taking longer than it usually ' +
        'does. Nothing is stuck: the page moves on by itself when it finishes.';
    }}, 1000);
  }};
</script>
</body></html>'''


def places_html(lane: str, eligible: list, reading=None, assumed_level: str = "",
                nothing_because: str = "") -> str:
    """Step three. Only the countries this person's own documents opened."""
    cards = []
    for item in eligible:
        name = JURISDICTIONS.get(item.jurisdiction, {}).get("name", item.jurisdiction)
        top = item.reasons[0] if item.reasons else None
        more = len(item.reasons) - 1

        why = ""
        if top is not None:
            why = (f'<span class="why">Because <q>{_e(top.matched)}</q> is on their '
                   f'published list'
                   + (f", and your CV says <q>{_e(top.because)}</q>" if top.because else "")
                   + (f". And {more} more." if more > 0 else ".")
                   + '</span>')

        counts = []
        if item.requirements:
            counts.append(f"{item.requirements:,} requirements read")
        if getattr(item, "postings", 0):
            counts.append(f"{item.postings:,} live postings")
        count_line = (f'<span class="counts">{" &middot; ".join(counts)}</span>'
                      if counts else "")

        cards.append(
            f'<label class="pick"><input type="checkbox" name="place" '
            f'value="{_e(item.jurisdiction)}" checked>'
            f'<span class="box"><b>{_e(name)}</b>{why}{count_line}</span></label>')

    level_line = ""
    if lane == "study" and assumed_level:
        subjects = list(getattr(reading, "subjects", []) or []) if reading else []
        studied = (f' in <b>{_e(", ".join(subjects))}</b>' if subjects else "")
        if reading is not None and getattr(reading, "found", False):
            level_line = (
                f'<p class="level">Your documents say you hold <b>{_e(reading.held)}</b>, '
                f'from <q>{_e(reading.quote[:90])}</q> on {_e(reading.filename)}. '
                f'So we are showing courses at <b>{_e(assumed_level)}</b> level'
                f'{studied}. '
                f'<a href="/start/level">Studying something else? Change it.</a></p>')
        else:
            level_line = (
                f'<p class="level">We could not tell what you already hold from what you '
                f'uploaded, so we are assuming you are applying for <b>{_e(assumed_level)}</b>. '
                f'<a href="/start/level">Change it.</a></p>')

    if not eligible:
        body = f'''<div class="none">{_e(nothing_because) or
          "Nothing we have read matches what you uploaded yet."}</div>
        <p style="margin-top:24px"><a class="quiet" style="margin:0"
          href="/start/documents">Add or change what you uploaded</a></p>'''
    else:
        body = f'''<form method="post" action="/start/places">
          <div class="picks">{"".join(cards)}</div>
          <button class="go" type="submit">Build my guide</button>
          <a class="quiet" href="/start/documents">Change what you uploaded</a>
        </form>'''

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>Where you can go</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  {_crumbs(3)}
  <h1>Where you can actually go</h1>
  <p class="sub">These are the countries whose own published documents fit what you gave us.
  Every one says why it is here. Countries you would not qualify for are not on this list,
  because showing them would waste your time and your money.</p>
  {level_line}
  {body}
</main></body></html>'''

def level_html(held: str, assumed: str, subjects: list[str],
               quote: str = "", filename: str = "") -> str:
    """Correct what we read off the documents.

    Linked from the countries screen, because that is where somebody discovers
    we got it wrong: they see courses at the wrong level, or in a field they left
    behind. Two controls, no more. The level is a choice of four and the subject
    is free text, because a list of subjects long enough to be useful is longer
    than anybody will read.
    """
    from .eligibility import LEVEL_NAMES

    read = ""
    if held and quote:
        read = (f'<p class="level">We read <b>{_e(held)}</b> from '
                f'<q>{_e(quote[:80])}</q> on {_e(filename)}.</p>')

    options = []
    for key in ("bachelors", "masters", "doctorate"):
        checked = " checked" if key == assumed else ""
        options.append(
            f'<label class="pick"><input type="radio" name="level" '
            f'value="{key}"{checked}>'
            f'<span class="box"><b>{_e(LEVEL_NAMES.get(key, key)).capitalize()}</b>'
            f'</span></label>')

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}<title>What are you studying?</title>
<style>{STYLE}</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>
  {_crumbs(3)}
  <h1>What are you applying for?</h1>
  <p class="sub">We worked this out from your documents. If it is wrong, change it
  here and the countries will be worked out again.</p>
  {read}

  <form method="post" action="/start/level">
    <fieldset style="border:0;padding:0;margin:0 0 26px">
      <legend style="font:600 1rem var(--font-body);margin-bottom:12px">Which level?</legend>
      <div class="picks">{"".join(options)}</div>
    </fieldset>

    <label style="display:block;margin-bottom:26px">
      <b style="display:block;font:600 1rem var(--font-body);margin-bottom:4px">
        What do you want to study?</b>
      <em style="display:block;font-style:normal;font-family:var(--font-mono);
                 font-size:.71rem;color:var(--ink-soft);margin-bottom:9px">
        A subject or two. Leave it empty to see everything at this level.</em>
      <input type="text" name="subjects" value="{_e(", ".join(subjects))}"
             placeholder="Civil engineering, nursing"
             style="width:100%;padding:13px 14px;border:1px solid var(--rule);
                    border-radius:var(--radius-sm);background:var(--paper-raised);
                    color:var(--ink);font:.96rem var(--font-body)"></label>

    <button class="go" type="submit">Show me the countries</button>
    <a class="quiet" href="/start/places">Back</a>
  </form>
</main></body></html>'''
