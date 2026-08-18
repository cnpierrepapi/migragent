"""Settings, all from the environment.

Nothing here has a default that would let a misconfigured worker run against the
wrong project or quietly fall back to a weaker model.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


@dataclass(frozen=True)
class Config:
    project: str
    region: str

    # Gemini 3.5 is not served from us-central1. Every 3.5 model returns 404
    # there and resolves at "global" instead, so model calls are pinned to a
    # different location from the rest of the estate on purpose. This is the
    # single most expensive gotcha carried over from the last build.
    model: str
    model_location: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            project=_require("GOOGLE_CLOUD_PROJECT"),
            region=os.environ.get("MIGRAGENT_REGION", "us-central1"),
            model=os.environ.get("MIGRAGENT_MODEL", "gemini-3.5-flash"),
            model_location=os.environ.get("MIGRAGENT_MODEL_LOCATION", "global"),
        )
