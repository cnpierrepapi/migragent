"""Generate a short clip with Seedance on GMI Cloud, and prepare it for the web.

    python -m tools.make_video hero "daylight across a wooden table, hands turning a page"
    python -m tools.make_video hero --from-file web/brand/video/raw/hero.mp4

Video is the one thing this project cannot make on Google Cloud: every Veo model
returns 404 on this project, the same way every Imagen endpoint did in D3. So
video comes from GMI Cloud, which is a second vendor and is named as one.

THE KEY IS NOT IN THIS REPO
---------------------------
It is read from MIGRAGENT_SECRETS/migragent-env.txt, outside the working tree,
and it is never printed. Nothing here writes it to a file the repo can see.

WHAT COMES BACK, AND WHAT WE DO TO IT
-------------------------------------
Seedance returns a 1248x704 h264 file of a few megabytes. That is fine for a
download and far too heavy for a page that currently loads in under a second, so
ffmpeg produces three things:

    hero.mp4     h264, faststart, for everything
    hero.webm    vp9, smaller, for browsers that take it
    hero.jpg     the poster, shown before the video loads and instead of it on a
                 slow connection or when motion is reduced

A hero that autoplays is muted and silent by construction: there is no audio
track in the output at all, which is stronger than an attribute a browser may
ignore.

THE MONEY
---------
GMI's own documentation says the unit price is TBD, so nothing here assumes a
clip is cheap. One clip per run, no batch mode, and the request is printed before
it is sent.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SECRETS = Path("C:/Users/user/MIGRAGENT_SECRETS/migragent-env.txt")
SUBMIT = "https://console.gmicloud.ai/api/v1/ie/requestqueue/apikey/requests"
MODEL = "seedance-1-0-pro-250528"

RAW = Path("web/brand/video/raw")
OUT = Path("web/brand/video")

# The look, so every clip belongs to the same shoot as the stills.
LOOK = (" Bright natural daylight, warm and clean, unhurried. Documentary framing, shallow "
        "depth of field, gentle slow movement. Nobody looks at the camera. "
        "No text, no lettering, no signage, no logos, no crest, no seal, no flag. "
        "Any paper is blank or out of focus, never readable.")


def api_key() -> str:
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.startswith("GMI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"no GMI_API_KEY in {SECRETS}")


def _post(url: str, body: dict, key: str) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def _get(url: str, key: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def ffmpeg() -> str:
    for candidate in Path("C:/Users/user/AppData/Local/Microsoft/WinGet/Packages").rglob("ffmpeg.exe"):
        return str(candidate)
    return "ffmpeg"


def generate(name: str, prompt: str, seconds: int = 5, resolution: str = "1080p") -> Path:
    key = api_key()
    payload = {"prompt": prompt + LOOK, "duration": seconds, "resolution": resolution,
               "ratio": "16:9", "watermark": False, "camerafixed": False}

    print(f"model {MODEL}, {seconds}s, {resolution}")
    print(f"prompt: {payload['prompt'][:160]}...\n")

    submitted = _post(SUBMIT, {"model": MODEL, "payload": payload}, key)
    request_id = submitted["request_id"]
    print(f"request {request_id}: {submitted.get('status')}")

    started = time.monotonic()
    while True:
        state = _get(f"{SUBMIT}/{request_id}", key)
        status = state.get("status")
        if status in ("success", "failed", "cancelled"):
            break
        print(f"  {status}, {time.monotonic() - started:.0f}s", flush=True)
        time.sleep(15)

    if status != "success":
        raise SystemExit(f"the clip {status}: {json.dumps(state)[:300]}")

    url = state["outcome"]["video_url"]
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{name}.mp4"
    urllib.request.urlretrieve(url, raw)
    print(f"\ndownloaded {raw} ({raw.stat().st_size / 1e6:.1f} MB) "
          f"in {time.monotonic() - started:.0f}s")
    return raw


def prepare(name: str, raw: Path) -> None:
    """Web sized mp4, webm and poster. No audio track in either output."""
    OUT.mkdir(parents=True, exist_ok=True)
    tool = ffmpeg()

    mp4, webm, poster = OUT / f"{name}.mp4", OUT / f"{name}.webm", OUT / f"{name}.jpg"

    subprocess.run([tool, "-v", "error", "-y", "-i", str(raw), "-an",
                    "-vf", "scale=1280:-2", "-c:v", "libx264", "-crf", "26",
                    "-preset", "slow", "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run([tool, "-v", "error", "-y", "-i", str(raw), "-an",
                    "-vf", "scale=1280:-2", "-c:v", "libvpx-vp9", "-crf", "34",
                    "-b:v", "0", "-row-mt", "1", str(webm)], check=True)
    subprocess.run([tool, "-v", "error", "-y", "-ss", "1", "-i", str(raw),
                    "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "4",
                    str(poster)], check=True)

    for path in (mp4, webm, poster):
        print(f"  {path}  {path.stat().st_size / 1024:.0f} KB")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 64

    name = sys.argv[1]

    if "--from-file" in sys.argv:
        raw = Path(sys.argv[sys.argv.index("--from-file") + 1])
        if not raw.exists():
            raise SystemExit(f"{raw} does not exist")
    else:
        prompt = sys.argv[2] if len(sys.argv) > 2 else ""
        if not prompt:
            print(__doc__)
            return 64
        seconds = int(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 5
        resolution = (sys.argv[sys.argv.index("--resolution") + 1]
                      if "--resolution" in sys.argv else "1080p")
        raw = generate(name, prompt, seconds, resolution)

    print("\npreparing for the web:")
    prepare(name, raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
