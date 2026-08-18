"""Build the guide for one lane, as HTML and as a PDF.

    python tools/build_guide.py CA study
    python tools/build_guide.py UK study --out out/

The PDF is printed from the same HTML a person sees, by the same browser, rather
than rendered a second time by a different library. One document, one renderer,
so the saved file and the page cannot drift apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from google.cloud import firestore  # noqa: E402

from migragent import identity  # noqa: E402
from migragent.corpus import Corpus  # noqa: E402
from migragent.guide import build, to_html  # noqa: E402
from migragent.registry import Registry  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 64
    jurisdiction, lane = sys.argv[1].upper(), sys.argv[2].lower()
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path("out")
    out.mkdir(parents=True, exist_ok=True)

    creds = identity.credentials_for(identity.RESEARCHER, PROJECT)
    db = firestore.Client(project=PROJECT, credentials=creds)
    corpus = Corpus(db)
    registry = Registry(db)

    requirements = corpus.requirements_for(jurisdiction, lane)
    questions = corpus.open_questions_for(jurisdiction, lane)
    total = registry.total_sources()

    guide = build(jurisdiction, lane, requirements, questions, total)
    print(f"{guide.title}")
    print(f"  {len(requirements)} requirements from {guide.sources_read} pages")
    print(f"  {len(questions)} open questions")
    print(f"  {total} sources in the registry")

    stem = f"{jurisdiction.lower()}-{lane}"
    html_path = out / f"{stem}.html"
    html_path.write_text(to_html(guide), encoding="utf-8")
    print(f"\nwrote {html_path}")

    # The brand files live beside the guide so the printed page carries the same
    # type and colour as the screen, with no network fetch for the stylesheet.
    brand_out = out / "brand"
    brand_out.mkdir(exist_ok=True)
    for name in ("tokens.css", "favicon.svg"):
        src = Path("web/brand") / name
        if src.exists():
            (brand_out / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    pdf_path = out / f"{stem}.pdf"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.pdf(path=str(pdf_path), format="A4", print_background=True,
                     margin={"top": "18mm", "bottom": "18mm",
                             "left": "16mm", "right": "16mm"})
            browser.close()
        print(f"wrote {pdf_path} ({pdf_path.stat().st_size:,} bytes)")
    except Exception as exc:  # noqa: BLE001
        print(f"PDF not produced: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
