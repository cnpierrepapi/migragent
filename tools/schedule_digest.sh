#!/usr/bin/env bash
# The daily digest: turning what the watch round found into what people are told.
#
#   bash tools/schedule_digest.sh
#
# WHY 05:20 UTC, forty minutes after the watch round. The watch round took 220
# seconds across ten parallel tasks on 19 August 2026 and has no reason to grow
# by an order of magnitude, so forty minutes is a wide margin rather than a
# guess. If it ever overruns, the digest reads a corpus that is one day behind
# and tells people about yesterday's changes tomorrow; it does not tell them
# anything untrue, and the next run catches up. That is the failure mode we
# want from a scheduling collision.
#
# WHY ONE TASK. The digest reads rows the round already wrote and groups its own
# work by lane. Ten tasks would each have to read every watch to find out which
# ones were theirs.
#
# WHY IT IS SAFE TO RUN DAILY, AND TWICE. Every alert id is derived from the
# case and the thing that happened, so a second run writes the same documents
# rather than a second copy of them, and `seen_at` is kept off the merge payload
# so a re-run cannot mark something unread that somebody has already read.
set -euo pipefail

PROJECT="project-e0928f2f-5abf-46a3-b8a"
REGION="us-central1"
JOB="migragent-ingest"
SCHEDULER_JOB="migragent-daily-digest"

# The same principal that starts the watch round: it may start this job and may
# do nothing else at all. Created by tools/schedule_watch.sh, and created here
# too so either script works on a fresh project.
RUNNER="migragent-scheduler@${PROJECT}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$RUNNER" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create migragent-scheduler --project "$PROJECT" \
    --display-name "Starts the daily watch round and nothing else"
fi

gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${RUNNER}" --role roles/run.invoker --quiet

# Starting a job with an env override needs run.jobs.runWithOverrides, which
# run.invoker does not grant, and the request below carries one. See the long
# note in tools/schedule_watch.sh: the failure looks nothing like a missing
# permission.
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${RUNNER}" --role roles/run.jobsExecutorWithOverrides --quiet

URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run"

# One task, and it says so. The job's own task count is set for the ten lane
# round; without this override the digest would run ten identical times, and
# while the derived ids make that harmless it would still be nine pointless
# passes over every watch.
BODY='{"overrides":{"containerOverrides":[{"env":[{"name":"MIGRAGENT_MODE","value":"digest"}]}],"taskCount":1}}'

if gcloud scheduler jobs describe "$SCHEDULER_JOB" --project "$PROJECT" \
     --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "20 5 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --update-headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s --quiet
  echo "updated $SCHEDULER_JOB"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "20 5 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s \
    --description "Tell each watching case what moved for them overnight" --quiet
  echo "created $SCHEDULER_JOB"
fi

echo
echo "A job showing ENABLED only proves a row exists. To prove it arrives:"
echo "  gcloud scheduler jobs run $SCHEDULER_JOB --location $REGION --project $PROJECT"
echo "  gcloud run jobs executions list --job $JOB --region $REGION --project $PROJECT --limit 3"
