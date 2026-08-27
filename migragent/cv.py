"""Reading a CV, which is a document like the others in exactly one way.

WHY IT IS NOT JUST ANOTHER DOCUMENT
-----------------------------------
Every other upload answers a question a government asked: does this person have
a degree, a passport, an English test. A CV answers nobody's question. It is a
claim a person makes about themselves, in whatever shape they chose.

So it gets its own reader, and two rules come with it.

**It does not feed the readiness score.** Readiness is the share of extracted
requirements a person's documents cover. A CV covers almost none of them, and
letting it move that number would make the one honest number in the product
dishonest. It is scored against a listing instead, in migragent/fit.py, and only
where a listing exists to score it against.

**Nothing is credited that the CV does not say.** The same discipline the corpus
uses: every skill, role and qualification carries a verbatim span from the CV,
checked against the document's own text before it is allowed to count. The
failure here is the mirror of the one in extraction. A model that has read ten
thousand CVs will happily award somebody Python and stakeholder management
because they are a project manager, and then a fit score is measuring the
model's expectations rather than the person.

A CV with no text layer, a scan or a photograph, has nothing to check against.
Those claims are kept and marked unverified, exactly as a photographed passport
is, and everything downstream shows the mark. Throwing them away would punish
the person for owning a scanner.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .model import call_json
from .clock import now_iso

MAX_BYTES = 10 * 1024 * 1024

CV_FIELDS = "case_cv"

# The CV re-shaped for each country, one document per case and country.
CV_CLONES = "case_cv_clones"


from .fold import fold_ci as _normalise  # noqa: E402


@dataclass
class Claim:
    """One thing the CV says about the person, and the words that say it."""

    kind: str            # role, skill, qualification, language, licence
    value: str
    quote: str
    verified: bool = False
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CV:
    """What one uploaded CV turned out to say."""

    filename: str
    read_at: str
    claims: list[Claim] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    text_layer: bool = False
    error: str | None = None

    # pdf, ocr or none. See migragent/documents.py for why the difference
    # between "the document's own text" and "a reading of the pixels" is carried
    # rather than flattened into a boolean.
    text_source: str = "none"

    @property
    def verified(self) -> list[Claim]:
        return [c for c in self.claims if c.verified]

    def of_kind(self, kind: str) -> list[Claim]:
        return [c for c in self.claims if c.kind == kind]

    @property
    def headline_role(self) -> str | None:
        roles = self.of_kind("role")
        return roles[0].value if roles else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "read_at": self.read_at,
            "text_layer": self.text_layer,
            "text_source": self.text_source,
            "claims": [c.to_dict() for c in self.claims],
            "dropped": self.dropped,
            "error": self.error,
        }


KINDS = ("role", "skill", "qualification", "language", "licence")

PROMPT = """You are reading one CV, uploaded by a person who is applying to \
work or study in another country.

List what this CV states about them. For each item return:
  "kind": one of role, skill, qualification, language, licence
  "value": the thing itself, in a few words. A job title, a named skill, a \
qualification, a language, a licence or registration.
  "detail": employer, institution, dates or level, if the CV states them, else null
  "quote": a VERBATIM span copied exactly from the CV that states this. Copy it \
character for character.

Rules:
- Only what this CV says. Do not add skills that usually go with a job title. \
Do not infer a language from a country. If it is not written down, it does not \
exist here.
- Every quote is checked against the document text automatically, and anything \
that does not appear word for word is discarded.
- Keep the person's own wording in "value" where you can.

Return only JSON: {"claims": [...]}"""


class CVReader:
    """Reads a CV with Gemini and keeps only what the document can be shown to say."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def read(self, filename: str, data: bytes, mime: str,
             extractable_text: str = "", text_source: str = "") -> CV:
        now = now_iso()
        has_text = bool(extractable_text.strip())
        cv = CV(filename=filename, read_at=now, text_layer=has_text,
                text_source=text_source or ("pdf" if has_text else "none"))

        if len(data) > MAX_BYTES:
            cv.error = f"file is {len(data):,} bytes, over the {MAX_BYTES:,} limit"
            return cv

        import base64

        try:
            parsed = call_json(
                project=self._project, model=self._model, location=self._location,
                credentials=self._credentials,
                parts=[{"inlineData": {"mimeType": mime,
                                       "data": base64.b64encode(data).decode()}},
                       {"text": PROMPT}],
            )
        except Exception as exc:  # noqa: BLE001
            cv.error = str(exc)
            return cv

        haystack = _normalise(extractable_text)

        for item in parsed.get("claims", []):
            kind = str(item.get("kind") or "").strip().lower()
            value = str(item.get("value") or "").strip()
            quote = str(item.get("quote") or "").strip()
            if kind not in KINDS or not value:
                continue

            detail = str(item.get("detail") or "").strip() or None

            if not cv.text_layer:
                cv.claims.append(Claim(kind=kind, value=value, quote=quote,
                                       verified=False, detail=detail))
                continue

            if quote and _normalise(quote) in haystack:
                cv.claims.append(Claim(kind=kind, value=value, quote=quote,
                                       verified=True, detail=detail))
            elif cv.text_source == "ocr":
                # Same rule as documents.py: a miss against text read off a
                # photograph is not evidence of invention. OCR reads columns, and
                # a two-column CV comes back interleaved, so a true line can fail
                # a contiguity check. Kept and marked rather than dropped.
                cv.claims.append(Claim(kind=kind, value=value, quote=quote,
                                       verified=False, detail=detail))
            else:
                cv.dropped.append({"kind": kind, "value": value, "quote": quote,
                                   "why": "the quote is not in the CV text"})

        return cv


class CVStore:
    """Holds what a CV said. Never the CV.

    Same rule as every other upload: the file is read in memory and the fields
    are what survive. See docs/DATA_PROTECTION.md.
    """

    def __init__(self, client) -> None:
        self._db = client

    def put(self, case_id: str, cv: CV) -> None:
        self._db.collection(CV_FIELDS).document(case_id).set(cv.to_dict())

    def get(self, case_id: str) -> CV | None:
        snap = self._db.collection(CV_FIELDS).document(case_id).get()
        if not snap.exists:
            return None
        row = snap.to_dict()
        return CV(
            filename=row.get("filename", ""),
            read_at=row.get("read_at", ""),
            text_layer=bool(row.get("text_layer")),
            text_source=row.get("text_source", "none"),
            error=row.get("error"),
            dropped=row.get("dropped", []),
            claims=[Claim(**c) for c in row.get("claims", [])],
        )

    def delete(self, case_id: str) -> None:
        self._db.collection(CV_FIELDS).document(case_id).delete()


class CVClones:
    """The same CV, in each country's shape, kept so it is not redrafted daily.

    One document per case and country. They are drafts and are stored as drafts:
    the body, the note that says it is a draft, and nothing that could be
    mistaken for a fact about the person that their own CV did not already say.
    """

    COLLECTION = CV_CLONES

    def __init__(self, client) -> None:
        self._db = client

    def put(self, case_id: str, jurisdiction: str, piece) -> None:
        self._db.collection(CV_CLONES).document(f"{case_id}-{jurisdiction}").set({
            "case_id": case_id,
            "jurisdiction": jurisdiction,
            "title": piece.title,
            "body": piece.body,
            "note": piece.note,
        })

    def get(self, case_id: str, jurisdiction: str) -> dict[str, Any] | None:
        snap = self._db.collection(CV_CLONES).document(f"{case_id}-{jurisdiction}").get()
        return snap.to_dict() if snap.exists else None

    def for_case(self, case_id: str) -> list[dict[str, Any]]:
        from google.cloud import firestore

        query = self._db.collection(CV_CLONES).where(
            filter=firestore.FieldFilter("case_id", "==", case_id))
        rows = [s.to_dict() for s in query.stream()]
        rows.sort(key=lambda r: r.get("jurisdiction", ""))
        return rows
