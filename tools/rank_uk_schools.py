"""Rank UK schools by the immigrant density of the town they are in.

    python -m tools.rank_uk_schools
    python -m tools.rank_uk_schools --dry

WHY THIS IS AN INFERENCE AND IS LABELLED AS ONE
------------------------------------------------
Canada does not need this. IRCC publishes study permit holders per designated
learning institution, so the Canadian ranking is a measured count from the
department that issued the permits.

The UK has no such route open to us. HESA publishes the equivalent and sits
behind a Cloudflare managed challenge that refuses a plain client and a real
browser alike, which is an active bot check rather than a robots rule, and this
project does not defeat those.

So the UK ranking is a proxy: schools in places where a lot of people were born
outside the UK are more likely to teach a lot of people born outside the UK.
That is a reasonable inference and it is not a fact. It is nowhere near the
quality of the Canadian number and the two must never be presented as the same
kind of thing.

**Nothing here is ever shown to anybody.** It exists to decide which schools are
worth spending deep reading on, which is the same job the rubric does, under the
same rule: internal scoring, no frontend display. A person is never told a school
is good, popular with internationals, or ranked. They are told what a school's
own pages say about its courses, and that is unaffected by any of this.

The row records `intl_basis: "inferred"` so no later screen and no later author
can mistake it for the Canadian number, which records `intl_basis: "published"`.

THE DATA
--------
ONS Census 2021, table TS004, country of birth by lower-tier local authority.
Open, no robots.txt on the host, no challenge. The share used is everyone not
born in the United Kingdom, as a percentage of the local authority's residents.

nomisweb's API would have been the classic route and its robots.txt disallows
/api, so it is not used.

MATCHING A TOWN TO A LOCAL AUTHORITY
-------------------------------------
The register gives a town, sometimes a county, sometimes "Various". Exact name
matching against local authority names, then a small table of the towns that are
obviously inside a bigger authority, then nothing. A school whose town cannot be
matched keeps no score rather than an average one: an average would quietly rank
it mid-table, which is a claim, where absent is not.
"""
from __future__ import annotations
import os

import csv
import io
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402
from tools.find_school_sites import _key  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-e0928f2f-5abf-46a3-b8a")

TS004 = "https://download.ons.gov.uk/downloads/datasets/TS004/editions/2021/versions/3.csv"
TS004_PAGE = "https://www.ons.gov.uk/datasets/TS004/editions/2021/versions/3"

CACHE = Path("out/ons_ts004.csv")

# Towns that are plainly inside a larger local authority the census names
# differently. Kept short and obvious on purpose: every entry is a judgement,
# and a long table of them would be a lot of quiet judgements.
INSIDE = {
    "ascot": "windsor and maidenhead",
    "eton": "windsor and maidenhead",
    "hampshire": "",          # a county, not a town. Deliberately unmatched.
    "various": "",
    "surrey": "",
    "kent": "",
    "essex": "",
}

# London is 181 of the 946 rows, a fifth of the register, and it is not a local
# authority: it is thirty-three of them. Leaving it unmatched threw away the
# single largest group of UK schools, so the boroughs are summed into one London
# figure rather than hand-mapping each school to a borough it does not state.
#
# This list is stable, public and checkable, which is why it is acceptable where
# a long table of town-to-authority guesses would not be. A school that says
# "London" gets London's real share; it does not get Brent's because somebody
# decided that was close enough.
LONDON_BOROUGHS = (
    "barking and dagenham", "barnet", "bexley", "brent", "bromley", "camden",
    "city of london", "croydon", "ealing", "enfield", "greenwich", "hackney",
    "hammersmith and fulham", "haringey", "harrow", "havering", "hillingdon",
    "hounslow", "islington", "kensington and chelsea", "kingston upon thames",
    "lambeth", "lewisham", "merton", "newham", "redbridge",
    "richmond upon thames", "southwark", "sutton", "tower hamlets",
    "waltham forest", "wandsworth", "westminster",
)


def fetch(force: bool = False) -> str:
    if CACHE.exists() and not force:
        print(f"using cached {CACHE}")
        return CACHE.read_text(encoding="utf-8-sig", errors="replace")

    fetcher = Fetcher(delay_seconds=1.0)
    state, why = fetcher.permission(TS004)
    if state != "allowed":
        raise SystemExit(f"the robots gate says {state}: {why}")

    print(f"downloading {TS004}")
    request = urllib.request.Request(TS004, headers={"User-Agent": fetcher.user_agent})
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(raw)
    print(f"  {len(raw):,} bytes")
    return raw.decode("utf-8-sig", "replace")


def shares(text: str) -> dict[str, float]:
    """{local authority key: percentage of residents born outside the UK}."""
    reader = csv.DictReader(io.StringIO(text))
    fields = [c for c in (reader.fieldnames or []) if c]

    def find(*needles: str) -> str | None:
        """Match on words rather than on punctuation.

        The header is "Country of birth (12 categories)", with spaces and
        brackets, so matching the literal "country_of_birth" found nothing. The
        Code column is excluded explicitly: it contains every word the label
        column does and it comes first.
        """
        for column in fields:
            flat = " ".join("".join(ch if ch.isalnum() else " "
                                    for ch in column).lower().split())
            if flat.endswith(" code"):
                continue
            if all(n in flat for n in needles):
                return column
        return None

    la_col = find("local", "authorities")
    cat_col = find("country", "birth")
    count_col = find("observation") or find("count")
    if not (la_col and cat_col and count_col):
        raise SystemExit(f"the ONS columns moved; found {fields[:12]}")

    total: dict[str, float] = {}
    foreign: dict[str, float] = {}

    for row in reader:
        la = (row.get(la_col) or "").strip()
        category = (row.get(cat_col) or "").strip().lower()
        raw = (row.get(count_col) or "").strip()
        if not la or not category or not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue

        key = _key(la)
        total[key] = total.get(key, 0.0) + value
        # Everything that is not "born in the United Kingdom" and is not the
        # total row. The census splits the UK into its four countries in this
        # table, so each is excluded by name rather than by a substring on "UK".
        if category.startswith("does not apply") or category == "total":
            total[key] -= value
            continue
        if not category.startswith("europe: united kingdom"):
            foreign[key] = foreign.get(key, 0.0) + value

    table = {k: round(100.0 * foreign.get(k, 0.0) / v, 2)
             for k, v in total.items() if v > 0}

    # One figure for London, summed across the boroughs rather than averaged,
    # so a small borough does not weigh the same as a large one.
    london_people = sum(total.get(b, 0.0) for b in LONDON_BOROUGHS)
    london_foreign = sum(foreign.get(b, 0.0) for b in LONDON_BOROUGHS)
    if london_people > 0:
        table["london"] = round(100.0 * london_foreign / london_people, 2)

    return table


def main() -> int:
    dry = "--dry" in sys.argv
    table = shares(fetch(force="--force" in sys.argv))
    print(f"{len(table)} local authorities with a non-UK-born share")
    top = sorted(table.items(), key=lambda kv: -kv[1])[:8]
    for name, pct in top:
        print(f"    {pct:5.1f}%  {name[:50]}")

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    store = Institutions(db)
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(store.COLLECTION).stream()
            if d.to_dict().get("jurisdiction") == "UK"]

    matched, unmatched = 0, []
    batch = db.batch()
    written = 0

    for row in rows:
        town = (row.get("location") or "").strip()
        key = _key(town)
        key = INSIDE.get(key, key)
        pct = table.get(key) if key else None
        if pct is None:
            unmatched.append(town or "(no location)")
            continue
        matched += 1
        if dry:
            continue
        batch.set(db.collection(store.COLLECTION).document(row["id"]), {
            "intl_share_local": pct,
            # The load-bearing field. "inferred" here, "published" on the
            # Canadian rows, so the difference survives contact with every
            # later author and every later screen.
            "intl_basis": "inferred",
            "intl_metric": (f"percentage of residents of {town} born outside the UK, "
                            f"Census 2021. A proxy for the school's own intake, "
                            f"not a measurement of it. Internal ranking only."),
            "intl_source_url": TS004_PAGE,
            "intl_publisher": "ONS Census 2021 table TS004",
        }, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    if written % 400 and not dry:
        batch.commit()

    print(f"\nranked {matched} of {len(rows)} UK institutions")
    print(f"no local authority matched for {len(unmatched)}")
    seen = []
    for town in unmatched:
        if town not in seen:
            seen.append(town)
    print("   ", ", ".join(seen[:14]))
    if dry:
        print("--dry, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
