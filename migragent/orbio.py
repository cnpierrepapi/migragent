"""Public-page reading, paid for by $MIGRA's trading fees.

WHAT GOES THROUGH HERE
----------------------
Only calls whose caller passed `public=True` to `model.call_json`, which means
the prompt is text from public government and school pages and nothing else.
Today that is extraction, change notes, lane checks, shortage lists and school
courses, all run by the daily worker. Nothing about a person ever comes here:
documents, CVs, cases, drafts and fit scores stay on Vertex, which is what
docs/DATA_PROTECTION.md promises. `tools/test_orbio_route.py` checks that none of
those callers can reach this file.

A part that is not plain text is refused before anything is sent. A public call
has no business carrying a file, and the cheapest place to catch a caller that
was wrongly marked public is before the bytes leave.

WHY IT IS ORBIO
---------------
$MIGRA launched on Orbio's agent launchpad. 45% of its creator fees are sold for
USDG and land as gateway balance on the treasury wallet, which is also the agent
wallet. That balance buys the same Gemini model the rest of the product uses,
through an OpenAI-shaped API. So trading in the token pays for the reading the
token is about. Checked on 30 Sep 2026: the gateway answered as
google/gemini-3.8-flash when asked for it, and its usage block is OpenRouter's,
so requests reach Google through OpenRouter.

WHEN IT IS NOT ORBIO
--------------------
Always a fallback, never a dependency. With no key configured this is off. When
the balance runs out (402), the key is refused (401/403), or the gateway keeps
failing, `generate_json` returns None and the caller goes to Vertex exactly as
it did before this file existed. After a refusal it stays off for ten minutes so
a dry balance does not add a failed request in front of every call in a round.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

ENDPOINT = "https://www.orbio.so/api/v1/chat/completions"
TIMEOUT = 180
MAX_ATTEMPTS = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
COOLDOWN_SECONDS = 600

# Orbio's finish reasons are OpenAI's; `model._json_from` reads Vertex's.
FINISH = {"stop": "STOP", "length": "MAX_TOKENS", "content_filter": "SAFETY"}

_off_until = 0.0
# Per process, which is per round: the worker runs one lane per task. The cost
# is the gateway's own figure from each answer's usage block, not an estimate.
served: dict[str, Any] = {"orbio": 0, "fallback": 0, "usd": 0.0}


class NotPublic(ValueError):
    """A call marked public carried something other than text."""


def _key() -> str:
    return os.environ.get("ORBIO_API_KEY", "").strip()


def enabled() -> bool:
    return bool(_key()) and time.time() >= _off_until


def model_id(model: str) -> str:
    """Vertex names the model bare; Orbio names it with its publisher."""
    return model if "/" in model else f"google/{model}"


def to_messages(parts: list[dict[str, Any]]) -> list[dict[str, str]]:
    texts = []
    for part in parts:
        if set(part) != {"text"}:
            raise NotPublic(f"a public call carried a {sorted(part)} part; only text may go to Orbio")
        texts.append(part["text"])
    return [{"role": "user", "content": "".join(texts)}]


def to_vertex(payload: dict[str, Any]) -> dict[str, Any]:
    """An OpenAI-shaped answer in the shape `model._json_from` already reads."""
    try:
        choice = payload["choices"][0]
    except (KeyError, IndexError, TypeError):
        return {"note": f"orbio returned no choices: {json.dumps(payload)[:200]}"}
    text = (choice.get("message") or {}).get("content") or ""
    return {"candidates": [{"content": {"parts": [{"text": text}]},
                            "finishReason": FINISH.get(choice.get("finish_reason") or "", "")}],
            "servedBy": "orbio", "model": payload.get("model"), "usage": payload.get("usage")}


def _switch_off(why: str) -> None:
    global _off_until
    _off_until = time.time() + COOLDOWN_SECONDS
    log.warning("orbio off for %ss: %s", COOLDOWN_SECONDS, why)


def generate_json(*, model: str, parts: list[dict[str, Any]], temperature: float,
                  max_output_tokens: int | None, post=None) -> dict[str, Any] | None:
    """A Vertex-shaped response from Orbio, or None to mean "use Vertex"."""
    body: dict[str, Any] = {"model": model_id(model), "messages": to_messages(parts),
                            "temperature": temperature,
                            "response_format": {"type": "json_object"}}
    if max_output_tokens:
        body["max_tokens"] = max_output_tokens
    send = post or _post

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            answer = to_vertex(send(json.dumps(body).encode()))
            if "candidates" not in answer:
                log.warning("%s; using Vertex", answer.get("note"))
                break
            served["orbio"] += 1
            try:
                served["usd"] += float((answer.get("usage") or {}).get("cost") or 0)
            except (TypeError, ValueError):
                pass
            return answer
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 402, 403):
                _switch_off(f"HTTP {exc.code}")
                break
            if exc.code not in RETRY_STATUSES:
                log.warning("orbio refused the request, HTTP %s; using Vertex", exc.code)
                break
        except (OSError, ValueError) as exc:
            log.warning("orbio attempt %s failed: %s", attempt, exc)
        if attempt < MAX_ATTEMPTS:
            time.sleep(random.uniform(0, 2.0 * (2 ** (attempt - 1))))
    served["fallback"] += 1
    return None


def balance() -> dict[str, str] | None:
    """The gateway balance as Orbio reports it, or None. Read by the worker only.

    The web service shows this figure without holding the key: the worker
    writes it to Firestore after each round, and the page reads it from there.
    """
    if not _key():
        return None
    request = urllib.request.Request("https://www.orbio.so/api/v1/key", headers={
        "Authorization": f"Bearer {_key()}", "User-Agent": "migragent"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            b = json.load(response).get("balance") or {}
        return {"available": str(b.get("available", "")), "used": str(b.get("used", ""))}
    except (OSError, ValueError):
        return None


def _post(body: bytes) -> dict[str, Any]:
    request = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {_key()}", "Content-Type": "application/json",
        "User-Agent": "migragent"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)
