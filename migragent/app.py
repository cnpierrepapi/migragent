"""The web application: MIGRAGENT, the immigration wire.

WHAT IT IS NOW
--------------
An AI reporter. It reads official immigration pages every morning, writes up
every rule change as an article with a report, and publishes them here. It no
longer takes anybody's case: the intake, uploads, guides, dashboards, alerts,
CV builder and the $MIGRA checkout were removed on 2 October 2026. Their old
addresses redirect to the front page so a stale link lands somewhere useful.

The one piece of the old product kept on purpose is `/tasks/sweep`, which
deletes cases past their retention window. People used the old intake and were
promised their data would be deleted on that schedule; the promise outlives
the feature.

WHO CAN DO WHAT
---------------
Runs as `migragent-web`. It cannot become the watcher, so a request cannot
start a crawl round. The admin desk can write a desk article, and for that one
call it borrows the researcher's model access, the same arrangement the old
document reader used. The desk can also add a page to the crawl list; the
crawl itself still only happens on the watcher's schedule.

Health is served at `/health` and not `/healthz`. Something in front of Cloud Run
claims that path and the application never sees it, which is rule 31.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, make_response, redirect, request, send_from_directory

from . import identity
from .architecture_page import architecture_html
from .cases import RETENTION_DAYS, Cases
from .data_page import data_html
from .landing_page import landing_html
from .registry import JURISDICTIONS, Registry
from .rounds_page import rounds_html

BRAND_DIR = Path(__file__).resolve().parent.parent / "web" / "brand"
DOCS = Path(__file__).resolve().parent.parent / "docs"

MODEL = os.environ.get("MIGRAGENT_MODEL", "gemini-3.5-flash")
MODEL_LOCATION = os.environ.get("MIGRAGENT_MODEL_LOCATION", "global")

app = Flask(__name__)
# Room for a PDF the desk uploads. Nothing else accepts a file.
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024 * 1024


def _project() -> str:
    return os.environ["GOOGLE_CLOUD_PROJECT"]


def _db():
    from google.cloud import firestore

    return firestore.Client(project=_project(),
                            credentials=identity.credentials_for(identity.WEB, _project()))


# The pages read counts off whole collections. None of them move between one
# request and the next, so the readers below are memoised for a minute.
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60.0


def _cached(key: str, build):
    hit = _CACHE.get(key)
    if hit is not None and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    value = build()
    _CACHE[key] = (time.monotonic(), value)
    return value


def _requirement_counts(db) -> dict[tuple[str, str], int]:
    """Live requirements per country and lane. The one place that counts them."""
    counts: dict[tuple[str, str], int] = {}
    for row in db.collection("requirements").select(["jurisdiction", "lane", "retired_at"]).stream():
        d = row.to_dict()
        if d.get("retired_at"):
            continue
        key = (d.get("jurisdiction", ""), d.get("lane", ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _source_stats() -> dict[str, Any]:
    """What the agent reads, per country, and the totals. Cached for a minute."""
    def build():
        import collections

        from .round import OFFERED

        db = _db()
        reqs = _requirement_counts(db)
        pages: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for d in db.collection("sources").select(
                ["jurisdiction", "lane", "url", "kind", "last_read_at", "robots_allowed",
                 "discovered_via", "title"]).stream():
            r = d.to_dict()
            pages[r.get("jurisdiction", "")].append(r)
        changes = collections.Counter()
        rules = collections.Counter()
        for d in db.collection("changes").select(["jurisdiction", "material"]).stream():
            r = d.to_dict()
            changes[r.get("jurisdiction")] += 1
            if r.get("material"):
                rules[r.get("jurisdiction")] += 1
        articles = collections.Counter()
        for d in db.collection("articles").select(["jurisdiction", "hidden"]).stream():
            r = d.to_dict()
            if not r.get("hidden"):
                articles[r.get("jurisdiction")] += 1

        rows = []
        for code, meta in JURISDICTIONS.items():
            ps = pages.get(code, [])
            rows.append({
                "code": code, "name": meta["name"], "daily": code in OFFERED,
                "pages": len(ps), "study": sum(p.get("lane") == "study" for p in ps),
                "work": sum(p.get("lane") == "work" for p in ps),
                "blocked": sum(p.get("robots_allowed") is False for p in ps),
                "requirements": reqs.get((code, "study"), 0) + reqs.get((code, "work"), 0),
                "changes": changes.get(code, 0), "rules": rules.get(code, 0),
                "articles": articles.get(code, 0),
                "last_read": max((p.get("last_read_at") or "" for p in ps), default=""),
                "urls": sorted(ps, key=lambda p: (p.get("lane", ""), p.get("url", ""))),
            })
        rows.sort(key=lambda r: (not r["daily"], -r["pages"], r["name"]))
        totals = {
            "pages": sum(r["pages"] for r in rows),
            "countries": sum(1 for r in rows if r["pages"]),
            "daily": sum(1 for r in rows if r["daily"]),
            "requirements": sum(r["requirements"] for r in rows),
            "rules": sum(r["rules"] for r in rows),
            "articles": sum(r["articles"] for r in rows),
        }
        return {"rows": rows, "totals": totals}

    return _cached("source_stats", build)


# --- the wire -------------------------------------------------------------------

@app.get("/health")
def health() -> Response:
    return Response("ok", mimetype="text/plain")


@app.get("/brand/<path:name>")
def brand(name: str) -> Response:
    return send_from_directory(BRAND_DIR, name)


@app.get("/")
def landing() -> Response:
    from .articles import recent

    stats = _source_stats()
    try:
        filed = recent(_db(), limit=6)
    except Exception:  # noqa: BLE001
        # The front page must not fall over because the wire has a bad moment.
        filed = []
    return Response(landing_html(stats=stats, articles=filed), mimetype="text/html")


@app.get("/articles")
def articles_index() -> Response:
    """The wire. Articles the agent wrote, newest change first. See migragent/articles.py."""
    from .articles import recent
    from .articles_page import index_html

    return Response(index_html(recent(_db(), limit=120)), mimetype="text/html")


@app.get("/articles/<slug>")
def article(slug: str) -> Response:
    from .articles import by_slug
    from .articles_page import article_html

    found = by_slug(_db(), slug)
    if not found or found.get("hidden"):
        return redirect("/articles")
    return Response(article_html(found), mimetype="text/html")


@app.get("/api/state")
def live_state() -> Response:
    """What the agent is doing, polled by the front page. See migragent/live.py."""
    from . import live

    response = jsonify(live.state(_db(), _source_stats()["totals"]["requirements"]))
    response.headers["Cache-Control"] = "public, max-age=15"
    return response


@app.get("/sources")
def sources() -> Response:
    """Every country and every page the agent reads, from the registry itself."""
    from .sources_page import sources_html

    return Response(sources_html(_source_stats()), mimetype="text/html")


@app.get("/rounds")
def rounds() -> Response:
    """What the reading job has been doing, off the rows the job itself wrote."""
    from .round import ChangeWriter, RunLog

    def build():
        db = _db()
        recent_rounds = RunLog(db).recent(limit=24)
        changes: list = []
        writer = ChangeWriter(db)
        for code in sorted({r.get("jurisdiction", "") for r in recent_rounds} - {""}):
            changes.extend(writer.for_jurisdiction(code, limit=6))
        changes.sort(key=lambda c: c.get("after_read_at", ""), reverse=True)
        counts = Registry(db).counts()
        requirements = sum(_requirement_counts(db).values())
        return recent_rounds, changes[:10], counts, requirements

    recent_rounds, changes, counts, requirements = _cached("rounds", build)
    return Response(rounds_html(recent_rounds, changes, sources=counts.get("total", 0),
                                read_sources=counts.get("readable", 0), requirements=requirements),
                    mimetype="text/html")


@app.get("/migra")
def migra() -> Response:
    """$MIGRA: what the token does for the reporter. No checkout; nothing is sold here."""
    from .migra_page import migra_html

    return Response(migra_html(), mimetype="text/html")


def _doc_page(name: str, render) -> Response:
    import datetime

    path = DOCS / name
    if not path.exists():
        return Response("Not available.", mimetype="text/plain", status=404)
    updated = datetime.datetime.fromtimestamp(
        path.stat().st_mtime, datetime.timezone.utc).strftime("%d %B %Y")
    return Response(render(path.read_text(encoding="utf-8"), updated=updated), mimetype="text/html")


@app.get("/data")
def data_protection() -> Response:
    """The data notice, rendered from the document the build is held to."""
    return _doc_page("DATA_PROTECTION.md", data_html)


@app.get("/architecture")
def architecture() -> Response:
    """How it is built, rendered from the same file the repository holds."""
    return _doc_page("ARCHITECTURE.md", architecture_html)


# Addresses the old case product used. Each lands on the closest page that still
# exists rather than a 404, because links to them are out there.
LEGACY = {
    "/coverage": "/sources", "/subscribe": "/migra", "/start": "/", "/start/documents": "/",
    "/start/level": "/", "/start/places": "/", "/working": "/", "/result": "/", "/guide": "/",
    "/work": "/", "/dashboard": "/", "/courses": "/", "/alerts": "/", "/board": "/",
    "/cv/new": "/", "/credits": "/migra",
}
for _old, _new in LEGACY.items():
    app.add_url_rule(_old, f"legacy_{_old}", (lambda to=_new: redirect(to, code=301)),
                     methods=["GET", "POST"])


@app.route("/cv/<path:_rest>", methods=["GET", "POST"])
@app.route("/wallet/<path:_rest>", methods=["GET", "POST"])
@app.route("/credits/<path:_rest>", methods=["GET", "POST"])
@app.route("/board/<path:_rest>", methods=["GET", "POST"])
@app.route("/start/<path:_rest>", methods=["POST"])
def legacy_tree(_rest: str) -> Response:
    return redirect("/", code=301)


@app.post("/delete")
def delete_case() -> Response:
    """Delete an old case now, for anybody whose browser still holds its cookie.

    The case product is gone, but people who used it were promised they could
    delete everything at any time, not only when the retention window closes.
    The button for this is on /data.
    """
    cid = request.cookies.get("migragent_case")
    removed = Cases(_db()).delete(cid) if cid else {}
    resp = make_response(redirect("/data?deleted=" + ("1" if removed.get("case") else "0")))
    resp.delete_cookie("migragent_case")
    return resp


for _gone in ("/begin", "/run-stream", "/fit", "/interested", "/profile", "/watch", "/watch/off", "/cv"):
    app.add_url_rule(_gone, f"gone_{_gone}", (lambda: redirect("/", code=301)), methods=["GET", "POST"])


@app.post("/tasks/sweep")
def sweep() -> Response:
    """Delete old cases past their retention date. Called by Cloud Scheduler.

    Kept after the case product was removed: people who used it were told their
    data goes on this schedule. Cloud Run requires an authenticated invoker for
    this path; the token below is the second lock.
    """
    expected = os.environ.get("MIGRAGENT_TASK_TOKEN", "")
    if not expected or request.headers.get("X-Migragent-Task") != expected:
        return jsonify({"error": "not authorised"}), 403
    swept = Cases(_db()).sweep()
    return jsonify({"swept": swept, "retention_days": RETENTION_DAYS})


# --- the admin desk ---------------------------------------------------------------
#
# One person signs in with the admin key, which lives in Secret Manager and
# reaches this service as MIGRAGENT_ADMIN_KEY. Without it the desk does not
# exist. The session is a cookie signed with that key, HttpOnly, Secure and
# SameSite=Strict, good for twelve hours; every form also carries a token
# derived from the session, and five wrong keys from one address in fifteen
# minutes locks that address out for the rest of the window.

SESSION_COOKIE = "mg_desk"
SESSION_SECONDS = 12 * 3600
_failures: dict[str, list[float]] = {}


def _admin_key() -> str:
    return os.environ.get("MIGRAGENT_ADMIN_KEY", "").strip()


def _signer():
    from itsdangerous import URLSafeTimedSerializer

    return URLSafeTimedSerializer(_admin_key(), salt="migragent-desk")


def _session() -> str | None:
    """The session value if the cookie is genuine and fresh, else None."""
    raw = request.cookies.get(SESSION_COOKIE, "")
    if not raw or not _admin_key():
        return None
    try:
        _signer().loads(raw, max_age=SESSION_SECONDS)
    except Exception:  # noqa: BLE001
        return None
    return raw


def _csrf(session: str) -> str:
    return hmac.new(_admin_key().encode(), session.encode(), hashlib.sha256).hexdigest()


def _client_ip() -> str:
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "?")


def _locked_out(ip: str) -> bool:
    now = time.time()
    _failures[ip] = [t for t in _failures.get(ip, []) if now - t < 900]
    return len(_failures[ip]) >= 5


def _desk_guard():
    """(session, None) for a signed-in desk and a valid form; (None, response) otherwise."""
    session = _session()
    if not session:
        return None, redirect("/admin")
    if request.method == "POST" and not hmac.compare_digest(request.form.get("csrf", ""), _csrf(session)):
        return None, Response("That form had expired. Go back and try again.", status=400)
    return session, None


@app.get("/admin")
def admin() -> Response:
    from .admin_page import desk_html, login_html

    if not _admin_key():
        return Response(login_html(disabled=True), mimetype="text/html", status=503)
    session = _session()
    if not session:
        return Response(login_html(message=request.args.get("m", "")), mimetype="text/html")
    from .articles import ARTICLES, SKIPPED
    from google.cloud import firestore

    db = _db()
    subs = [d.to_dict() for d in db.collection("desk_submissions")
            .order_by("submitted_at", direction=firestore.Query.DESCENDING).limit(25).stream()]
    arts = [d.to_dict() for d in db.collection(ARTICLES)
            .order_by("observed_on", direction=firestore.Query.DESCENDING).limit(60).stream()]
    skips = [{**d.to_dict(), "id": d.id} for d in db.collection(SKIPPED).limit(30).stream()]
    resp = make_response(desk_html(csrf=_csrf(session), submissions=subs, articles=arts, skips=skips,
                                   stats=_source_stats(), message=request.args.get("m", "")))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/admin/login")
def admin_login() -> Response:
    key = _admin_key()
    ip = _client_ip()
    if not key:
        return redirect("/admin")
    if _locked_out(ip):
        return redirect("/admin?m=Too many wrong keys. Try again in fifteen minutes.")
    if not hmac.compare_digest(request.form.get("key", "").strip(), key):
        _failures.setdefault(ip, []).append(time.time())
        return redirect("/admin?m=That key is not right.")
    _failures.pop(ip, None)
    resp = make_response(redirect("/admin"))
    resp.set_cookie(SESSION_COOKIE, _signer().dumps({"n": secrets.token_hex(8)}), max_age=SESSION_SECONDS,
                    httponly=True, secure=True, samesite="Strict", path="/")
    return resp


@app.post("/admin/logout")
def admin_logout() -> Response:
    resp = make_response(redirect("/admin?m=Signed out."))
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


def _desk_text(upload) -> tuple[str, str]:
    """Text from an uploaded PDF or image, and how it was got. ("", "") for none."""
    if not upload or not upload.filename:
        return "", ""
    from .documents import MIME_BY_SUFFIX, extract_text

    suffix = Path(upload.filename).suffix.lower()
    mime = MIME_BY_SUFFIX.get(suffix, "")
    data = upload.read()
    if not data:
        return "", ""
    text = extract_text(data, mime) if mime else ""
    if text:
        return text, f"text layer of {upload.filename}"
    from .ocr import OCR, can_read

    if mime and can_read(mime):
        ocr_text, _note = OCR(identity.credentials_for(identity.RESEARCHER, _project())).read(data, mime)
        if ocr_text:
            return ocr_text, f"OCR of {upload.filename}"
    return "", ""


@app.post("/admin/filing")
def admin_filing() -> Response:
    """A filing by hand: a page the crawl cannot read, a PDF, an announcement."""
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    from datetime import datetime, timezone

    from .articles import Writer

    url = (request.form.get("url") or "").strip()
    code = request.form.get("jurisdiction", "")
    lane = request.form.get("lane", "")
    if not url.startswith("https://") or code not in JURISDICTIONS or lane not in ("study", "work"):
        return redirect("/admin?m=A filing needs an https source URL, a country and a lane.")

    pasted = (request.form.get("text") or "").strip()
    from_file, how_file = _desk_text(request.files.get("file"))
    text = "\n\n".join(t for t in (pasted, from_file) if t)[:200_000]
    how = " and ".join(h for h in ("pasted text" if pasted else "", how_file) if h) or "nothing"

    sub = {"id": secrets.token_hex(8), "url": url, "jurisdiction": code, "lane": lane,
           "observed_on": (request.form.get("observed_on") or "")[:10],
           "title": (request.form.get("title") or "").strip()[:200],
           "note": (request.form.get("note") or "").strip()[:500], "how": how, "text": text,
           "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "writing"}
    db = _db()
    ref = db.collection("desk_submissions").document(sub["id"])
    ref.set(sub)
    writer = Writer(db, None, _project(), MODEL, MODEL_LOCATION,
                    identity.credentials_for(identity.RESEARCHER, _project()), pause=0)
    try:
        outcome = writer.write_desk(sub)
    except Exception as exc:  # noqa: BLE001
        ref.update({"status": "failed", "outcome": f"{type(exc).__name__}: {exc}"[:300]})
        return redirect("/admin?m=The model call failed; the submission is saved. Try again later.")
    if "written" in outcome:
        ref.update({"status": "published", "article_slug": outcome["written"]})
        _CACHE.clear()
        return redirect(f"/admin?m=Published: /articles/{outcome['written']}")
    ref.update({"status": "not published", "outcome": outcome["skipped"]})
    return redirect(f"/admin?m=Not published: {outcome['skipped']}")


@app.post("/admin/source")
def admin_source() -> Response:
    """Add a page to the crawl list. The watcher reads it on its next round."""
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    from .registry import Source, source_id

    url = (request.form.get("url") or "").strip()
    code = request.form.get("jurisdiction", "")
    lane = request.form.get("lane", "")
    if not url.startswith("https://") or code not in JURISDICTIONS or lane not in ("study", "work"):
        return redirect("/admin?m=A page needs an https URL, a country and a lane.")
    reg = Registry(_db())
    if reg.by_url(code, lane, url):
        return redirect("/admin?m=That page is already on the crawl list.")
    reg.put(Source(source_id=source_id(code, lane, url), jurisdiction=code, lane=lane,
                   kind="government", url=url, title=(request.form.get("title") or "").strip()[:200],
                   language=JURISDICTIONS[code]["languages"][0], discovered_via="desk"))
    _CACHE.clear()
    return redirect("/admin?m=Added to the crawl list. It is read on the next round for that country.")


@app.post("/admin/article/<aid>/<action>")
def admin_article(aid: str, action: str) -> Response:
    """Hide an article from the wire, or put it back. Nothing is deleted."""
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    if action not in ("hide", "show"):
        return redirect("/admin")
    from .articles import ARTICLES

    _db().collection(ARTICLES).document(aid).update({"hidden": action == "hide"})
    _CACHE.clear()
    return redirect(f"/admin?m={'Hidden' if action == 'hide' else 'Back on the wire'}.")
