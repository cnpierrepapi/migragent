"""Turn the generated stills into something a page can afford to load.

    python -m tools.prepare_images

The generator returns PNGs of well over a megabyte each. These pages currently
render in a few hundred milliseconds and a single one of those files would be
three times the weight of everything else on the page put together.

So each still becomes WebP at two widths, 1600 for a hero on a large screen and
800 for everything else, and the page picks with `srcset` rather than sending the
big one to a phone on a train.

The PNGs stay in the repo as the negatives. They are what a re-crop or a
different treatment starts from, and throwing them away to save space in a git
history is the sort of economy that costs a day later.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from PIL import Image  # noqa: E402

SOURCE = Path("web/brand/images")
OUT = Path("web/brand/images/web")

WIDTHS = (1600, 800)
QUALITY = 78


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stills = sorted(p for p in SOURCE.glob("*.png"))
    if not stills:
        print(f"no PNGs in {SOURCE}")
        return 1

    total_before = total_after = 0

    for still in stills:
        image = Image.open(still).convert("RGB")
        total_before += still.stat().st_size

        for width in WIDTHS:
            if image.width < width:
                continue
            height = round(image.height * width / image.width)
            resized = image.resize((width, height), Image.LANCZOS)
            out = OUT / f"{still.stem}-{width}.webp"
            resized.save(out, "WEBP", quality=QUALITY, method=6)
            total_after += out.stat().st_size
            print(f"  {out.name:<44} {out.stat().st_size / 1024:>6.0f} KB")

    print(f"\n{len(stills)} stills: {total_before / 1e6:.1f} MB of PNG "
          f"became {total_after / 1e6:.1f} MB of WebP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
