"""Generate the photographic set for MIGRAGENT.

Runs on Vertex AI in the same Google Cloud project the app runs in, so no key
leaves the project and no second vendor is involved.

Model: gemini-2.5-flash-image. Probed on 18 August 2026; every Imagen endpoint
and every gemini-3 image endpoint returned 404 on this project, and this one
returned 200 at both us-central1 and global. See docs/DEFECTS.md D3.

    python tools/make_images.py
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
LOCATION = "global"
MODEL = "gemini-2.5-flash-image"
OUT = Path("web/brand/images")

# The look, repeated on every prompt so the set hangs together as one shoot.
# The look. Rewritten on 21 August 2026, because the first set was wrong.
#
# It was documentary, muted, desaturated and mostly shot at night, and it was
# good photography of the wrong feeling: it said immigration is grim and lonely.
# A person using this has already got enough of that. What the product actually
# offers is a clear morning and a stack of paper that finally makes sense, so
# the set is bright, warm and unhurried, and the person in it is getting
# somewhere rather than sitting in the dark.
LOOK = (
    "Bright editorial photograph, photorealistic, 35mm, generous natural daylight, warm clean "
    "colour, light wood and pale paper, airy and uncluttered, shallow depth of field, calm and "
    "unhurried, unposed, nobody looking at the camera, no stock-photo grinning, no flash. "
)

# The bans exist because this product's whole claim is that it does not fake
# things. An invented crest or a legible passport page would be a forgery
# sitting on the marketing page of a product that sells not inventing.
BANS = (
    " Absolutely no text, no lettering, no signage, no logos, no government crest, no seal, "
    "no coat of arms, no flag. No readable document: any paper is blurred or out of focus. "
    "No passport interior page, no photo page, no document number, no name. "
    "No recognisable face. No aeroplane, no globe, no world map, no pins, no suitcase."
)

SHOTS = {
    # The home page hero still, and the poster the video falls back to.
    "01-morning-table-paper":
        "Hands laying a single sheet of blank paper flat on a sunlit wooden table beside a glass "
        "of water, wide morning light from a window on the left, seen from just above and behind "
        "the shoulder so the face is out of frame.",
    # Above the guide.
    "02-sorted-stack-daylight":
        "A neat stack of blank printed pages squared off on a pale desk in full daylight, a plain "
        "unmarked folder beside it, shot from a low three-quarter angle, clean bright surfaces, "
        "no booklet and no passport anywhere in the frame.",
    # The documents step.
    "03-two-hands-sorting":
        "Two hands sorting blank sheets into two small piles on a light table, bright even "
        "daylight, motion soft in the fingers, shot straight down from above.",
    # The work and board screens: getting somewhere, not waiting.
    "04-workshop-daylight":
        "A bright workshop bench by a tall window, tools laid in order, sawdust in the light, "
        "nobody in frame, warm timber and pale walls.",
    "05-open-window-desk":
        "A tidy desk beside an open window with daylight and a plant, a closed notebook and a "
        "pen, no screen visible, shot from a low angle so the light fills the frame.",
    # The board, quietly: things in order, room to move.
    "06-pinned-cards-wall":
        "Half a dozen blank cards pinned in a loose column on a pale wall in daylight, slight "
        "shadows under each card, shot square on, no writing on any card.",
    # Endings that are not grim: a door held open, a corridor with light in it.
    "07-open-door-light":
        "An interior door standing open onto a bright room, daylight spilling across the "
        "threshold onto a wooden floor, nobody in frame.",
    "08-counter-daylight":
        "A clean public service counter in daylight, the far side soft and out of focus, pale "
        "surfaces, one blank sheet on the counter, nobody recognisable in frame.",
}


def token() -> str:
    # On Windows gcloud is a .cmd wrapper, so the bare name is not an
    # executable that CreateProcess can find. Resolve it properly rather than
    # reaching for shell=True.
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not exe:
        raise RuntimeError("gcloud is not on PATH")
    return subprocess.run(
        [exe, "auth", "print-access-token"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def generate(name: str, scene: str, bearer: str) -> Path | None:
    url = (f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}"
           f"/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent")
    body = {
        "contents": [{"role": "user", "parts": [{"text": LOOK + scene + BANS}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.load(resp)

    for cand in payload.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                path = OUT / f"{name}.png"
                path.write_bytes(base64.b64decode(blob["data"]))
                return path
    print(f"  no image part returned for {name}: {json.dumps(payload)[:300]}")
    return None


# Eight images back to back is enough to hit the quota, and three of the first
# eight did. This file calls Vertex directly instead of going through
# migragent/model.py, so it never learned D20: a 429 is weather, and a generator
# that gives up on the first one leaves a half drawn set that looks like a model
# refusing to draw a door.
ATTEMPTS = 4
BASE_DELAY = 8.0


def generate_with_retry(name: str, scene: str, bearer: str):
    import random
    import time
    import urllib.error

    for attempt in range(1, ATTEMPTS + 1):
        try:
            return generate(name, scene, bearer)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == ATTEMPTS:
                raise
            wait = BASE_DELAY * attempt + random.uniform(0, 4)
            print(f"  HTTP {exc.code}, waiting {wait:.0f}s and asking again "
                  f"({attempt} of {ATTEMPTS})", flush=True)
            time.sleep(wait)
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bearer = token()
    force = "--force" in sys.argv
    made = kept = 0

    for name, scene in SHOTS.items():
        existing = OUT / f"{name}.png"
        if existing.exists() and not force:
            # Re-running to fill the gaps should not pay again for the ones that
            # already worked. `--force` redraws the whole set.
            print(f"keeping {name}")
            kept += 1
            continue

        print(f"generating {name} ...", flush=True)
        try:
            path = generate_with_retry(name, scene, bearer)
        except Exception as exc:  # noqa: BLE001
            print(f"  failed: {exc}")
            continue
        if path:
            print(f"  wrote {path} ({path.stat().st_size:,} bytes)")
            made += 1

    missing = len(SHOTS) - made - kept
    print(f"\n{made} drawn, {kept} kept, {missing} still missing")
    return 0 if made or kept else 1


if __name__ == "__main__":
    sys.exit(main())
