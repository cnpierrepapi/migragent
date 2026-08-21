"""Reading the text off a photograph, so a photograph can be checked too.

THE GAP THIS CLOSES
-------------------
Most people who need this product photograph their documents. A WASSCE result
slip, a passport data page, a trade certificate: these arrive as pictures taken
on a phone, not as PDFs with an embedded text layer.

Until now that meant a second-class path. The model read the image perfectly
well, because it is multimodal, but `extract_text` returned nothing for anything
that was not a PDF, so there was no text to check the model's claims against and
every field off a photograph was kept and marked unverified.

That is the wrong way round. The discipline of this product is that a claim
counts when it can be checked against the document's own words, and the people
most likely to be told "unverified" were the people least likely to own a
scanner.

WHY AN INDEPENDENT OCR ENGINE AND NOT THE MODEL
------------------------------------------------
Gemini could transcribe the image and we could check its claims against its own
transcription. That is the model marking its own homework: a hallucinated date in
the transcription would then "verify" the same hallucinated date in the claim,
and the check would pass while being worth nothing.

Cloud Vision is a different engine doing a different job. It does not know what a
passport is, it is not trying to answer a question, and it has no stake in the
claim being true. When the model says the expiry date is 2029 and Vision's
reading of the pixels also contains 2029, two independent things agree.

WHAT AN OCR CHECK IS WORTH, WHICH IS LESS THAN A TEXT LAYER
------------------------------------------------------------
A PDF text layer is what the document literally contains. OCR is a reading of
what the pixels appear to say, and readings are wrong sometimes: 0 and O, 1 and
l, 5 and S, and worse on a creased slip photographed at an angle.

So OCR-verified is a third state and is carried as one. `text_source` says how
the text was obtained, every screen that shows a verification can say which kind
it was, and nothing pretends a photograph is a text layer. A grade misread by one
character is exactly the sort of error this product exists not to make
confidently.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any

ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"

# What Vision is asked for. DOCUMENT_TEXT_DETECTION is the dense-text model: it
# is built for pages of printed text, which is what every document here is, and
# it beats TEXT_DETECTION badly on forms and tables. A WASSCE slip is a table.
FEATURE = "DOCUMENT_TEXT_DETECTION"

# Vision takes images, not PDFs. PDFs already have `extract_text`, and a scanned
# PDF with no text layer is a real case this does not yet cover: it would need
# the asyncBatchAnnotate file API and a bucket to write to. Named here so the
# gap is visible rather than discovered.
IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp")

TIMEOUT = 45

# The same ceiling the document reader uses. Vision's own limit is 20MB after
# base64 expansion, which is roughly 15MB of file.
MAX_BYTES = 15 * 1024 * 1024


def can_read(mime: str) -> bool:
    return mime in IMAGE_TYPES


def _looks_like_text(text: str) -> bool:
    """Enough real words to be worth checking quotes against.

    OCR on a photograph of a wall returns a handful of stray characters, and
    treating those as a text layer would mean claims failing verification for
    the wrong reason: not because the model invented them, but because there was
    nothing to find them in.
    """
    letters = sum(1 for c in text if c.isalpha())
    return len(text.strip()) >= 24 and letters >= 12


class OCR:
    """Cloud Vision, called directly. No client library, same as everything else.

    A failure here is never fatal. If Vision is unavailable, over quota, or
    refuses the image, the document falls back to exactly the behaviour it had
    before this existed: read by the model, claims kept, marked unverified. A
    person's upload must not fail because a second service had a bad afternoon.
    """

    def __init__(self, credentials: Any) -> None:
        self._credentials = credentials

    def _token(self) -> str:
        from google.auth.transport.requests import Request

        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return self._credentials.token

    def read(self, data: bytes, mime: str) -> tuple[str, str]:
        """The text on the image, and a note about how it went.

        Returns `(text, note)`. An empty text is not an error state to raise on:
        a blank page is a legitimate answer, and so is a failure we chose to
        swallow. The note says which, and it ends up on the screen.
        """
        if not can_read(mime):
            return "", f"{mime} is not an image this can read"
        if len(data) > MAX_BYTES:
            return "", f"the image is {len(data) // 1024 // 1024}MB, too large to read"

        body = {
            "requests": [{
                "image": {"content": base64.b64encode(data).decode()},
                "features": [{"type": FEATURE}],
                # No language hints. Vision detects script well, and a wrong hint
                # is worse than none: hinting English on a French transcript
                # measurably degrades the accented characters.
            }]
        }

        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._token()}",
                     "Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            return "", f"the text reader answered {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return "", f"the text reader could not be reached: {type(exc).__name__}"

        responses = payload.get("responses") or [{}]
        first = responses[0] if responses else {}

        if first.get("error"):
            return "", f"the text reader refused this image: " \
                       f"{str(first['error'].get('message', ''))[:80]}"

        annotation = first.get("fullTextAnnotation") or {}
        text = re.sub(r"\s+", " ", str(annotation.get("text") or "")).strip()

        if not text:
            return "", "no text could be read from this image"
        if not _looks_like_text(text):
            return "", "too little text on this image to check anything against"

        return text, f"{len(text)} characters read from the image"
