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

WHY THE AGENT COMES THROUGH HERE TOO
------------------------------------
ADK ships its own model client. Left alone it would open its own connection to
Vertex, and every lesson in this file would apply to four callers and not to the
fifth, which is the one that talks the most. So `call_content` exists: it takes a
request that already has tools and a system instruction on it, and puts it
through the same retry loop as everything else. `migragent/agent_llm.py` is the
adapter, and `tools/test_agent.py` checks the claim rather than trusting it.
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


def endpoint(project: str, location: str, model: str) -> str:
    return (f"https://aiplatform.googleapis.com/v1/projects/{project}"
            f"/locations/{location}/publishers/google/models/{model}:generateContent")


def _post(url: str, body: bytes, credentials) -> dict[str, Any]:
    """The retry loop. Every model call in this product goes through here.

    Kept as one function rather than copied into each caller, because the whole
    point of D20 is that there is one place where a 429 is recognised as a 429.
    """
    import google.auth.transport.requests

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
                return json.load(response)
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

    raise ModelError(last_status, last_detail, MAX_ATTEMPTS)  # pragma: no cover


def call_content(*, project: str, model: str, location: str, credentials,
                 body: dict[str, Any]) -> dict[str, Any]:
    """Send a request that is already assembled, and return the raw response.

    For callers that build their own request because they need tools, a system
    instruction or a conversation with more than one turn in it. The retries and
    the error type are the same ones everything else gets.
    """
    return _post(endpoint(project, location, model), json.dumps(body).encode(), credentials)


def _json_from(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """The object in a response, or why there is not one."""
    try:
        candidates = payload["candidates"]
        content = candidates[0]["content"]["parts"]
    except (KeyError, IndexError):
        # No candidates usually means a safety block or an empty generation, and
        # saying so beats a KeyError three frames up.
        return None, f"no candidates in the response: {json.dumps(payload)[:200]}"

    text = "".join(p.get("text", "") for p in content)
    try:
        return json.loads(text), ""
    except json.JSONDecodeError:
        pass

    # `strict=False` allows raw control characters inside strings. Quoting a job
    # advert verbatim means quoting its line breaks, and a model that copies one
    # into a string without escaping it produces an object that is complete,
    # correct and rejected. That failed twice on the same posting and read as a
    # truncated answer, because the parser stops at the first bad character and
    # what it had read up to then looked like a good beginning.
    try:
        return json.loads(text, strict=False), ""
    except json.JSONDecodeError:
        pass

    # Salvage before giving up. A thinking model sometimes puts a sentence of its
    # own in front of the answer or a stray line after it, and the object in the
    # middle is perfectly good.
    #
    # This does not repair broken JSON and must not: it finds the outermost
    # balanced braces and parses between them, so a genuinely truncated answer
    # still fails, which is what should happen to a truncated answer.
    salvaged = _outermost_object(text)
    if salvaged is not None:
        return salvaged, ""

    reason = candidates[0].get("finishReason", "")
    if reason == "MAX_TOKENS":
        return None, f"the answer was cut off at the token limit after {len(text):,} characters"
    return None, (f"the response was not JSON ({reason or 'no reason given'}, "
                  f"{len(text):,} characters): {text[:160]}")


def call_json(*, project: str, model: str, location: str, credentials,
              parts: list[dict[str, Any]], temperature: float = 0.0,
              max_output_tokens: int | None = None) -> dict[str, Any]:
    """Call Gemini and parse the JSON it returns.

    `parts` is the content parts list, so a caller can pass text, or inline
    document data followed by a prompt, without this function knowing which.

    `max_output_tokens` is for callers whose answer is long by nature. Thinking
    is spent from the same budget as the answer, and this model spends thousands
    of tokens on it before writing a word.

    WHY A BAD ANSWER IS RETRIED
    ---------------------------
    The transport retries are for HTTP statuses. This one is for the body: the
    same posting, scored twice with temperature zero, came back as a complete
    object once and as a truncated one the next time. That is weather, like a
    429, and one more attempt costs a second and turns three failures in five
    into none. A second failure is reported rather than retried forever, because
    a prompt that reliably produces half an object is a bug and should look like
    one.
    """
    config: dict[str, Any] = {"temperature": temperature,
                              "responseMimeType": "application/json"}
    if max_output_tokens:
        config["maxOutputTokens"] = max_output_tokens
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}

    why = ""
    for attempt in (1, 2):
        payload = call_content(project=project, model=model, location=location,
                               credentials=credentials, body=body)
        parsed, why = _json_from(payload)
        if parsed is not None:
            return parsed

    raise ModelError(None, f"{why} (asked twice)", 2)


def _outermost_object(text: str) -> dict[str, Any] | None:
    """The first complete `{...}` in a string, or None.

    Brace counting rather than a regex, because a regex cannot count and the
    quotes inside the object contain braces of their own often enough to matter.
    """
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1], strict=False)
                except json.JSONDecodeError:
                    return None
    return None


def call_raw(*, project: str, model: str, location: str, credentials,
             parts: list[dict[str, Any]], response_modalities: list[str] | None = None,
             extra_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Same retries, for calls that do not return JSON, such as images."""
    config: dict[str, Any] = dict(extra_config or {})
    if response_modalities:
        config["responseModalities"] = response_modalities
    return call_content(
        project=project, model=model, location=location, credentials=credentials,
        body={"contents": [{"role": "user", "parts": parts}], "generationConfig": config},
    )
