"""The web application: intake, guide, PDF.

Runs as `migragent-web`, which can read and write Firestore and cannot become
the watcher, so a request handler cannot start a crawl round. It has no model
access of its own; where a request genuinely needs the model, for reading a
document or matching coverage, it borrows the researcher for the length of that
call and the borrowing is visible in the code at the point of use. The watcher
has no token creator binding at all, which is what makes the crawl unreachable
from a request, and that is checked in tools/test_isolation.py rather than
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
from .board import Board, Piece
from .cases import RETENTION_DAYS, Cases
from .cv import CVReader, CVStore
from .drafts import Drafter, PeopleDrafter
from .fetcher import Fetcher
from .fit import FitScorer, Fits
from .listings import Listings, matched_for, occupations_matching
from .occupations import Shortages
from .corpus import Corpus
from .coverage import Matcher, document_worth
from .detect import agreement, detect
from .documents import KINDS, MIME_BY_SUFFIX, DocumentReader, extract_text
from .form import FormBuilder
from .intake_page import intake_html, working_html
from .result_page import result_html
from .routes import RouteFinder
from .run import Run, sse_done
from .guide import build, to_html
from .registry import JURISDICTIONS, Registry
from .upload_page import upload_html
from .work_page import board_html, jobs_html

BRAND_DIR = Path(__file__).resolve().parent.parent / "web" / "brand"

MODEL = os.environ.get("MIGRAGENT_MODEL", "gemini-3.5-flash")
MODEL_LOCATION = os.environ.get("MIGRAGENT_MODEL_LOCATION", "global")

# Where the confetti fires. This is a chosen line, not a computed one, and it is
# described that way on the page. What is computed is the score itself, which is
# the part that has to be true. Nothing is gated on it: you can take a guide with
# nothing uploaded at all, because a guide with no documents is still a guide and
# holding it hostage would be a worse product and a dishonest one.
CELEBRATE_AT = 50

# Below this, a lane says how few requirements it has rather than calling itself
# ready. A chosen line, like CELEBRATE_AT, and described as one.
#
# Reason for the number: a guide has to carry eligibility, documents, cost and
# timing before it is a guide rather than a fragment of a checklist, and the
# lanes that clear this comfortably all do. Canada's study permit has 568 and
# Saudi Arabia's work lane has 3. Whatever the right line is, it is somewhere
# between those, and the screen shows the real count either way so nobody has to
# take this number on trust.
DEEP_ENOUGH = 25

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
    """Two questions and a drop zone. The lane is derived behind it.

    The first version of this page listed fourteen jurisdiction and lane rows
    labelled ready, watched and uncovered. That is our filing system. Nobody
    arrives thinking "CA study", they arrive thinking about a master's in Canada,
    so coverage now appears only where it changes what they can expect.
    """
    db = _db()
    registry, corpus = Registry(db), Corpus(db)

    # Counted from the requirements themselves rather than from the read log,
    # because a page read that kept nothing is not coverage, and a requirement
    # retired because its page stopped saying it must stop counting the moment
    # it is retired.
    extracted: dict[tuple[str, str], int] = {}
    for row in db.collection("requirements").select(
            ["jurisdiction", "lane", "retired_at"]).stream():
        d = row.to_dict()
        if d.get("retired_at"):
            continue
        key = (d.get("jurisdiction", ""), d.get("lane", ""))
        extracted[key] = extracted.get(key, 0) + 1

    unverified: dict[tuple[str, str], str] = {}
    found: dict[tuple[str, str], int] = {}
    for row in db.collection("sources").select(
            ["jurisdiction", "lane", "last_read_at", "blocked", "unverified_reason"]).stream():
        d = row.to_dict()
        key = (d.get("jurisdiction", ""), d.get("lane", ""))
        if d.get("unverified_reason") and not d.get("last_read_at"):
            unverified.setdefault(key, d["unverified_reason"])
        if d.get("blocked") is None and d.get("last_read_at"):
            key = (d.get("jurisdiction", ""), d.get("lane", ""))
            found[key] = found.get(key, 0) + 1

    coverage_by_lane = {}
    for code in JURISDICTIONS:
        for lane in ("study", "work"):
            key = (code, lane)
            count = extracted.get(key, 0)
            if count >= DEEP_ENOUGH:
                coverage_by_lane[key] = ("ready", f"{count} requirements read")
            elif count:
                # Thin, and it says the number rather than the word. Saudi
                # Arabia's work lane has three requirements and Canada's study
                # permit has 568, and before this they were both "ready", which
                # reported that extraction had run rather than what it found.
                # Same mistake as a progress bar that measures uploading instead
                # of coverage.
                #
                # Not disabled. Somebody who wants the three requirements we can
                # actually source for Saudi Arabia should be able to have them,
                # knowing there are three.
                coverage_by_lane[key] = ("thin", f"only {count} requirements so far")
            elif found.get(key):
                coverage_by_lane[key] = ("watched", f"{found[key]} pages found, none read yet")
            elif unverified.get(key):
                coverage_by_lane[key] = ("unavailable", unverified[key])
            else:
                coverage_by_lane[key] = ("uncovered", "no readable official source")

    # The number on the front page is the same number the lanes are built from,
    # summed, rather than a figure typed into a template and left to rot.
    return Response(intake_html(coverage_by_lane, registry.total_sources(),
                                live=sum(extracted.values())),
                    mimetype="text/html")


def _case_or_none(cases: Cases):
    cid = request.cookies.get("migragent_case")
    return cases.get(cid) if cid else None


@app.post("/begin")
def begin() -> Response:
    """One submit: the two choices, and whatever files came with them.

    Documents are read here rather than on the working screen, because a file
    has to arrive before anything can read it. Their read times are real and the
    working screen replays them with the counts they actually produced.
    """
    jurisdiction = (request.form.get("place") or "").upper()
    lane = (request.form.get("lane") or "").lower()
    if jurisdiction not in JURISDICTIONS or lane not in ("study", "work"):
        return jsonify({"error": "Pick what you are doing and where."}), 400

    db = _db()
    cases = Cases(db)
    case = cases.create(jurisdiction, lane)

    reader = DocumentReader(_project(), MODEL, MODEL_LOCATION,
                            identity.credentials_for(identity.RESEARCHER, _project()))
    for uploaded in request.files.getlist("file"):
        if not uploaded.filename:
            continue
        mime = MIME_BY_SUFFIX.get(Path(uploaded.filename).suffix.lower())
        if mime is None:
            continue
        data = uploaded.read()
        doc = reader.read(uploaded.filename, data, mime, extract_text(data, mime))
        del data
        if not doc.error:
            cases.add_document(case.case_id, doc)

    response = make_response(jsonify({"ok": True, "case": case.case_id[:8]}))
    # Session cookie. No account exists in this build, so this is deliberately
    # the weakest link between a person and their data: nobody can guess it and
    # nobody can recover it.
    response.set_cookie("migragent_case", case.case_id, httponly=True,
                        samesite="Lax", secure=True, max_age=RETENTION_DAYS * 86400)
    return response


@app.get("/working")
def working() -> Response:
    cases = Cases(_db())
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")
    return Response(working_html(case, len(cases.documents(case.case_id))),
                    mimetype="text/html")


@app.get("/run-stream")
def run_stream() -> Response:
    """Server sent events, one per real step, as each one finishes."""
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return Response(sse_done(), mimetype="text/event-stream")

    creds = identity.credentials_for(identity.RESEARCHER, _project())
    run = Run(
        cases=cases,
        corpus=Corpus(db),
        registry=Registry(db),
        matcher=Matcher(_project(), MODEL, MODEL_LOCATION, creds),
        finder=RouteFinder(_project(), MODEL, MODEL_LOCATION, creds),
        builder=FormBuilder(_project(), MODEL, MODEL_LOCATION, creds),
        detect_fn=detect,
        agreement_fn=agreement,
    )
    return Response(run.stream(case), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/result")
def result() -> Response:
    """The guide, the routes, and the form only you can answer."""
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")
    return Response(
        result_html(case, cases.coverage(case.case_id) or {},
                    cases.result(case.case_id) or {},
                    cases.documents(case.case_id)),
        mimetype="text/html")


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


# ---------------------------------------------------------------- work and board


@app.get("/work")
def work() -> Response:
    """What this person's CV matched. There is nothing else on this screen.

    No search box, no filters, no browse. A person drops a CV and is shown what
    it matched, each row carrying the line in their own CV that put it there.
    Rule 39.
    """
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")

    cv = CVStore(db).get(case.case_id)
    place = JURISDICTIONS.get(case.jurisdiction, {}).get("name", case.jurisdiction)

    listings: list = []
    if cv is not None:
        roles = [c.value for c in cv.of_kind("role")] + [c.value for c in cv.of_kind("licence")]
        # CV to occupations first, then occupations to listings. The government's
        # list of what it is short of is the join, and narrowing in the query is
        # what stops a person being matched against an arbitrary slice of the
        # board.
        wanted = occupations_matching(roles, Shortages(db).for_jurisdiction(case.jurisdiction))
        listings = matched_for(roles, Listings(db).for_occupations(case.jurisdiction, wanted))

    scored = {row.get("listing_id"): row
              for row in [Fits(db).get(case.case_id, listing.get("listing_id"))
                          for listing in listings]
              if row}

    return Response(jobs_html(cv, listings, scored, place), mimetype="text/html")


@app.post("/cv")
def upload_cv() -> Response:
    """Read a CV, keep what it says, never keep the file.

    The CV does not touch the readiness score. That number is the share of a
    government's stated requirements a person's documents cover, and a CV covers
    almost none of them. It is scored against a listing instead, where there is
    a listing to score it against.
    """
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")

    uploaded = request.files.get("cv")
    if uploaded is None or not uploaded.filename:
        return redirect("/work")

    mime = MIME_BY_SUFFIX.get(Path(uploaded.filename).suffix.lower())
    if mime is None:
        return redirect("/work")

    data = uploaded.read()
    reader = CVReader(_project(), MODEL, MODEL_LOCATION,
                      identity.credentials_for(identity.RESEARCHER, _project()))
    cv = reader.read(uploaded.filename, data, mime, extract_text(data, mime))
    del data

    CVStore(db).put(case.case_id, cv)
    return redirect("/work")


@app.post("/fit")
def score_fit() -> Response:
    """Score the CV against one posting, from the posting's own words."""
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")

    listing_id = request.form.get("listing") or ""
    listing = db.collection("listings").document(listing_id).get()
    cv = CVStore(db).get(case.case_id)
    if not listing.exists or cv is None:
        return redirect("/work")

    row = listing.to_dict()
    # Fetched here, at the moment somebody asks, because a posting's own words
    # are what the score is made of and the search results page does not carry
    # them. The robots gate applies exactly as it does everywhere else.
    page = Fetcher(delay_seconds=0.5).fetch(row.get("url", ""))
    scorer = FitScorer(_project(), MODEL, MODEL_LOCATION,
                       identity.credentials_for(identity.RESEARCHER, _project()))
    fit = scorer.score(page, cv, listing_id, case.case_id)
    Fits(db).put(fit)
    return redirect("/work")


@app.post("/interested")
def interested() -> Response:
    """Put an application on the board. It does not move again without them."""
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")

    listing_id = request.form.get("listing") or ""
    snap = db.collection("listings").document(listing_id).get()
    if not snap.exists:
        return redirect("/work")

    fit = Fits(db).get(case.case_id, listing_id) or {}
    Board(db).add(case.case_id, snap.to_dict(), fit.get("score"))
    return redirect("/board")


@app.get("/board")
def board() -> Response:
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")
    return Response(board_html(Board(db).for_case(case.case_id)), mimetype="text/html")


@app.post("/board/move")
def move_item() -> Response:
    """A person moved this. Nothing else can."""
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")
    Board(db).advance(case.case_id, request.form.get("item") or "",
                      request.form.get("column") or "")
    return redirect("/board")


@app.post("/board/draft")
def draft_piece() -> Response:
    """Write one piece of an application, when a person asks for it.

    On demand rather than on "I'm interested", because a click that silently
    spends two model calls is a click that has to justify itself, and most
    people want to look at the job before anybody writes anything.
    """
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        return redirect("/")

    kind = request.form.get("kind") or ""
    identifier = request.form.get("item") or ""
    board = Board(db)
    item = board.get(case.case_id, identifier)
    cv = CVStore(db).get(case.case_id)
    if item is None or kind not in ("cv", "cover_letter", "people"):
        return redirect("/board")
    if cv is None and kind != "people":
        # The two written pieces are made out of the CV and cannot exist without
        # one. The people are about the employer and do not need it.
        return redirect("/board")

    snap = db.collection("listings").document(item.listing_id).get()
    listing = snap.to_dict() if snap.exists else {"title": item.title,
                                                  "employer": item.employer}

    reader = identity.credentials_for(identity.RESEARCHER, _project())
    if kind == "people":
        piece = PeopleDrafter(_project(), MODEL, MODEL_LOCATION, reader).people(listing)
    else:
        drafter = Drafter(_project(), MODEL, MODEL_LOCATION, reader)
        piece = (drafter.rewrite_cv(cv, listing, case.jurisdiction) if kind == "cv"
                 else drafter.cover_letter(cv, listing, case.jurisdiction))
    board.attach(case.case_id, identifier, piece)
    return redirect("/board")
