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


def _signup_box(path: str, country: str = "") -> str:
    """The alerts box, showing the outcome of a signup that just came back to this page."""
    from .signup import box

    return box(path, country=country, message=request.args.get("signup_error", ""),
               leave_token=request.args.get("joined", ""))


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
    return Response(landing_html(stats=stats, articles=filed, signup=_signup_box("/")), mimetype="text/html")


@app.get("/articles")
def articles_index() -> Response:
    """The wire. Articles the agent wrote, newest change first. See migragent/articles.py."""
    from .articles import recent
    from .articles_page import index_html

    return Response(index_html(recent(_db(), limit=120), signup=_signup_box("/articles")), mimetype="text/html")


@app.get("/articles/<slug>")
def article(slug: str) -> Response:
    from .articles import by_slug
    from .articles_page import article_html

    found = by_slug(_db(), slug)
    if not found or found.get("hidden"):
        return redirect("/articles")
    return Response(article_html(found, signup=_signup_box(f"/articles/{slug}", found.get("jurisdiction", ""))),
                    mimetype="text/html")


@app.get("/search")
def search_page() -> Response:
    from .search import index, search
    from .search_page import search_html

    q = (request.args.get("q") or "").strip()[:120]
    hits = search(index(_db()), q) if q else []
    return Response(search_html(q, hits), mimetype="text/html")


@app.get("/guides")
def guides_index() -> Response:
    from .guides import published
    from .guides_page import index_html

    return Response(index_html(_cached("guides", lambda: published(_db())), signup=_signup_box("/guides")),
                    mimetype="text/html")


@app.get("/guides/<slug>")
def guide(slug: str) -> Response:
    from .guides import affiliates, by_slug
    from .guides_page import guide_html

    found = by_slug(_db(), slug)
    if not found or found.get("hidden"):
        return redirect("/guides")
    return Response(guide_html(found, _cached("affiliates", lambda: affiliates(_db())),
                               signup=_signup_box(f"/guides/{slug}", found.get("jurisdiction", ""))),
                    mimetype="text/html")


@app.get("/api/state")
def live_state() -> Response:
    """What the agent is doing, polled by the front page. See migragent/live.py."""
    from . import live

    response = jsonify(live.state(_db(), _source_stats()["totals"]["requirements"]))
    response.headers["Cache-Control"] = "public, max-age=15"
    return response


@app.post("/alerts/signup")
def alerts_signup() -> Response:
    """Put a reader on the alerts list. See migragent/signup.py."""
    from urllib.parse import quote

    from .signup import save

    back = request.form.get("path") or "/articles"
    if not back.startswith("/") or back.startswith("//"):
        back = "/articles"
    ok, value = save(_db(), request.form, back)
    if not ok and value == "bot":
        return redirect(back)
    sep = "&" if "?" in back else "?"
    target = f"{back}{sep}{'joined=' + quote(value) if ok else 'signup_error=' + quote(value)}#alerts"
    return redirect(target)


@app.get("/alerts/leave")
def alerts_leave() -> Response:
    from .signup import leave

    gone = leave(_db(), request.args.get("t", ""))
    return Response(
        f'<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
        f'<title>MIGRAGENT</title><p style="font:1.1rem Georgia,serif;max-width:40em;margin:4em auto">'
        f'{"Done. Your email is deleted from the alerts list." if gone else "That link has already been used, or it is not ours."}'
        f' <a href="/">Back to the wire</a></p>', mimetype="text/html")


# --- The Desk: reservations with a Paystack deposit ---------------------------------------
#
# See migragent/desk_page.py. The key is PAYSTACK_SECRET_KEY, from Secret Manager.
# Nothing is marked paid on the browser's word: the server asks Paystack.

PAYSTACK = "https://api.paystack.co"


def _paystack_key() -> str:
    return os.environ.get("PAYSTACK_SECRET_KEY", "").strip()


def _paystack(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    import json
    import urllib.request

    req = urllib.request.Request(PAYSTACK + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {_paystack_key()}",
                                          "Content-Type": "application/json", "User-Agent": "migragent"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _mark_paid(reference: str, data: dict[str, Any]) -> bool:
    """Paid only if Paystack says success, for the deposit amount, in naira."""
    from .desk_page import DEPOSIT_KOBO, RESERVATIONS

    ok = (data.get("status") == "success" and int(data.get("amount") or 0) == DEPOSIT_KOBO
          and data.get("currency") == "NGN")
    ref = _db().collection(RESERVATIONS).document(reference)
    if ok and ref.get().exists:
        ref.update({"status": "paid", "paid_at": data.get("paid_at") or "", "channel": data.get("channel") or ""})
    return ok


@app.get("/desk")
def desk() -> Response:
    from .desk_page import desk_html

    m = request.args.get("m", "")
    return Response(desk_html(live=bool(_paystack_key()), message=m, bad=bool(request.args.get("bad"))),
                    mimetype="text/html")


@app.post("/desk/reserve")
def desk_reserve() -> Response:
    import re
    from datetime import datetime, timezone

    from .desk_page import DEPOSIT_KOBO, PLANS, RESERVATIONS
    from .seo import SITE

    if (request.form.get("website") or "").strip():
        return redirect("/desk")
    email = (request.form.get("email") or "").strip().lower()
    plan = request.form.get("plan", "")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,24}$", email, re.I) or plan not in {k for k, *_ in PLANS}:
        return redirect("/desk?bad=1&m=Check the email address and pick a plan.")
    reference = "desk-" + secrets.token_hex(8)
    row = {"reference": reference, "email": email, "plan": plan,
           "name": (request.form.get("name") or "").strip()[:120],
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "status": "waitlist" if not _paystack_key() else "pending"}
    _db().collection(RESERVATIONS).document(reference).set(row)
    if not _paystack_key():
        return redirect("/desk?m=You're on the waitlist. We'll email you when reservations open.")
    try:
        out = _paystack("POST", "/transaction/initialize", {
            "email": email, "amount": DEPOSIT_KOBO, "currency": "NGN", "reference": reference,
            "callback_url": f"{SITE}/desk/thanks", "metadata": {"plan": plan, "product": "migragent-desk"}})
        url = (out.get("data") or {}).get("authorization_url")
    except Exception:  # noqa: BLE001
        url = None
    if not url:
        return redirect("/desk?bad=1&m=Paystack didn't answer. Nothing was charged; try again in a minute.")
    return redirect(url)


@app.get("/desk/thanks")
def desk_thanks() -> Response:
    from .desk_page import RESERVATIONS, thanks_html

    reference = request.args.get("reference", "")
    paid, plan = False, ""
    if reference.startswith("desk-") and _paystack_key():
        try:
            data = _paystack("GET", f"/transaction/verify/{reference}").get("data") or {}
            paid = _mark_paid(reference, data)
        except Exception:  # noqa: BLE001
            paid = False
        snap = _db().collection(RESERVATIONS).document(reference).get()
        plan = (snap.to_dict() or {}).get("plan", "") if snap.exists else ""
    return Response(thanks_html(paid, plan), mimetype="text/html")


@app.post("/paystack/webhook")
def paystack_webhook() -> Response:
    """Paystack's own word, signed with the secret key, for payments whose browser never came back."""
    import json

    key = _paystack_key()
    raw = request.get_data()
    sig = request.headers.get("x-paystack-signature", "")
    if not key or not hmac.compare_digest(sig, hmac.new(key.encode(), raw, hashlib.sha512).hexdigest()):
        return Response("", status=401)
    event = json.loads(raw or b"{}")
    data = event.get("data") or {}
    if event.get("event") == "charge.success" and str(data.get("reference", "")).startswith("desk-"):
        # Ask Paystack again rather than trusting the event body alone.
        try:
            _mark_paid(data["reference"], _paystack("GET", f"/transaction/verify/{data['reference']}").get("data") or {})
        except Exception:  # noqa: BLE001
            pass
    return Response("", status=200)


@app.get("/robots.txt")
def robots_txt() -> Response:
    from .seo import SITE

    body = ("User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nDisallow: /tasks/\n"
            "Disallow: /delete\n\n"
            f"Sitemap: {SITE}/sitemap.xml\nSitemap: {SITE}/news-sitemap.xml\n")
    return Response(body, mimetype="text/plain")


def _xml(s: Any) -> str:
    from xml.sax.saxutils import escape

    return escape(str(s or ""))


@app.get("/sitemap.xml")
def sitemap() -> Response:
    """Every public page and every article, with the date it last changed."""
    from .articles import recent
    from .seo import SITE

    urls = [("/", "daily"), ("/articles", "daily"), ("/sources", "weekly"), ("/rounds", "daily"),
            ("/migra", "weekly"), ("/architecture", "monthly"), ("/data", "monthly"),
            ("/desk", "weekly"), ("/guides", "weekly")]
    items = [f"<url><loc>{SITE}{p}</loc><changefreq>{f}</changefreq></url>" for p, f in urls]
    for a in recent(_db(), limit=1000):
        items.append(f"<url><loc>{SITE}/articles/{_xml(a.get('slug'))}</loc>"
                     f"<lastmod>{_xml((a.get('published_at') or a.get('observed_on') or '')[:10])}</lastmod></url>")
    try:
        from .guides import published as published_guides

        for g in published_guides(_db()):
            items.append(f"<url><loc>{SITE}/guides/{_xml(g.get('slug'))}</loc>"
                         f"<lastmod>{_xml((g.get('updated_at') or '')[:10])}</lastmod></url>")
    except Exception:  # noqa: BLE001
        pass
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(items) + "</urlset>")
    return Response(body, mimetype="application/xml")


@app.get("/news-sitemap.xml")
def news_sitemap() -> Response:
    """Google News: only articles written in the last two days, as Google asks."""
    from datetime import datetime, timedelta, timezone

    from .articles import recent
    from .seo import SITE

    since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    items = []
    for a in recent(_db(), limit=200):
        if (a.get("published_at") or "") < since:
            continue
        items.append(
            f"<url><loc>{SITE}/articles/{_xml(a.get('slug'))}</loc><news:news>"
            "<news:publication><news:name>MIGRAGENT</news:name><news:language>en</news:language></news:publication>"
            f"<news:publication_date>{_xml(a.get('published_at'))}</news:publication_date>"
            f"<news:title>{_xml(a.get('headline'))}</news:title></news:news></url>")
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">' + "".join(items) + "</urlset>")
    return Response(body, mimetype="application/xml")


@app.get("/feed.xml")
def feed() -> Response:
    """The wire as RSS, newest change first."""
    from email.utils import format_datetime
    from datetime import datetime, timezone

    from .articles import recent
    from .seo import SITE

    def rfc822(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            return ""
        return format_datetime(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))

    items = "".join(
        f"<item><title>{_xml(a.get('headline'))}</title><link>{SITE}/articles/{_xml(a.get('slug'))}</link>"
        f"<guid isPermaLink=\"true\">{SITE}/articles/{_xml(a.get('slug'))}</guid>"
        f"<pubDate>{rfc822(a.get('published_at') or '')}</pubDate><description>{_xml(a.get('dek'))}</description></item>"
        for a in recent(_db(), limit=50))
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>MIGRAGENT, the wire</title>'
            f"<link>{SITE}/articles</link><description>Immigration rule changes, written up by an AI agent "
            f"that reads the official pages every morning.</description><language>en</language>{items}</channel></rss>")
    return Response(body, mimetype="application/rss+xml")


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


@app.get("/migra/vote")
def vote_page() -> Response:
    from .governance import proposals, tally
    from .vote_page import vote_html

    db = _db()
    items = [(p, _cached(f"tally-{p['id']}", lambda p=p: tally(db, p))) for p in proposals(db)]
    return Response(vote_html(items), mimetype="text/html")


@app.post("/migra/vote")
def vote_cast() -> Response:
    from .governance import cast

    body = request.get_json(silent=True) or {}
    why = cast(_db(), str(body.get("proposal", "")), str(body.get("option", "")),
               str(body.get("wallet", "")), str(body.get("signature", "")))
    if why:
        return jsonify({"error": why}), 400
    _CACHE.pop(f"tally-{body.get('proposal')}", None)
    return jsonify({"ok": True})


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
    from .desk_page import RESERVATIONS
    from .guides import AFFILIATES, GUIDES
    from .signup import SUBSCRIBERS

    signups: dict[str, int] = {}
    for d in db.collection(SUBSCRIBERS).select(["role"]).stream():
        role = (d.to_dict() or {}).get("role", "other")
        signups[role] = signups.get(role, 0) + 1
    reservations = [d.to_dict() for d in db.collection(RESERVATIONS)
                    .order_by("at", direction=firestore.Query.DESCENDING).limit(50).stream()]
    guides = sorted((d.to_dict() for d in db.collection(GUIDES).stream()),
                    key=lambda g: (g.get("jurisdiction", ""), g.get("title", "")))
    affs = [{**d.to_dict(), "id": d.id} for d in db.collection(AFFILIATES).stream()]
    resp = make_response(desk_html(csrf=_csrf(session), submissions=subs, articles=arts, skips=skips,
                                   stats=_source_stats(), message=request.args.get("m", ""),
                                   guides=guides, affiliates=affs, signups=signups, reservations=reservations))
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


@app.post("/admin/proposal")
def admin_proposal() -> Response:
    """Put a question to $MIGRA holders."""
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    from .governance import create

    title = (request.form.get("title") or "").strip()
    question = (request.form.get("question") or "").strip()
    options = [o.strip() for o in (request.form.get("options") or "").split(",") if o.strip()]
    try:
        days = int(request.form.get("days") or 7)
    except ValueError:
        days = 7
    if not title or len(options) < 2:
        return redirect("/admin?m=A vote needs a title and at least two options, separated by commas.")
    pid = create(_db(), title, question, options, days)
    return redirect(f"/admin?m=Vote {pid} is open at /migra/vote.")


@app.post("/admin/affiliate")
def admin_affiliate() -> Response:
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    from .guides import AFFILIATES, TOPICS

    url = (request.form.get("url") or "").strip()
    topic = request.form.get("topic", "")
    name = (request.form.get("name") or "").strip()[:80]
    if not url.startswith("https://") or topic not in TOPICS or not name:
        return redirect("/admin?m=An affiliate link needs a topic, a name and an https URL.")
    countries = [c.strip().upper() for c in (request.form.get("countries") or "").split(",")
                 if c.strip().upper() in JURISDICTIONS]
    _db().collection(AFFILIATES).document(secrets.token_hex(6)).set(
        {"topic": topic, "name": name, "url": url, "blurb": (request.form.get("blurb") or "").strip()[:160],
         "countries": countries, "active": True})
    _CACHE.clear()
    return redirect("/admin?m=Affiliate link added.")


@app.post("/admin/affiliate/<aff_id>/remove")
def admin_affiliate_remove(aff_id: str) -> Response:
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    from .guides import AFFILIATES

    _db().collection(AFFILIATES).document(aff_id).delete()
    _CACHE.clear()
    return redirect("/admin?m=Affiliate link removed.")


@app.post("/admin/guide/<gid>/<action>")
def admin_guide(gid: str, action: str) -> Response:
    _session_value, refused = _desk_guard()
    if refused:
        return refused
    if action not in ("hide", "show"):
        return redirect("/admin")
    from .guides import GUIDES

    _db().collection(GUIDES).document(gid).update({"hidden": action == "hide"})
    _CACHE.clear()
    return redirect(f"/admin?m=Guide {'hidden' if action == 'hide' else 'back up'}.")


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
