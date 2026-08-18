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
LOOK = (
    "Documentary editorial photograph, photorealistic, 35mm, natural available light only, "
    "no flash, muted desaturated colour, cool neutral white balance, shallow depth of field, "
    "quiet and unposed, nobody looking at the camera, no smiling, no stock-photo styling. "
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
    "01-kitchen-table-form":
        "A person's hands resting on a paper form on a scratched kitchen table, a cold mug of tea "
        "beside it, late afternoon light through a window, seen from just above and behind the "
        "shoulder so the face is out of frame.",
    # Regenerated: the first version put a gold emblem and lettering on a
    # passport cover, which breaks this set's own rule. No passport in frame at
    # all now. See D4 in docs/DEFECTS.md.
    "02-printed-guide-desk":
        "A thick stack of printed pages squared off on a plain desk beside a pair of reading "
        "glasses and a plain unmarked manila folder, shot from a low three-quarter angle, "
        "morning light from the left. There is no passport and no booklet anywhere in the frame.",
    "03-bank-counter-queue":
        "The back of a person waiting at a bank counter, shot from further back in the queue, the "
        "counter and clerk soft and out of focus, cool fluorescent interior light.",
    "04-waiting-room-chairs":
        "A row of empty moulded plastic chairs against a scuffed institutional wall in an official "
        "waiting room, one chair holding a folded coat, hard morning light across the floor.",
    "05-night-desk-laptop":
        "A person alone at a desk late at night, lit only by a laptop screen, papers spread around "
        "the keyboard, shot from behind so the face is not visible, deep shadows, warm screen glow "
        "against a dark room.",
    "06-hallway-envelope":
        "A single envelope lying on a doormat in a narrow flat hallway, morning light falling from "
        "a frosted door pane, shot from standing height looking down.",
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bearer = token()
    made = 0
    for name, scene in SHOTS.items():
        print(f"generating {name} ...", flush=True)
        try:
            path = generate(name, scene, bearer)
        except Exception as exc:  # noqa: BLE001
            print(f"  failed: {exc}")
            continue
        if path:
            print(f"  wrote {path} ({path.stat().st_size:,} bytes)")
            made += 1
    print(f"\n{made} of {len(SHOTS)} images generated")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
