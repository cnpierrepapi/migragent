"""How many of a university's students came from abroad, and who says so.

WHERE THIS NUMBER COMES FROM, AND WHY IT IS NOT A GOVERNMENT
------------------------------------------------------------
No government in this registry publishes international share per institution.
The UK's statistics agency, HESA, is the authority and returns 403 to every
request. QS permits crawling in its robots.txt and then refuses every request.
Australia's department will not serve a robots.txt and its open data portal
disallows crawling outright.

Times Higher Education publishes an international student percentage on each
university's page, permits crawling, and serves it. So that is the source, and it
is a publisher rather than a government.

**That difference is carried, not hidden.** Every share stored here records who
published it and which edition it came from, and the provenance is `portal`. It
is exactly the distinction already made for requirements: an official page and a
portal page are both real citations with real links and real dates, and the
reader is told which one they are looking at. Rule 8, and rule 7 for the
publisher and the year.

THE RISK THIS MODULE EXISTS TO CONTAIN
--------------------------------------
The page for a university has to be found from its name, and a name is not a URL.
Guessing a URL from a name and trusting what comes back is how one university's
figures end up attributed to another, which would be a precise, sourced, linked
and completely wrong number.

So a page is only read if the page itself says it is about the institution we
asked for. The name on the page is compared against the name from the register,
and a mismatch is recorded as a mismatch rather than resolved by hoping.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .fetcher import Fetched
from .extract import page_text

PUBLISHER = "Times Higher Education"
BASE = "https://www.timeshighereducation.com/world-university-rankings/"

_SHARE = re.compile(r"International student percentage\s*([0-9]{1,3})\s*%", re.I)
_EDITION = re.compile(r"World University Rankings\s*(20\d\d)")
_WORDS = re.compile(r"[^a-z0-9]+")

# Words a ranking slug drops, and which also carry no identity: two schools are
# never told apart by "the" or "of".
_NOISE = {"the", "of", "at", "in", "and", "a"}


def slug_for(name: str) -> str:
    """The ranking's URL segment for an institution name.

    A guess, and treated as one. Whatever it returns is only used to find a
    candidate page, and the page still has to prove it is about this institution
    before anything is read from it.
    """
    words = [w for w in _WORDS.sub(" ", name.lower()).split() if w and w not in _NOISE]
    return "-".join(words)


def names_match(register_name: str, page_name: str) -> bool:
    """Whether the page is about the institution we went looking for.

    Compared on significant words rather than exact strings, because a register
    and a ranking will punctuate and abbreviate differently for the same school.
    Every significant word from the shorter name must appear in the longer one,
    which accepts "University of Manchester" against "The University of
    Manchester" and rejects "University of East London" against "University of
    West London", where exactly one word differs and it is the one that matters.
    """
    a = {w for w in _WORDS.sub(" ", register_name.lower()).split() if w not in _NOISE}
    b = {w for w in _WORDS.sub(" ", page_name.lower()).split() if w not in _NOISE}
    if not a or not b:
        return False
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    return smaller.issubset(larger)


@dataclass
class Share:
    """One institution's international student percentage, and its provenance."""

    institution_name: str
    jurisdiction: str
    international_share: float

    # The span the number was read from, so the figure can be checked against the
    # page rather than trusted.
    quote: str

    publisher: str = PUBLISHER
    edition: str | None = None
    provenance: str = "portal"

    source_url: str = ""
    read_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def read_share(page: Fetched, register_name: str, jurisdiction: str) -> tuple[Share | None, str]:
    """Pull the share from a ranking page, or say why it was not taken.

    Returns (share, reason). A reason is always given, including on success, so a
    run can report what it did rather than only what it kept.
    """
    if not page.ok:
        return None, f"page not read: {page.outcome} {page.status or ''}".strip()

    text = page_text(page)
    if not text:
        return None, "no readable text on the page"

    # What the page says it is about. The first line of a ranking page is the
    # institution's name.
    page_name = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not names_match(register_name, page_name):
        return None, f"page is about {page_name[:60]!r}, not this institution"

    found = _SHARE.search(text)
    if not found:
        return None, "the page does not state an international student percentage"

    edition = _EDITION.search(text)
    return Share(
        institution_name=register_name,
        jurisdiction=jurisdiction,
        international_share=float(found.group(1)),
        quote=found.group(0).strip(),
        edition=f"World University Rankings {edition.group(1)}" if edition else None,
        source_url=page.final_url or page.url,
        read_at=page.read_at,
    ), "read"
