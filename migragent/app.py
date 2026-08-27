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
from typing import Any
from pathlib import Path

from flask import (Flask, Response, jsonify, make_response, redirect, request,
                   send_from_directory)

from . import identity
from .clock import now_iso as _now_iso
from .alerts import Alerts, Watches
from .alerts_page import alerts_html
from .board import Board
from .cases import RETENTION_DAYS, Cases
from .cv import CVClones, CVReader, CVStore
from .cv_builder import FIELDS as CV_FIELDS, build as build_cv, missing_for_matching
from .cv_builder_page import clone_html, cv_builder_html
from .dashboard_page import dashboard_html
from .architecture_page import architecture_html
from .data_page import data_html
from .drafts import CLONE_INTO, Drafter, PeopleDrafter
from .eligibility import next_level, study_countries, work_countries
from .fetcher import Fetcher
from .flow_page import (choose_html, documents_html, level_html,
                        places_html)
from .fit import FitScorer, Fits
from .listings import Listings, matched_for, occupations_matching
from .occupations import Shortages
from .level import from_documents as level_from_documents
from .level import subjects_from_documents
from .profile import AvatarRejected, Profiles
from .rubric import best, score_study, score_work
from .courses_page import courses_html
from .coverage_page import coverage_html
from .entitlements import is_subscriber, redact_all
from .gaps import with_gaps
from .subscribe_page import subscribe_html
from .corpus import Corpus
from .coverage import Matcher
from .agents.coverage import AgentMatcher, enabled as agent_coverage_enabled
from .detect import agreement, detect
from .documents import MIME_BY_SUFFIX, DocumentReader, extract_text
from .ocr import OCR, can_read as ocr_can_read
from .form import FormBuilder
from .intake_page import working_html
from .landing_page import landing_html
from .result_page import result_html
from .routes import RouteFinder
from .run import Run, sse_done
from .timing import RunTimes
from .guide import build, to_html
from .registry import JURISDICTIONS, Registry
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


def _text_for(data: bytes, mime: str) -> tuple[str, str, str]:
    """The text to check quotes against, and how we came by it.

    A PDF carries its own. A photograph does not, and most people photograph
    their documents, so the alternative to reading the pixels is telling the
    majority of this product's users that nothing they own can be verified.

    OCR is a separate engine from the one making the claims, deliberately. Using
    the model to transcribe and then checking the model's claims against its own
    transcription would be marking its own homework: a hallucinated date would
    verify itself.

    A failure returns no text, and the document falls back to exactly what it did
    before OCR existed. An upload must not fail because a second service is
    having a bad afternoon.
    """
    layer = extract_text(data, mime)
    if layer:
        return layer, "pdf", "checked against the document's own text layer"

    if not ocr_can_read(mime):
        return "", "none", ""

    text, note = OCR(identity.credentials_for(identity.RESEARCHER, _project())).read(data, mime)
    if not text:
        return "", "none", note
    return text, "ocr", note


@app.get("/health")
def health() -> Response:
    return Response("ok", mimetype="text/plain")


@app.get("/brand/<path:name>")
def brand(name: str) -> Response:
    return send_from_directory(BRAND_DIR, name)


@app.get("/start")
def home() -> Response:
    """Step one of the flow: what are you trying to do.

    This used to be the whole intake: pick a lane, pick a country off a list of
    fourteen, drop your documents in. The country question has moved to the end
    and become an answer rather than a question, so what is left here is one
    tap. See migragent/flow_page.py.
    """
    _extracted, live, sources = _coverage()
    return Response(choose_html(live=live, sources=sources), mimetype="text/html")


def cases_documents(db, case_id: str) -> list:
    return Cases(db).documents(case_id)


# The course corpus the study path is built against. It is read from a
# collection the school ingestion fills, and until that ingestion has run this
# returns nothing for every country.
#
# That is the honest failure and not a placeholder: a study country appears when
# a school on its register can be shown to teach this level,
# and inventing a country because we have not looked yet would be exactly the
# claim this product exists not to make. The screen says the reading is under
# way rather than showing an empty list with no explanation.
COURSES = "courses"


def _courses_by_country(db, level: str) -> dict[str, list]:
    from google.cloud import firestore

    out: dict[str, list] = {}
    try:
        query = (db.collection(COURSES)
                 .where(filter=firestore.FieldFilter("level", "==", level))
                 .limit(2000))
        for snap in query.stream():
            row = snap.to_dict()
            out.setdefault(row.get("jurisdiction", ""), []).append(row)
    except Exception:  # noqa: BLE001
        return {}
    return {k: v for k, v in out.items() if k}


def _requirement_counts(db) -> dict[tuple[str, str], int]:
    """Live requirements per country and lane, which several screens want.

    This is the one place that counts requirements. The landing page, the
    coverage page and the two intake screens all go through here, because the
    same ten-line loop was written out four times and two of the copies did not
    know the other two existed.
    """
    counts: dict[tuple[str, str], int] = {}
    for row in db.collection("requirements").select(
            ["jurisdiction", "lane", "retired_at"]).stream():
        d = row.to_dict()
        if d.get("retired_at"):
            continue
        key = (d.get("jurisdiction", ""), d.get("lane", ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


# The front pages read counts off whole Firestore collections. The landing page
# alone used to scan `requirements` twice plus `institutions`, `courses` and
# `listings` once each, about eleven thousand document reads, on every hit
# including every crawler. None of those numbers move between one request and
# the next, so the readers below are memoised for a minute. The ingest job
# changes the underlying rows a few times a day; a minute of staleness on a
# marketing number is a fair trade for not rescanning the store per pageview.
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60.0


def _cached(key: str, build):
    import time

    hit = _CACHE.get(key)
    if hit is not None and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    value = build()
    _CACHE[key] = (time.monotonic(), value)
    return value


@app.post("/start/lane")
def start_lane() -> Response:
    """Step one. A case exists from here on, with no country yet.

    That is the whole inversion: a case used to be impossible without a country,
    because a country was the first thing anybody was asked for.
    """
    intent = (request.form.get("intent") or "").lower()
    if intent not in ("study", "work", "both"):
        return redirect("/start")

    lane = (request.form.get("lane") or "").lower()
    if intent != "both":
        lane = intent
    elif lane not in ("study", "work"):
        # "Both" without saying which matters more is the one answer the form
        # will not accept, because everything downstream answers one lane first
        # and picking for them would be picking the wrong one half the time.
        return redirect("/start")

    case = Cases(_db()).create("", lane, intent=intent)
    response = make_response(redirect("/start/documents"))
    response.set_cookie("migragent_case", case.case_id, max_age=60 * 60 * 24 * 30,
                        httponly=True, samesite="Lax", secure=True)
    return response


@app.get("/start/documents")
def start_documents() -> Response:
    db, cases, case = load_case()
    return Response(documents_html(case.lane, case.intent or case.lane),
                    mimetype="text/html")


@app.post("/start/documents")
def read_documents() -> Response:
    """Read what they uploaded, then send them to the countries it opened.

    A CV goes to the CV store and is cloned into each country's shape here,
    because the clones are what the work path is for and waiting until they have
    found a job to produce them is the wrong order.
    """
    db, cases, case = load_case()

    creds = identity.credentials_for(identity.RESEARCHER, _project())
    uploads = [u for u in request.files.getlist("file") if u and u.filename]

    if case.lane == "work":
        reader = CVReader(_project(), MODEL, MODEL_LOCATION, creds)
        for uploaded in uploads[:1]:
            mime = MIME_BY_SUFFIX.get(Path(uploaded.filename).suffix.lower())
            if mime is None:
                continue
            data = uploaded.read()
            text, source, _note = _text_for(data, mime)
            cv = reader.read(uploaded.filename, data, mime, text, text_source=source)
            del data
            if cv.claims:
                CVStore(db).put(case.case_id, cv)
                drafter = Drafter(_project(), MODEL, MODEL_LOCATION, creds)
                clones = CVClones(db)
                for code in CLONE_INTO:
                    clones.put(case.case_id, code, drafter.clone(cv, code))
    else:
        reader = DocumentReader(_project(), MODEL, MODEL_LOCATION, creds)
        for uploaded in uploads:
            mime = MIME_BY_SUFFIX.get(Path(uploaded.filename).suffix.lower())
            if mime is None:
                continue
            data = uploaded.read()
            text, source, note = _text_for(data, mime)
            doc = reader.read(uploaded.filename, data, mime, text,
                              text_source=source, text_note=note)
            del data
            if not doc.error:
                cases.add_document(case.case_id, doc)

    return redirect("/start/places")


def _eligible_for(db, case) -> tuple[list, Any, str, str]:
    """The countries this case's own documents opened, and why.

    Returns (eligible, level reading, assumed level, why nothing) so the screen
    can explain an empty list rather than showing an empty list.
    """
    counts = _requirement_counts(db)

    if case.lane == "work":
        cv = CVStore(db).get(case.case_id)
        if cv is None:
            return [], None, "", ("We have not read a CV yet, so there is nothing to match "
                                  "against what countries say they are short of. "
                                  "Upload one, or answer five questions and we will build it.")

        roles = ([c.value for c in cv.of_kind("role")]
                 + [c.value for c in cv.of_kind("licence")])
        shortages = {code: Shortages(db).for_jurisdiction(code) for code in JURISDICTIONS}
        shortages = {k: v for k, v in shortages.items() if v}

        postings = Listings(db).counts()
        eligible = work_countries(
            roles, shortages,
            requirements={k: counts.get((k, "work"), 0) for k in JURISDICTIONS},
            postings=postings,
        )

        # A WORK COUNTRY HAS TO BE ABLE TO SHOW JOBS.
        #
        # The UK and Spain publish shortage lists we have read, so a CV can match
        # them, and neither has a job board we can read: the UK's will not serve
        # robots.txt and Spain's did not answer. Offering them here would end the
        # work path on a country with no jobs behind it, which is the one thing
        # this path promises.
        #
        # So the list is countries where the whole path works. Being told we
        # cannot help is worse news and better information than being sent to a
        # country we cannot follow through on.
        deliverable = [e for e in eligible if postings.get(e.jurisdiction)]

        if not deliverable:
            held = ", ".join(roles[:4]) or "nothing we could read"
            covered = ", ".join(
                JURISDICTIONS.get(k, {}).get("name", k)
                for k in sorted(postings) if postings[k]) or "nowhere yet"
            matched_elsewhere = [e.jurisdiction for e in eligible]
            extra = ""
            if matched_elsewhere:
                names = ", ".join(JURISDICTIONS.get(k, {}).get("name", k)
                                  for k in matched_elsewhere)
                extra = (f" {names} does publish a shortage that fits you, and we cannot read "
                         f"its job board, so we are not going to pretend we can find you work "
                         f"there.")
            return [], None, "", (
                f"Nothing we can follow through on matches {held}. We can only find real "
                f"jobs in {covered} so far.{extra} That is about how few boards we can "
                f"read, not about your trade.")
        return deliverable, None, "", ""

    # Study.
    documents = cases_documents(db, case.case_id)
    reading = level_from_documents(documents)
    assumed = next_level(reading.held) if reading.found else "bachelors"

    # WHAT THEY STUDIED, not just what level they reached. Without this the
    # subject filter received an empty list and did nothing, so a school leaver
    # was shown 1,293 bachelors courses across two countries: every course we
    # hold at their level. That is a phone book, not a shortlist, and it is the
    # exact failure this product exists to remove.
    #
    # A degree certificate names a field and is a strong signal. A school
    # certificate lists the subjects everybody sits and is a weak one, so
    # English and Mathematics are dropped before matching. Either way the screen
    # says what was taken and lets it be changed: people move field between
    # qualifications and this must not quietly hide the courses they came for.
    subjects = subjects_from_documents(documents)

    # A correction they typed beats anything we read. `assumed` is our reading of
    # a transcript; `case.level` is somebody telling us what they are actually
    # applying for, and there is no contest between those two.
    if getattr(case, "level", ""):
        assumed = case.level
    if getattr(case, "subjects", None):
        subjects = list(case.subjects)

    courses = _courses_by_country(db, assumed)
    eligible = study_countries(assumed, subjects, courses,
                               requirements={k: counts.get((k, "study"), 0)
                                             for k in JURISDICTIONS})
    # Nothing matched the subjects but the level has courses: show the level
    # rather than nothing. A missed subject match is our word overlap being
    # narrow, not the country being closed to them.
    if not eligible and subjects:
        eligible = study_countries(assumed, [], courses,
                                   requirements={k: counts.get((k, "study"), 0)
                                                 for k in JURISDICTIONS})
        subjects = []
    if not eligible:
        return [], reading, assumed, (
            "We have not read enough about individual schools yet to say which of them "
            "teach this at the level you need. That reading is under way. Nothing is "
            "shown here until it can be shown with the school's own words behind it.")
    reading.subjects = subjects
    return eligible, reading, assumed, ""


@app.get("/start/level")
def study_level() -> Response:
    """Correct the level and subject we read off the documents."""
    db, cases, case = load_case()

    documents = cases_documents(db, case.case_id)
    reading = level_from_documents(documents)
    assumed = case.level or (next_level(reading.held) if reading.found else "bachelors")
    subjects = list(case.subjects) or subjects_from_documents(documents)

    return Response(level_html(held=reading.held, assumed=assumed, subjects=subjects,
                               quote=reading.quote, filename=reading.filename),
                    mimetype="text/html")


@app.post("/start/level")
def save_study_level() -> Response:
    db, cases, case = load_case()

    level = (request.form.get("level") or "").strip().lower()
    if level not in ("bachelors", "masters", "doctorate"):
        level = ""

    # Free text, split on commas. Nothing is matched against a controlled list,
    # because a list of subjects long enough to cover what people study is
    # longer than anybody will read, and rejecting a subject we do not recognise
    # would be telling somebody their field does not exist.
    raw = request.form.get("subjects") or ""
    subjects = [s.strip() for s in raw.split(",") if s.strip()][:6]

    cases.set_study_choice(case.case_id, level, subjects)
    return redirect("/start/places")


@app.get("/start/places")
def start_places() -> Response:
    db, cases, case = load_case()

    eligible, reading, assumed, nothing = _eligible_for(db, case)
    return Response(places_html(case.lane, eligible, reading, assumed, nothing),
                    mimetype="text/html")


@app.post("/start/places")
def choose_places() -> Response:
    """Save what they picked, and let the rubric decide which is answered first.

    The primary is not the first one they ticked. Which order somebody taps
    checkboxes in carries no information about where they should start, and the
    rubric has an opinion built from what we can actually deliver.
    """
    db, cases, case = load_case()

    picked = [p.upper() for p in request.form.getlist("place") if p.upper() in JURISDICTIONS]
    if not picked:
        return redirect("/start/places")

    eligible, _reading, _assumed, _why = _eligible_for(db, case)
    mine = [e for e in eligible if e.jurisdiction in picked]

    if case.lane == "work":
        ranked = score_work(mine)
    else:
        ranked = score_study(mine)

    # The score never reaches a screen. It reaches the log, so a decision about
    # somebody's future is at least auditable by us. See migragent/rubric.py.
    for score in ranked:
        app.logger.info("rubric %s %s", case.lane, score.explain())

    primary = best(ranked) or picked[0]
    ordered = [s.jurisdiction for s in ranked] or picked
    cases.set_places(case.case_id, ordered, primary)
    return redirect("/working")


def _coverage() -> tuple[dict, int, int]:
    """What the two front pages both need: coverage per lane, and two totals."""
    def build():
        db = _db()
        extracted = _requirement_counts(db)
        return extracted, sum(extracted.values()), Registry(db).total_sources()

    return _cached("coverage", build)


@app.get("/")
def landing() -> Response:
    """What this is, for somebody who has never heard of it.

    The form is not here. It is at /start, and every call to action points
    there, so this page can be about the product rather than about a fieldset.
    """
    extracted, live, sources = _coverage()

    # ONLY COUNTRIES WHERE THE WHOLE PATH WORKS REACH THE FRONT PAGE.
    #
    # Listing a country because we have read its visa rules sends somebody down a
    # path that ends with no schools to choose from or no jobs to look at. Study
    # opens when there are courses to point at; work opens when there is a job
    # board we can read. Everything else is on /coverage with its real numbers,
    # which is a more useful answer than the words coming soon.
    db = _db()
    rows, _totals = _country_coverage(db)

    places = []
    open_lanes = 0
    for row in rows:
        lanes = []
        if row["study_ready"]:
            lanes.append("Study")
        if row["work_ready"]:
            lanes.append("Work")
        if not lanes:
            continue
        open_lanes += len(lanes)
        if row["study_ready"] and row["work_ready"]:
            note = (f'{row["courses"]:,} courses, {row["jobs"]:,} live jobs')
        elif row["study_ready"]:
            note = f'{row["courses"]:,} courses at {row["schools_read"]:,} schools'
        else:
            note = f'{row["jobs"]:,} live jobs'
        places.append((row["name"], " and ".join(lanes), note))

    waiting = len(rows) - len(places)

    return Response(landing_html(live=live, sources=sources, lanes_open=open_lanes,
                                 places=places, openings=Listings(db).total(),
                                 waiting=waiting),
                    mimetype="text/html")


def _case_or_none(cases: Cases):
    cid = request.cookies.get("migragent_case")
    return cases.get(cid) if cid else None


class _NoCase(Exception):
    """Raised by load_case when the cookie points at no case. Carries the
    response the caller wants sent instead."""

    def __init__(self, response):
        self.response = response


@app.errorhandler(_NoCase)
def _no_case(exc: _NoCase):
    return exc.response


def load_case(on_missing=None):
    """The Firestore client, the Cases store, and the current case.

    Twenty-odd handlers opened with the same five lines: build the client, build
    the store, read the cookie, bail to /start if there is no case. That is one
    call now. A handler that wants a different answer for the missing case, an
    event-stream close or a JSON error, passes it as `on_missing`.
    """
    db = _db()
    cases = Cases(db)
    case = _case_or_none(cases)
    if case is None:
        raise _NoCase(on_missing if on_missing is not None else redirect("/start"))
    return db, cases, case


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
        text, source, note = _text_for(data, mime)
        doc = reader.read(uploaded.filename, data, mime, text,
                          text_source=source, text_note=note)
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
    db, cases, case = load_case()
    # A case exists from step one now, before any country is chosen. Running it
    # in that state would build a guide for nowhere, so it goes back to the step
    # it has not finished rather than failing on an empty jurisdiction.
    if not case.ready:
        return redirect("/start/places")

    db = _db()
    documents = len(cases.documents(case.case_id))
    # The CV counts as something to read. It is stored apart from the documents
    # and the screen said "0 documents to read" to somebody who had just
    # uploaded one, which reads as the file having been lost.
    if CVStore(db).get(case.case_id) is not None:
        documents += 1
    return Response(working_html(case, documents,
                                 RunTimes(db).estimate(case.lane, documents)),
                    mimetype="text/html")


@app.get("/run-stream")
def run_stream() -> Response:
    """Server sent events, one per real step, as each one finishes."""
    db, cases, case = load_case(
        on_missing=Response(sse_done(), mimetype="text/event-stream"))

    creds = identity.credentials_for(identity.RESEARCHER, _project())
    if not case.ready:
        return Response(sse_done(), mimetype="text/event-stream")

    run = Run(
        cases=cases,
        corpus=Corpus(db),
        registry=Registry(db),
        matcher=(AgentMatcher(_project(), MODEL, MODEL_LOCATION, creds)
                 if agent_coverage_enabled()
                 else Matcher(_project(), MODEL, MODEL_LOCATION, creds)),
        finder=RouteFinder(_project(), MODEL, MODEL_LOCATION, creds),
        builder=FormBuilder(_project(), MODEL, MODEL_LOCATION, creds),
        detect_fn=detect,
        agreement_fn=agreement,
        times=RunTimes(db),
        cvs=CVStore(db),
    )
    return Response(run.stream(case), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/result")
def result() -> Response:
    """The guide, the routes, and the form only you can answer."""
    db, cases, case = load_case()
    return Response(
        result_html(case, cases.coverage(case.case_id) or {},
                    cases.result(case.case_id) or {},
                    cases.documents(case.case_id)),
        mimetype="text/html")


@app.post("/delete")
def delete_case() -> Response:
    db, cases, case = load_case(on_missing=(jsonify({"error": "no case"}), 400))
    removed = cases.delete(case.case_id)

    # Two callers, two answers. The upload screen deletes with fetch and wants
    # the counts back to show them; the dashboard deletes with a plain form and
    # wants to land somewhere. A form post that returned JSON would drop
    # somebody on a page of braces immediately after the most consequential
    # button in the product.
    wants_json = request.headers.get("X-Requested-With") == "fetch" or request.is_json
    if wants_json or "text/html" not in (request.headers.get("Accept") or ""):
        response = make_response(jsonify({"removed": removed}))
    else:
        response = make_response(redirect("/"))
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
    """The data protection notice, rendered from the document the build is held to.

    The page a person reads and the standard the code is checked against are one
    file, so they cannot drift into a promise and a practice. See data_page.py
    for why the markdown is parsed here rather than with a library.
    """
    import datetime

    path = Path(__file__).resolve().parent.parent / "docs" / "DATA_PROTECTION.md"
    if not path.exists():
        return Response("Not available.", mimetype="text/plain", status=404)

    updated = datetime.datetime.fromtimestamp(
        path.stat().st_mtime, datetime.timezone.utc).strftime("%d %B %Y")
    return Response(data_html(path.read_text(encoding="utf-8"), updated=updated),
                    mimetype="text/html")


@app.get("/architecture")
def architecture() -> Response:
    """How the thing is built, rendered from the same file the repository holds.

    Same arrangement as /data and for the same reason. A description of the
    architecture that lives only in a submission is a description nobody has to
    keep true.
    """
    import datetime

    path = Path(__file__).resolve().parent.parent / "docs" / "ARCHITECTURE.md"
    if not path.exists():
        return Response("Not available.", mimetype="text/plain", status=404)

    updated = datetime.datetime.fromtimestamp(
        path.stat().st_mtime, datetime.timezone.utc).strftime("%d %B %Y")
    return Response(architecture_html(path.read_text(encoding="utf-8"), updated=updated),
                    mimetype="text/html")


@app.get("/guide")
def guide() -> Response:
    jurisdiction = (request.args.get("jurisdiction") or "").upper()
    lane = (request.args.get("lane") or "").lower()
    if jurisdiction not in JURISDICTIONS or lane not in ("study", "work"):
        return redirect("/start")

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
    db, cases, case = load_case()

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
    db, cases, case = load_case()

    uploaded = request.files.get("cv")
    if uploaded is None or not uploaded.filename:
        return redirect("/work")

    mime = MIME_BY_SUFFIX.get(Path(uploaded.filename).suffix.lower())
    if mime is None:
        return redirect("/work")

    data = uploaded.read()
    reader = CVReader(_project(), MODEL, MODEL_LOCATION,
                      identity.credentials_for(identity.RESEARCHER, _project()))
    text, source, _note = _text_for(data, mime)
    cv = reader.read(uploaded.filename, data, mime, text, text_source=source)
    del data

    CVStore(db).put(case.case_id, cv)
    return redirect("/work")


@app.post("/fit")
def score_fit() -> Response:
    """Score the CV against one posting, from the posting's own words."""
    db, cases, case = load_case()

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
    db, cases, case = load_case()

    listing_id = request.form.get("listing") or ""
    snap = db.collection("listings").document(listing_id).get()
    if not snap.exists:
        return redirect("/work")

    fit = Fits(db).get(case.case_id, listing_id) or {}
    Board(db).add(case.case_id, snap.to_dict(), fit.get("score"))
    return redirect("/board")


@app.get("/dashboard")
def dashboard() -> Response:
    """Everything made for one person, in one place.

    Assembled from what already exists rather than from a new store: the clones,
    the board, the watch and the guide are all read where they live. A dashboard
    with its own copy of any of that would be a second version of the truth,
    drifting from the first.
    """
    db, cases, case = load_case()

    clones = CVClones(db).for_case(case.case_id)
    columns = Board(db).for_case(case.case_id)

    # The drafts written for particular jobs live on board items. Flattened here
    # with the job they were written for, so a card can say which it belongs to.
    pieces: list[dict] = []
    for items in columns.values():
        for item in items:
            for piece in getattr(item, "pieces", []):
                pieces.append({"kind": piece.kind, "title": piece.title,
                               "for": f"Written for {item.title}"
                                      f"{' at ' + item.employer if item.employer else ''}."})

    return Response(dashboard_html(
        profile=Profiles(db).get(case.case_id),
        place=JURISDICTIONS.get(case.jurisdiction, {}).get("name", case.jurisdiction),
        clones=clones,
        pieces=pieces,
        has_guide=cases.result(case.case_id) is not None,
        watch=Watches(db).get(case.case_id),
        unseen=Alerts(db).unseen_count(case.case_id),
        columns=columns,
        has_cv=CVStore(db).get(case.case_id) is not None,
        saved=request.args.get("saved", ""),
        error=request.args.get("error", ""),
    ), mimetype="text/html")


@app.post("/profile")
def save_profile() -> Response:
    """A name, an address and a picture. All optional, none of it verified.

    The picture arrives as a data URI the browser already resized. It is checked
    again here, properly, because the browser's good behaviour is a convenience
    and not a control: the prefix, the media type, the decoded size and the
    file's own magic number all have to agree before anything is stored.
    """
    db, cases, case = load_case()

    avatar = request.form.get("avatar")
    try:
        Profiles(db).save(
            case.case_id,
            name=request.form.get("name", ""),
            email=request.form.get("email", ""),
            # An empty field means "not sent" here, not "delete my picture".
            avatar=avatar if avatar else None,
        )
    except AvatarRejected as exc:
        return redirect(f"/dashboard?error={html_module.escape(str(exc))}")

    cases.touch(case.case_id)
    return redirect("/dashboard?saved=Saved.")


@app.get("/cv/new")
def cv_form() -> Response:
    """The CV builder, prefilled when there is already one to edit."""
    db, cases, case = load_case()

    profile = Profiles(db).get(case.case_id)
    cv = CVStore(db).get(case.case_id)

    answers: dict[str, str] = {}
    if cv is not None:
        for kind, _label, _hint, _many in CV_FIELDS:
            answers[kind] = "\n".join(c.value for c in cv.of_kind(kind))

    return Response(cv_builder_html(answers=answers, name=profile.name,
                                    editing=cv is not None),
                    mimetype="text/html")


@app.post("/cv/new")
def cv_create() -> Response:
    """Turn what somebody typed into the same CV an upload would have produced.

    Then clone it into each country's shape, which is the point of having it at
    all. The clones borrow the researcher, because the web identity has no model
    access of its own, and the borrowing is visible here at the point of use.
    """
    db, cases, case = load_case()

    name = request.form.get("name", "")
    answers = {kind: request.form.get(kind, "") for kind, _l, _h, _m in CV_FIELDS}
    cv = build_cv(answers, name=name)

    problem = missing_for_matching(cv)
    if problem:
        return Response(cv_builder_html(answers=answers, name=name, error=problem,
                                        editing=True), mimetype="text/html")

    CVStore(db).put(case.case_id, cv)
    if name.strip():
        Profiles(db).save(case.case_id, name=name)

    drafter = Drafter(_project(), MODEL, MODEL_LOCATION,
                      identity.credentials_for(identity.RESEARCHER, _project()))
    clones = CVClones(db)
    for code in CLONE_INTO:
        clones.put(case.case_id, code, drafter.clone(cv, code))

    cases.touch(case.case_id)
    return redirect("/dashboard?saved=Your CV is written, and shaped for three places.")


@app.get("/cv/<code>")
def read_clone(code: str) -> Response:
    """One country's version of the CV, as plain text on a plain page."""
    db, cases, case = load_case()

    clone = CVClones(db).get(case.case_id, code.upper())
    if clone is None:
        return redirect("/dashboard")

    return Response(clone_html(clone), mimetype="text/html")


def _country_coverage(db) -> tuple[list[dict], dict]:
    """What we hold per country, and the totals under it.

    Memoised for a minute by `_cached`. This walks four whole collections, and
    the landing page and the coverage page both call it. The numbers move a
    handful of times a day when the ingest job runs, so recomputing per request
    scanned the store for nothing.
    """
    return _cached("country_coverage", lambda: _country_coverage_build(db))


def _country_coverage_build(db) -> tuple[list[dict], dict]:
    import collections

    reqs = collections.Counter(_requirement_counts(db))

    schools = collections.Counter()
    for d in db.collection("institutions").select(["jurisdiction"]).stream():
        schools[d.to_dict().get("jurisdiction")] += 1
    courses = collections.Counter()
    # Schools we have actually read courses from, which is not the same as
    # schools on the register. The front page said "2,448 courses at 946
    # schools", and 946 is the size of the UK sponsor register: it implied we
    # had read every one of them when we had read 117.
    read_schools: dict[str, set] = {}
    for d in db.collection("courses").select(["jurisdiction", "institution"]).stream():
        row = d.to_dict()
        code = row.get("jurisdiction")
        courses[code] += 1
        read_schools.setdefault(code, set()).add(row.get("institution"))
    jobs = Listings(db).counts()

    rows = []
    for code, meta in JURISDICTIONS.items():
        study_reqs = reqs[(code, "study")]
        work_reqs = reqs[(code, "work")]
        rows.append({
            "code": code,
            "name": meta["name"],
            "study_reqs": study_reqs,
            "work_reqs": work_reqs,
            "schools": schools.get(code, 0),
            "schools_read": len(read_schools.get(code, ())),
            "courses": courses.get(code, 0),
            "jobs": jobs.get(code, 0),
            # A lane is open when the whole path works, not when we hold a row
            # for it. Study needs courses to point at; work needs jobs.
            "study_ready": bool(study_reqs and courses.get(code, 0)),
            "work_ready": bool(work_reqs and jobs.get(code, 0)),
        })

    rows.sort(key=lambda r: (not (r["study_ready"] or r["work_ready"]),
                             -(r["courses"] + r["jobs"]), r["name"]))
    totals = {
        "reqs": sum(reqs.values()),
        "sources": Registry(db).total_sources(),
        "schools": sum(schools.values()),
        "schools_read": sum(len(v) for v in read_schools.values()),
        "courses": sum(courses.values()),
        "jobs": sum(jobs.values()),
    }
    return rows, totals


@app.get("/coverage")
def coverage() -> Response:
    """Every country, including the empty ones. Linked from the front page."""
    rows, totals = _country_coverage(_db())
    return Response(coverage_html(rows, totals), mimetype="text/html")


@app.get("/courses")
def courses() -> Response:
    """The end of the study path: what they can actually apply to.

    Countries in rubric order, which is an opinion the page carries and never
    prints. Courses carry their gaps and a link to the school for each one, and
    intake dates are redacted for anybody who has not subscribed. Three rules,
    three modules, none of them decided here.
    """
    db, cases, case = load_case()

    eligible, reading, assumed, _why = _eligible_for(db, case)
    subjects = list(getattr(reading, "subjects", []) or []) if reading else []
    chosen = set(case.chosen) or {e.jurisdiction for e in eligible}

    ranked = score_study([e for e in eligible if e.jurisdiction in chosen])
    order = [s.jurisdiction for s in ranked] or sorted(chosen)
    for score in ranked:
        app.logger.info("rubric study %s", score.explain())

    subscriber = is_subscriber(case)
    schools = {r.get("name", ""): r
               for r in (d.to_dict() for d in
                         db.collection("institutions").stream())}

    by_country: list[tuple[str, list]] = []
    for code in order:
        rows = _courses_by_country(db, assumed).get(code, [])
        if subjects:
            from .listings import _words
            wanted = [w for s in subjects for w in _words(s)]
            rows = [r for r in rows
                    if wanted and _words(r.get("title", "")) & set(wanted)] or rows
        rows = redact_all(rows, subscriber)
        rows = with_gaps(rows, schools)
        if rows:
            by_country.append((code, rows))

    return Response(courses_html(by_country=by_country, level=assumed,
                                 subjects=subjects, subscriber=subscriber),
                    mimetype="text/html")


@app.get("/subscribe")
def subscribe() -> Response:
    db = _db()
    case = _case_or_none(Cases(db))
    lane = (case.lane if case else "study") or "study"
    profile = Profiles(db).get(case.case_id) if case else None
    return Response(subscribe_html(lane=lane,
                                   saved=request.args.get("saved", ""),
                                   email=getattr(profile, "email", "") or ""),
                    mimetype="text/html")


@app.post("/subscribe")
def subscribe_interest() -> Response:
    """Record that somebody wants this. It does not take money and says so.

    The address goes on the profile, which is deleted with the case, rather than
    into a marketing list that outlives them.
    """
    db, cases, case = load_case()

    email = (request.form.get("email") or "").strip()
    lane = (request.form.get("lane") or "study").strip()
    if email:
        Profiles(db).save(case.case_id, email=email)
        db.collection("subscribe_interest").document(case.case_id).set({
            "case_id": case.case_id,
            "lane": lane,
            "jurisdiction": case.jurisdiction,
            "at": _now_iso(),
        })
        cases.touch(case.case_id)
    return redirect("/subscribe?saved=Noted. We will write once, when billing opens.")


@app.get("/alerts")
def alerts() -> Response:
    """What moved since you last looked.

    Opening the page marks everything read, which is why the unseen flags are
    computed before `mark_seen` runs: otherwise a person's first view of an
    alert would be the view that decides it is old news.
    """
    db, cases, case = load_case()

    store = Alerts(db)
    rows = store.for_case(case.case_id)
    store.mark_seen(case.case_id)

    place = JURISDICTIONS.get(case.jurisdiction, {}).get("name", case.jurisdiction)
    return Response(alerts_html(rows, Watches(db).get(case.case_id), place),
                    mimetype="text/html")


@app.post("/watch")
def start_watch() -> Response:
    """Turn the watch on for this case. Never on by default.

    A product that starts watching somebody the moment they ask a question has
    decided something for them. This is one button, and `/watch/off` is the
    same button.
    """
    db, cases, case = load_case()
    Watches(db).start(case.case_id, case.jurisdiction, case.lane)
    cases.touch(case.case_id)
    return redirect("/alerts")


@app.post("/watch/off")
def stop_watch() -> Response:
    db, cases, case = load_case()
    Watches(db).stop(case.case_id)
    return redirect("/alerts")


@app.get("/board")
def board() -> Response:
    db, cases, case = load_case()
    return Response(board_html(Board(db).for_case(case.case_id)), mimetype="text/html")


@app.post("/board/move")
def move_item() -> Response:
    """A person moved this. Nothing else can."""
    db, cases, case = load_case()
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
    db, cases, case = load_case()

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


if __name__ == "__main__":
    # For running it on your own machine. Production is gunicorn, started by the
    # Dockerfile, and this block is not involved there. It exists because the
    # README told a stranger to run `python -m migragent.app` and nothing
    # happened, which is a worse first impression than a missing feature.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), debug=False)
