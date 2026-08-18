#!/usr/bin/env bash
# The retention sweep, on a schedule.
#
# This exists so the schedule is in the repo rather than being something
# somebody once clicked. docs/DATA_PROTECTION.md promises a 30 day window, and a
# promise enforced by a cron job nobody can find is barely enforced at all.
#
# The token is generated once and kept outside the repo. It is a second lock:
# Cloud Run can also be set to require an authenticated invoker, and the header
# check means a leaked URL alone is not enough.
#
#   bash tools/schedule_sweep.sh
set -euo pipefail

REGION="us-central1"
JOB="migragent-retention-sweep"
SECRETS="${MIGRAGENT_SECRETS:-$HOME/MIGRAGENT_SECRETS}"
TOKEN_FILE="$SECRETS/task-token.txt"

if [ ! -f "$TOKEN_FILE" ]; then
  mkdir -p "$SECRETS"
  python -c "import secrets;print(secrets.token_urlsafe(32))" > "$TOKEN_FILE"
  echo "generated a new task token at $TOKEN_FILE"
  echo "redeploy with MIGRAGENT_TASK_TOKEN set to it before this job will work"
fi
TOKEN="$(cat "$TOKEN_FILE")"

URL="$(gcloud run services describe migragent --region "$REGION" \
        --format='value(status.url)')/tasks/sweep"

# 03:17 rather than 03:00, because everything in the world runs on the hour.
if gcloud scheduler jobs describe "$JOB" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB" --location "$REGION" \
    --schedule "17 3 * * *" --time-zone "Etc/UTC" --uri "$URL" \
    --http-method POST --update-headers "X-Migragent-Task=$TOKEN" \
    --attempt-deadline 300s --quiet
  echo "updated $JOB"
else
  gcloud scheduler jobs create http "$JOB" --location "$REGION" \
    --schedule "17 3 * * *" --time-zone "Etc/UTC" --uri "$URL" \
    --http-method POST --headers "X-Migragent-Task=$TOKEN" \
    --attempt-deadline 300s \
    --description "Delete cases past their 30 day retention window" --quiet
  echo "created $JOB"
fi

echo
echo "A job showing ENABLED only proves a row exists. To prove it arrives:"
echo "  gcloud scheduler jobs run $JOB --location $REGION"
echo "  gcloud logging read 'httpRequest.requestUrl:\"/tasks/sweep\" AND httpRequest.userAgent:\"Google-Cloud-Scheduler\"' --limit 3 --freshness=10m"
