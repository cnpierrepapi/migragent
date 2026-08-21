"""Find the official website of every school on the registers.

    python -m tools.find_school_sites          # resolve and store
    python -m tools.find_school_sites --dry     # resolve, print, store nothing

THE PROBLEM
-----------
The registers name 2,065 institutions and give no websites. The UK's sponsor CSV
has a name, a status and a town; Canada's DLI table has a name, a province and a
DLI number. Neither publishes where the school actually lives on the internet,
and nothing can be read from a school until we know where to read it.

WHY WIKIDATA, AND WHAT IT IS AND IS NOT ALLOWED TO BE
------------------------------------------------------
Wikidata publishes the official website of most universities and colleges as a
structured property, free, in bulk, and without a per-school API call. The
alternative was a grounded search per institution: 2,065 model calls to answer a
question that is already answered in a public database.

**It is a lookup aid and never a source.** Nothing Wikidata says ever becomes a
requirement, a course, or a sentence shown to anybody. It answers exactly one
question, "where should we look", and everything actually claimed still comes
from the school's own page with the school's own words. A wrong website here
produces a school we cannot read, not a school we describe wrongly.

That distinction is why using a crowd-edited source is acceptable at all, and it
is worth keeping sharp: the moment anything from here is displayed as fact, it
has become a source, and it is not one.

RATE LIMITS
-----------
The public endpoint drops to one request a minute after a short burst, and says
so in the 429 body. So this asks a handful of broad questions rather than many
narrow ones, waits properly between them, and caches every answer to disk so a
re-run costs nothing. Politeness here is not optional: it is a free service and
the User-Agent names us.

WHAT IT CANNOT DO
-----------------
Language schools, private colleges and small career institutes are largely
absent from Wikidata. They are a real share of Canada's DLI list, and this will
simply not find them. Those rows keep no website and are skipped by the
ingestion rather than guessed at.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.institutions import Institutions  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
ENDPOINT = "https://query.wikidata.org/sparql"

CACHE = Path("out/wikidata_schools.json")

# The endpoint asks for a real User-Agent naming the project and a contact. A
# generic one gets blocked, correctly.
UA = ("MIGRAGENT/0.1 (immigration guidance research; https://migragent.onenept.com) "
      "python-urllib")

# TWO QUERIES PER COUNTRY, and the shape of them was found by measurement.
#
# A flat VALUES list of class ids missed the University of Cambridge, which is a
# loud enough failure to throw the approach out: Cambridge is P31 "collegiate
# university", and a hand-written list of classes will always be missing the one
# somebody used for the school you care about.
#
# Walking the subclass tree under "educational institution" (Q2385804) times the
# endpoint out at 504. Walking it under "higher education institution" (Q38723)
# returns in about ten seconds and finds Cambridge, Oxford, Imperial and Leeds.
# So that is the primary query.
#
# The VALUES query stays as a supplement for institutions somebody filed outside
# the higher-education tree, mostly Canadian career colleges and CEGEPs.
HIGHER_ED = "wd:Q38723"

EXTRA_CLASSES = " ".join([
    "wd:Q189004",     # college
    "wd:Q1051063",    # CEGEP
    "wd:Q4671277",    # academic institution
    "wd:Q23002054",   # private not-for-profit educational institution
    "wd:Q1371037",    # technical school
])

COUNTRIES = {"CA": ("wd:Q16", "Canada"), "UK": ("wd:Q145", "United Kingdom")}

# The endpoint's own stated limit once it starts pushing back.
PAUSE = 65


def _sparql(country_qid: str, walk: bool) -> str:
    if walk:
        where = f"?item wdt:P31/wdt:P279* {HIGHER_ED} ;"
    else:
        where = f"VALUES ?type {{ {EXTRA_CLASSES} }} ?item wdt:P31 ?type ;"
    return f"""
SELECT ?itemLabel ?website WHERE {{
  {where}
        wdt:P17 {country_qid} ;
        wdt:P856 ?website .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""


def query(country_qid: str, walk: bool = True) -> list[dict]:
    sparql = _sparql(country_qid, walk)
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": sparql, "format": "json"})
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})

    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)["results"]["bindings"]
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
                wait = PAUSE * attempt
                print(f"    HTTP {exc.code}, waiting {wait}s ({attempt} of 3)", flush=True)
                time.sleep(wait)
                continue
            raise
    return []


def _key(name: str) -> str:
    """A name reduced to what two spellings of the same school share.

    Deliberately blunt. It strips accents, punctuation and a leading "the", and
    nothing else: it does NOT drop the word "university" or expand "St" to
    "Saint", because both of those turn two different schools into one. A missed
    match costs a school we do not read. A wrong match points our reader at
    somebody else's website and files their courses under the wrong name.
    """
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(r"^the ", "", text)
    return re.sub(r"\s+", " ", text)


def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:  # noqa: BLE001
        return ""


def fetch_all(force: bool = False) -> dict[str, dict[str, str]]:
    """{jurisdiction: {name key: website}}, cached to disk."""
    if CACHE.exists() and not force:
        print(f"using cached {CACHE}")
        return json.loads(CACHE.read_text(encoding="utf-8"))

    out: dict[str, dict[str, str]] = {}
    asked = 0
    for code, (qid, label) in COUNTRIES.items():
        found: dict[str, str] = {}
        for walk in (True, False):
            if asked:
                print(f"  waiting {PAUSE}s before the next query", flush=True)
                time.sleep(PAUSE)
            asked += 1
            kind = "higher education" if walk else "colleges and institutes"
            print(f"  asking Wikidata for {label}, {kind} ...", flush=True)
            rows = query(qid, walk=walk)
            for binding in rows:
                name = binding.get("itemLabel", {}).get("value", "")
                site = binding.get("website", {}).get("value", "")
                if not name or not site.startswith("http"):
                    continue
                # Several websites for one institution happens. First wins; they
                # are nearly always the same host. The walk runs first, so a
                # higher-education answer is never overwritten by a broader one.
                found.setdefault(_key(name), site)
            print(f"    {len(rows)} rows, {len(found)} usable names so far", flush=True)
        out[code] = found

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main() -> int:
    dry = "--dry" in sys.argv
    force = "--force" in sys.argv

    sites = fetch_all(force=force)

    db = firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(identity.WEB, PROJECT))
    store = Institutions(db)

    rows = [{**d.to_dict(), "id": d.id}
            for d in db.collection(store.COLLECTION).stream()]
    print(f"\n{len(rows)} institutions on the registers")

    matched = 0
    misses: list[str] = []
    batch = db.batch()
    written = 0

    for row in rows:
        code = row.get("jurisdiction", "")
        name = row.get("name", "")
        site = sites.get(code, {}).get(_key(name))
        if not site:
            misses.append(f"{code} {name}")
            continue
        matched += 1
        if dry:
            continue
        batch.set(db.collection(store.COLLECTION).document(row["id"]), {
            "website": site,
            "website_host": _host(site),
            # Named on the row, permanently, so nobody downstream can mistake a
            # lookup aid for a source. See the module docstring.
            "website_source": "wikidata",
        }, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    if written % 400 and not dry:
        batch.commit()

    print(f"matched {matched} of {len(rows)} ({100 * matched / max(1, len(rows)):.0f}%)")
    print(f"no website found for {len(misses)}")
    for line in misses[:12]:
        print(f"    {line[:78]}")
    if dry:
        print("\n--dry, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
