#!/usr/bin/env bash
# The weekly guides: evergreen pages rewritten when their requirements change.
#
#   bash tools/schedule_guides.sh
#
# WHY SUNDAY 06:10 UTC. After a week of morning rounds, and after that morning's
# articles, so a guide is rewritten from the freshest requirements. Weekly is
# enough: a guide explains a whole route, and the wire already reports the day
# something on it changes.
#
# WHY IT IS CHEAP. Each guide carries a fingerprint of the requirements it was
# written from. If none changed, the guide is not rewritten and costs nothing.
#
# WHY ONE TASK. It reads the requirement corpus once and writes guides one at a
# time, paced, so ten tasks would only race each other.
set -euo pipefail

PROJECT="project-e0928f2f-5abf-46a3-b8a"
REGION="us-central1"
JOB="migragent-ingest"
SCHEDULER_JOB="migragent-weekly-guides"

# The principal that starts the other daily jobs: it may start this job and
# nothing else. Created by tools/schedule_watch.sh.
RUNNER="migragent-scheduler@${PROJECT}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$RUNNER" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create migragent-scheduler --project "$PROJECT" \
    --display-name "Starts the daily watch round and nothing else"
fi

gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${RUNNER}" --role roles/run.invoker --quiet
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${RUNNER}" --role roles/run.jobsExecutorWithOverrides --quiet

URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run"
BODY='{"overrides":{"containerOverrides":[{"env":[{"name":"MIGRAGENT_MODE","value":"guides"}]}],"taskCount":1}}'

if gcloud scheduler jobs describe "$SCHEDULER_JOB" --project "$PROJECT" \
     --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "10 6 * * 0" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --update-headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s --quiet
  echo "updated $SCHEDULER_JOB"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "10 6 * * 0" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s \
    --description "Rewrite evergreen guides whose requirements changed" --quiet
  echo "created $SCHEDULER_JOB"
fi

echo
echo "To run it now rather than wait for Sunday 06:10 UTC:"
echo "  gcloud scheduler jobs run $SCHEDULER_JOB --location $REGION --project $PROJECT"
