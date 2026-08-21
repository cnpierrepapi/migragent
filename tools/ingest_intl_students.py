"""How many international students each school actually takes, from the state.

    python -m tools.ingest_intl_students
    python -m tools.ingest_intl_students --dry

WHY THIS EXISTS
---------------
The study path is supposed to show schools that actually take people like the
person asking, and the deep reading budget has to go somewhere. Spending it on
whichever schools sound famous would be spending it on our own prejudice. So the
target list is ranked by a published number: how many international students a
school really has.

Build 3 concluded that this number "is not published per institution by any of
these governments" and left the field empty rather than estimate it. That was
half right. No government publishes a *percentage*, which is what was looked
for. Canada publishes the numerator, per institution, monthly, as open data.

CANADA: SOLID
-------------
IRCC publishes study permit holders by designated learning institution, on
open.canada.ca, under the Open Government Licence. 66,861 rows of monthly counts
per DLI. That is a direct count of international students per school from the
department that issued their permits, which is better evidence than any ranking.

Counts under a threshold are published as "--", suppressed for privacy. A
suppressed cell is not a zero and is not treated as one: it is absent, and a
school whose every cell is suppressed ends up with no number rather than a
number of nought.

THE UNITED KINGDOM: BLOCKED, AND SAYING SO
-------------------------------------------
HESA publishes exactly the equivalent (Figure 7, HE student enrolments by HE
provider and domicile) and hesa.ac.uk sits behind a Cloudflare managed
challenge. Not a robots rule, which we would obey: an active bot check that
returns 403 to a plain client AND to a real browser. Getting past that is
bot-detection evasion and this project does not do it.

data.gov.uk lists the datasets and every resource URL points back at hesa.ac.uk,
so the catalogue does not help. The Office for Students publishes sector-level
analysis rather than provider-level domicile counts.

So the UK number is not ingested here, and no substitute is invented for it.
`--uk-file` takes a HESA CSV that somebody downloaded in a browser themselves,
which is a legitimate way to obtain open data published under the OGL, and the
row records where it came from so it is still cited like everything else.
"""
from __future__ import annotations

import csv
import io
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402
from tools.find_school_sites import _key  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"

IRCC_URL = ("https://www.ircc.canada.ca/opendata-donneesouvertes/data/"
            "ODP-TR-Study-DLI_name_PT_Admin_type.csv")
IRCC_PAGE = ("https://open.canada.ca/data/en/dataset/"
             "90115b00-f9b8-49e8-afa3-b4cff8facaee")

CACHE = Path("out/ircc_dli.csv")

# Suppressed cells. Absent, never zero.
SUPPRESSED = {"--", "-", "", "n/a", ".."}


def fetch_ircc(force: bool = False) -> str:
    if CACHE.exists() and not force:
        print(f"using cached {CACHE} ({CACHE.stat().st_size:,} bytes)")
        return CACHE.read_bytes().decode("utf-8-sig", "replace")

    fetcher = Fetcher(delay_seconds=1.0)
    state, why = fetcher.permission(IRCC_URL)
    if state != "allowed":
        raise SystemExit(f"the robots gate says {state}: {why}")

    print(f"downloading {IRCC_URL}")
    request = urllib.request.Request(IRCC_URL, headers={"User-Agent": fetcher.user_agent})
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(raw)
    print(f"  {len(raw):,} bytes")
    return raw.decode("utf-8-sig", "replace")


def read_canada(text: str) -> tuple[dict[str, int], str]:
    """{DLI name key: study permit holders}, and the year they are from.

    The most recent year with data is used, and the year is returned so it can
    be stored beside the number. A count with no year on it is a count somebody
    will still be quoting in four years.
    """
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    fields = reader.fieldnames or []

    # The column is EN_DESIGNATED_LEARNING_INSTITUTION, not EN_DLI_NAME. Matched
    # on either spelling because IRCC has used both across releases of this file.
    name_col = next((c for c in fields if c and
                     ("DLI_NAME" in c.upper()
                      or "DESIGNATED_LEARNING_INSTITUTION" in c.upper())), None)
    year_col = next((c for c in fields if c and c.upper() == "EN_YEAR"), None)
    total_col = next((c for c in fields if c and c.upper() == "TOTAL"), None)
    if not (name_col and year_col and total_col):
        raise SystemExit(f"the IRCC columns moved; found {fields[:14]}")

    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in reader:
        raw = (row.get(total_col) or "").strip()
        if raw.lower() in SUPPRESSED:
            continue
        try:
            count = int(raw.replace(",", ""))
        except ValueError:
            continue
        name = (row.get(name_col) or "").strip()
        year = (row.get(year_col) or "").strip()
        if not name or not year:
            continue
        # Monthly rows. The yearly figure taken is the LARGEST month, not the
        # sum: the same student appears in every month they hold a permit, so
        # summing twelve months would multiply the school's population by twelve.
        by_year[year][_key(name)] = max(by_year[year][_key(name)], count)

    if not by_year:
        raise SystemExit("no usable rows in the IRCC file")

    # The most recent year that looks complete. The newest year in a monthly
    # file is usually part-year, and a part-year peak is still a real peak, so
    # it is used and the year is recorded honestly rather than dropped.
    latest = max(by_year)
    return dict(by_year[latest]), latest


def read_uk_file(path: Path) -> tuple[dict[str, int], str]:
    """A HESA CSV somebody downloaded themselves. Shape is checked, not assumed."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = text[:4000]
    delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fields = [c for c in (reader.fieldnames or []) if c]

    name_col = next((c for c in fields if "provider" in c.lower()), None)
    count_col = next((c for c in fields if "number" in c.lower() or "count" in c.lower()
                      or "enrolment" in c.lower()), None)
    domicile_col = next((c for c in fields if "domicile" in c.lower()), None)
    if not (name_col and count_col):
        raise SystemExit(f"could not find a provider and a count column in {fields[:12]}")

    out: dict[str, int] = defaultdict(int)
    for row in reader:
        if domicile_col:
            domicile = (row.get(domicile_col) or "").strip().lower()
            # Only students who came from outside the UK. Without this the
            # number is total enrolment, which ranks by size and not by who a
            # school actually takes from abroad.
            if domicile in ("united kingdom", "uk", "home", "england", "scotland",
                            "wales", "northern ireland", "total"):
                continue
        raw = (row.get(count_col) or "").strip().replace(",", "")
        if raw.lower() in SUPPRESSED:
            continue
        try:
            out[_key((row.get(name_col) or "").strip())] += int(float(raw))
        except ValueError:
            continue
    return dict(out), "as published in the supplied file"


def main() -> int:
    dry = "--dry" in sys.argv
    force = "--force" in sys.argv

    counts: dict[str, tuple[dict[str, int], str, str, str]] = {}

    text = fetch_ircc(force=force)
    canada, year = read_canada(text)
    print(f"Canada: {len(canada):,} institutions with a published count, year {year}")
    top = sorted(canada.items(), key=lambda kv: -kv[1])[:8]
    for name, n in top:
        print(f"    {n:>7,}  {name[:60]}")
    counts["CA"] = (canada, year, "IRCC study permit holders by DLI", IRCC_PAGE)

    if "--uk-file" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--uk-file") + 1])
        uk, year_uk = read_uk_file(path)
        print(f"\nUK: {len(uk):,} providers from {path}")
        counts["UK"] = (uk, year_uk, f"HESA, from {path.name}", "https://www.hesa.ac.uk/")
    else:
        print("\nUK: skipped. hesa.ac.uk is behind a Cloudflare managed challenge and "
              "this project does not defeat bot checks.")
        print("    Pass --uk-file <path> with a HESA CSV downloaded in a browser.")

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    store = Institutions(db)
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(store.COLLECTION).stream()]

    matched = 0
    batch = db.batch()
    written = 0
    for row in rows:
        code = row.get("jurisdiction", "")
        if code not in counts:
            continue
        table, year, publisher, page = counts[code]
        n = table.get(_key(row.get("name", "")))
        if n is None:
            continue
        matched += 1
        if dry:
            continue
        batch.set(db.collection(store.COLLECTION).document(row["id"]), {
            "intl_students": int(n),
            "intl_year": year,
            "intl_publisher": publisher,
            "intl_source_url": page,
            # The counterpart of the UK rows' "inferred". These two fields are
            # the only thing stopping a later author treating a measured count
            # and a neighbourhood proxy as the same number.
            "intl_basis": "published",
            # WHAT THE NUMBER ACTUALLY COUNTS, stored beside it, because
            # "international students" would overstate it and somebody would
            # eventually put it on a screen. IRCC's monthly file counts study
            # permit holders per month, not students enrolled, so the figure
            # kept is the peak month of the year: a school's busiest intake
            # month. It ranks schools correctly by how many international
            # students they take and it is NOT their international population.
            "intl_metric": ("study permit holders in the busiest month of the year, "
                            "not total enrolment"),
        }, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    if written % 400 and not dry:
        batch.commit()

    print(f"\nmatched a published count to {matched} of {len(rows)} institutions")
    if dry:
        print("--dry, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
