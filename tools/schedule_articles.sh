#!/usr/bin/env bash
# The daily articles: turning the morning's rule changes into the wire.
#
#   bash tools/schedule_articles.sh
#
# WHY 05:40 UTC. The watch round starts at 04:40 and writes the changes; the
# digest runs at 05:20 and tells watching cases. Articles come last, an hour
# after the round, so they read every change the round found. If the round ever
# overruns, an article is written the next morning instead, because the writer
# looks back two days and never writes the same change twice.
#
# WHY ONE TASK. The writer reads rows the round already wrote, groups changes
# that are the same news across several pages, and writes one article per group.
# Ten tasks would each read every change and race to write the same articles.
#
# WHY IT IS SAFE TO RUN TWICE. An article's id is derived from the change ids it
# covers. A second run finds the article already there and moves on, and a group
# that could not be published is recorded in article_skips with the reason, so
# it is not retried every morning either.
#
# WHAT IT COSTS. One model call per article, through Orbio when the $MIGRA
# balance can pay and through Vertex when it cannot. See migragent/orbio.py.
set -euo pipefail

PROJECT="project-e0928f2f-5abf-46a3-b8a"
REGION="us-central1"
JOB="migragent-ingest"
SCHEDULER_JOB="migragent-daily-articles"

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
BODY='{"overrides":{"containerOverrides":[{"env":[{"name":"MIGRAGENT_MODE","value":"articles"}]}],"taskCount":1}}'

if gcloud scheduler jobs describe "$SCHEDULER_JOB" --project "$PROJECT" \
     --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "40 5 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --update-headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s --quiet
  echo "updated $SCHEDULER_JOB"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" --project "$PROJECT" \
    --location "$REGION" --schedule "40 5 * * *" --time-zone "Etc/UTC" \
    --uri "$URI" --http-method POST --message-body "$BODY" \
    --headers "Content-Type=application/json" \
    --oauth-service-account-email "$RUNNER" --attempt-deadline 1800s \
    --description "Write up the morning's rule changes as articles, each with its report" --quiet
  echo "created $SCHEDULER_JOB"
fi

echo
echo "To run it now rather than wait for 05:40 UTC:"
echo "  gcloud scheduler jobs run $SCHEDULER_JOB --location $REGION --project $PROJECT"
