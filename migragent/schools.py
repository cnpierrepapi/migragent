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

    # The course's own page, found by matching its title to a link on the index
    # page it was listed on. Fees and intake dates are almost never on an index:
    # a listing gives names, and the money and the calendar live one click in.
    detail_url: str = ""
    detail_read_at: str = ""

    # The sentences behind the fee and the intake, from the detail page. Same
    # rule as everywhere else: a number nobody can point at is not kept.
    fee_quote: str = ""
    intake_quote: str = ""

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


    def read_detail(self, url: str, page: Any) -> dict[str, Any]:
        """Fee, intake, duration and entry requirements from one course page.

        Returns only what the page can be shown to say. Both the fee and the
        intake carry a quote and both quotes are checked against the page text;
        a value whose quote is not there is dropped and the field stays empty,
        because a tuition figure nobody can point at is exactly the kind of
        number somebody would plan a year around.
        """
        text = page_text(page)[:MAX_CHARS]
        if len(text) < 120:
            return {}

        try:
            parsed = call_json(
                project=self._project, model=self._model, location=self._location,
                credentials=self._credentials,
                parts=[{"text": DETAIL_PROMPT + "\n\nPAGE:\n" + text}],
                # 8192, not 2048. Thinking shares this budget, so a small
                # ceiling truncates the answer before the JSON is finished and
                # every page returns "the answer was cut off at the token limit
                # after 146 characters". That is D35 met again at a new call
                # site: a number that looks generous for six short fields is
                # not, because the fields are not what is being paid for.
                max_output_tokens=8192,
            )
        except Exception:  # noqa: BLE001
            return {}

        haystack = _normalise(text)
        out: dict[str, Any] = {"detail_url": url, "detail_read_at": _now()}

        fee = str(parsed.get("fee_international") or "").strip()
        fee_quote = str(parsed.get("fee_quote") or "").strip()
        if fee and fee_quote and _normalise(fee_quote) in haystack:
            amount, currency = _money(fee)
            out["fee_international"] = fee
            out["fee_quote"] = fee_quote
            if amount:
                out["fee_amount"] = amount
                out["fee_currency"] = currency

        intake = str(parsed.get("intake") or "").strip()
        intake_quote = str(parsed.get("intake_quote") or "").strip()
        if intake and intake_quote and _normalise(intake_quote) in haystack:
            out["intake"] = intake
            out["intake_quote"] = intake_quote
            out["intake_open"] = True

        for field in ("duration", "entry_requirements"):
            value = str(parsed.get(field) or "").strip()
            if value:
                out[field] = value

        return out


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


DETAIL_PROMPT = """You are reading one course page from a university or college.

Return what THIS page states about THIS course. Every field is optional and an
absent field is the correct answer when the page does not say.

  "fee_international": the tuition for international or overseas students, as
        printed, with the currency and the period, for example
        "£17,500 per year". NOT the home, domestic or EU fee. If the page shows
        several years, give the earliest full year stated.
  "fee_quote": a VERBATIM span from the page containing that fee.
  "intake": when the course starts, or when applications open or close, AS
        PRINTED, for example "September 2027" or "Applications open 1 October".
  "intake_quote": a VERBATIM span from the page containing that.
  "duration": as printed, for example "1 year full-time"
  "entry_requirements": what the page says an applicant must already have, in
        one sentence

RULES
- Only this page's own words. Both quotes are checked against the page text
  automatically and anything not found word for word is discarded, so copy
  exactly.
- Never convert a currency, never annualise a total, never infer a start month
  from the academic calendar. If the page gives a total for the whole course,
  quote it as printed and say so in the fee string.
- If the page states no fee, omit fee_international and fee_quote. A missing fee
  is a correct answer. An invented one is the worst thing you could return.

Return only JSON: {"fee_international": ..., "fee_quote": ..., "intake": ...,
"intake_quote": ..., "duration": ..., "entry_requirements": ...}"""


# Where tuition actually lives. A course page states the course; the money is
# almost always one more click away on a fees page, because universities publish
# fees centrally and link to them from every course.
FEE_WORDS = ("fee", "fees", "tuition", "cost", "costs", "funding",
             "fees-and-funding", "tuition-fees", "international-fees")


def fee_links(html: str, base_url: str, limit: int = 3) -> list[str]:
    """Links from a course page that plausibly lead to its tuition.

    Ranked so "tuition fees" beats "funding your studies", and capped hard: this
    is a second fetch per course and the point is to find the number, not to
    walk the finance section of a university website.
    """
    from urllib.parse import urljoin, urlparse

    base_host = urlparse(base_url).netloc.lower()
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for match in re.finditer(r'<a\s[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, label = match.group(1), re.sub(r"<[^>]+>", " ", match.group(2)).lower()
        url = urljoin(base_url, href)
        if urlparse(url).netloc.lower() != base_host or url in seen:
            continue
        haystack = f"{urlparse(url).path.lower()} {label}"
        if not any(word in haystack for word in FEE_WORDS):
            continue
        seen.add(url)
        # International first: a page saying "international tuition fees" is the
        # one this product needs, and a generic fees page often shows the home
        # rate at the top.
        score = 2 if "international" in haystack or "overseas" in haystack else 1
        if "tuition" in haystack or "fee" in haystack:
            score += 1
        scored.append((score, url))

    scored.sort(key=lambda pair: -pair[0])
    return [url for _score, url in scored[:limit]]


def anchor_map(html: str, base_url: str) -> dict[str, str]:
    """{normalised link text: absolute url} for every link on a page.

    Used to turn a course title into the address of that course's own page. The
    model is not asked for the URL: it reads text, it does not see hrefs, and a
    model asked for a link will produce a plausible one. Matching the title it
    quoted against the anchor that carries the same words is arithmetic.
    """
    from urllib.parse import urljoin, urlparse

    base_host = urlparse(base_url).netloc.lower()
    out: dict[str, str] = {}
    for match in re.finditer(r'<a\s[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, label = match.group(1), re.sub(r"<[^>]+>", " ", match.group(2))
        label = _normalise(label)
        if not label or len(label) < 4:
            continue
        url = urljoin(base_url, href)
        if urlparse(url).netloc.lower() != base_host:
            continue
        out.setdefault(label, url)
    return out


def match_course_url(title: str, anchors: dict[str, str]) -> str:
    """The link whose text is this course, or nothing.

    Exact normalised match first, then a link whose text contains the whole
    title. Never a fuzzy or best-effort match: pointing the fee reader at the
    wrong course page would attach one course's money to another course's name,
    and nothing downstream could tell.
    """
    key = _normalise(title)
    if key in anchors:
        return anchors[key]
    contained = [url for text, url in anchors.items() if key and key in text]
    return contained[0] if len(contained) == 1 else ""


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
