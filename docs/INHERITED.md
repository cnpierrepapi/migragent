# What came from the previous build, and why

MIGRAGENT is built in the same Google Cloud project as an earlier build, which was deleted on 18
August: the VM, both Cloud SQL instances, the Cloud Run service, its service accounts, its Pub/Sub
topic, its Firestore data and its DNS record are all gone. What follows is what was kept, and it was
kept because it is not specific to any domain.

## Working plumbing

- The Google Cloud project, billing, and the enabled APIs: Vertex AI, Cloud Run, Cloud Build,
  Artifact Registry, Firestore, Pub/Sub.
- A Cloud Run deploy path that works, including the build service account roles.

## Gotchas already paid for

These each cost real time to find and none of them are obvious.

- **Gemini 3.5 returns 404 in `us-central1`.** Every 3.5 model does. They resolve at
  `location="global"`, so model calls are pinned to a different location from everything else.
  `gemini-3.5-pro` was unavailable in both, so treat only Flash as reliable.
- **A new Google Cloud project's default compute service account has no roles at all.** Editor is no
  longer granted by default. This produced a 403 on the first Vertex call and again on the first
  Cloud Build. It needs `storage.objectUser`, `artifactregistry.writer` and `logging.logWriter` for
  builds to work.
- **Do not detect the ambient identity from the credential on Cloud Run.** `service_account_email`
  reads `default` until refreshed, so a self check silently fails and the service tries to
  impersonate itself, which hangs instead of erroring. State it in an environment variable.
- **`/healthz` never reaches a Cloud Run application.** Something in front claims the path. Use
  `/health`.
- **Firestore grants permissions per database, not per collection.** If two principals must be kept
  apart, they need separate databases and IAM conditions, not separate collections.
- **Avoid Firestore composite indexes.** Sort in Python instead, or a fresh clone returns a 400 on an
  index nobody created.
- **`gcloud compute ssh --command` mangles a command that starts with an absolute path** on Windows,
  rewriting it into a Windows path. `cd /somewhere && ./script` works.
- **Verify every file copy with a checksum.** A silent stale copy cost time twice.

## Rules carried over, which matter more here

- **No citation, no claim.** In the previous build this protected a data catalog. Here it protects
  somebody's savings and half a year of their life, so it is stricter: a requirement with no official
  source is not stated at all, it goes to open questions.
- **Never write a claim into a document before the test that proves it exists.** This was the real
  failure of the last build. The isolation claim was written into the docs as fact and was not true
  at the time, and it was read before it was tested.
- **A heuristic over names looks like understanding and is not.** A "decision" detector matched column
  names and reported survey answers as decisions about people. Derive from the source, and attach the
  line that proves it.
- **Never fake a record.** An agent run is never backdated. This directly shaped how change tracking
  works here.
