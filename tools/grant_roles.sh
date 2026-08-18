#!/usr/bin/env bash
# Least privilege roles for the four MIGRAGENT workers.
#
# Idempotent: gcloud add-iam-policy-binding is a no-op if the binding is already
# there, so this can be re-run after any change.
#
# The point of this file is that the permission model is readable in one place
# rather than being whatever somebody clicked in a console. Every role below has
# a reason next to it, and anything not listed is deliberately absent.
#
#   bash tools/grant_roles.sh
set -euo pipefail

PROJECT="project-e0928f2f-5abf-46a3-b8a"
SA_SUFFIX="@${PROJECT}.iam.gserviceaccount.com"

RESEARCHER="migragent-researcher${SA_SUFFIX}"
WRITER="migragent-writer${SA_SUFFIX}"
WATCHER="migragent-watcher${SA_SUFFIX}"
WEB="migragent-web${SA_SUFFIX}"

grant() {
  local member="$1" role="$2"
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${member}" --role="$role" \
    --condition=None --quiet >/dev/null
  echo "  ${role}"
}

echo "researcher: reads sources, extracts requirements, writes NOTHING a user reads"
# Gemini, for extraction.
grant "$RESEARCHER" roles/aiplatform.user
# Read the source registry. VIEWER, not user. This is the whole point: a bad
# extraction cannot become a published guide because the researcher physically
# cannot write one. tools/test_isolation.py proves it.
grant "$RESEARCHER" roles/datastore.viewer
# Write raw page snapshots. Creator only, so it can add a snapshot and cannot
# read back or delete the ones already there.
grant "$RESEARCHER" roles/storage.objectCreator
grant "$RESEARCHER" roles/logging.logWriter

echo "writer: the only identity that may publish a guide"
grant "$WRITER" roles/aiplatform.user
grant "$WRITER" roles/datastore.user
grant "$WRITER" roles/logging.logWriter

echo "watcher: re-reads sources on a schedule and records what moved"
grant "$WATCHER" roles/aiplatform.user
grant "$WATCHER" roles/datastore.user
# Needs to read yesterday's snapshot to diff against today's, so admin rather
# than creator.
grant "$WATCHER" roles/storage.objectAdmin
grant "$WATCHER" roles/pubsub.subscriber
grant "$WATCHER" roles/logging.logWriter

echo "web: takes intake, serves guides"
grant "$WEB" roles/datastore.user
grant "$WEB" roles/logging.logWriter

echo "web may mint tokens for the researcher and the writer, and nothing else"
for TARGET in "$RESEARCHER" "$WRITER"; do
  gcloud iam service-accounts add-iam-policy-binding "$TARGET" \
    --member="serviceAccount:${WEB}" \
    --role="roles/iam.serviceAccountTokenCreator" --quiet >/dev/null
  echo "  ${TARGET}"
done

echo
echo "Deliberately absent, and each absence is the point:"
echo "  researcher has no datastore.user      a bad extraction cannot publish itself"
echo "  researcher has no storage read        it cannot see or alter earlier snapshots"
echo "  web has no aiplatform.user            a request handler cannot call a model directly"
echo "  web cannot impersonate the watcher    a web request cannot trigger a crawl round"
echo "  nothing holds roles/editor            new projects no longer grant it and we do not want it"
