"""The intermediates in migragent/certs, and the hosts that need them.

    python -m tools.test_tls

Checked through plain OpenSSL with certifi's roots, which is how the job in
Cloud Run verifies. On Windows the fetcher's own context asks the OS, and the OS
fetches missing intermediates by itself, so testing `fetcher.TLS` here would
pass with or without the fix and prove nothing.
"""
from __future__ import annotations

import os
import socket
import ssl
import sys

sys.path.insert(0, ".")

import certifi  # noqa: E402

from migragent.fetcher import CERTS, _add_intermediates  # noqa: E402

# Hosts known to send a bare leaf. Each one fails without migragent/certs.
BARE_LEAF = ["aima.gov.pt"]
CONTROL = ["www.gov.uk"]

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    passed, failed = passed + ok, failed + (not ok)
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def handshake(host: str, extra: bool) -> str:
    ctx = ssl.create_default_context(cafile=certifi.where())
    if extra:
        _add_intermediates(ctx)
    try:
        with socket.create_connection((host, 443), timeout=20) as s, \
                ctx.wrap_socket(s, server_hostname=host):
            return "ok"
    except ssl.SSLCertVerificationError as exc:
        return exc.verify_message or "verify failed"


def main() -> int:
    pems = [n for n in os.listdir(CERTS) if n.endswith(".pem")]
    check("certs folder holds at least one intermediate", bool(pems), ", ".join(pems))

    ctx = ssl.create_default_context(cafile=certifi.where())
    before = len(ctx.get_ca_certs())
    _add_intermediates(ctx)
    added = [c for c in ctx.get_ca_certs()][before:]
    check("every file loads", len(added) == len(pems), f"{len(added)} loaded")
    # An intermediate is issued by someone else. A file whose subject is its own
    # issuer would be a root, and a root has no business being added here.
    check("none of them is a root", all(c["subject"] != c["issuer"] for c in added))

    for host in BARE_LEAF:
        check(f"{host} fails without the certs (still a bare leaf)", handshake(host, False) != "ok")
        check(f"{host} verifies with the certs", handshake(host, True) == "ok")
    for host in CONTROL:
        check(f"{host} still verifies", handshake(host, True) == "ok")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
