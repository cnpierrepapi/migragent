"""Can we read each country's government job board, and how.

    python -m tools.probe_job_boards

WHY THIS EXISTS
---------------
listings.py carries a note from 19 August listing which boards allowed us. That
note is a year of internet away from being trustworthy and it was never acted
on: only Canada was ever implemented, so ten countries have a shortage list or a
guide and no jobs at all.

This tests every board for real and records four things per country:

    robots      what the gate says, which decides everything else
    static      whether a plain client gets the page
    listings    whether job postings are IN the HTML, or arrive by script
    rendered    whether a browser changes the answer

A board that is allowed and serves listings statically is a day's work to
ingest. One that needs rendering is two. One the gate refuses is not work at
all, it is a closed door, and saying so is more useful than a plan.
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")

from migragent.extract import page_text  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.render import BrowserFetcher  # noqa: E402

# One search or listing URL per country, not a homepage: a homepage tells you
# nothing about whether the results are readable.
BOARDS = [
    ("CA", "Canada",  "Job Bank",
     "https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=welder"),
    ("UK", "United Kingdom", "Find a job (DWP)",
     "https://findajob.dwp.gov.uk/search?q=welder"),
    ("US", "United States", "USAJOBS",
     "https://www.usajobs.gov/search/results/?k=welder"),
    ("AU", "Australia", "Workforce Australia",
     "https://www.workforceaustralia.gov.au/individuals/jobs/search?query=welder"),
    ("FR", "France", "France Travail",
     "https://candidat.francetravail.fr/offres/recherche?motsCles=soudeur"),
    ("ES", "Spain", "Empléate (SEPE)",
     "https://www.empleate.gob.es/empleo/#/ofertas-empleo"),
    ("IT", "Italy", "Cliclavoro",
     "https://www.cliclavoro.gov.it/Pagine/Offerte-di-lavoro.aspx"),
    ("DE", "Germany", "Bundesagentur für Arbeit",
     "https://www.arbeitsagentur.de/jobsuche/suche?was=Schwei%C3%9Fer"),
    ("PT", "Portugal", "IEFP NetEmprego",
     "https://www.iefp.pt/ofertas-emprego"),
    ("EU", "EU-wide", "EURES",
     "https://europa.eu/eures/portal/jv-se/search"),
]

# HOW A RESULTS PAGE IS RECOGNISED, having got this wrong once.
#
# The first version looked for path keywords like /job/ or /offre/. That found
# two links on Canada's Job Bank, a board this project has already ingested two
# thousand postings from, so the detector was wrong rather than the board: Job
# Bank marks each posting with <article id="article-NNN"> and the keyword never
# appears.
#
# What every results page has, whatever it calls things and whatever language it
# is in, is MANY LINKS OF THE SAME SHAPE. So: reduce each link to its shape by
# replacing digits and long slugs, count the shapes, and take the largest group.
# Ten links of one shape is a list of results. Two is a navigation bar.
_HREF = re.compile(r'href="([^"]+)"', re.I)
_DIGITS = re.compile(r"\d+")
_SLUG = re.compile(r"[a-z0-9][a-z0-9\-_%]{11,}", re.I)


def result_shapes(html: str) -> tuple[int, str]:
    """Size of the largest group of same-shaped links, and the shape."""
    shapes: dict[str, int] = {}
    for href in _HREF.findall(html):
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        path = href.split("?")[0]
        shape = _SLUG.sub("*", _DIGITS.sub("#", path))
        if shape.count("/") < 2:
            continue
        shapes[shape] = shapes.get(shape, 0) + 1
    if not shapes:
        return 0, ""
    shape, n = max(shapes.items(), key=lambda kv: kv[1])
    return n, shape


def looks_like_results(html: str, text: str) -> tuple[int, bool]:
    n, _shape = result_shapes(html)
    hits = bool(re.search(r"\d[\d.,\s]{1,9}\s*(results|jobs|offres|ofertas|"
                          r"stellen|angebote|resultados|risultati|vagas)",
                          text, re.I))
    return n, hits


def main() -> int:
    fetcher = Fetcher(delay_seconds=1.5)
    rows = []

    with BrowserFetcher(fetcher=fetcher) as browser:
        for code, country, board, url in BOARDS:
            state, why = fetcher.permission(url)
            static_ok = listings_static = rendered_ok = listings_rendered = False
            note = ""

            if state == "allowed":
                page = fetcher.fetch(url)
                static_ok = page.ok
                if page.ok:
                    html = page.body.decode("utf-8", "replace")
                    n, _ = looks_like_results(html, page_text(page))
                    listings_static = n >= 8
                    note = f"{n} repeated links"
                else:
                    note = page.outcome

                if not listings_static:
                    r = browser.fetch(url)
                    rendered_ok = r.ok
                    if r.ok:
                        html = r.body.decode("utf-8", "replace")
                        n, _ = looks_like_results(html, page_text(r))
                        listings_rendered = n >= 8
                        note += f", {n} rendered"
                    else:
                        note += f", render {r.outcome}"
            else:
                note = why[:60]

            verdict = ("static" if listings_static else
                       "headless" if listings_rendered else
                       "BLOCKED" if state != "allowed" else "no listings found")
            rows.append((code, country, board, state, verdict, note))
            print(f"  {code}  {board[:26]:28}{state:<11}{verdict:<16}{note[:38]}",
                  flush=True)

    print(f"\n{'':3}{'Country':16}{'Board':27}{'robots':<11}{'access':<16}")
    print("-" * 76)
    for code, country, board, state, verdict, _n in rows:
        print(f"{code:3}{country[:15]:16}{board[:26]:27}{state:<11}{verdict:<16}")
    ok = [r for r in rows if r[4] in ("static", "headless")]
    print(f"\n{len(ok)} of {len(rows)} boards are readable: "
          f"{', '.join(r[0] for r in ok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
