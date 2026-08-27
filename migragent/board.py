"""The activity board: what a person still has to do, and what they have done.

WHY THIS EXISTS AT ALL
----------------------
The guide ends when they land. The board does not, because everybody is always
looking for the next job, and the shortage lists and the postings keep moving
whether or not anybody is watching them.

WHAT AN ITEM IS
---------------
Clicking "I'm interested" on a listing creates one item. The item carries the
work the application actually needs: the CV rewritten for that listing, a cover
letter drafted, and the people worth speaking to. Each piece arrives as a draft
and says so.

THE RULE THIS FILE ENFORCES
---------------------------
**Nothing is ever ticked off on a person's behalf.** Only a person moves an item,
and the only move this code makes on its own is putting a new item in the first
column. The board is the record of what they did, not a claim about what we did
for them, and an item that marched itself to "sent" would be a lie about an
application nobody submitted.

So `advance` takes the column a person chose, and there is no function anywhere
that decides an item is finished.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from .clock import now_iso as _now

BOARD = "board_items"

# In the order a person moves through them. The names say who acts.
COLUMNS = ("to_prepare", "ready_to_send", "sent")
COLUMN_NAMES = {
    "to_prepare": "To prepare",
    "ready_to_send": "Ready to send",
    "sent": "Sent",
}



def item_id(case_id: str, listing_id: str) -> str:
    return hashlib.sha256(f"{case_id}\n{listing_id}".encode()).hexdigest()[:24]


@dataclass
class Piece:
    """One part of the application, and who wrote it.

    `is_draft` is not decoration. Everything this product writes for somebody is
    a draft they have to read, and the flag travels with the text so no screen
    can show it without saying so.
    """

    kind: str            # cv, cover_letter, people, form
    title: str
    body: str = ""
    is_draft: bool = True
    written_at: str = field(default_factory=_now)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Item:
    """One application a person said they were interested in."""

    item_id: str
    case_id: str
    listing_id: str
    title: str
    url: str
    created_at: str

    employer: str | None = None
    location: str | None = None
    column: str = "to_prepare"
    fit_score: int | None = None
    moved_at: str | None = None
    pieces: list[Piece] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        row = {k: v for k, v in asdict(self).items() if v is not None}
        row["pieces"] = [p.to_dict() for p in self.pieces]
        return row


class Board:
    """Reads and writes board items."""

    def __init__(self, client) -> None:
        self._db = client

    def add(self, case_id: str, listing: dict[str, Any],
            fit_score: int | None = None) -> Item:
        """Create the item for a listing, or return the one already there.

        Clicking twice is not two applications. The id is derived from the case
        and the listing, so a second click lands on the same item and whatever
        the person has already done to it survives.
        """
        identifier = item_id(case_id, listing.get("listing_id", ""))
        existing = self.get(case_id, identifier)
        if existing is not None:
            return existing

        item = Item(
            item_id=identifier,
            case_id=case_id,
            listing_id=listing.get("listing_id", ""),
            title=listing.get("title", ""),
            url=listing.get("url", ""),
            employer=listing.get("employer"),
            location=listing.get("location"),
            fit_score=fit_score,
            created_at=_now(),
        )
        self._db.collection(BOARD).document(identifier).set(item.to_dict())
        return item

    def get(self, case_id: str, identifier: str) -> Item | None:
        snap = self._db.collection(BOARD).document(identifier).get()
        if not snap.exists:
            return None
        row = snap.to_dict()
        if row.get("case_id") != case_id:
            # Somebody else's item. Not found, rather than forbidden, because a
            # different answer would confirm the item exists.
            return None
        pieces = [Piece(**p) for p in row.pop("pieces", [])]
        return Item(**row, pieces=pieces)

    def for_case(self, case_id: str) -> dict[str, list[Item]]:
        """Every item, in columns, oldest first inside each."""
        from google.cloud import firestore

        query = (self._db.collection(BOARD)
                 .where(filter=firestore.FieldFilter("case_id", "==", case_id)))
        columns: dict[str, list[Item]] = {c: [] for c in COLUMNS}
        for doc in query.stream():
            row = doc.to_dict()
            pieces = [Piece(**p) for p in row.pop("pieces", [])]
            item = Item(**row, pieces=pieces)
            columns.setdefault(item.column, []).append(item)
        for items in columns.values():
            items.sort(key=lambda i: i.created_at)
        return columns

    def advance(self, case_id: str, identifier: str, column: str) -> Item | None:
        """Move an item, because a person moved it.

        The column has to be one of ours, and that is the whole of the
        validation: which column a person thinks their application is in is
        theirs to decide, including moving it back.
        """
        if column not in COLUMNS:
            return None
        item = self.get(case_id, identifier)
        if item is None:
            return None
        item.column = column
        item.moved_at = _now()
        self._db.collection(BOARD).document(identifier).set(
            {"column": column, "moved_at": item.moved_at}, merge=True)
        return item

    def attach(self, case_id: str, identifier: str, piece: Piece) -> Item | None:
        """Add or replace one piece of the application.

        Replaced by kind, so asking for the cover letter again gives a new draft
        rather than a second one, and the person is never left choosing between
        two things they did not write.
        """
        item = self.get(case_id, identifier)
        if item is None:
            return None
        item.pieces = [p for p in item.pieces if p.kind != piece.kind] + [piece]
        self._db.collection(BOARD).document(identifier).set(
            {"pieces": [p.to_dict() for p in item.pieces]}, merge=True)
        return item

    def delete_for_case(self, case_id: str) -> int:
        from google.cloud import firestore

        query = (self._db.collection(BOARD)
                 .where(filter=firestore.FieldFilter("case_id", "==", case_id)))
        deleted = 0
        for doc in query.stream():
            doc.reference.delete()
            deleted += 1
        return deleted
