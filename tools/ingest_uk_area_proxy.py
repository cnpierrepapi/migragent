"""Rank UK schools by how many migrants live where they are. INTERNAL ONLY.

    python -m tools.ingest_uk_area_proxy
    python -m tools.ingest_uk_area_proxy --dry

WHY THIS IS NOT A SOURCE, AND MUST NEVER BECOME ONE
-----------------------------------------------------
Canada publishes study permit holders per institution, so Canadian schools are
ranked on a real count of the actual thing. The UK equivalent is HESA's, and
hesa.ac.uk sits behind a Cloudflare managed challenge that this project will not
defeat. So the UK has no published per-school number here.

What this does instead is an inference, and it is worth being blunt about the
size of the leap: a school in a place where many people were born outside the UK
is assumed to be a school more migrants go to. That is plausible and it is not
evidence. Bath has few migrants and a large university full of them; Slough is
the other way round.

It is acceptable for exactly one reason. The score is used only to decide WHICH
SCHOOLS WE SPEND READING BUDGET ON. It never reaches a screen, it never ranks
anything a person sees, and no sentence anywhere is built on it. Being wrong
means we read the wrong hundred schools, which costs us time. Being wrong on a
page would mean telling somebody something untrue about their future.

That boundary is enforced in the field name and in the note stored beside it, so
that anybody who later reaches for this value on a template has to read the
sentence saying not to.

THE NUMBERS THEMSELVES ARE REAL
--------------------------------
ONS Census 2021, usual residents by country of birth, by local authority, from
the ONS API. Born outside the UK over all residents. The inference is in the
mapping from "this area" to "this school", not in the data.

Nomis carries the same table and its robots.txt disallows us, so the ONS API is
used and Nomis is not touched.

WHAT IT COVERS
--------------
Census 2021 is England and Wales. Scotland and Northern Ireland ran separate
censuses under NRS and NISRA, so Edinburgh, Glasgow and Belfast get no score
here rather than a borrowed one. Towns that are not local authority names get no
score either. No score means the school falls to the bottom of the reading queue,
not that it is excluded from the product.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"

API = "https://api.beta.ons.gov.uk/v1/population-types/UR/census-observations"
SOURCE = ("ONS Census 2021, usual residents by country of birth, "
          "by local authority")

CACHE = Path("out/ons_country_of_birth.json")

UA = "MIGRAGENT/0.1 (+https://migragent.onenept.com) research"

OUTSIDE = "born outside the uk"
INSIDE = "born in the uk"

# The one sentence anybody reaching for this value has to read first.
NOTE = ("INFERRED, NOT PUBLISHED. The share of residents born outside the UK in "
        "the local authority this school sits in. Used only to order which "
        "schools we read. Never display this and never build a claim on it: it "
        "says nothing about who attends this school.")


def _get(url: str) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def fetch(area_type: str, force: bool = False) -> list[dict]:
    cache = CACHE.with_name(f"ons_country_of_birth_{area_type}.json")
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))
    print(f"  asking ONS for {area_type} ...", flush=True)
    data = _get(f"{API}?area-type={area_type}&dimensions=country_of_birth_3a")
    obs = data.get("observations", [])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(obs), encoding="utf-8")
    print(f"    {len(obs)} observations", flush=True)
    return obs


def shares(observations: list[dict]) -> dict[str, float]:
    """{area name lowercased: share born outside the UK}."""
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in observations:
        area = category = ""
        for dim in row.get("dimensions", []):
            if dim.get("dimension_id") == "country_of_birth_3a":
                category = (dim.get("option") or "").strip().lower()
            else:
                area = (dim.get("option") or "").strip()
        if not area or category not in (INSIDE, OUTSIDE):
            continue
        totals[area][category] += int(row.get("observation") or 0)

    out: dict[str, float] = {}
    for area, counts in totals.items():
        people = counts[INSIDE] + counts[OUTSIDE]
        if people:
            out[area.lower()] = counts[OUTSIDE] / people
    return out


def _key(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"^(city of|london borough of|royal borough of) ", "", text)


def main() -> int:
    dry = "--dry" in sys.argv
    force = "--force" in sys.argv

    print("ONS Census 2021, country of birth:")
    local = shares(fetch("ltla", force))
    region = shares(fetch("rgn", force))
    print(f"  {len(local)} local authorities, {len(region)} regions")

    by_key = {_key(k): v for k, v in local.items()}
    region_by_key = {_key(k): v for k, v in region.items()}

    # London is 181 of the 946 UK rows and is not a local authority: it is 33 of
    # them. A school that says "London" gets the London region figure, which is
    # the honest answer to the question actually being asked.
    london = region_by_key.get("london")
    if london:
        print(f"  London region: {london:.1%} born outside the UK")

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    store = Institutions(db)
    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(store.COLLECTION).stream()
            if d.to_dict().get("jurisdiction") == "UK"]
    print(f"\n{len(rows)} UK institutions")

    matched = 0
    misses: list[str] = []
    batch = db.batch()
    written = 0

    for row in rows:
        town = (row.get("location") or "").strip()
        key = _key(town)
        if not key or key == "various":
            misses.append(town or "(no location)")
            continue

        share = by_key.get(key) or region_by_key.get(key)
        if share is None and key == "london":
            share = london
        if share is None:
            misses.append(town)
            continue

        matched += 1
        if dry:
            continue
        batch.set(db.collection(store.COLLECTION).document(row["id"]), {
            "area_migrant_share": round(share, 4),
            "area_matched": town,
            "area_source": SOURCE,
            "area_note": NOTE,
        }, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    if written % 400 and not dry:
        batch.commit()

    print(f"scored {matched} of {len(rows)} ({100 * matched / max(1, len(rows)):.0f}%)")
    unique = sorted(set(misses))
    print(f"no area figure for {len(misses)} rows, {len(unique)} distinct places")
    print(f"  {', '.join(unique[:14])}")
    if dry:
        print("\n--dry, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
