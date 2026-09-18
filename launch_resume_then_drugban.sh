#!/usr/bin/env bash
# Ensure B1-B4/ablation coverage is complete before beginning the expensive
# DrugBAN sequence.  This replaces the earlier wait-only launcher.
set -euo pipefail

PROJECT_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
MAIN_PID_FILE="/mnt/sda/fulaiyi/queue.pid"
MAIN_PID="$(cat "$MAIN_PID_FILE")"

mkdir -p "$PROJECT_ROOT/logs"
while kill -0 "$MAIN_PID" 2>/dev/null; do
    printf '[%s] Waiting for initial paper queue PID=%s\n' "$(date -Is)" "$MAIN_PID" \
        >> "$PROJECT_ROOT/logs/resume_then_drugban.log"
    sleep 60
done

printf '[%s] Initial queue stopped; resuming incomplete main-method folds.\n' "$(date -Is)" \
    >> "$PROJECT_ROOT/logs/resume_then_drugban.log"
/bin/bash "$PROJECT_ROOT/run_missing_paper_tasks.sh"

printf '[%s] Main-method coverage complete; starting DrugBAN queue.\n' "$(date -Is)" \
    >> "$PROJECT_ROOT/logs/resume_then_drugban.log"
exec /bin/bash "$PROJECT_ROOT/run_drugban_queue.sh"
