"""The model ADK talks to, which is the model everything else talks to.

WHY THIS FILE EXISTS
--------------------
ADK comes with its own client. Point an agent at "gemini-3.5-flash" and it opens
its own connection to Vertex, with its own idea of what to do about a 429.

That would have been fine except for D20: every model call in this product goes
through `migragent/model.py` because five callers each retrying differently is
how one rate limit turned into three unrelated looking bugs. An agent is the
chattiest caller in the system, firing a call per turn per page. Letting the
loudest one out of the room would have left the rule true of everything except
the thing it matters most for.

So this is a `BaseLlm` that ADK is happy to drive, and underneath it is the same
retry loop, the same backoff, the same `ModelError` carrying a status code. The
agent gets no special treatment when the quota is hit.

WHAT THIS IS NOT
----------------
It is not streaming. The REST call returns one response and this yields it. ADK
supports streaming and nothing here needs it: a research turn is used whole or
not at all, and there is no user watching tokens arrive.

HOW THE TWO SHAPES DIFFER
-------------------------
ADK hands over an `LlmRequest` whose config mixes two things that Vertex keeps
apart: sampling settings, which belong inside `generationConfig`, and the tools,
the system instruction and the safety settings, which sit at the top level.
Getting that split wrong does not raise, it just silently ignores the tools, so
the split is written out by name below rather than guessed at.

The names below were checked field by field against `GenerateContentConfig` on
google-genai 2.x, not remembered. It carries 35 fields: 6 top level, 3 that mean
something only to the client library, and 26 that are sampling settings.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from . import model as model_module

# Fields Vertex expects at the top level of a generateContent request. Anything
# else in the config is a sampling setting and goes inside generationConfig.
TOP_LEVEL = {"tools", "toolConfig", "systemInstruction", "safetySettings",
             "cachedContent", "labels"}

# Client side settings that mean something to the genai library and nothing to
# the REST endpoint. Sent anyway, they are rejected as unknown fields.
#
# These three are the whole list on google-genai 2.x. Retry options are real but
# they live inside HttpOptions rather than beside it, so dropping httpOptions
# already takes them with it. An earlier version of this set also named
# abortSignal, which is not a field on this type at all.
NOT_FOR_THE_WIRE = {"httpOptions", "automaticFunctionCalling",
                    "shouldReturnHttpResponse"}


def request_body(llm_request: LlmRequest) -> dict[str, Any]:
    """Turn what ADK built into what Vertex accepts.

    Separated out so it can be tested without a network, a project or a
    credential, which is most of what can go wrong here.
    """
    body: dict[str, Any] = {
        "contents": [c.model_dump(mode="json", by_alias=True, exclude_none=True)
                     for c in (llm_request.contents or [])],
    }

    config = llm_request.config
    dumped = (config.model_dump(mode="json", by_alias=True, exclude_none=True)
              if config is not None else {})

    generation: dict[str, Any] = {}
    for key, value in dumped.items():
        if key in NOT_FOR_THE_WIRE:
            continue
        if key in TOP_LEVEL:
            body[key] = value
        else:
            generation[key] = value

    # A system instruction may arrive as a bare string. Vertex wants the same
    # shape as a content block, and sending the string gets a 400 that says
    # nothing useful about which field was wrong.
    system = body.get("systemInstruction")
    if isinstance(system, str):
        body["systemInstruction"] = {"parts": [{"text": system}]}

    if generation:
        body["generationConfig"] = generation
    return body


class MigragentLlm(BaseLlm):
    """A model ADK can drive, wired to the one caller that retries properly."""

    model_config = {"arbitrary_types_allowed": True}

    project: str = ""
    location: str = "global"
    credentials: Any = None

    @classmethod
    def supported_models(cls) -> list[str]:
        # Registered by hand rather than by pattern. An agent should not be able
        # to end up on a different model because a name happened to match.
        return []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        payload = model_module.call_content(
            project=self.project, model=self.model, location=self.location,
            credentials=self.credentials, body=request_body(llm_request),
        )
        yield LlmResponse.create(types.GenerateContentResponse.model_validate(payload))
