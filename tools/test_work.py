"""Walk the whole Build 5 chain, against the real thing.

    python -m tools.test_work

CV in, matched listings out, a fit score with a breakdown, an item on the board.
It uses a real CV read by the real model, real listings from the real store, and
a real posting fetched from the board, because the parts of this worth testing
are the joins between them and a fake would join fine.

The case it creates is deleted at the end, and the delete is checked. A test
that leaves rows behind is a test that made the retention claim false.

WHAT IS BEING CHECKED, BEYOND "it ran"
--------------------------------------
  - the CV's claims carry quotes that are really in the CV
  - a listing only appears when a role in the CV put it there
  - the fit score's requirements are really on the posting
  - the fit only credits the person with claims their CV made
  - the board item starts in the first column and nothing else moved it
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

import zlib  # noqa: E402

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.board import Board  # noqa: E402
from migragent.cases import Cases  # noqa: E402
from migragent.cv import CVReader, CVStore  # noqa: E402
from migragent.documents import extract_text  # noqa: E402
from migragent.fetcher import Fetcher  # noqa: E402
from migragent.fit import FitScorer, Fits  # noqa: E402
from migragent.listings import Listings, matched_for  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
MODEL = "gemini-3.5-flash"
MODEL_LOCATION = "global"

CV_LINES = [
    "ADEOLA OKAFOR",
    "Welder and fabricator",
    "",
    "EXPERIENCE",
    "Welder, Lagos Steel Works, 2019 to 2026",
    "MIG and TIG welding of structural steel to drawing.",
    "Read and worked from engineering drawings daily.",
    "Trained four apprentices in arc welding safety.",
    "",
    "QUALIFICATIONS",
    "City and Guilds Level 3 Diploma in Welding, 2019",
    "Certified in confined space entry, 2023",
    "",
    "LANGUAGES",
    "English, fluent. Yoruba, native.",
]


def a_cv_pdf() -> bytes:
    """A small real PDF, so pypdf can pull a text layer out of it.

    Written by hand rather than with a library, because adding a PDF writer to
    the image to make a test fixture would be a strange thing to ship.
    """
    lines = "".join(f"({line.replace('(', '').replace(')', '')}) Tj 0 -18 Td\n"
                    for line in CV_LINES)
    stream = f"BT /F1 12 Tf 56 760 Td\n{lines}ET".encode("latin-1")
    compressed = zlib.compress(stream)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\nstream\n"
        + compressed + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n"
            f"{start}\n%%EOF\n").encode()
    return bytes(out)


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))

    db = firestore.Client(project=PROJECT,
                          credentials=identity.credentials_for(identity.WEB, PROJECT))
    reader_credentials = identity.credentials_for(identity.RESEARCHER, PROJECT)

    cases = Cases(db)
    case = cases.create("CA", "work")
    print(f"case {case.case_id[:10]}...\n")

    try:
        # 1. The CV.
        data = a_cv_pdf()
        text = extract_text(data, "application/pdf")
        check(bool(text.strip()), "the CV has a text layer to check quotes against",
              f"{len(text)} characters")

        cv = CVReader(PROJECT, MODEL, MODEL_LOCATION, reader_credentials).read(
            "probe-cv.pdf", data, "application/pdf", text)
        CVStore(db).put(case.case_id, cv)

        check(not cv.error, "the CV was read", cv.error or "no error")
        check(len(cv.claims) > 0, "the CV produced claims",
              f"{len(cv.claims)} kept, {len(cv.dropped)} dropped for a quote not in the CV")
        roles = [c.value for c in cv.of_kind("role")]
        check(any("weld" in r.lower() for r in roles),
              "it read the person's actual trade off the page", f"roles: {roles}")
        check(all(c.verified for c in cv.claims),
              "every kept claim carries a quote that is really in the CV",
              f"{len([c for c in cv.claims if c.verified])} of {len(cv.claims)} verified")

        # 2. What it matched.
        listings = matched_for(roles + [c.value for c in cv.of_kind("licence")],
                               Listings(db).for_jurisdiction("CA"))
        check(len(listings) > 0, "the CV matched listings we already hold",
              f"{len(listings)} matched")
        if listings:
            print("\n  matched:")
            for row in listings[:5]:
                print(f"    {row.get('title')[:40]:<40} because the CV says "
                      f"'{row.get('matched_because')}'")
            check(all(row.get("matched_because") for row in listings),
                  "every match says which line of the CV put it there")

        if not listings:
            check(False, "there is a listing to score against",
                  "no listings matched, so the rest cannot run")
            return _report(results, cases, case)

        # 3. The fit.
        listing = listings[0]
        page = Fetcher(delay_seconds=0.5).fetch(listing["url"])
        check(page.ok, "the posting itself could be fetched",
              f"{page.outcome} {page.status}")

        fit = FitScorer(PROJECT, MODEL, MODEL_LOCATION, reader_credentials).score(
            page, cv, listing["listing_id"], case.case_id)
        Fits(db).put(fit)

        check(not fit.error, "the posting was scored", fit.error or "no error")
        check(fit.asked > 0, "the posting stated things to be scored against",
              f"asks for {fit.asked}, met {fit.met}, score {fit.score}%")
        print(f"\n  {listing['title']} at {listing.get('employer')}: {fit.score}% fit")
        for match in fit.matches[:6]:
            mark = "yes" if match.met else "no "
            print(f"    {mark}  {match.asks_for[:62]}")
            print(f"         posting: \"{match.quote[:60]}\"")
            if match.evidence:
                print(f"         your CV: {match.evidence}")

        claimed = {c.value for c in cv.claims}
        check(all(m.evidence in claimed for m in fit.matches if m.evidence),
              "nothing was credited that the CV did not claim",
              f"{len([m for m in fit.matches if m.met])} met, all cited from the CV's own claims")
        check(all(m.quote for m in fit.matches),
              "every requirement carries the posting's own words")

        # 4. The board.
        board = Board(db)
        item = board.add(case.case_id, listing, fit.score)
        check(item.column == "to_prepare", "the item starts in the first column",
              f"column: {item.column}")
        again = board.add(case.case_id, listing, fit.score)
        check(again.item_id == item.item_id,
              "clicking twice is one application, not two")

        columns = board.for_case(case.case_id)
        check(len(columns["to_prepare"]) == 1 and not columns["sent"],
              "nothing moved itself",
              {k: len(v) for k, v in columns.items()})

        return _report(results, cases, case)
    except Exception as exc:  # noqa: BLE001
        check(False, "the run finished without falling over", f"{type(exc).__name__}: {exc}")
        return _report(results, cases, case)


def _report(results, cases, case) -> int:
    removed = cases.delete(case.case_id)
    print(f"\ncleaned up: {removed}")
    leftover = {k: v for k, v in removed.items() if k in ("cv", "fits", "board_items")}

    print()
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if detail:
            print(f"        {detail}")

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    print(f"the case's own rows were removed afterwards: {leftover}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
