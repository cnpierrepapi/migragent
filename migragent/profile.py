"""A name and a face, which is the first thing here we deliberately keep.

THE PROMISE THIS CHANGES, AND HOW
---------------------------------
Every page in this product has said "the file is not kept", and that has been
exactly true: a passport is read in memory, the fields survive, the bytes do not.
A profile picture breaks that sentence, because the entire purpose of a profile
picture is to be kept and shown back to you. There is no version of the feature
where it is discarded.

So the promise gets more precise rather than quietly weaker:

    Documents you upload are never kept. A profile picture is, because it exists
    to be shown to you, and it is deleted with everything else.

That distinction is real and it is worth the extra sentence on the page. What
would not be worth it is leaving "nothing you upload is kept" on a screen while a
picture of somebody's face sits in the database underneath it.

WHY THE PICTURE ARRIVES ALREADY SMALL
-------------------------------------
The browser resizes it to 256 pixels on a canvas and sends a data URI. The
original file is never uploaded at all, so the full resolution photograph never
reaches this server, never sits in a request log, and never has to be trusted to
a deletion path. That is a stronger guarantee than deleting it promptly would be,
and it costs a dozen lines of JavaScript.

It also means no bucket, no second storage identity and no signed URLs for what
is, after all, a thumbnail. It lives in the case's own row.

None of which means the client is trusted. Everything below is checked again
here: the prefix, the media type, the decoded size. A person can post whatever
they like to this endpoint and the browser's good behaviour is a convenience, not
a control.
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

PROFILES = "case_profiles"

# 256px of WebP is comfortably under 40KB. The cap is generous enough that a
# stubborn PNG still fits and small enough that nobody is storing a photograph
# here by accident.
MAX_AVATAR_BYTES = 120 * 1024

# What a browser canvas actually produces. No SVG: it can carry script, and an
# avatar is the one field on the page that is rendered back to whoever looks at
# it. No GIF: an animated avatar is a decision nobody made.
AVATAR_TYPES = ("image/webp", "image/jpeg", "image/png")

_DATA_URI = re.compile(r"^data:(image/[a-z]+);base64,([A-Za-z0-9+/=\s]+)$")

# A name is a name. The cap is not a validation rule about what names look like,
# because that is a fight nobody wins and every attempt at it insults somebody:
# it is a length limit so a row cannot carry a paragraph.
MAX_NAME = 80


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AvatarRejected(Exception):
    """The picture was not something we will store, and why."""


def clean_avatar(data_uri: str) -> str:
    """Check a data URI properly, or refuse it.

    Returns the normalised data URI. Raises `AvatarRejected` with a sentence a
    person can act on, because "invalid image" tells somebody nothing about what
    to do next.
    """
    if not data_uri:
        raise AvatarRejected("no picture was sent")

    match = _DATA_URI.match(data_uri.strip())
    if not match:
        raise AvatarRejected("that was not an image the browser could prepare")

    media_type, payload = match.group(1), re.sub(r"\s+", "", match.group(2))
    if media_type not in AVATAR_TYPES:
        raise AvatarRejected(f"{media_type} is not one we store; "
                             f"use a JPEG, PNG or WebP")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise AvatarRejected("the picture data was damaged in transit") from None

    if not raw:
        raise AvatarRejected("the picture was empty")
    if len(raw) > MAX_AVATAR_BYTES:
        raise AvatarRejected(
            f"that is {len(raw) // 1024}KB after resizing, over the "
            f"{MAX_AVATAR_BYTES // 1024}KB limit")

    # The bytes have to actually be the thing the header claims. A JPEG magic
    # number on a file that is not a JPEG is the oldest trick there is, and the
    # browser is not the only thing that can post here.
    signatures = {
        "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
        "image/webp": raw[:4] == b"RIFF" and raw[8:12] == b"WEBP",
    }
    if not signatures.get(media_type):
        raise AvatarRejected(f"that file is not really a {media_type.split('/')[1]}")

    return f"data:{media_type};base64,{payload}"


def clean_name(name: str) -> str:
    """Trim it, collapse the whitespace, and stop there.

    No title casing, no splitting into first and last, no transliteration. All
    three of those get somebody's name wrong, and a product for people moving
    between countries is the last place that should be guessing at name shapes.
    """
    return re.sub(r"\s+", " ", (name or "").strip())[:MAX_NAME]


@dataclass
class Profile:
    """What somebody chose to tell us about themselves. All of it optional."""

    case_id: str
    name: str = ""
    avatar: str = ""
    updated_at: str = ""

    # Whether they want to be told at all. The watch has its own on and off
    # switch; this is the settings-screen mirror of it so a person can find it
    # where they would look for it.
    email: str = ""

    @property
    def initials(self) -> str:
        """Shown when there is no picture. Never invented from an email."""
        parts = [p for p in self.name.split() if p]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:1].upper()
        return (parts[0][:1] + parts[-1][:1]).upper()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Profiles:
    """One document per case. Written only when somebody fills something in."""

    COLLECTION = PROFILES

    def __init__(self, client) -> None:
        self._db = client

    def get(self, case_id: str) -> Profile:
        """Always returns a Profile. An empty one is a real answer here.

        Every screen wants to render a name or the absence of one, and making
        each of them handle None would put the same three lines in six places.
        """
        snap = self._db.collection(PROFILES).document(case_id).get()
        if not snap.exists:
            return Profile(case_id=case_id)
        row = snap.to_dict()
        return Profile(
            case_id=case_id,
            name=row.get("name", ""),
            avatar=row.get("avatar", ""),
            email=row.get("email", ""),
            updated_at=row.get("updated_at", ""),
        )

    def save(self, case_id: str, *, name: str | None = None,
             avatar: str | None = None, email: str | None = None) -> Profile:
        """Merge what was given. None means "not sent", not "clear it".

        Clearing is a separate call, because a settings form that omits a field
        must not delete it, and that is exactly the bug that costs somebody
        their picture when they change their name.
        """
        payload: dict[str, Any] = {"case_id": case_id, "updated_at": _now()}
        if name is not None:
            payload["name"] = clean_name(name)
        if avatar is not None:
            payload["avatar"] = clean_avatar(avatar) if avatar else ""
        if email is not None:
            payload["email"] = (email or "").strip()[:200]

        self._db.collection(PROFILES).document(case_id).set(payload, merge=True)
        return self.get(case_id)

    def clear_avatar(self, case_id: str) -> None:
        self._db.collection(PROFILES).document(case_id).set(
            {"avatar": "", "updated_at": _now()}, merge=True)

    def delete(self, case_id: str) -> int:
        ref = self._db.collection(PROFILES).document(case_id)
        if not ref.get().exists:
            return 0
        ref.delete()
        return 1
