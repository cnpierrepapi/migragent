#!/usr/bin/env bash
# Watch the school ingestion without asking anybody.
#
#   bash tools/progress.sh          # refreshes every 20 seconds
#   bash tools/progress.sh 5        # every 5 seconds
#   bash tools/progress.sh once     # print once and exit
#
# Reads the log files rather than the database, so it costs nothing and cannot
# slow the run down. The database counts are the slow part, so they refresh
# every fifth pass rather than every pass.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

EVERY="${1:-20}"
ONCE=0
[ "$EVERY" = "once" ] && { ONCE=1; EVERY=1; }

DEEP_QUEUE=330      # schools with a course index, from the shallow pass

count_schools() {
  # Each school starts a block like "  University of Manchester  (UK)".
  grep -cE '^  [^ ].*\((CA|UK)\)$' out/deep_wide.log 2>/dev/null || echo 0
}

bar() {  # bar <done> <total> <width>
  local d=$1 t=$2 w=$3 filled
  [ "$t" -eq 0 ] && t=1
  filled=$(( d * w / t ))
  printf '['
  printf '%0.s#' $(seq 1 $filled) 2>/dev/null
  printf '%0.s.' $(seq 1 $(( w - filled ))) 2>/dev/null
  printf '] %d/%d (%d%%)' "$d" "$t" $(( d * 100 / t ))
}

pass=0
while true; do
  pass=$(( pass + 1 ))
  [ "$ONCE" -eq 0 ] && clear

  echo "MIGRAGENT school ingestion  ·  $(date '+%H:%M:%S')"
  echo "------------------------------------------------------------"

  # --- stage 1, shallow -------------------------------------------------
  if grep -q '^shallow:' out/shallow_wide.log 2>/dev/null; then
    echo "shallow   DONE   $(grep '^shallow:' out/shallow_wide.log)"
  else
    echo "shallow   $(tail -1 out/shallow_wide.log 2>/dev/null | tr -s ' ' | cut -c1-60)"
  fi

  # --- stage 2, deep ----------------------------------------------------
  if grep -q '=== deep finished' out/deep_wide.log 2>/dev/null; then
    echo "deep      DONE   $(grep -E '^deep:' out/deep_wide.log | tail -1)"
  elif [ -f out/deep_wide.log ]; then
    printf 'deep      '; bar "$(count_schools)" "$DEEP_QUEUE" 28; echo
    echo "          $(grep -E '^  [^ ].*\((CA|UK)\)$' out/deep_wide.log 2>/dev/null | tail -1 | sed 's/^ *//' | cut -c1-52)"
  else
    echo "deep      queued"
  fi

  # --- stage 3, details -------------------------------------------------
  if grep -q '=== ALL DONE' out/deep_wide.log 2>/dev/null; then
    echo "details   DONE   $(grep -E '^details:' out/deep_wide.log | tail -1)"
  elif grep -q '=== deep finished' out/deep_wide.log 2>/dev/null; then
    echo "details   running"
  else
    echo "details   queued"
  fi

  # --- the database, every fifth pass ----------------------------------
  if [ $(( pass % 5 )) -eq 1 ]; then
    echo "------------------------------------------------------------"
    python - <<'PY' 2>/dev/null || echo "  (database unreachable this pass)"
import sys, collections
sys.path.insert(0, ".")
from google.cloud import firestore
from migragent import identity
P = "project-e0928f2f-5abf-46a3-b8a"
db = firestore.Client(project=P, credentials=identity.credentials_for(identity.WEB, P))
rows = [d.to_dict() for d in db.collection("courses").stream()]
by = collections.Counter(r.get("jurisdiction") for r in rows)
print(f"  courses {len(rows):>5}   schools {len({r.get('institution') for r in rows}):>4}"
      f"   CA {by.get('CA',0):>4}  UK {by.get('UK',0):>4}")
print(f"  fees    {sum(1 for r in rows if r.get('fee_amount')):>5}"
      f"   intakes {sum(1 for r in rows if r.get('intake')):>4}"
      f"   entry {sum(1 for r in rows if r.get('entry_requirements')):>6}")
PY
  fi

  echo "------------------------------------------------------------"
  if grep -q '=== ALL DONE' out/deep_wide.log 2>/dev/null; then
    echo "ALL DONE"
    exit 0
  fi
  [ "$ONCE" -eq 1 ] && exit 0
  echo "refreshing every ${EVERY}s   ·   ctrl-c to stop"
  sleep "$EVERY"
done
