"""The web application: intake, guide, PDF.

Runs as `migragent-web`, which can read and write Firestore and cannot call a
model or become the watcher. So a request handler cannot start a crawl round or
run up inference, which is checked in tools/test_isolation.py rather than
asserted here.

Health is served at `/health` and not `/healthz`. Something in front of Cloud Run
claims that path and the application never sees it, which cost a deploy cycle to
find on the previous build and is rule 31.
"""
from __future__ import annotations

import html as html_module
import os
from pathlib import Path

from flask import (Flask, Response, jsonify, make_response, redirect, request,
                   send_from_directory)

from . import identity
from .cases import RETENTION_DAYS, Cases
from .corpus import Corpus
from .coverage import Matcher, document_worth
from .documents import KINDS, MIME_BY_SUFFIX, DocumentReader, extract_text
from .guide import build, to_html
from .registry import JURISDICTIONS, Registry
from .upload_page import upload_html

BRAND_DIR = Path(__file__).resolve().parent.parent / "web" / "brand"

MODEL = os.environ.get("MIGRAGENT_MODEL", "gemini-3.5-flash")
MODEL_LOCATION = os.environ.get("MIGRAGENT_MODEL_LOCATION", "global")

# Where the confetti fires. This is a chosen line, not a computed one, and it is
# described that way on the page. What is computed is the score itself, which is
# the part that has to be true. Nothing is gated on it: you can take a guide with
# nothing uploaded at all, because a guide with no documents is still a guide and
# holding it hostage would be a worse product and a dishonest one.
CELEBRATE_AT = 50

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024 * 1024


def _project() -> str:
    return os.environ["GOOGLE_CLOUD_PROJECT"]


def _db():
    from google.cloud import firestore

    return firestore.Client(
        project=_project(),
        credentials=identity.credentials_for(identity.WEB, _project()),
    )


@app.get("/health")
def health() -> Response:
    return Response("ok", mimetype="text/plain")


@app.get("/brand/<path:name>")
def brand(name: str) -> Response:
    return send_from_directory(BRAND_DIR, name)


@app.get("/")
def home() -> Response:
    db = _db()
    registry = Registry(db)
    corpus = Corpus(db)

    # The real numbers, read live. On the day it is nine it says nine.
    total_sources = registry.total_sources()

    # A lane is only offered as covered if requirements have actually been
    # extracted for it. A lane with sources but no extraction is listed as being
    # watched and says so, rather than being quietly offered as finished.
    #
    # Both scans project only the fields they use. Firestore bills and delivers
    # whole documents otherwise, and a source row carries a snapshot path, two
    # digests and a blocked reason that this page never looks at. With a registry
    # meant to grow into the thousands, pulling all of that to colour fourteen
    # labels is the wrong shape.
    extracted: set[tuple[str, str]] = set()
    for row in db.collection("reads").select(["jurisdiction", "lane", "kept"]).stream():
        d = row.to_dict()
        if d.get("kept", 0) > 0:
            extracted.add((d.get("jurisdiction", ""), d.get("lane", "")))

    have_sources: dict[tuple[str, str], int] = {}
    blocked: dict[tuple[str, str], str] = {}
    for row in db.collection("sources").select(
        ["jurisdiction", "lane", "last_read_at", "blocked", "blocked_reason"]
    ).stream():
        d = row.to_dict()
        key = (d.get("jurisdiction", ""), d.get("lane", ""))
        if d.get("blocked") is None and d.get("last_read_at"):
            have_sources[key] = have_sources.get(key, 0) + 1
        elif d.get("blocked") and key not in have_sources:
            blocked[key] = d.get("blocked_reason") or d.get("blocked") or "not readable"

    options = []
    for code, meta in JURISDICTIONS.items():
        for lane in ("study", "work"):
            key = (code, lane)
            count = have_sources.get(key, 0)
            if key in extracted:
                state, note = "ready", f"{count} pages read"
            elif count:
                state, note = "watched", f"{count} pages found, not read yet"
            else:
                state, note = "uncovered", blocked.get(key, "no readable official source")
            options.append((code, meta["name"], lane, state, note, count))

    return Response(_home_html(options, total_sources, corpus.totals()),
                    mimetype="text/html")


def _case_or_none(cases: Cases):
    cid = request.cookies.get("migragent_case")
    return cases.get(cid) if cid else None


@app.get("/start")
def start() -> Response:
    jurisdiction = (request.args.get("jurisdiction") or "").upper()
    lane = (request.args.get("lane") or "").lower()
    if jurisdiction not in JURISDICTIONS or lane not in ("study", "work"):
        return redirect("/")

    db = _db()
    cases = Cases(db)
    case = cases.create(jurisdiction, lane)
    response = make_response(redirect("/documents"))
    # Session cookie. No account exists in this build, so this is deliberately
    # the weakest link between a person and their data: nobody can guess it and
    # nobody can recover it.
    response.set_cookie("migragent_case", case.case_id, httponly=True,
                        samesite="Lax", secure=True, max_age=RETENTION_DAYS * 86400)
    return response


@app.get("/documents")
def documents() -> Response:
    db = _db()
    cases, corpus, registry = Cases(db), Corpus(db), Registry(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")

    near = {s.url.rstrip("/") for s in registry.near_lane(case.jurisdiction, case.lane)}
    requirements = corpus.requirements_for(case.jurisdiction, case.lane, allowed_urls=near)
    worth = document_worth(requirements)
    uploaded = cases.documents(case.case_id)
    cov = cases.coverage(case.case_id) or {}

    return Response(upload_html(case, worth, uploaded, cov, len(requirements),
                                CELEBRATE_AT, KINDS),
                    mimetype="text/html")


@app.post("/upload")
def upload() -> Response:
    db = _db()
    cases, corpus, registry = Cases(db), Corpus(db), Registry(db)
    case = _case_or_none(cases)
    if case is None:
        return jsonify({"error": "no case"}), 400

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "no file"}), 400

    suffix = Path(uploaded.filename).suffix.lower()
    mime = MIME_BY_SUFFIX.get(suffix)
    if mime is None:
        return jsonify({"error": f"{suffix or 'that file type'} cannot be read. "
                                 f"PDF, PNG, JPG or WEBP."}), 400

    data = uploaded.read()

    # The bytes live in this variable and nowhere else. Nothing writes them to
    # disk or to a bucket. See docs/DATA_PROTECTION.md.
    reader = DocumentReader(_project(), MODEL, MODEL_LOCATION,
                            identity.credentials_for(identity.RESEARCHER, _project()))
    doc = reader.read(uploaded.filename, data, mime, extract_text(data, mime))
    del data

    if doc.error:
        return jsonify({"error": doc.error}), 502

    cases.add_document(case.case_id, doc)

    near = {s.url.rstrip("/") for s in registry.near_lane(case.jurisdiction, case.lane)}
    requirements = corpus.requirements_for(case.jurisdiction, case.lane, allowed_urls=near)
    matcher = Matcher(_project(), MODEL, MODEL_LOCATION,
                      identity.credentials_for(identity.RESEARCHER, _project()))
    coverage = matcher.match(case.jurisdiction, case.lane, requirements,
                             cases.documents(case.case_id))
    cases.save_coverage(case.case_id, coverage.to_dict())

    return jsonify({
        "kind": doc.kind,
        "filename": doc.filename,
        "fields": len(doc.fields),
        "verified_fields": len(doc.verified_fields),
        "text_layer": doc.text_layer,
        "dropped": len(doc.dropped),
        "score": coverage.score,
        "covered": coverage.covered,
        "of": coverage.document_requirements,
        "celebrate": coverage.score >= CELEBRATE_AT,
    })


@app.post("/delete")
def delete_case() -> Response:
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return jsonify({"error": "no case"}), 400
    removed = cases.delete(case.case_id)
    response = make_response(jsonify({"removed": removed}))
    response.delete_cookie("migragent_case")
    return response


@app.post("/tasks/sweep")
def sweep() -> Response:
    """Delete cases past their retention date.

    Called by Cloud Scheduler. Cloud Run requires an authenticated invoker for
    this path, so an anonymous request never reaches this function; the check
    below is the second lock rather than the only one.
    """
    expected = os.environ.get("MIGRAGENT_TASK_TOKEN", "")
    if not expected or request.headers.get("X-Migragent-Task") != expected:
        return jsonify({"error": "not authorised"}), 403

    swept = Cases(_db()).sweep()
    return jsonify({"swept": swept, "retention_days": RETENTION_DAYS})


@app.get("/data")
def data_protection() -> Response:
    """What happens to an uploaded document, served from the doc itself.

    The page a person reads and the document the build is held to are the same
    file, so they cannot drift apart into a promise and a practice.
    """
    path = Path(__file__).resolve().parent.parent / "docs" / "DATA_PROTECTION.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "Not available."
    body = html_module.escape(text)
    return Response(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>What happens to your documents</title>'
        f'<link rel="icon" href="/brand/favicon.svg">'
        f'<link rel="stylesheet" href="/brand/tokens.css">'
        f'<style>body{{margin:0;padding:48px 24px 96px}}'
        f'pre{{max-width:820px;margin:0 auto;white-space:pre-wrap;line-height:1.65;'
        f'font-family:var(--font-mono);font-size:.86rem;color:var(--ink)}}</style>'
        f'</head><body><pre>{body}</pre></body></html>',
        mimetype="text/html")


@app.get("/guide")
def guide() -> Response:
    jurisdiction = (request.args.get("jurisdiction") or "").upper()
    lane = (request.args.get("lane") or "").lower()
    if jurisdiction not in JURISDICTIONS or lane not in ("study", "work"):
        return redirect("/")

    db = _db()
    corpus, registry = Corpus(db), Registry(db)
    near = {s.url.rstrip("/") for s in registry.near_lane(jurisdiction, lane)}
    built = build(
        jurisdiction, lane,
        corpus.requirements_for(jurisdiction, lane, allowed_urls=near),
        corpus.open_questions_for(jurisdiction, lane, allowed_urls=near),
        registry.total_sources(),
    )
    return Response(to_html(built), mimetype="text/html")


def _home_html(options: list, total_sources: int, totals: dict) -> str:
    rows = []
    for code, name, lane, state, note, _count in options:
        disabled = "" if state == "ready" else " aria-disabled=\"true\""
        href = f"/start?jurisdiction={code}&lane={lane}" if state == "ready" else "#"
        rows.append(f'''
      <a class="opt {state}" href="{href}"{disabled}>
        <span class="place">{name}</span>
        <span class="lane">{lane}</span>
        <span class="state">{state}</span>
        <span class="note">{note}</span>
      </a>''')

    return f'''<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MIGRAGENT</title>
<link rel="icon" href="/brand/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/brand/tokens.css">
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; padding: 56px 28px 96px }}
  main {{ max-width: 860px; margin: 0 auto }}
  .mark {{ display: flex; align-items: center; gap: 12px; color: var(--primary); margin-bottom: 40px }}
  .mark svg {{ width: 32px; height: 32px }}
  .mark span {{ font-family: var(--font-display); font-size: 1.4rem; color: var(--ink); letter-spacing: .02em }}
  h1 {{ font-size: clamp(2.1rem, 5.5vw, 3.2rem); line-height: 1.05; margin: 0 0 14px }}
  .lead {{ color: var(--ink); font-size: 1.1rem; line-height: 1.65; max-width: 58ch; margin: 0 0 10px }}
  .sub {{ color: var(--ink-soft); line-height: 1.65; max-width: 58ch; margin: 0 0 8px }}
  .counts {{ font-family: var(--font-mono); font-size: .8rem; color: var(--ink-soft);
             border-top: 1px solid var(--rule); margin-top: 30px; padding-top: 14px }}
  h2 {{ font-size: .82rem; text-transform: uppercase; letter-spacing: .14em; font-family: var(--font-body);
        font-weight: 600; color: var(--ink-soft); margin: 44px 0 14px }}
  .opts {{ display: grid; gap: 8px }}
  .opt {{ display: grid; grid-template-columns: 1fr auto auto; gap: 6px 16px; align-items: center;
          padding: 16px 18px; border: 1px solid var(--rule); border-radius: var(--radius);
          background: var(--paper-raised); text-decoration: none; color: inherit;
          transition: border-color var(--motion-fast) var(--ease) }}
  .opt.ready:hover {{ border-color: var(--primary) }}
  .opt[aria-disabled="true"] {{ opacity: .62; cursor: not-allowed }}
  .place {{ font-weight: 600 }}
  .lane {{ font-family: var(--font-mono); font-size: .78rem; color: var(--ink-soft) }}
  .state {{ font: 500 .68rem var(--font-body); text-transform: uppercase; letter-spacing: .08em;
            border: 1px solid var(--rule); border-radius: 100px; padding: 3px 10px }}
  .ready .state {{ color: var(--primary); border-color: var(--primary) }}
  .uncovered .state {{ color: var(--warn); border-color: var(--warn) }}
  .note {{ grid-column: 1 / -1; font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }}
</style>
</head>
<body>
<main>
  <div class="mark">
    <svg viewBox="0 0 64 64"><path d="M10 36 V8 L32 28 L54 8 V36" fill="none" stroke="currentColor" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 50 Q32 61 45 50" fill="none" stroke="currentColor" stroke-width="7.5" stroke-linecap="round"/></svg>
    <span>MIGRAGENT</span>
  </div>

  <h1>Nothing is stated<br>without a source.</h1>
  <p class="lead">You are applying to move country, or to be licensed to work in one. Pick your
  lane and get a guide you can save as a PDF.</p>
  <p class="sub">Every requirement carries the official page it came from and the date that page
  was read. Anything that could not be sourced goes to open questions at the back rather than being
  guessed at. This is not legal advice.</p>

  <div class="counts">
    {total_sources} sources in the registry &nbsp;·&nbsp;
    {totals.get("pages_read", 0)} pages read &nbsp;·&nbsp;
    {totals.get("requirements", 0)} requirements &nbsp;·&nbsp;
    {totals.get("dropped", 0)} dropped for having no quote on the page
  </div>

  <h2>Pick a lane</h2>
  <div class="opts">{"".join(rows)}</div>

  <h2>What the labels mean</h2>
  <p class="sub"><b>Ready</b> means pages have been read and requirements extracted.
  <b>Watched</b> means the pages are in the registry and have not been read yet.
  <b>Uncovered</b> means no official source could be read at all, and the reason is shown. A lane
  that is not covered says so here rather than handing you a thinner guide without mentioning it.</p>
</main>
</body>
</html>
'''
