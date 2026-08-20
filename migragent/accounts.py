"""Who somebody is, when they choose to tell us.

WHY THERE WAS NO ACCOUNT UNTIL NOW
----------------------------------
A case has lived in a cookie since Build 2, deliberately: the weakest possible
link between a person and their data, guessable by nobody, recoverable by nobody,
gone when the retention window closes. That is a good property for a guide
somebody reads once.

It is a bad property for a board. The board is the part that is supposed to still
be useful next month, and a board that evaporates when somebody opens their
laptop instead of their phone is not.

WHAT AN ACCOUNT CHANGES, AND WHAT IT DOES NOT
---------------------------------------------
It changes one thing: a case can be found again from another browser. It does not
change what is stored, how long it is kept, or the delete path. A signed-in
person's data is the same rows with a `uid` on them, the retention window still
applies, and `delete` still empties every collection.

Signing in is never required. Everything works without an account, exactly as it
did, because somebody researching whether they can leave their country should not
have to create a login to find out.

HOW A TOKEN IS CHECKED
----------------------
The browser signs in with Firebase and sends the ID token. This verifies it
against Google's published keys, checks the audience is this project, and takes
the `sub` claim as the person's id. Nothing else in the token is trusted, and the
token is never stored.

A rejected token is treated as no token rather than as an error. The product
works signed out, so a stale token means the person is signed out, not that the
page is broken.
"""
from __future__ import annotations

from typing import Any

from google.cloud import firestore

# Firebase mints tokens whose audience is the project id and whose issuer is
# securetoken.google.com. `verify_firebase_token` knows both, so nothing here has
# to hand-roll JWT checking, which is the kind of code that is wrong in a way
# nobody notices for a year.
_CLOCK_SKEW_SECONDS = 30


def uid_from_token(id_token: str, project: str) -> str | None:
    """The person's id, or None if the token is missing, stale or not ours."""
    if not id_token:
        return None

    import google.auth.transport.requests
    from google.oauth2 import id_token as google_id_token

    try:
        claims = google_id_token.verify_firebase_token(
            id_token, google.auth.transport.requests.Request(), audience=project,
            clock_skew_in_seconds=_CLOCK_SKEW_SECONDS)
    except Exception:  # noqa: BLE001
        # Expired, forged, or issued for another project. All the same answer to
        # this product: nobody is signed in.
        return None

    if not claims:
        return None
    return claims.get("sub") or claims.get("user_id") or None


class People:
    """Which cases belong to which signed-in person.

    A thin table on purpose. The case is still the thing that holds the data, and
    this only says who may open it, so signing out or never signing in leaves
    every other part of the product working exactly as before.
    """

    COLLECTION = "case_owners"

    def __init__(self, client: firestore.Client) -> None:
        self._db = client

    def claim(self, uid: str, case_id: str) -> None:
        """Attach a case to a person.

        Called when somebody signs in while holding a case cookie. The case they
        were already working on becomes theirs, so signing in never costs them
        the work that made them sign in.
        """
        if not uid or not case_id:
            return
        self._db.collection(self.COLLECTION).document(case_id).set(
            {"uid": uid, "case_id": case_id}, merge=True)

    def cases_for(self, uid: str, limit: int = 10) -> list[str]:
        if not uid:
            return []
        query = (self._db.collection(self.COLLECTION)
                 .where(filter=firestore.FieldFilter("uid", "==", uid))
                 .limit(limit))
        return [doc.to_dict().get("case_id", "") for doc in query.stream()]

    def owns(self, uid: str, case_id: str) -> bool:
        if not uid or not case_id:
            return False
        snap = self._db.collection(self.COLLECTION).document(case_id).get()
        return bool(snap.exists and snap.to_dict().get("uid") == uid)

    def release(self, case_id: str) -> None:
        """Forget who owned a case. Called from the delete path."""
        self._db.collection(self.COLLECTION).document(case_id).delete()


def config_for(project: str, api_key: str, auth_domain: str) -> dict[str, Any]:
    """What the browser needs to sign somebody in.

    The API key is not a secret and is not treated as one: it identifies the
    project to Firebase and every Firebase web app ships it in its HTML. What
    protects the data is the token check above and the Firestore rules, not this
    string being hidden.
    """
    return {"apiKey": api_key, "authDomain": auth_domain, "projectId": project}
