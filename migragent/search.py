"""Search across the guides and the wire.

Small enough to do in memory: a hundred-odd guides and a growing list of
articles, rebuilt every five minutes from Firestore. A query matches when every
word in it appears somewhere in a document (country names count, so "canada
study" finds Canada's study guides). Words in a title score five times words in
the body, words in the summary twice, so "skilled worker" puts the Skilled
Worker guide first, not a page that mentions it once.
"""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

from .registry import JURISDICTIONS

_INDEX: dict[str, Any] = {"at": 0.0, "docs": []}
TTL = 300
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an and are as at be by can do does for from how i in is it my of on or the to what when where who "
            "with you your".split())


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def words(text: str) -> list[str]:
    return [w for w in _WORD.findall(_fold(text)) if w not in _STOP]


def _doc(kind: str, url: str, title: str, summary: str, body: str, country: str, lane: str, date: str) -> dict[str, Any]:
    name = JURISDICTIONS.get(country, {}).get("name", country)
    return {"kind": kind, "url": url, "title": title, "summary": summary, "country": name, "lane": lane, "date": date,
            "t": set(words(title)), "s": set(words(summary)),
            "b": set(words(" ".join([body, name, country, lane])))}


def build(db) -> list[dict[str, Any]]:
    from .articles import recent
    from .guides import published

    docs = []
    for g in published(db):
        body = " ".join([p["text"] for s in g.get("sections") or [] for p in s["paragraphs"]]
                        + [s["heading"] for s in g.get("sections") or []]
                        + [f["q"] + " " + f["a"] for f in g.get("faq") or []])
        docs.append(_doc("guide", f"/guides/{g['slug']}", g.get("title", ""), g.get("dek", ""), body,
                         g.get("jurisdiction", ""), g.get("lane", ""), (g.get("updated_at") or "")[:10]))
    for a in recent(db, limit=500):
        body = " ".join([x.get("group") or x.get("text") or "" for s in ("what_changed", "who_for", "dates")
                         for x in a.get(s) or []])
        docs.append(_doc("article", f"/articles/{a['slug']}", a.get("headline", ""), a.get("dek", ""), body,
                         a.get("jurisdiction", ""), a.get("lane", ""), a.get("observed_on", "")))
    return docs


def index(db) -> list[dict[str, Any]]:
    if not _INDEX["docs"] or time.time() - _INDEX["at"] > TTL:
        _INDEX.update(at=time.time(), docs=build(db))
    return _INDEX["docs"]


def search(docs: list[dict[str, Any]], q: str, limit: int = 40) -> list[dict[str, Any]]:
    terms = words(q)[:8]
    if not terms:
        return []

    def has(d, w):
        # A prefix match, so "visa" finds "visas" and "regulari" finds "regularisation".
        return any(x.startswith(w) for x in d["t"] | d["s"] | d["b"]) if len(w) >= 4 else w in d["t"] | d["s"] | d["b"]

    def score(d):
        s = 0
        for w in terms:
            s += 5 * any(x.startswith(w) for x in d["t"]) + 2 * any(x.startswith(w) for x in d["s"]) + \
                 any(x.startswith(w) for x in d["b"])
        return s + (1 if d["kind"] == "guide" else 0)

    hits = [d for d in docs if all(has(d, w) for w in terms)]
    return sorted(hits, key=lambda d: (score(d), d["date"]), reverse=True)[:limit]
