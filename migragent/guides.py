"""Guides: evergreen pages for search, built only from requirements we can cite.

WHAT A GUIDE IS
---------------
One official page, explained. "UK Skilled Worker visa: requirements, documents
and costs" is what people type into a search box, and the answer is already in
the corpus: every requirement extracted from that page, each with the verbatim
sentence it came from, checked when it was read.

So a guide is written from those requirements and nothing else. Every
paragraph, checklist line and FAQ answer has to cite requirement ids from that
page; the code drops anything that cites nothing or cites an id it was not
given, and the guide page shows each citation with its quote and a link. The
house voice from migragent/voice.py applies, with one rewrite for any line that
breaks it and a drop if the rewrite still does.

WHEN IT IS WRITTEN
------------------
By the `guides` worker mode, weekly. A guide is only rewritten when the set of
requirements behind it changed, so a quiet week costs nothing. Public text
only, so it may go through Orbio.

AFFILIATES
----------
A guide names which topics a reader would need next (an English test, moving
money, health insurance). The page shows an affiliate box for a topic only if
the editor has added a real link for it, always labelled as an affiliate link.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from .articles import slugify
from .voice import RULES as VOICE_RULES
from .voice import hits as voice_hits
from .voice import tidy

GUIDES = "guides"
AFFILIATES = "affiliates"
MIN_REQUIREMENTS = 10
MAX_REQUIREMENTS = 140

TOPICS = {
    "english_test": "An English test",
    "money_transfer": "Moving money abroad",
    "proof_of_funds": "Showing funds",
    "health_insurance": "Health insurance",
    "student_loan": "Paying for study",
    "accommodation": "Somewhere to live",
    "flights": "Flights",
    "documents": "Translating and certifying documents",
}

PROMPT = """You are writing an evergreen guide for MIGRAGENT, an immigration site, about ONE
official government page. You are given the requirements extracted from that page, each with
an id. Write a guide a person could follow, using only those requirements.

Return JSON only:
{
  "title": "search-friendly, under 60 characters, names the country and the visa or route, e.g. 'UK Skilled Worker visa: requirements and costs'",
  "dek": "one plain sentence on who this route is for",
  "sections": [{"heading": "...", "paragraphs": [{"text": "...", "cites": ["id", "..."]}]}],
  "checklist": [{"item": "...", "cites": ["id"]}],
  "faq": [{"q": "a question people actually search for", "a": "...", "cites": ["id"]}],
  "topics": ["english_test", "money_transfer", "proof_of_funds", "health_insurance", "student_loan",
             "accommodation", "flights", "documents"]
}

Rules:
- Every paragraph, checklist item and FAQ answer must cite at least one requirement id from the
  list, and say only what those requirements say. Never cite an id that is not in the list.
- Sections in a useful order: who can apply, what you need to show, documents, costs and money,
  timing, after you arrive. Skip a section if no requirement supports it.
- 4 to 8 FAQ entries, phrased the way people search ("How much money do I need for ...").
- "topics": only the ones a reader of this guide would genuinely need next. Can be empty.
- Write in English whatever the page's language.
""" + VOICE_RULES + "\nREQUIREMENTS:\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def candidates(db, min_reqs: int = MIN_REQUIREMENTS) -> list[dict[str, Any]]:
    """One candidate per official page with enough live requirements to explain."""
    pages: dict[str, dict[str, Any]] = {}
    for d in db.collection("requirements").stream():
        r = d.to_dict()
        if r.get("retired_at") or not r.get("source_url"):
            continue
        p = pages.setdefault(r["source_url"], {"source_url": r["source_url"], "jurisdiction": r.get("jurisdiction"),
                                               "lane": r.get("lane"), "source_id": r.get("source_id"), "reqs": []})
        p["reqs"].append({"id": d.id, "text": r.get("text", ""), "quote": r.get("quote", ""),
                          "category": r.get("category", "")})
    out = []
    for p in pages.values():
        if len(p["reqs"]) < min_reqs:
            continue
        p["reqs"] = sorted(p["reqs"], key=lambda x: x["id"])[:MAX_REQUIREMENTS]
        p["fingerprint"] = hashlib.sha256("|".join(f'{x["id"]}:{x["text"]}' for x in p["reqs"]).encode()).hexdigest()[:20]
        p["guide_id"] = hashlib.sha256(p["source_url"].encode()).hexdigest()[:16]
        out.append(p)
    return sorted(out, key=lambda p: -len(p["reqs"]))


def _cited(cites: Any, known: set[str]) -> list[str]:
    return [c for c in (cites or []) if isinstance(c, str) and c in known]


def validate(parsed: dict[str, Any], known: set[str]) -> tuple[dict[str, Any], int, int]:
    """Keep only content that cites requirements we gave it. Returns (guide, kept, dropped)."""
    kept = dropped = 0
    sections = []
    for sec in parsed.get("sections") or []:
        paras = []
        for para in sec.get("paragraphs") or []:
            cites = _cited(para.get("cites"), known)
            if para.get("text") and cites:
                paras.append({"text": tidy(str(para["text"])), "cites": cites})
                kept += 1
            else:
                dropped += 1
        if paras and sec.get("heading"):
            sections.append({"heading": tidy(str(sec["heading"])), "paragraphs": paras})
    checklist, faq = [], []
    for it in parsed.get("checklist") or []:
        cites = _cited(it.get("cites"), known)
        if it.get("item") and cites:
            checklist.append({"item": tidy(str(it["item"])), "cites": cites}); kept += 1
        else:
            dropped += 1
    for it in parsed.get("faq") or []:
        cites = _cited(it.get("cites"), known)
        if it.get("q") and it.get("a") and cites:
            faq.append({"q": tidy(str(it["q"])), "a": tidy(str(it["a"])), "cites": cites}); kept += 1
        else:
            dropped += 1
    topics = [t for t in parsed.get("topics") or [] if t in TOPICS]
    return {"title": tidy(str(parsed.get("title") or ""))[:90], "dek": tidy(str(parsed.get("dek") or ""))[:240],
            "sections": sections, "checklist": checklist, "faq": faq, "topics": topics}, kept, dropped


def _texts(g: dict[str, Any]) -> list[tuple[str, Any, str]]:
    """Every written string in a guide, with a way to put a rewrite back."""
    out: list[tuple[str, Any, str]] = [("title", g, "title"), ("dek", g, "dek")]
    for s in g["sections"]:
        out.append(("heading", s, "heading"))
        out += [("para", p, "text") for p in s["paragraphs"]]
    out += [("check", c, "item") for c in g["checklist"]]
    for f in g["faq"]:
        out += [("faq q", f, "q"), ("faq a", f, "a")]
    return out


class GuideWriter:
    def __init__(self, db, project: str, model: str, location: str, credentials) -> None:
        self._db, self._project, self._model, self._location = db, project, model, location
        self._credentials = credentials

    def _call(self, text: str, max_tokens: int = 12000) -> dict[str, Any]:
        from .model import call_json

        return call_json(project=self._project, model=self._model, location=self._location,
                         credentials=self._credentials, max_output_tokens=max_tokens,
                         public=True,  # requirements read from public government pages
                         parts=[{"text": text}])

    def write(self, cand: dict[str, Any]) -> dict[str, Any]:
        from . import orbio
        from .registry import JURISDICTIONS

        ref = self._db.collection(GUIDES).document(cand["guide_id"])
        old = ref.get()
        if old.exists and (old.to_dict() or {}).get("fingerprint") == cand["fingerprint"]:
            return {"unchanged": cand["source_url"]}
        before = dict(orbio.served)
        known = {r["id"] for r in cand["reqs"]}
        country = JURISDICTIONS.get(cand["jurisdiction"], {}).get("name", cand["jurisdiction"])
        listing = "\n".join(json.dumps({"id": r["id"], "category": r["category"], "says": r["text"]},
                                       ensure_ascii=False) for r in cand["reqs"])
        parsed = self._call(PROMPT + f"(country: {country}; route: {cand['lane']}; page: {cand['source_url']})\n"
                            + listing)
        guide, kept, dropped = validate(parsed, known)
        if not guide["title"] or kept < 6:
            return {"skipped": f"only {kept} cited lines survived for {cand['source_url']}"}

        # Voice: one batch rewrite for the lines that break it, then drop what still does.
        bad = [(label, obj, key) for label, obj, key in _texts(guide) if voice_hits(obj[key])]
        rewritten = removed = 0
        if bad:
            try:
                fixed = self._call("Rewrite each line so it follows the rules below. Keep the meaning exactly; "
                                   "add nothing. Return JSON only: {\"lines\": [\"...\"]} in the same order.\n"
                                   + VOICE_RULES + "\nLINES:\n" + json.dumps([o[k] for _l, o, k in bad],
                                                                           ensure_ascii=False), 4000)
                lines = fixed.get("lines") or []
                for (label, obj, key), new in zip(bad, lines):
                    new = tidy(str(new))
                    if new and not voice_hits(new):
                        obj[key] = new
                        rewritten += 1
            except Exception:  # noqa: BLE001
                pass
        for sec in guide["sections"]:
            n = len(sec["paragraphs"])
            sec["paragraphs"] = [p for p in sec["paragraphs"] if not voice_hits(p["text"])]
            removed += n - len(sec["paragraphs"])
        guide["sections"] = [s for s in guide["sections"] if s["paragraphs"]]
        n = len(guide["checklist"]) + len(guide["faq"])
        guide["checklist"] = [c for c in guide["checklist"] if not voice_hits(c["item"])]
        guide["faq"] = [f for f in guide["faq"] if not (voice_hits(f["q"]) or voice_hits(f["a"]))]
        removed += n - len(guide["checklist"]) - len(guide["faq"])

        used = {c for s in guide["sections"] for p in s["paragraphs"] for c in p["cites"]} | \
               {c for it in guide["checklist"] + guide["faq"] for c in it["cites"]}
        cites = {r["id"]: {"text": r["text"], "quote": r["quote"]} for r in cand["reqs"] if r["id"] in used}
        base = slugify(guide["title"])
        code = cand["jurisdiction"].lower()
        name = slugify(country)
        # Prefix the country only when the title doesn't already start with it.
        slug = base if base.startswith((code + "-", name + "-")) else f"{code}-{base}"
        doc = {**guide, "id": cand["guide_id"], "slug": slug,
               "jurisdiction": cand["jurisdiction"], "lane": cand["lane"], "source_url": cand["source_url"],
               "fingerprint": cand["fingerprint"], "cites": cites, "updated_at": _now(),
               "created_at": (old.to_dict() or {}).get("created_at", _now()) if old.exists else _now(),
               "hidden": (old.to_dict() or {}).get("hidden", False) if old.exists else False,
               "report": {"requirements_given": len(cand["reqs"]), "lines_kept": kept, "lines_dropped": dropped,
                          "voice_rewritten": rewritten, "voice_removed": removed, "model": self._model,
                          "served_by": "orbio" if orbio.served["orbio"] > before["orbio"] else "vertex",
                          "cost_usd": round(orbio.served["usd"] - before["usd"], 6)}}
        if old.exists and (old.to_dict() or {}).get("slug"):
            doc["slug"] = old.to_dict()["slug"]  # a guide keeps its address when it is rewritten
        ref.set(doc)
        return {"written": doc["slug"]}


def published(db) -> list[dict[str, Any]]:
    rows = [d.to_dict() for d in db.collection(GUIDES).stream()]
    return sorted([r for r in rows if not r.get("hidden")], key=lambda r: (r.get("jurisdiction", ""), r.get("title", "")))


def by_slug(db, slug: str) -> dict[str, Any] | None:
    from google.cloud import firestore

    for d in db.collection(GUIDES).where(filter=firestore.FieldFilter("slug", "==", slug)).limit(1).stream():
        return d.to_dict()
    return None


def affiliates(db) -> list[dict[str, Any]]:
    return [{**d.to_dict(), "id": d.id} for d in db.collection(AFFILIATES).stream()
            if (d.to_dict() or {}).get("active", True)]
