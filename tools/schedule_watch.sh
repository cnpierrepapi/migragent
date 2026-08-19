#!/usr/bin/env bash
# The daily watch round, on a schedule.
#
# The schedule lives in the repo rather than in somebody's console history, for
# the same reason the retention sweep does: a job nobody can find is a job
# nobody can check.
#
#   bash tools/schedule_watch.sh
#
# WHY 04:40 UTC. Late enough that European government sites have published
# whatever they publish overnight, early enough that a change is on the country
# watch screen before anybody in Europe or Africa starts their day. Not on the
# hour, because everything in the world runs on the hour.
#
# WHY IT IS SAFE TO RUN DAILY. Hash first stops a byte-identical page before
# anything is spent, and the text gate stops a page whose bytes moved and whose
# words did not. Measured on 19 August 2026: a watch round over 143 pages with
# nothing changed reported zero changes, made no model calls, and took 220
# seconds across ten parallel tasks.
set -euo pipefail

PROJECT="project-e0928f2f-5abf-46a3-b8a"
REGION="us-central1"
JOB="migragent-ingest"
SCHEDULER_JOB="migragent-daily-watch"

# Cloud Scheduler calls the Cloud Run Admin API to start the job. That needs an
# identity of its own, which is neither the watcher nor the web service: it may
# start the round and may do nothing else at all.
RUNNER="migragent-scheduler@${PROJECT}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$RUNNER" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create migragent-scheduler --project "$PROJECT" \
    --display-name "Starts the daily watch round and nothing else"
fi

gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${RUNNER}" --role roles/run.invoker --quiet

# Starting the job needs run.jobs.run, which run.invoker grants. Starting it
# with an env override needs run.jobs.runWithOverrides, which it does NOT, and
# the request below carries one: MIGRAGENT_MODE=watch, so the daily round
# watches rather than extracting.
#
# The failure looks nothing like a missing permission. Scheduler reports
# code=7 with a correct looking policy sitting in front of it naming the right
# principal and a role that really does contain run.jobs.run.
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${RUNNER}" --role roles/run.jobsExecutorWithOverrides --quiet

# The v2 endpoint, not the v1 namespaces one. v1 addresses the job as
# namespaces/PROJECT/jobs/NAME, which is not the resource the run.invoker
# binding is written against, so Scheduler got PERMISSION_DENIED with a correct
# looking policy in front of it. v2 addresses the same job by its real resource
# path and the binding applies.
URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run"

BODY='{"overrides":{"containerOverrides":[{"env":[{"name":"MIGRAGENT_MODE","value":"watch"}]}]}}'

if gcloud scheduler jobs describe "$SCHEDULER_JOB" --project "$PROJECT" \
     --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "40 4 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --update-headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s --quiet
  echo "updated $SCHEDULER_JOB"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "40 4 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s \
    --description "Re-read every watched source and record what moved" --quiet
  echo "created $SCHEDULER_JOB"
fi

echo
echo "A job showing ENABLED only proves a row exists. To prove it arrives:"
echo "  gcloud scheduler jobs run $SCHEDULER_JOB --location $REGION --project $PROJECT"
echo "  gcloud run jobs executions list --job $JOB --region $REGION --project $PROJECT --limit 3"
