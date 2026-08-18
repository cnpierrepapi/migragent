"""Each worker runs as itself.

Carried over from an earlier build because the reasoning is not specific to any
domain. The intent is that a worker holds only the permissions its job needs,
and that the machine it runs on holds none of its own: it is allowed to mint
tokens for these identities and nothing else.

STATE ON 18 AUGUST 2026: the four accounts below exist and hold no roles at all.
Nothing is enforced yet, so nothing in this file may be described as a
guarantee. An earlier version of this docstring said a claim like "the reader
cannot write" is enforced by Google rather than by our code choosing to behave.
That sentence was not true when it was written, which is the exact failure
recorded in docs/INHERITED.md, and it travelled here by being copied across with
the file. See D1 in docs/DEFECTS.md.

It goes back only after two things: the least privilege grants are applied, and
a test shows the researcher being refused a write. Not before.
"""
from __future__ import annotations

import os

from google.auth import default, impersonated_credentials

# The researcher reads official sources and extracts requirements. It holds no
# write access to anything a user will read, so a bad extraction cannot become
# a published guide without passing through the writer.
RESEARCHER = "migragent-researcher"

# The writer assembles the guide. It is the only identity that may publish one.
WRITER = "migragent-writer"

# The watcher re-reads sources on a schedule and records what moved.
WATCHER = "migragent-watcher"

# The web app. Takes intake, serves guides, sends notifications. It may write a
# case and read a guide, and it may not publish one, so a bug in a request
# handler cannot forge a requirement.
WEB = "migragent-web"

PRINCIPALS = (RESEARCHER, WRITER, WATCHER, WEB)

_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def service_account(principal: str, project: str) -> str:
    if principal not in PRINCIPALS:
        raise ValueError(f"{principal} is not known: {', '.join(PRINCIPALS)}")
    return f"{principal}@{project}.iam.gserviceaccount.com"


def credentials_for(principal: str, project: str, lifetime: int = 600):
    """Credentials that belong to the worker, not to the host.

    Short lived on purpose, so a process that hangs does not leave a long lived
    token in memory.

    Asking the ambient credential who it is does not work on Cloud Run: it
    reports "default" until it has been refreshed over the network, so the
    comparison silently fails and the service tries to impersonate itself, which
    it cannot do and which hangs rather than failing cleanly. That cost a deploy
    cycle to find last time. So the deployment states it instead, and being
    explicit means a misconfigured deployment fails loudly rather than quietly
    running as the wrong thing.
    """
    source, _ = default(scopes=[_SCOPE])

    if os.environ.get("MIGRAGENT_AMBIENT_PRINCIPAL") == principal:
        return source

    return impersonated_credentials.Credentials(
        source_credentials=source,
        target_principal=service_account(principal, project),
        target_scopes=[_SCOPE],
        lifetime=lifetime,
    )
