"""Read the schools: shallow over all of them, deep over the ranked few.

    python -m tools.ingest_schools --shallow --limit 300
    python -m tools.ingest_schools --deep --limit 20
    python -m tools.ingest_schools --details --limit 200
    python -m tools.ingest_schools --plan

TWO PASSES, AND WHY
-------------------
SHALLOW is one request per school: fetch the homepage through the robots gate
and find the link to its course listing. It costs no model calls, it establishes
which schools are reachable and willing at all, and it leaves a `courses_url` on
the row so the deep pass has somewhere to start.

DEEP reads that course listing and the pages it links to, and turns them into
courses with quotes. It costs a model call per page, so it is spent on a ranked
list rather than on whoever happens to sort first.

HOW THE RANKING WORKS, AND WHAT IT IS ALLOWED TO BE
----------------------------------------------------
Canada: study permit holders per institution, published by IRCC. A real count of
the real thing.

The United Kingdom: HESA's equivalent is behind a Cloudflare challenge this
project will not defeat, so UK schools are ordered by the share of residents born
outside the UK in the local authority they sit in. That is an inference and a
sizeable one. It is acceptable ONLY because it decides which schools we read and
never appears anywhere: being wrong means reading the wrong hundred schools.

Both are filtered to higher education, because the UK register is half
independent secondary schools and a person applying for a BSc will never go to
one. That filter is imperfect too, and the deep read is the real one: a school
with no degree-level courses produces no courses and drops out by itself.

THE GATE IS THE GATE
--------------------
Universities are not governments and this changes nothing. A school that will not
serve robots.txt is not crawled, one that disallows us is not crawled, and the
outcome is recorded on the row so a later run does not try again for nothing.
"""
from __future__ import annotations

import sys
import time
from typing import Any

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402
from migragent.schools import (Course, CourseReader, Courses, anchor_map,  # noqa: E402
                               contact_links, course_links, fee_links,
                               match_course_url)

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
MODEL = "gemini-3.5-flash"
LOCATION = "global"

# Pages read per school on the deep pass. Each is a model call, and a school's
# course index plus a handful of listing pages is enough to know what it teaches
# at each level. Reading a whole prospectus would spend the budget on one school.
PAGES_PER_SCHOOL = 4


def rank(db) -> list[dict[str, Any]]:
    """The deep reading order. See the module docstring for what it rests on."""
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(Institutions.COLLECTION).stream()]

    def eligible(row: dict) -> bool:
        if not row.get("website") or not row.get("higher_ed"):
            return False
        routes = row.get("routes") or []
        # Child Student only is a school, not a university. The register says so
        # itself, and it is the one part of this filter that comes from the
        # government rather than from Wikidata.
        if routes and "Student" not in routes:
            return False
        return True

    # RANKED WITHIN EACH COUNTRY, THEN INTERLEAVED, because the two scores are
    # not the same kind of number and comparing them directly is meaningless.
    # Canada's is a headcount of permit holders; the UK's is a percentage of a
    # local population. Multiplying the percentage by a thousand to make the
    # magnitudes look similar, which is what this did first, put every London
    # school above every Canadian one except Toronto. That was a units error
    # dressed as a judgement.
    per_country: dict[str, list[dict]] = {}
    for row in rows:
        if not eligible(row):
            continue
        code = row.get("jurisdiction", "")
        if code == "CA":
            # Canada publishes the real thing: permit holders per institution.
            score = float(row.get("intl_students") or 0)
        else:
            # THE UK, IN ORDER OF HOW CLOSE THE NUMBER IS TO THE QUESTION.
            #
            # 1. international_share, where an earlier build already stored it:
            #    the institution's own international student percentage, with a
            #    quote and a source. It is a Times Higher Education figure, so a
            #    commercial estimate rather than a government statistic, and it
            #    can never be displayed for that reason. For deciding which
            #    schools to READ it is far better than the alternative, because
            #    it is the actual quantity being asked about.
            # 2. intl_share_local, the census proxy: how many people in this
            #    town were born abroad. A real number about the wrong subject.
            #
            # Both are internal ranking only. The difference between them is
            # recorded on the row, not flattened into one field, so a later
            # reader can see which of the two produced an order.
            score = float(row.get("international_share") or 0)
            if score <= 0:
                # Scaled under the THE range on purpose: a school with a real
                # percentage should outrank one carried only by its postcode,
                # and 100 is the ceiling of the first scale.
                score = float(row.get("intl_share_local") or 0) / 100.0
        # A school with no score is not unreadable, it is unranked. Canada has
        # institutions IRCC suppressed the count for; the UK has towns the census
        # does not name as a local authority. Dropping them meant 155 readable
        # schools were never read because we did not know where to put them in a
        # queue, which is the tail wagging the dog.
        #
        # They go after everything scored, in name order, and get read when the
        # ranked ones are done.
        row["_score"] = score
        per_country.setdefault(code, []).append(row)

    for code, group in per_country.items():
        # Name as the tiebreak so a run is reproducible. Every London school
        # shares one area figure, so within London the order IS arbitrary; it is
        # at least arbitrary the same way every time. Unscored schools sort last
        # because -0.0 is the smallest key here, not because they are worth less.
        group.sort(key=lambda r: (-r["_score"], r.get("name", "")))

    # Alternate, so a budget spent early still covers both countries. Neither
    # country is more deserving and the reading order should not decide that.
    ranked: list[dict] = []
    queues = [list(g) for g in per_country.values()]
    while any(queues):
        for queue in queues:
            if queue:
                ranked.append(queue.pop(0))
    return ranked


def shallow(db, fetcher: Fetcher, rows: list[dict], limit: int) -> None:
    """One fetch per school: is it reachable, and where does it list courses."""
    done = reachable = indexed = 0

    for row in rows[:limit]:
        site = row.get("website")
        name = row.get("name", "")
        done += 1

        state, why = fetcher.permission(site)
        if state != "allowed":
            db.collection(Institutions.COLLECTION).document(row["id"]).set(
                {"site_state": state, "site_note": why[:200]}, merge=True)
            print(f"  {done:>4} {state:<11} {name[:44]}", flush=True)
            continue

        page = fetcher.fetch(site)
        if not page.ok:
            db.collection(Institutions.COLLECTION).document(row["id"]).set(
                {"site_state": "unreadable",
                 "site_note": f"{page.outcome}: {getattr(page, 'reason', '') or ''}"[:200]},
                merge=True)
            print(f"  {done:>4} unreadable  {name[:44]}", flush=True)
            continue

        reachable += 1
        html = page.body.decode("utf-8", "replace")
        links = course_links(html, site)
        payload = {"site_state": "reachable", "site_note": ""}
        if links:
            indexed += 1
            payload["courses_url"] = links[0]
            payload["courses_url_options"] = links[:6]
        # Where to send somebody with a question we cannot answer. Every course
        # we read will have gaps, and gaps.py turns each one into a question
        # pointed at this address. Found once here rather than per course.
        contacts = contact_links(html, site)
        if contacts:
            payload["contact_url"] = contacts[0]
        db.collection(Institutions.COLLECTION).document(row["id"]).set(payload, merge=True)
        print(f"  {done:>4} ok          {name[:44]:46} {len(links)} course links",
              flush=True)

    print(f"\nshallow: {done} tried, {reachable} reachable, {indexed} with a course index")


def deep(db, fetcher: Fetcher, reader: CourseReader, rows: list[dict],
         limit: int, browser: Any = None) -> None:
    """Read the course pages and store what they can be shown to say."""
    store = Courses(db)
    schools = kept = dropped = 0

    for row in rows[:limit]:
        # Seed from EVERY candidate index, not just the best-ranked one. Ranking
        # links is a guess, and a wrong guess used to cost the whole school:
        # Manchester's queue started at /study/cpd/ and never reached
        # /study/masters/courses/. Reading four candidates costs the same four
        # pages the crawl was going to spend anyway, and it stops one bad guess
        # from silently deleting a university.
        starts = [u for u in (row.get("courses_url_options") or []) if u]
        if not starts:
            starts = [u for u in (row.get("courses_url"), row.get("website")) if u]
        if not starts or row.get("site_state") not in (None, "reachable"):
            continue

        name, code = row.get("name", ""), row.get("jurisdiction", "")
        schools += 1
        print(f"\n  {name[:56]}  ({code})", flush=True)

        queue = list(starts[:PAGES_PER_SCHOOL])
        seen: set[str] = set()
        got: list[Course] = []

        while queue and len(seen) < PAGES_PER_SCHOOL:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)

            state, _why = fetcher.permission(url)
            if state != "allowed":
                continue
            page = fetcher.fetch(url)
            if not page.ok:
                continue

            html = page.body.decode("utf-8", "replace")
            courses, misses = reader.read(url, page, code, name)

            # A course catalogue is usually a JavaScript application: the HTML
            # that arrives is a shell, a search box and a footer, and the courses
            # are fetched afterwards. Reading the shell finds nothing and
            # concludes the school teaches nothing, which is wrong about the
            # school rather than honest about the page.
            #
            # So a page that yields nothing is rendered and read again. The
            # BrowserFetcher checks the robots gate itself before it opens
            # anything, and identifies as MIGRAGENT rather than impersonating
            # somebody's Chrome: this is for meeting a transport, never for
            # getting past a policy or a bot check.
            if not courses and browser is not None:
                rendered = browser.fetch(url)
                if rendered.ok:
                    courses, misses = reader.read(url, rendered, code, name)
                    html = rendered.body.decode("utf-8", "replace")
                    if courses:
                        print(f"      {len(courses):>3} kept after rendering   {url[:56]}",
                              flush=True)

            got += courses
            dropped += len(misses)
            if courses or misses:
                print(f"      {len(courses):>3} kept, {len(misses):>3} dropped   {url[:60]}",
                      flush=True)

            if len(seen) < PAGES_PER_SCHOOL:
                for link in course_links(html, url, limit=6):
                    if link not in seen:
                        queue.append(link)

        if got:
            store.record(got)
            kept += len(got)
            db.collection(Institutions.COLLECTION).document(row["id"]).set(
                {"courses_read_at": got[0].read_at, "courses_found": len(got)},
                merge=True)

    print(f"\ndeep: {schools} schools, {kept} courses kept, {dropped} dropped")
    print(f"courses now held: {store.counts()}")


def details(db, fetcher: Fetcher, reader: CourseReader, limit: int,
            browser: Any = None) -> None:
    """Open each course's own page and read the fee and the intake off it.

    A course index gives names. The money and the calendar are one click in, on
    the course's own page, which is why the deep pass produced 173 courses with
    ten intake dates and no fees at all between them.

    The link is found by matching the course title against the anchors on the
    index page it came from, in plain code. The model is never asked for a URL:
    it reads text, it does not see hrefs, and a model asked for a link produces a
    plausible one. A title that matches no anchor, or more than one, is skipped
    rather than guessed at, because pointing the fee reader at the wrong page
    would attach one course's money to another course's name and nothing
    downstream could tell.
    """
    store = Courses(db)
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(store.COLLECTION).stream()]
    todo = [r for r in rows if not r.get("detail_read_at")][:limit]
    print(f"{len(rows)} courses held, {len(todo)} without a detail read\n")

    # Grouped by the index page they came from, so each index is fetched once
    # for its links rather than once per course listed on it.
    by_index: dict[str, list[dict]] = {}
    for row in todo:
        by_index.setdefault(row.get("source_url", ""), []).append(row)

    found = fees = intakes = skipped = 0

    for index_url, courses in by_index.items():
        if not index_url:
            continue
        page = fetcher.fetch(index_url)
        html = page.body.decode("utf-8", "replace") if page.ok else ""
        if not html and browser is not None:
            rendered = browser.fetch(index_url)
            if rendered.ok:
                html = rendered.body.decode("utf-8", "replace")
        anchors = anchor_map(html, index_url) if html else {}
        print(f"  {len(anchors)} links on {index_url[:66]}", flush=True)

        for row in courses:
            url = match_course_url(row.get("title", ""), anchors)
            if not url:
                skipped += 1
                continue

            detail = fetcher.fetch(url)
            if not detail.ok and browser is not None:
                detail = browser.fetch(url)
            if not detail.ok:
                skipped += 1
                continue

            read = reader.read_detail(url, detail)
            if not read:
                skipped += 1
                continue

            # A course page states the course; the money is usually one more
            # click away, because universities publish tuition centrally and
            # link to it from every course. One hop, at most two pages, and only
            # when the course page itself gave no fee.
            if not read.get("fee_amount"):
                detail_html = detail.body.decode("utf-8", "replace")
                for fee_url in fee_links(detail_html, url, limit=2):
                    fee_page = fetcher.fetch(fee_url)
                    if not fee_page.ok and browser is not None:
                        fee_page = browser.fetch(fee_url)
                    if not fee_page.ok:
                        continue
                    more = reader.read_detail(fee_url, fee_page)
                    if more.get("fee_amount"):
                        # Only the money is taken from the fees page. Its intake
                        # and entry requirements, if it has any, belong to
                        # whatever course that page is about, which is usually
                        # all of them.
                        for field in ("fee_international", "fee_quote",
                                      "fee_amount", "fee_currency"):
                            if more.get(field):
                                read[field] = more[field]
                        read["fee_source_url"] = fee_url
                        break

            found += 1
            if read.get("fee_amount"):
                fees += 1
            if read.get("intake"):
                intakes += 1
            db.collection(store.COLLECTION).document(row["id"]).set(read, merge=True)
            print(f"      {row.get('title','')[:38]:40} "
                  f"fee={read.get('fee_international','-')[:22]:24} "
                  f"intake={read.get('intake','-')[:20]}", flush=True)

    print(f"\ndetails: {found} pages read, {fees} with a fee, "
          f"{intakes} with an intake, {skipped} skipped")


def contacts(db, fetcher: Fetcher, rows: list[dict], limit: int) -> None:
    """Backfill the contact page for schools whose homepage was already read.

    A separate pass because contact discovery arrived after the shallow pass had
    already run over two hundred schools, and re-running the whole thing to pick
    up one field would re-fetch two hundred homepages for no other reason.
    """
    done = found = 0
    for row in rows[:limit]:
        if row.get("contact_url") or not row.get("website"):
            continue
        if row.get("site_state") not in (None, "reachable"):
            continue
        done += 1
        page = fetcher.fetch(row["website"])
        if not page.ok:
            continue
        html = page.body.decode("utf-8", "replace")
        links = contact_links(html, row["website"])
        if not links:
            continue
        found += 1
        db.collection(Institutions.COLLECTION).document(row["id"]).set(
            {"contact_url": links[0]}, merge=True)
        print(f"  {row.get('name','')[:44]:46} {links[0][:60]}", flush=True)

    print(f"\ncontacts: {done} checked, {found} with a contact page")


def main() -> int:
    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    rows = rank(db)

    limit = 25
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    if "--plan" in sys.argv or not any(
            f in sys.argv for f in ("--shallow", "--deep", "--details",
                                    "--contacts", "--retry")):
        print(f"{len(rows)} schools eligible for deep reading\n")
        for i, row in enumerate(rows[:limit], 1):
            if row.get("jurisdiction") == "CA":
                basis = f"{int(row['_score']):,} permit holders"
            elif row.get("international_share"):
                basis = f"{row['international_share']:.0f}% international (THE)"
            elif row.get("intl_share_local"):
                basis = f"{row['intl_share_local']:.1f}% migrant area"
            else:
                basis = "unranked"
            print(f"  {i:>3}. {row.get('jurisdiction')} {row.get('name', '')[:44]:46}"
                  f"{basis}")
        return 0

    # One host at a time, and a real pause. These are not government sites with
    # a crawl budget to spare, and there are hundreds of them.
    fetcher = Fetcher(delay_seconds=1.5)

    if "--shallow" in sys.argv:
        shallow(db, fetcher, rows, limit)

    if "--contacts" in sys.argv:
        contacts(db, fetcher, rows, limit)

    if "--details" in sys.argv:
        reader = CourseReader(PROJECT, MODEL, LOCATION,
                              identity.credentials_for(identity.RESEARCHER, PROJECT))
        with BrowserFetcher(fetcher=fetcher) as browser:
            details(db, fetcher, reader, limit, browser=browser)

    if "--retry" in sys.argv:
        # Schools the deep pass reached and got nothing from. Before the link
        # ranking was fixed these were mostly real universities whose queue
        # started at a landing page, so they are worth reading again rather than
        # being written off as teaching nothing.
        rows = [r for r in rows
                if r.get("site_state") == "reachable" and not r.get("courses_found")]
        print(f"{len(rows)} schools were reachable and produced no courses\n")
        reader = CourseReader(PROJECT, MODEL, LOCATION,
                              identity.credentials_for(identity.RESEARCHER, PROJECT))
        with BrowserFetcher(fetcher=fetcher) as browser:
            deep(db, fetcher, reader, rows, limit, browser=browser)

    if "--deep" in sys.argv:
        reader = CourseReader(PROJECT, MODEL, LOCATION,
                              identity.credentials_for(identity.RESEARCHER, PROJECT))
        with BrowserFetcher(fetcher=fetcher) as browser:
            deep(db, fetcher, reader, rows, limit, browser=browser)

    return 0


if __name__ == "__main__":
    sys.exit(main())
