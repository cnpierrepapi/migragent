"""Seed the source registry with the government pages for seven jurisdictions.

Every candidate below is actually fetched before it is written, and whatever
came back is what gets recorded. A URL that 403s is stored as blocked with the
reason rather than quietly dropped, and a lane whose official page cannot be
read does not get to look covered. That is rules 5 and 11.

Nothing here is a claim that these are the only pages that matter. They are the
entry points; the researcher follows the site's own links from there.

Every URL below was fetched and returned 200 at least once, except the ones that
are recorded as blocked, which are blocked for reasons the run prints out. No
URL was added here on the strength of looking plausible.

    python tools/seed_registry.py            write to Firestore
    python tools/seed_registry.py --dry-run  fetch and report, write nothing
"""
from __future__ import annotations

import hashlib
import re
import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.registry import Registry, Source, source_id  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"

# jurisdiction, lane, url, title, language
CANDIDATES = [
    ("UK", "study", "https://www.gov.uk/student-visa",
     "Student visa", "en"),
    ("UK", "work", "https://www.gov.uk/skilled-worker-visa",
     "Skilled Worker visa", "en"),

    ("US", "study", "https://travel.state.gov/content/travel/en/us-visas/study/student-visa.html",
     "Student visa", "en"),
    ("US", "work",
     "https://travel.state.gov/content/travel/en/us-visas/employment/temporary-worker-visas.html",
     "Temporary worker visas", "en"),

    ("CA", "study",
     "https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/study-permit.html",
     "Study permit", "en"),
    ("CA", "work",
     "https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/permit.html",
     "Work permit", "en"),

    ("AU", "study", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500",
     "Student visa subclass 500", "en"),
    ("AU", "work",
     "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-independent-189",
     "Skilled Independent visa subclass 189", "en"),

    ("FR", "study", "https://www.service-public.fr/particuliers/vosdroits/F16162",
     "Titre de sejour etudiant", "fr"),
    ("FR", "work", "https://www.service-public.fr/particuliers/vosdroits/F2728",
     "Titre de sejour salarie", "fr"),

    # RESEEDED 19 August 2026. The first pair pointed at the foreign ministry:
    # a consular services index and a ministry homepage. Both are navigation,
    # and Spain produced ONE citable requirement while the same walk found 65
    # one hop further out. The entries were the problem, not the crawler.
    #
    # Requirements for living in Spain are published by the migration ministry,
    # not the foreign one, and each route has its own front door. Those pages
    # were unreachable until D24, because Spain's portal serves 403 to
    # Python's default user agent and 404 to a client that says who it is, and
    # a 404 means there is no robots.txt at all, which is permission.
    #
    # Still deliberately two different pages, one per lane. Seeding both lanes
    # with the same URL once made the navigation sample hold that page twice,
    # so every link looked like navigation and Spain returned zero. See D11.
    ("ES", "study",
     "https://www.inclusion.gob.es/web/migraciones/estudiar",
     "Estudiar en Espana", "es"),
    ("ES", "work",
     "https://www.inclusion.gob.es/web/migraciones/cuenta-ajena",
     "Residencia y trabajo por cuenta ajena", "es"),

    ("AE", "study", "https://u.ae/en/information-and-services/visa-and-emirates-id",
     "Visa and Emirates ID", "en"),
    ("AE", "work", "https://u.ae/en/information-and-services/jobs",
     "Jobs and employment", "en"),

    # Added 19 August 2026. Three European corridors and one Gulf corridor that
    # the first seven missed, chosen against where people actually move rather
    # than against a list somebody wrote down.
    #
    # Each of these was fetched before it was written here, and two obvious
    # candidates were rejected on what came back rather than on preference:
    #
    #   make-it-in-germany.com  Germany's own portal, behind a Radware bot wall
    #                           that returns a captcha to a real browser
    #   universitaly.it         Italy's student portal, returns "we need to
    #                           verify that you're not a robot"
    #
    # Both are refusals, and a refusal is not a puzzle to solve. We read the
    # ministries instead, which serve us without being asked twice.
    # Both Italian lanes on the visa portal, which publishes a page per visa
    # type including study and every category of work. The labour ministry was
    # the first choice for work and is a news site with a ministry attached.
    ("IT", "study", "https://vistoperitalia.esteri.it/infovisto?code=17_0_D",
     "Visto per studio, lunga permanenza", "it"),
    ("IT", "work", "https://vistoperitalia.esteri.it/infovisto?code=12_0_D",
     "Visto per lavoro subordinato, lunga permanenza", "it"),

    ("DE", "study",
     "https://www.bamf.de/EN/Themen/MigrationAufenthalt/ZuwandererDrittstaaten/Bildung/bildung-node.html",
     "Education and study in Germany", "en"),
    ("DE", "work",
     "https://www.bamf.de/EN/Themen/MigrationAufenthalt/ZuwandererDrittstaaten/Arbeit/arbeit-node.html",
     "Working in Germany", "en"),

    # Both Portuguese lanes on one host, deliberately. The walk learns what is
    # navigation by comparing pages of the same host, so a host with a single
    # entry page teaches it nothing and gets skipped entirely. Portugal, Italy
    # and Saudi Arabia were each seeded across two hosts with one page apiece and
    # all six were skipped for exactly that reason. See D26.
    ("PT", "study", "https://aima.gov.pt/pt/estudar",
     "Estudar em Portugal", "pt"),
    ("PT", "work", "https://aima.gov.pt/pt/trabalhar",
     "Trabalhar em Portugal", "pt"),

    # Two entries for the Saudi study lane, on one host, because one page on a
    # host teaches the walk nothing about what is navigation. The education
    # ministry's front page carries no links a crawler can follow at all, even
    # rendered, so the higher education page is what makes the pair possible.
    ("SA", "study", "https://www.moe.gov.sa/en/Pages/default.aspx",
     "Ministry of Education", "en"),
    ("SA", "study", "https://www.moe.gov.sa/en/education/highereducation/Pages/default.aspx",
     "Higher education", "en"),
    ("SA", "work", "https://www.hrsd.gov.sa/en",
     "Ministry of Human Resources and Social Development", "en"),
]


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    fetcher = Fetcher(delay_seconds=2.0)
    built: list[Source] = []

    print(f"checking {len(CANDIDATES)} government pages across "
          f"{len({c[0] for c in CANDIDATES})} jurisdictions\n")

    for jurisdiction, lane, url, title, language in CANDIDATES:
        result = fetcher.fetch(url)
        source = Source(
            source_id=source_id(jurisdiction, lane, url),
            jurisdiction=jurisdiction,
            lane=lane,
            kind="government",
            url=url,
            title=title,
            language=language,
            provenance="official",
            discovered_via="seed",
            robots_checked_at=result.read_at,
        )

        allowed, why = fetcher.allowed(url)
        source.robots_allowed = allowed

        if result.outcome == "fetched":
            source.last_read_at = result.read_at
            source.last_status = result.status
            source.stable_sha256 = result.sha256
            source.raw_sha256 = result.raw_sha256
            mark = "ok     "
            detail = f"{result.status}, {len(result.body):,} bytes"
        elif result.outcome == "network_unknown":
            # We could not reach it and we cannot say whose fault that is, so
            # the row says exactly that and stays retryable. D8.
            source.unverified_reason = result.reason
            source.last_attempt_at = result.read_at
            mark = "unknown"
            detail = f"no answer after {result.attempts} attempts, cause unknown"
        else:
            source.blocked = {
                "blocked_by_robots": "robots_disallowed",
                "refused": "server_refused",
                "unreachable": "gone",
                "not_html": "not_html",
            }[result.outcome]
            source.last_status = result.status
            source.blocked_reason = result.reason or why
            source.last_attempt_at = result.read_at
            mark = "BLOCKED"
            detail = source.blocked_reason

        print(f"  {mark}  {jurisdiction} {lane:<5}  {detail}")
        print(f"           {url}")
        built.append(source)

    readable = [s for s in built if s.readable]
    blocked = [s for s in built if s.blocked is not None]
    unknown = [s for s in built if s.unverified]

    print(f"\n{len(readable)} readable, {len(blocked)} blocked, "
          f"{len(unknown)} unverified, of {len(built)}")

    if unknown:
        print("\nUnverified. Nothing answered and we cannot say whose fault that is,")
        print("so these are not marked blocked and will be retried:")
        for s in unknown:
            print(f"  {s.jurisdiction} {s.lane}")

    if blocked:
        print("\nBlocked, and these lanes do not get to look covered:")
        for s in blocked:
            print(f"  {s.jurisdiction} {s.lane}: {s.blocked} ({s.blocked_reason})")

    lanes_with_nothing = sorted(
        {(s.jurisdiction, s.lane) for s in blocked}
        - {(s.jurisdiction, s.lane) for s in readable}
    )
    if lanes_with_nothing:
        print("\nLanes with NO readable official source at all:")
        for j, lane in lanes_with_nothing:
            print(f"  {j} {lane}")

    if dry_run:
        print("\ndry run, nothing written")
        return 0

    # The writer is the only identity that may write here.
    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WRITER, PROJECT),
    )
    registry = Registry(db)
    written = registry.bulk_put(built)
    print(f"\nwrote {written} rows")
    print(f"registry now: {registry.counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
