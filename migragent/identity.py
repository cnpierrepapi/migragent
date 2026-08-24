"""Each worker runs as itself.

Each worker holds only the permissions its job needs. Roles are applied by
tools/grant_roles.sh, which keeps the whole model in one readable place.

MEASURED ON 18 AUGUST 2026 by tools/test_isolation.py, which reported 4 passed,
0 failed, 0 unproven:

  - the researcher CAN read the source registry
  - the researcher CANNOT write to Firestore, refused with PermissionDenied 403
  - the writer CAN write, which is what makes the line above evidence rather
    than a database being unreachable
  - nothing can mint a token for the watcher

So "the researcher cannot publish a guide" is enforced by Google rather than by
our code choosing to behave. That sentence is allowed here only because the test
above exists and passed, and it comes straight back out if it ever stops
passing. An earlier version of this file asserted it while the four accounts
held no roles at all, which is D1 in docs/DEFECTS.md and the same failure
already recorded in docs/INHERITED.md.

The watcher is the strongest boundary of the four and it is worth naming: it has
no serviceAccountTokenCreator bindings whatsoever, so no principal anywhere can
become it. It runs as itself on its own Cloud Run job, started by Cloud
Scheduler, never by impersonation. A web request therefore cannot start a crawl
round by any path. This used to say the job was reached through Pub/Sub, which
stopped being true when Decision 4 took Pub/Sub out.

What none of this does is keep the researcher out of a case. It holds
roles/datastore.viewer, Firestore grants read at the database rather than at the
collection, and the product simply never asks it for one. D39.

Re-run the test after any change here or in tools/grant_roles.sh:

    python tools/test_isolation.py
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
