"""Reading the documents somebody uploads.

This is the multimodal half of the product: a passport photo page, a transcript
PDF, an IELTS result, a degree certificate.

THE SAME RULE AS EVERYWHERE ELSE
--------------------------------
A model reads the document and says what is on it. Every field it returns has to
carry a quote from the document, and every quote is checked against the text the
document actually contains before the field is allowed to exist. A field with no
findable quote is dropped and counted.

For a scan with no extractable text layer there is nothing to check a quote
against, so the fields are kept and **marked unverified**, and everything
downstream that uses them says so. That is the honest handling: not pretending
the check ran, and not throwing away a perfectly good passport because it is a
photograph.

WHAT IS DELIBERATELY NOT STORED
-------------------------------
The document bytes are held only long enough to read them, and what persists is
the fields, not the file. Nobody needs a copy of somebody's passport sitting in
a bucket to tell them their passport expires before their course ends. See
docs/DATA_PROTECTION.md.
"""
from __future__ import annotations

import base64
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .detect import Detection, agreement, detect
from .model import call_json

# What a document can be. The list is short on purpose: these are the documents
# that actually appear in immigration and licensing requirements.
KINDS = (
    "passport",
    "national_id",
    "degree_certificate",
    "transcript",
    "english_test",
    "language_test_other",
    "professional_registration",
    "employment_letter",
    "bank_statement",
    "police_certificate",
    "medical_exam",
    "birth_certificate",
    "marriage_certificate",
    "offer_letter",
    "other",
)

MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}

MAX_BYTES = 20 * 1024 * 1024


def _normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'),
                 ("”", '"'), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass
class Field:
    """One thing the document says, and the words that say it."""

    name: str
    value: str
    quote: str
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReadDocument:
    """What one uploaded file turned out to be."""

    kind: str
    filename: str
    read_at: str
    fields: list[Field] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    text_layer: bool = False
    error: str | None = None

    # The words' own opinion of what this document is, and whether it agrees
    # with the model. Computed here, at read time, because this is the only
    # moment the document's text exists: it is deliberately never stored.
    detected_kind: str | None = None
    detected_reason: str = ""
    agreement_state: str = "unchecked"
    agreement_note: str = ""

    @property
    def verified_fields(self) -> list[Field]:
        return [f for f in self.fields if f.verified]

    def value_of(self, name: str) -> str | None:
        for f in self.fields:
            if f.name == name:
                return f.value
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "filename": self.filename,
            "read_at": self.read_at,
            "text_layer": self.text_layer,
            "fields": [f.to_dict() for f in self.fields],
            "dropped": self.dropped,
            "error": self.error,
            "detected_kind": self.detected_kind,
            "detected_reason": self.detected_reason,
            "agreement_state": self.agreement_state,
            "agreement_note": self.agreement_note,
        }


PROMPT = """You are reading one document a person has uploaded as part of an \
immigration or licensing application.

Return JSON:
{
  "kind": one of KINDS_LIST,
  "fields": [
    {"name": "...", "value": "...", "quote": "..."}
  ]
}

Field names to use where the document shows them: holder_name, document_number, \
date_of_issue, date_of_expiry, issuing_authority, issuing_country, \
date_of_birth, nationality, institution, qualification, classification, \
award_date, overall_score, listening_score, reading_score, writing_score, \
speaking_score, test_date, registration_number, employer, job_title, \
start_date, end_date, currency, balance.

Rules:
- Only fields the document actually shows. Never infer, never complete a partial \
number, never guess an authority from a flag or a crest.
- "quote" must be text that appears in the document, copied exactly. It is \
checked automatically and anything that does not match is discarded.
- If the document is unreadable or is not one of the listed kinds, return kind \
"other" with an empty fields list.

Return only the JSON."""


class DocumentReader:
    """Reads an uploaded file with Gemini, and keeps what it can be shown to say."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _call(self, data: bytes, mime: str) -> dict[str, Any]:
        """The file and the prompt, through the shared caller.

        Reading a document is one model call among five in a single run, and
        before the shared caller existed a rate limit here came back as
        `error: HTTPError` and the document silently produced no fields. See D20.
        """
        prompt = PROMPT.replace("KINDS_LIST", ", ".join(KINDS))
        return call_json(
            project=self._project, model=self._model,
            location=self._location, credentials=self._credentials,
            parts=[
                {"inlineData": {"mimeType": mime,
                                "data": base64.b64encode(data).decode()}},
                {"text": prompt},
            ],
        )

    def read(self, filename: str, data: bytes, mime: str,
             extractable_text: str = "") -> ReadDocument:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        doc = ReadDocument(kind="other", filename=filename, read_at=now,
                           text_layer=bool(extractable_text.strip()))

        if len(data) > MAX_BYTES:
            doc.error = f"file is {len(data):,} bytes, over the {MAX_BYTES:,} limit"
            return doc

        try:
            parsed = self._call(data, mime)
        except Exception as exc:  # noqa: BLE001
            doc.error = str(exc)
            return doc

        doc.kind = parsed.get("kind") if parsed.get("kind") in KINDS else "other"

        # The words get their vote here, on the document's actual text, which
        # exists only inside this call. An earlier version ran the detector
        # later on the field names and values, which is not the document and
        # scored 1 on everything. See D21.
        detection = detect(extractable_text)
        doc.detected_kind = detection.kind
        doc.detected_reason = detection.reason
        doc.agreement_state, doc.agreement_note = agreement(doc.kind, detection)

        haystack = _normalise(extractable_text)

        for item in parsed.get("fields", []):
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "").strip()
            quote = str(item.get("quote") or "").strip()
            if not name or not value:
                continue

            if not doc.text_layer:
                # A photograph of a passport has no text to check against. The
                # field is kept and marked unverified rather than dropped, and
                # everything downstream shows that mark. Discarding it would
                # throw away the most useful document most people own.
                doc.fields.append(Field(name=name, value=value, quote=quote, verified=False))
                continue

            if quote and _normalise(quote) in haystack:
                doc.fields.append(Field(name=name, value=value, quote=quote, verified=True))
            else:
                doc.dropped.append({
                    "name": name, "value": value, "quote": quote,
                    "why": "the quote is not in the document text",
                })

        return doc


def looks_like_text(text: str) -> bool:
    """Is this actually words, or is it decompressed noise wearing a string type?

    This guard exists because of a real failure, not as defensive habit. The
    first extractor pulled everything between brackets out of the raw PDF bytes.
    On a Chromium-produced PDF the content streams are compressed, so it
    returned 12,146 characters of binary, `text_layer` was set to True, and
    every genuinely correct field the model read was then dropped for having a
    quote that was not in "the document". See D19.

    A silently wrong haystack turns the quote check from a guard into a
    shredder, so the haystack now has to prove it is text.
    """
    if len(text) < 20:
        return False
    whitespace = {" ", "\n", "\t", "\r"}
    printable = sum(1 for c in text if c.isprintable() or c in whitespace)
    if printable / len(text) < 0.9:
        return False
    letters = sum(1 for c in text if c.isalpha())
    return letters / len(text) > 0.35


def extract_text(data: bytes, mime: str) -> str:
    """Pull the text layer out of a PDF, for checking quotes against.

    A file with no text layer is not a problem. It means fields read from it are
    marked unverified rather than dropped, which is the right answer for a
    photograph of a passport.

    What IS a problem is claiming a text layer that is not one, so anything that
    does not pass `looks_like_text` is treated as no text layer at all.
    """
    if mime != "application/pdf":
        return ""
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        text = re.sub(r"\s+", " ", text).strip()
    except Exception:  # noqa: BLE001
        return ""
    return text if looks_like_text(text) else ""
