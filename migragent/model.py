"""One way to call the model, with retries and errors that say what happened.

WHY THIS EXISTS
---------------
Five places were each calling Vertex with their own copy of the same twenty
lines, and none of them retried. A single run fires five calls back to back, hit
the quota, and produced three different symptoms that all looked like different
bugs:

  - a document read returned zero fields with `error: HTTPError`
  - two route searches reported "the route search failed: HTTPError"
  - the form generator returned one question instead of twelve

Every one of those was HTTP 429, Too Many Requests. The bare exception name hid
it, so the failure looked like a model behaving badly rather than a rate limit.
That is D20.

So: one caller, backoff on the statuses worth retrying, and an error that
carries the status code and the first part of the body. An error message that
does not say what went wrong costs more than the failure it describes.

WHAT IS NOT RETRIED
-------------------
400 and 403 are answers, not weather. Retrying a malformed request or a missing
permission just makes the same mistake more slowly and buries the message.
"""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BASE_DELAY = 2.0
TIMEOUT = 180


class ModelError(RuntimeError):
    """A model call that failed, with enough detail to act on."""

    def __init__(self, status: int | None, detail: str, attempts: int) -> None:
        self.status = status
        self.detail = detail
        self.attempts = attempts
        where = f"HTTP {status}" if status else "no response"
        super().__init__(f"{where} after {attempts} attempt(s): {detail}")


def call_json(*, project: str, model: str, location: str, credentials,
              parts: list[dict[str, Any]], temperature: float = 0.0) -> dict[str, Any]:
    """Call Gemini and parse the JSON it returns.

    `parts` is the content parts list, so a caller can pass text, or inline
    document data followed by a prompt, without this function knowing which.
    """
    import google.auth.transport.requests

    url = (f"https://aiplatform.googleapis.com/v1/projects/{project}"
           f"/locations/{location}/publishers/google/models/{model}:generateContent")
    body = json.dumps({
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature,
                             "responseMimeType": "application/json"},
    }).encode()

    last_status: int | None = None
    last_detail = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        credentials.refresh(google.auth.transport.requests.Request())
        request = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {credentials.token}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            last_status = exc.code
            try:
                last_detail = exc.read()[:300].decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                last_detail = str(exc)
            if exc.code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                raise ModelError(last_status, last_detail, attempt) from exc
        except Exception as exc:  # noqa: BLE001
            last_detail = f"{type(exc).__name__}: {exc}"
            if attempt == MAX_ATTEMPTS:
                raise ModelError(None, last_detail, attempt) from exc

        # Full jitter. Several workers hitting the same quota at once should not
        # come back in step and hit it again together.
        time.sleep(random.uniform(0, BASE_DELAY * (2 ** (attempt - 1))))
    else:  # pragma: no cover
        raise ModelError(last_status, last_detail, MAX_ATTEMPTS)

    try:
        candidates = payload["candidates"]
        content = candidates[0]["content"]["parts"]
    except (KeyError, IndexError) as exc:
        # A response with no candidates usually means a safety block or an empty
        # generation, and saying so beats a KeyError three frames up.
        raise ModelError(None, f"no candidates in the response: {json.dumps(payload)[:200]}",
                         1) from exc

    text = "".join(p.get("text", "") for p in content)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelError(None, f"the response was not JSON: {text[:200]}", 1) from exc


def call_raw(*, project: str, model: str, location: str, credentials,
             parts: list[dict[str, Any]], response_modalities: list[str] | None = None,
             extra_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Same retries, for calls that do not return JSON, such as images."""
    import google.auth.transport.requests

    url = (f"https://aiplatform.googleapis.com/v1/projects/{project}"
           f"/locations/{location}/publishers/google/models/{model}:generateContent")
    config: dict[str, Any] = dict(extra_config or {})
    if response_modalities:
        config["responseModalities"] = response_modalities
    body = json.dumps({"contents": [{"role": "user", "parts": parts}],
                       "generationConfig": config}).encode()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        credentials.refresh(google.auth.transport.requests.Request())
        request = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {credentials.token}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            if exc.code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                raise ModelError(exc.code, detail, attempt) from exc
        except Exception as exc:  # noqa: BLE001
            if attempt == MAX_ATTEMPTS:
                raise ModelError(None, f"{type(exc).__name__}: {exc}", attempt) from exc
        time.sleep(random.uniform(0, BASE_DELAY * (2 ** (attempt - 1))))

    raise ModelError(None, "exhausted retries", MAX_ATTEMPTS)  # pragma: no cover
