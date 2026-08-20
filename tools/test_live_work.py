"""Walk Build 5 the way a person would, over HTTP, against the deployed service.

    python -m tools.test_live_work
    python -m tools.test_live_work --url https://migragent-ba5o2l34rq-uc.a.run.app

Everything else tests the modules. This tests the product: a case is started, a
CV is uploaded, the matched jobs come back, one is scored, one goes on the board,
the pieces are drafted, and the case is deleted at the end. Nothing here imports
migragent except to build the fixture PDF, so a route that is wired wrong fails
here even when every unit underneath it passes.

That gap is real. The people finder was tested as a module and its route had
never once been called.
"""
from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, ".")

from tools.test_work import a_cv_pdf  # noqa: E402

DEFAULT_URL = "https://migragent-ba5o2l34rq-uc.a.run.app"


class Session:
    """The smallest cookie-holding client that will do."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = {}

    def _request(self, path: str, data=None, headers=None) -> tuple[int, str]:
        url = self.base + path
        request = urllib.request.Request(url, data=data, headers=headers or {})
        if self.jar:
            request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self.jar.items()))
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                body = response.read().decode("utf-8", "replace")
                status = response.status
                for header in response.headers.get_all("Set-Cookie") or []:
                    name, _, rest = header.partition("=")
                    self.jar[name.strip()] = rest.split(";")[0]
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")
        return status, body

    def get(self, path: str) -> tuple[int, str]:
        return self._request(path)

    def post_form(self, path: str, fields: dict[str, str]) -> tuple[int, str]:
        body = urllib.parse.urlencode(fields).encode()
        return self._request(path, body,
                             {"Content-Type": "application/x-www-form-urlencoded"})

    def post_file(self, path: str, field: str, filename: str, data: bytes,
                  mime: str, fields: dict[str, str] | None = None) -> tuple[int, str]:
        boundary = "----migragentprobe"
        parts = []
        for key, value in (fields or {}).items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n"
                         f"{value}\r\n".encode())
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
            + data + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return self._request(path, b"".join(parts),
                             {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def main() -> int:
    base = DEFAULT_URL
    if "--url" in sys.argv:
        base = sys.argv[sys.argv.index("--url") + 1]

    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail=""):
        results.append((bool(ok), name, str(detail)))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""),
              flush=True)

    session = Session(base)
    print(f"walking {base}\n", flush=True)

    status, _ = session.post_form("/begin", {"place": "CA", "lane": "work"})
    check(status == 200 and "migragent_case" in session.jar,
          "a case can be started", f"HTTP {status}")
    if "migragent_case" not in session.jar:
        return _report(results)

    started = time.monotonic()
    status, body = session.post_file("/cv", "cv", "probe-cv.pdf", a_cv_pdf(),
                                     "application/pdf")
    check(status in (200, 302), "a CV can be uploaded and read",
          f"HTTP {status} in {time.monotonic() - started:.0f}s")

    status, body = session.get("/work")
    listings = re.findall(r'name="listing" value="([^"]+)"', body)
    check(status == 200 and bool(listings), "the CV matched jobs on the live site",
          f"{len(set(listings))} shown")
    check("because your CV says" in body.lower() or "Matched because" in body,
          "each job says which line of the CV put it there")
    # Rule 39, checked as markup rather than as a word count. The first version
    # of this line searched the prose for the word "search", which the page uses
    # to say it does not have one.
    typed_in = re.findall(r'<input[^>]*type="(search|text)"', body)
    check(not typed_in and "<textarea" not in body,
          "there is nothing on the page to type a query into",
          f"typed inputs: {typed_in or 'none'}")
    if not listings:
        return _report(results)

    listing = listings[0]

    started = time.monotonic()
    status, _ = session.post_form("/fit", {"listing": listing})
    check(status in (200, 302), "a listing can be scored",
          f"HTTP {status} in {time.monotonic() - started:.0f}s")

    status, body = session.get("/work")
    scored = re.search(r'class="score">([^<]*)', body)
    check(bool(scored), "the score comes back on the page",
          scored.group(1).strip() if scored else "no score found")
    check("not a prediction that you will be offered the job" in body,
          "the number carries the sentence that limits it")

    status, _ = session.post_form("/interested", {"listing": listing})
    check(status in (200, 302), "\"I'm interested\" puts it on the board", f"HTTP {status}")

    status, body = session.get("/board")
    item = re.search(r'name="item" value="([^"]+)"', body)
    check(status == 200 and bool(item), "the board shows the application")
    check("To prepare" in body, "it starts in the first column")
    if not item:
        return _report(results)
    item_id = item.group(1)

    for kind, label in (("cover_letter", "a cover letter"), ("people", "the people to speak to")):
        started = time.monotonic()
        status, _ = session.post_form("/board/draft", {"item": item_id, "kind": kind})
        check(status in (200, 302), f"{label} can be drafted from the board",
              f"HTTP {status} in {time.monotonic() - started:.0f}s")

    status, body = session.get("/board")
    check("draft</span>" in body or "draft<" in body,
          "every drafted piece is labelled a draft on the card")
    check("Found through Google Search" in body,
          "the people are labelled as found by search, not by our own reading")
    check("@" not in re.sub(r'href="[^"]*"', "", body.split("People")[-1][:4000]),
          "no contact details appear on the board")

    status, body = session.post_form("/delete", {})
    check(status == 200 and '"case":1' in body.replace(" ", ""),
          "the case deletes itself and says what went", body.strip()[:120])

    return _report(results)


def _report(results) -> int:
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
