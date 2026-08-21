"""Which schools a country will actually accept, from the register that says so.

WHY THE REGISTER AND NOT A RANKING
----------------------------------
The plan asked for the top institutions by percentage of international students.
That number is not published per institution by any of these governments. It is
sold by data companies, estimated by league tables, or absent. Ranking on it
would mean either buying somebody's estimate and citing a government for it, or
inferring it ourselves, and both are the failure this product exists to avoid.

What governments do publish, officially and on a date, is the register of
institutions licensed to take international students. For a study visa that is
the fact that decides the case: an offer from a school that is not on the
register is not a route, however good the school is. So the register is what gets
read, and the share question stays open and visible rather than being filled in
with a number nobody can source.

WHY THIS IS PLAIN CODE
----------------------
A register is a table. The UK publishes a dated CSV and Canada an HTML table of
about 1,400 rows. Parsing a table is not judgement, and a model reading 1,400
rows would be slower, more expensive, and capable of returning a school that is
not in it. The rule stands: the model is for reading prose, and structure is read
by code.

There is no quote check here and none is needed. The register IS the evidence,
the whole file is stored as a snapshot, and the claim made is only ever "this
name appears in the official register read on this date".
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .fetcher import decode_body
from .newness import unseen_ids

_TAG = re.compile(r"<[^>]+>")
_ROW = re.compile(rb"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(rb"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def institution_id(jurisdiction: str, name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return f"{jurisdiction.lower()}-" + hashlib.sha256(key.encode()).hexdigest()[:20]


@dataclass
class Institution:
    """One school a government lists as able to take international students."""

    name: str
    jurisdiction: str

    # What the register says about it, where it says anything.
    status: str | None = None
    location: str | None = None
    code: str | None = None

    # Which routes the register licenses this institution for. A school listed
    # for Student and Child Student is licensed for both, and keeping only one
    # would answer a real question wrongly.
    routes: list[str] = field(default_factory=list)

    # Assembled from the fetch. Never inferred.
    source_url: str = ""
    read_at: str = ""
    register_name: str = ""

    # Deliberately absent rather than estimated. See the module docstring: no
    # government here publishes international share per institution, so the
    # fields exist, stay empty, and the product says the share is unknown rather
    # than ranking on a number it cannot source.
    international_share: float | None = None
    share_publisher: str | None = None
    share_data_year: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _clean(raw: bytes | str, content_type: str | None = None) -> str:
    text = decode_body(raw, content_type) if isinstance(raw, bytes) else raw
    text = _TAG.sub(" ", text)
    text = (text.replace("&amp;", "&").replace("&nbsp;", " ")
                .replace("&#39;", "'").replace("&quot;", '"'))
    return " ".join(text.split())


def from_csv(body: bytes, jurisdiction: str, *, name_column: str,
             status_column: str | None = None,
             location_column: str | None = None,
             route_column: str | None = None) -> list[Institution]:
    """Parse a register published as CSV, one entry per institution.

    Column names are given by the caller rather than guessed, because a register
    whose columns moved should fail loudly here rather than quietly produce a
    thousand institutions called "None".

    A sponsor appears once per route it is licensed for, so the UK register has
    1,309 rows and 946 institutions. Storing rows would have merged them on write
    and kept whichever happened to be last, quietly losing the fact that a school
    licensed for Student and Child Student is licensed for both. Routes are
    collected instead, and the count of institutions is the count of
    institutions.
    """
    text = body.decode("utf-8-sig", "ignore")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or name_column not in reader.fieldnames:
        raise ValueError(
            f"no column named {name_column!r} in the register; "
            f"columns are {reader.fieldnames}"
        )

    by_name: dict[str, Institution] = {}
    for row in reader:
        name = (row.get(name_column) or "").strip()
        if not name:
            continue
        key = name.lower()
        entry = by_name.get(key)
        if entry is None:
            entry = Institution(
                name=name,
                jurisdiction=jurisdiction,
                status=((row.get(status_column) or "").strip() or None) if status_column else None,
                location=((row.get(location_column) or "").strip() or None) if location_column else None,
            )
            by_name[key] = entry
        if route_column:
            route = (row.get(route_column) or "").strip()
            if route and route not in entry.routes:
                entry.routes.append(route)
    return list(by_name.values())


def from_html_table(body: bytes, jurisdiction: str, *, name_index: int = 0,
                    content_type: str | None = None,
                    location_index: int | None = None,
                    code_index: int | None = None,
                    min_cells: int = 2) -> list[Institution]:
    """Parse a register published as an HTML table.

    Rows shorter than `min_cells` are headers, spacers or footnotes and are
    skipped. The first row of each table is skipped when its first cell repeats a
    header word, so a column title never becomes an institution.
    """
    out: list[Institution] = []
    seen: set[str] = set()

    for raw_row in _ROW.findall(body):
        cells = [_clean(c, content_type) for c in _CELL.findall(raw_row)]
        if len(cells) < min_cells:
            continue
        name = cells[name_index] if name_index < len(cells) else ""
        if not name or name.lower() in ("name", "institution", "school", "dli name",
                                        "province/territory", "city"):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(Institution(
            name=name,
            jurisdiction=jurisdiction,
            location=(cells[location_index] if location_index is not None
                      and location_index < len(cells) else None) or None,
            code=(cells[code_index] if code_index is not None
                  and code_index < len(cells) else None) or None,
        ))
    return out


class Institutions:
    """Stores institutions. Its own collection, like occupations."""

    COLLECTION = "institutions"

    def __init__(self, client) -> None:
        self._db = client

    def record(self, items: Iterable[Institution]) -> int:
        """Store the register, and remember which rows were not on it before.

        A school appearing on the register is a door opening for somebody: an
        offer from a school that is not licensed is not a route, so a school
        that becomes licensed is news. That is only visible if we know which
        rows are new, and a merge write cannot tell us afterwards.
        """
        items = list(items)
        ids = {institution_id(x.jurisdiction, x.name): x for x in items}
        fresh = unseen_ids(self._db, self.COLLECTION, ids.keys())

        batch = self._db.batch()
        n = 0
        for item in items:
            doc_id = institution_id(item.jurisdiction, item.name)
            payload = item.to_dict()
            if doc_id in fresh:
                # Only ever written once. The read date is on every row already;
                # this is the date the row first existed, which is a different
                # fact and the one an alert stands on.
                payload["first_seen_at"] = item.read_at
            batch.set(
                self._db.collection(self.COLLECTION).document(doc_id),
                payload, merge=True,
            )
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return n

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self._db.collection(self.COLLECTION).select(["jurisdiction"]).stream():
            j = d.to_dict().get("jurisdiction", "")
            out[j] = out.get(j, 0) + 1
        return out

    def find(self, jurisdiction: str, name: str) -> dict[str, Any] | None:
        """Is this school on the register? The question a study case actually asks."""
        doc = self._db.collection(self.COLLECTION).document(
            institution_id(jurisdiction, name)).get()
        return {**doc.to_dict(), "id": doc.id} if doc.exists else None
