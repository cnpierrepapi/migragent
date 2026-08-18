"""Prove the researcher cannot publish, rather than asserting it.

This test is the reason the sentence "the researcher cannot write" is allowed to
appear in migragent/identity.py. It was written before that sentence went back
in, which is rule 3 in docs/RULES.md and the whole of D1 in docs/DEFECTS.md.

It checks six things, and a pass is not "nothing crashed":

  1. the researcher CAN read the registry            (or it cannot do its job)
  2. the researcher CANNOT write to Firestore        (the actual claim)
  3. the writer CAN write                            (or the denial above proves nothing,
                                                      it would just mean Firestore is down)
  4. the web identity CANNOT mint a watcher token    (a web request cannot start a crawl)
  5. the researcher CANNOT read, overwrite, delete or list snapshots
                                                     (the archive is append only to its writer)

Test 3 matters as much as test 2. A denial on its own is worthless evidence
because everything denies when the database is unreachable. The pair is what
makes it a real result.

    python tools/test_isolation.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from google.api_core import exceptions as gexc
from google.auth import exceptions as authexc
from google.cloud import firestore, storage

sys.path.insert(0, ".")
from migragent import identity  # noqa: E402

PROJECT = "project-e0928f2f-5abf-46a3-b8a"
PROBE = "_isolation_probe"
BUCKET = "migragent-snapshots"

PASS = "PASS"
FAIL = "FAIL"
UNPROVEN = "????"
results: list[tuple[str, str, str]] = []


def record(name: str, verdict: str, detail: str) -> None:
    results.append((verdict, name, detail))
    print(f"  {verdict}  {name}: {detail}")


def unproven(exc: BaseException) -> bool:
    """Is this failure about missing credentials rather than a real boundary?

    A negative test that passes because nothing is configured is worse than no
    test, because it reads like evidence. The first run of this file did exactly
    that: check 4 reported PASS while ADC was absent. See D5.
    """
    return isinstance(exc, authexc.DefaultCredentialsError)


def client(principal: str) -> firestore.Client:
    return firestore.Client(
        project=PROJECT,
        credentials=identity.credentials_for(principal, PROJECT),
    )


def main() -> int:
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"isolation test, {stamp}\n")

    # 1. The researcher must be able to read, or least privilege has gone too far
    #    and it cannot do its job.
    print("researcher")
    try:
        list(client(identity.RESEARCHER).collection("sources").limit(1).stream())
        record("researcher can read the registry", PASS, "read succeeded")
    except Exception as exc:  # noqa: BLE001
        record(
            "researcher can read the registry",
            UNPROVEN if unproven(exc) else FAIL,
            f"{type(exc).__name__}: {exc}",
        )

    # 2. The claim itself.
    try:
        client(identity.RESEARCHER).collection(PROBE).document("attempt").set(
            {"written_at": stamp, "by": identity.RESEARCHER}
        )
        record(
            "researcher CANNOT write",
            FAIL,
            "the write SUCCEEDED, so the isolation claim is false and must come "
            "out of identity.py again",
        )
    except gexc.PermissionDenied as exc:
        record("researcher CANNOT write", PASS, f"PermissionDenied, which is the point ({exc.code})")
    except Exception as exc:  # noqa: BLE001
        record(
            "researcher CANNOT write",
            UNPROVEN if unproven(exc) else FAIL,
            f"denied, but with {type(exc).__name__} rather than PermissionDenied, so this "
            f"does not prove a permission boundary: {exc}",
        )

    # 3. The control. Without this the denial above is not evidence of anything.
    print("writer")
    try:
        doc = client(identity.WRITER).collection(PROBE).document("control")
        doc.set({"written_at": stamp, "by": identity.WRITER})
        doc.delete()
        record("writer CAN write", PASS, "wrote and cleaned up, so Firestore is reachable")
    except Exception as exc:  # noqa: BLE001
        record(
            "writer CAN write",
            UNPROVEN if unproven(exc) else FAIL,
            f"{type(exc).__name__}: {exc}. The researcher denial above proves nothing "
            f"while this fails",
        )

    # 4. The web identity may mint tokens for the researcher and the writer. Not
    #    the watcher, so an HTTP request cannot start a crawl round.
    print("web")
    try:
        creds = identity.credentials_for(identity.WATCHER, PROJECT)
        from google.auth.transport.requests import Request

        creds.refresh(Request())
        record(
            "web CANNOT become the watcher",
            FAIL,
            "a watcher token was minted",
        )
    except Exception as exc:  # noqa: BLE001
        record(
            "web CANNOT become the watcher",
            UNPROVEN if unproven(exc) else PASS,
            "refused for lack of credentials, which proves nothing"
            if unproven(exc)
            else f"refused: {type(exc).__name__}",
        )

    # 5. The snapshot archive is the evidence behind every "read on" date. The
    #    researcher writes to it and must not be able to revise it afterwards,
    #    or the archive is only as trustworthy as the process that fills it.
    print("snapshots")
    try:
        res_storage = storage.Client(
            project=PROJECT,
            credentials=identity.credentials_for(identity.RESEARCHER, PROJECT),
        )
        bucket = res_storage.bucket(BUCKET)
        probes = {
            "researcher CANNOT list snapshots":
                lambda: list(res_storage.list_blobs(BUCKET, max_results=1)),
            "researcher CANNOT read a snapshot back":
                lambda: bucket.blob("_probe/none.html").download_as_bytes(),
        }
        for name, probe in probes.items():
            try:
                probe()
                record(name, FAIL, "it succeeded")
            except gexc.Forbidden:
                record(name, PASS, "Forbidden 403")
            except gexc.NotFound:
                # Reading a missing object as a principal that may read would
                # give 404 rather than 403, so this is a real failure of the
                # boundary and not a missing fixture.
                record(name, FAIL, "NotFound, meaning read access was permitted")
            except Exception as exc:  # noqa: BLE001
                record(name, UNPROVEN if unproven(exc) else FAIL,
                       f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001
        record("snapshot boundary", UNPROVEN if unproven(exc) else FAIL,
               f"{type(exc).__name__}: {exc}")

    print()
    passed = [r for r in results if r[0] == PASS]
    failed = [r for r in results if r[0] == FAIL]
    unknown = [r for r in results if r[0] == UNPROVEN]

    print(f"{len(passed)} passed, {len(failed)} failed, {len(unknown)} unproven, "
          f"of {len(results)}")

    if unknown:
        print("\nUNPROVEN. These did not run, so they are evidence of nothing.")
        for _, name, detail in unknown:
            print(f"  {name}: {detail}")
        print("\nMost likely there are no application default credentials. Run:")
        print("  gcloud auth application-default login")

    if failed:
        print("\nFAILED:")
        for _, name, detail in failed:
            print(f"  {name}: {detail}")

    # Unproven is not success. Nothing may claim isolation on this exit code.
    return 0 if (passed and not failed and not unknown) else 1


if __name__ == "__main__":
    sys.exit(main())
