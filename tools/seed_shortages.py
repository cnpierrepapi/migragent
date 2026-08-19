"""Register the shortage lists, then read them.

    python -m tools.seed_shortages --dry-run
    python -m tools.seed_shortages            register the pages
    python -m tools.seed_shortages --read     register, then extract occupations

Every URL below was fetched and returned a real page before it was written here.
Where a country's list could not be read, it is absent and the reason is in the
comment beside it rather than a plausible URL nobody checked.

These rows are `kind = shortage_list`, so they are watched by the same daily
round as everything else, which matters more here than anywhere: Spain republishes
its catalogue every quarter and the UK revises its salary list with the rules.
"""
from __future__ import annotations

import hashlib
import re
import sys

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.occupations import ShortageReader, Shortages  # noqa: E402
from migragent.registry import Registry, Source  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
MODEL = "gemini-3.5-flash"
MODEL_LOCATION = "global"

# jurisdiction, url, title, language
LISTS = [
    # The publication page is a wrapper around a spreadsheet attachment and
    # names no occupations at all, which the first run showed by keeping zero
    # from it. The immigration rules appendix is the same list in HTML, so it is
    # what gets read. The wrapper stays registered and watched, because it is
    # where a person lands and where a change would be announced.
    ("UK", "https://www.gov.uk/guidance/immigration-rules/"
           "immigration-rules-appendix-immigration-salary-list",
     "Immigration Rules Appendix Immigration Salary List", "en"),
    ("UK", "https://www.gov.uk/guidance/immigration-rules/"
           "immigration-rules-appendix-skilled-occupations",
     "Immigration Rules Appendix Skilled Occupations", "en"),
    ("UK", "https://www.gov.uk/government/publications/skilled-worker-visa-immigration-salary-list",
     "Immigration salary list, publication page", "en"),

    # Canada does not publish an occupation shortage list for immigration. It
    # publishes the categories it selects for, which is the same idea expressed
    # as groups of work rather than job titles, and it is the page that decides
    # who gets invited.
    ("CA", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/"
           "express-entry/submit-profile/rounds-invitations.html",
     "Express Entry rounds of invitations", "en"),
    ("CA", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/"
           "express-entry/eligibility/find-national-occupation-code.html",
     "National Occupational Classification codes", "en"),

    # Spain publishes the catalogue in the official gazette every quarter. Both
    # the gazette resolution and the employment service's own page are read: the
    # first is the authority, the second is where a person would actually land.
    ("ES", "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-4944",
     "Catalogo de Ocupaciones de Dificil Cobertura, primer trimestre 2026", "es"),
    ("ES", "https://www.sepe.es/HomeSepe/en/empresas/informacion-para-empresas/"
           "profesiones-de-dificil-cobertura/profesiones-mas-demandadas.html",
     "Profesiones de dificil cobertura", "es"),

    ("DE", "https://statistik.arbeitsagentur.de/DE/Navigation/Statistiken/"
           "Interaktive-Statistiken/Fachkraeftebedarf/Engpassanalyse-Nav.html",
     "Fachkraefteengpassanalyse", "de"),

    # NOT INCLUDED, and each of these is a fact rather than an omission:
    #
    # France   legifrance.gouv.fr will not serve its robots.txt, so the arrete
    #          listing metiers en tension cannot be read. francetravail.fr
    #          returns 24 characters to a client without JavaScript.
    # Italy    the labour ministry's decreto flussi pages 404 at every path
    #          tried. Italy's quota system is also not a shortage list in the
    #          same sense.
    # Portugal IEFP serves a homepage; no published shortage list was found on
    #          a readable path.
    # UAE, SA  no published shortage list found.
]


def source_id(jurisdiction: str, url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0].replace(".", "-")
    tail = re.sub(r"[^a-z0-9]+", "-", url.split(host, 1)[-1].lower()).strip("-")[-40:] or "root"
    digest = hashlib.sha256(url.encode()).hexdigest()[:8]
    return f"{jurisdiction.lower()}-shortage-{host}-{tail}-{digest}"


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    do_read = "--read" in sys.argv

    fetcher = Fetcher(delay_seconds=1.5)
    reader_creds = identity.credentials_for(identity.RESEARCHER, PROJECT)
    writer_creds = identity.credentials_for(identity.WRITER, PROJECT)
    writer_db = firestore.Client(project=PROJECT, credentials=writer_creds)

    registry = Registry(writer_db)
    shortages = Shortages(writer_db)
    shortage_reader = ShortageReader(PROJECT, MODEL, MODEL_LOCATION, reader_creds)

    print(f"checking {len(LISTS)} shortage lists\n")
    built: list[tuple[Source, object]] = []

    for jurisdiction, url, title, language in LISTS:
        page = fetcher.fetch(url)
        state, why = fetcher.permission(url)

        source = Source(
            source_id=source_id(jurisdiction, url),
            jurisdiction=jurisdiction,
            # A shortage list is about work, and saying so keeps it out of every
            # study guide without a second rule to remember.
            lane="work",
            kind="shortage_list",
            url=url,
            title=title,
            language=language,
            provenance="official",
            discovered_via="seed",
            depth=0,
            robots_allowed=(state == "allowed"),
            robots_checked_at=page.read_at,
        )

        if page.ok:
            source.last_read_at = page.read_at
            source.last_status = page.status
            source.stable_sha256 = page.sha256
            source.raw_sha256 = page.raw_sha256
            print(f"  ok       {jurisdiction}  {page.status}, {len(page.body):,} bytes  {title}")
        elif page.outcome == "network_unknown":
            source.unverified_reason = page.reason
            source.last_attempt_at = page.read_at
            print(f"  unknown  {jurisdiction}  {(page.reason or '')[:60]}")
        else:
            source.blocked = {"blocked_by_robots": "robots_disallowed",
                              "refused": "server_refused",
                              "unreachable": "gone",
                              "not_html": "not_html"}[page.outcome]
            source.blocked_reason = page.reason or why
            source.last_attempt_at = page.read_at
            print(f"  BLOCKED  {jurisdiction}  {source.blocked_reason}")

        built.append((source, page))

    if dry_run:
        print("\ndry run, nothing written")
        return 0

    registry.bulk_put([s for s, _ in built])
    print(f"\nwrote {len(built)} shortage list rows")

    if not do_read:
        print("pass --read to extract occupations from them")
        return 0

    print("\nreading them\n")
    total = dropped = 0
    for source, page in built:
        if not page.ok:
            continue
        reading = shortage_reader.read(page, source.jurisdiction, source.language)
        if reading.model_error:
            print(f"  {source.jurisdiction}  model error: {reading.model_error[:70]}")
            continue
        kept = shortages.record(reading, source.source_id)
        total += kept
        dropped += len(reading.dropped)
        print(f"  {source.jurisdiction}  kept {kept:>4}  dropped {len(reading.dropped):>3}  "
              f"publisher={str(reading.publisher)[:28]}  period={str(reading.period)[:22]}")
        for d in reading.dropped[:3]:
            print(f"        dropped: {d.get('title', '')[:40]} ({d.get('why', '')})")

    print(f"\n{total} occupations kept, {dropped} dropped")
    print(f"occupations now: {shortages.counts()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
