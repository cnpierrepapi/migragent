"""Courses, read from the schools that teach them.

WHAT THIS IS FOR
----------------
The study path promises a guide for a specific course at a specific school, and
a country list built from schools that actually teach what somebody wants. Both
need course data, and no government publishes it: a register says a school may
take international students, not what it teaches or when its intake opens.

So it is read from the schools themselves, one page at a time, under the same
rules as every government page in this product.

THE SAME DISCIPLINE, ON A HARDER SURFACE
-----------------------------------------
A government page is written to be read. A university course page is a marketing
asset with a hero video, a chatbot, three cookie banners and the entry
requirements in an accordion. That makes extraction harder; it does not make the
rules different.

  the robots gate      unchanged and non-negotiable. A university that will not
                       state its crawling rules is not crawled, exactly like a
                       government that will not.
  every claim quoted   a course's level, title, intake and fee each carry a
                       verbatim span from the page, checked against the page's
                       own text before it is kept.
  nothing inferred     a page that does not say when the intake opens produces a
                       course with no intake date, not a guessed one. "September"
                       is not on the page merely because most courses start then.

WHAT A COURSE IS AND IS NOT
---------------------------
It is a record that a named school published a named course at a named level, on
a date we read it. It is not an offer, not a prediction that somebody will get
in, and not advice about where to apply. The rubric may rank it; the person
decides.

WHY LEVEL MATTERS MOST
----------------------
Everything downstream keys off level. A transcript pointing at a bachelor's must
not produce a list of doctorates, so a course whose level cannot be read off the
page is dropped rather than defaulted. A wrong level is worse than a missing
course: it wastes the one thing this product is supposed to save.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .extract import MAX_CHARS, _normalise, page_text
from .model import call_json

COURSES = "courses"

# The levels the product serves. Anything else a school teaches is real and is
# not what anybody here is asking about.
LEVELS = ("bachelors", "masters", "doctorate")

# Words that appear in the links to a school's course listing. Used to find the
# page worth reading from the homepage, because a school's course index is never
# at a predictable path.
# Ordered by how strongly the word predicts an actual list of courses, because
# the first matching link is the one the deep pass starts from and picking
# "apply" over "programmes" costs the whole school. A school's "admissions" page
# is about how to apply; its "programmes" page is what it teaches, and only the
# second one answers the question being asked.
STRONG_WORDS = ("courses", "programmes", "programs", "degrees", "subjects",
                "course-search", "program-search", "undergraduate", "postgraduate",
                "course", "programme", "program")
WEAK_WORDS = ("study", "studies", "academics", "admissions", "apply", "future-students")

INDEX_WORDS = STRONG_WORDS + WEAK_WORDS

# Never follow these, whatever they are called. They are large, they are not
# courses, and a crawl that wanders into them spends its budget on news.
AVOID = ("news", "events", "blog", "alumni", "giving", "donate", "shop",
         "library", "research", "staff", "contact", "privacy", "cookie",
         "accessibility", "jobs", "vacancies", "sport", "login", "portal")

MAX_COURSES_PER_PAGE = 40


def course_id(source_url: str, title: str, level: str) -> str:
    """One course, one row, forever.

    Keyed on the page, the title and the level together. Level is in the key
    because a school genuinely offers "Computer Science" at three levels and
    they are three different courses with three different entry requirements.
    """
    key = f"{source_url}|{_normalise(title)}|{level}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Course:
    """One course a school published, with the words that say so."""

    course_id: str
    jurisdiction: str
    institution: str
    title: str
    level: str

    # The verbatim span that names this course on the page. Checked before the
    # row is kept, exactly like a requirement's quote.
    quote: str = ""
    source_url: str = ""
    read_at: str = ""

    # Everything below is optional and is absent rather than guessed.
    subject: str = ""
    duration: str = ""
    intake: str = ""
    intake_open: bool = False
    fee_international: str = ""
    fee_amount: float | None = None
    fee_currency: str = ""
    entry_requirements: str = ""

    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, "")}


PROMPT = """You are reading one page from a university or college website.

List the COURSES this page describes that a person could apply to. For each one:

  "title": the course name as printed, for example "MSc Civil Engineering"
  "level": exactly one of bachelors, masters, doctorate. Use the page's own
           words. A "BSc", "BA", "BEng" or "undergraduate" course is bachelors.
           An "MSc", "MA", "MBA", "LLM" or "taught postgraduate" course is
           masters. A "PhD", "DPhil", "professional doctorate" or "DBA" is
           doctorate. If the page does not say, omit the course entirely.
  "quote": a VERBATIM span copied exactly from the page that names this course.
           Character for character.
  "subject": the field of study in a few words, if the page states it
  "duration": as printed, for example "3 years full-time", if stated
  "intake": when the course starts or when applications open, AS PRINTED. Only
            if the page says. Never write "September" because courses usually
            start then.
  "fee_international": the fee for international or overseas students, as
            printed, including the currency. Only if the page states it. Do not
            give the home or domestic fee here.
  "entry_requirements": what the page says an applicant must already have, in
            one sentence, if stated

RULES
- Only courses this page actually describes. An index page listing course names
  is fine; a page about campus life has no courses on it.
- Every quote is checked against the page text automatically. Anything that does
  not appear word for word is discarded, so copy exactly.
- Omit any field the page does not state. Do not infer, estimate or complete.
- If the page describes no applicable courses, return an empty list.

Return only JSON: {"courses": [...]}"""


def looks_like_index(url: str, text: str = "") -> bool:
    lowered = url.lower()
    if any(word in lowered for word in AVOID):
        return False
    return any(word in lowered for word in INDEX_WORDS)


def course_links(html: str, base_url: str, limit: int = 25) -> list[str]:
    """Links from a page that plausibly lead to courses.

    Deliberately dull: it reads the href and the anchor text and keeps the ones
    that say "courses" or "programmes". A model choosing links would be a second
    model call per page to answer a question a substring match answers.
    """
    from urllib.parse import urljoin, urlparse

    base_host = urlparse(base_url).netloc.lower()
    found: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for match in re.finditer(r'<a\s[^>]*href="([^"#?]+)"[^>]*>(.*?)</a>',
                             html, re.S | re.I):
        href, label = match.group(1), re.sub(r"<[^>]+>", " ", match.group(2))
        url = urljoin(base_url, href)
        parsed = urlparse(url)

        # Same school only. A link to a partner university is that university's
        # course, filed under this one's name, which is D29's shape again.
        if parsed.netloc.lower() != base_host or parsed.scheme not in ("http", "https"):
            continue
        if url in seen:
            continue

        haystack = f"{parsed.path.lower()} {label.lower()}"
        if any(word in haystack for word in AVOID):
            continue
        if not any(word in haystack for word in INDEX_WORDS):
            continue

        seen.add(url)
        # Rank rather than take in document order. A navigation bar lists
        # "Apply" before "Courses" often enough that document order sends the
        # reader to the wrong page on most university sites.
        strength = next((len(STRONG_WORDS) - i for i, w in enumerate(STRONG_WORDS)
                         if w in haystack), 0)
        found.append((strength, len(parsed.path), url))

    found.sort(key=lambda item: (-item[0], item[1]))
    return [url for _strength, _length, url in found[:limit]]


class CourseReader:
    """Reads one page and keeps only the courses it can be shown to describe."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def read(self, url: str, page: Any, jurisdiction: str,
             institution: str) -> tuple[list[Course], list[dict[str, str]]]:
        """Courses kept, and courses dropped with the reason.

        Takes the fetched page rather than a decoded string, because page_text
        needs the content type to decode it: a French-language course page
        served as latin-1 comes out as mojibake otherwise, and every quote check
        against it then fails for the wrong reason.
        """
        return self.read_text(url, page_text(page), jurisdiction, institution)

    def read_text(self, url: str, raw_text: str, jurisdiction: str,
                  institution: str) -> tuple[list[Course], list[dict[str, str]]]:
        """The same read, from text somebody else extracted.

        Exists because a course catalogue is usually a JavaScript application.
        The static HTML of a university's "courses" page is a shell, a search box
        and a footer, and the courses arrive from an API afterwards. Reading the
        shell finds nothing and concludes the school teaches nothing, which is
        wrong about the school rather than honest about the page.

        So the deep pass renders those pages in a browser and hands the rendered
        text here. That is not a way around anybody's rules: the robots gate
        still decides whether the page may be fetched at all, and rendering only
        changes how completely we read a page we are already allowed to read.
        """
        text = (raw_text or "")[:MAX_CHARS]
        if len(text) < 200:
            return [], [{"why": "the page had almost no text on it"}]

        try:
            parsed = call_json(
                project=self._project, model=self._model, location=self._location,
                credentials=self._credentials,
                parts=[{"text": PROMPT + "\n\nPAGE:\n" + text}],
                max_output_tokens=8192,
            )
        except Exception as exc:  # noqa: BLE001
            return [], [{"why": f"the reader failed: {type(exc).__name__}"}]

        haystack = _normalise(text)
        now = _now()
        kept: list[Course] = []
        dropped: list[dict[str, str]] = []

        for item in (parsed.get("courses") or [])[:MAX_COURSES_PER_PAGE]:
            title = str(item.get("title") or "").strip()
            level = str(item.get("level") or "").strip().lower()
            quote = str(item.get("quote") or "").strip()

            if not title:
                continue
            if level not in LEVELS:
                # A level we cannot read is a course we do not keep. Defaulting
                # it would put doctorates in front of school leavers.
                dropped.append({"title": title, "level": level,
                                "why": "the page does not state a level we serve"})
                continue
            if not quote or _normalise(quote) not in haystack:
                dropped.append({"title": title, "level": level,
                                "why": "the quote is not on the page"})
                continue

            fee = str(item.get("fee_international") or "").strip()
            amount, currency = _money(fee)

            kept.append(Course(
                course_id=course_id(url, title, level),
                jurisdiction=jurisdiction,
                institution=institution,
                title=title,
                level=level,
                quote=quote,
                source_url=url,
                read_at=now,
                subject=str(item.get("subject") or "").strip(),
                duration=str(item.get("duration") or "").strip(),
                intake=str(item.get("intake") or "").strip(),
                # An intake we can see stated is an intake we can call open.
                # Silence is not an open door and is not treated as one.
                intake_open=bool(str(item.get("intake") or "").strip()),
                fee_international=fee,
                fee_amount=amount,
                fee_currency=currency,
                entry_requirements=str(item.get("entry_requirements") or "").strip(),
                verified=True,
            ))

        return kept, dropped


_MONEY = re.compile(r"(£|\$|€|C\$|CAD|GBP|USD|EUR)\s?([\d][\d,\.]{2,})", re.I)

_CURRENCIES = {"£": "GBP", "$": "USD", "€": "EUR", "c$": "CAD",
               "cad": "CAD", "gbp": "GBP", "usd": "USD", "eur": "EUR"}


def _money(text: str) -> tuple[float | None, str]:
    """A number and a currency out of a printed fee, or nothing.

    The rubric compares tuition across countries, so a fee has to become a
    number somewhere. It happens here, from the printed string, and both are
    kept: the string is what the school said and the number is what we did with
    it. Where the string cannot be parsed the number is absent, and a country
    with no parsed fee scores nothing on cost rather than scoring well.
    """
    match = _MONEY.search(text or "")
    if not match:
        return None, ""
    symbol = match.group(1).lower()
    try:
        amount = float(match.group(2).replace(",", ""))
    except ValueError:
        return None, ""
    return amount, _CURRENCIES.get(symbol, "")


class Courses:
    """Stores courses. Its own collection, like occupations and institutions."""

    COLLECTION = COURSES

    def __init__(self, client) -> None:
        self._db = client

    def record(self, courses: list[Course]) -> int:
        if not courses:
            return 0
        batch = self._db.batch()
        for n, course in enumerate(courses, 1):
            batch.set(self._db.collection(COURSES).document(course.course_id),
                      course.to_dict(), merge=True)
            if n % 400 == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return len(courses)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for doc in self._db.collection(COURSES).select(["jurisdiction"]).stream():
            key = doc.to_dict().get("jurisdiction", "?")
            out[key] = out.get(key, 0) + 1
        return out

    def for_level(self, jurisdiction: str, level: str, limit: int = 500) -> list[dict]:
        from google.cloud import firestore

        query = (self._db.collection(COURSES)
                 .where(filter=firestore.FieldFilter("jurisdiction", "==", jurisdiction))
                 .where(filter=firestore.FieldFilter("level", "==", level))
                 .limit(limit))
        return [d.to_dict() for d in query.stream()]
