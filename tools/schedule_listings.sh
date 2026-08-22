#!/usr/bin/env bash
# The daily digest: turning what the watch round found into what people are told.
#
#   bash tools/schedule_digest.sh
#
# WHY 05:00 UTC, twenty minutes after the watch round and twenty before the
# digest. The order is the whole point: the watch reads government pages, this
# asks the boards what went up, and only then does the digest tell people what
# is new. Run the digest first and it reports on yesterday's board. The watch round took 220
# seconds across ten parallel tasks on 19 August 2026 and has no reason to grow
# by an order of magnitude, so forty minutes is a wide margin rather than a
# guess. If it ever overruns, the digest reads a corpus that is one day behind
# and tells people about yesterday's changes tomorrow; it does not tell them
# anything untrue, and the next run catches up. That is the failure mode we
# want from a scheduling collision.
#
# WHY ONE TASK. One board, one host, one polite request at a time. Ten tasks
# would be ten crawlers on somebody's national employment service.
#
# WHY IT IS SAFE TO RUN DAILY, AND TWICE. Listings.record keeps first_seen_at
# off the merge payload, so a posting seen yesterday keeps yesterday's date and
# only a genuinely new row looks new to the digest. Running twice writes the same
# rows and creates no false "posted today".
#
# WHAT IT FIXES. The digest has always been able to say "a job you qualify for
# was posted", and nothing was ever adding jobs: the corpus was seeded by hand in
# August and sat still. Every alert of that kind that could fire had already
# fired. This is the half of that promise that was missing.
set -euo pipefail

PROJECT="project-e0928f2f-5abf-46a3-b8a"
REGION="us-central1"
JOB="migragent-ingest"
SCHEDULER_JOB="migragent-daily-listings"

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
BODY='{"overrides":{"containerOverrides":[{"env":[{"name":"MIGRAGENT_MODE","value":"listings"}]}],"taskCount":1}}'

if gcloud scheduler jobs describe "$SCHEDULER_JOB" --project "$PROJECT" \
     --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "00 5 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --update-headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s --quiet
  echo "updated $SCHEDULER_JOB"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "00 5 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s \
    --description "Ask the government job boards what went up overnight" --quiet
  echo "created $SCHEDULER_JOB"
fi

echo
echo "A job showing ENABLED only proves a row exists. To prove it arrives:"
echo "  gcloud scheduler jobs run $SCHEDULER_JOB --location $REGION --project $PROJECT"
echo "  gcloud run jobs executions list --job $JOB --region $REGION --project $PROJECT --limit 3"
