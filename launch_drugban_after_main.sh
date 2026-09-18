#!/usr/bin/env bash
# Wait for the chunked-GCN recovery queue, verify its result artifacts, then
# start DrugBAN.  It deliberately does not launch DrugBAN after a failed or
# partial main-method run.
set -euo pipefail

PROJECT_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
PYTHON_BIN="/mnt/sda/fulaiyi/aspect_env/bin/python"
MAIN_PID_FILE="$PROJECT_ROOT/logs/resume_chunked_gcn_20260827.pid"
MAIN_PID="$(cat "$MAIN_PID_FILE")"
MAIN_METHODS="lr,mlp,gcn,colddti,arnoldi_v4,arnoldi_s1,arnoldi_s2,arnoldi_s12,arnoldi_s12_shuffle"

mkdir -p "$PROJECT_ROOT/logs"
while kill -0 "$MAIN_PID" 2>/dev/null; do
    printf '[%s] Waiting for chunked main queue PID=%s\n' "$(date -Is)" "$MAIN_PID" >> "$PROJECT_ROOT/logs/drugban_launcher.log"
    sleep 300
done

if [[ -s "$PROJECT_ROOT/logs/resume_failed_tasks.txt" ]]; then
    printf '[%s] Main queue has failed tasks; DrugBAN will not start.\n' "$(date -Is)" >> "$PROJECT_ROOT/logs/drugban_launcher.log"
    exit 1
fi

if ! "$PYTHON_BIN" "$PROJECT_ROOT/verify_paper_coverage.py" \
    --root "$PROJECT_ROOT" --methods "$MAIN_METHODS" --expected-per-group 15 \
    >> "$PROJECT_ROOT/logs/drugban_launcher.log" 2>&1; then
    printf '[%s] Main coverage verification failed; DrugBAN will not start.\n' "$(date -Is)" >> "$PROJECT_ROOT/logs/drugban_launcher.log"
    exit 1
fi

printf '[%s] Main coverage verified; starting DrugBAN queue.\n' "$(date -Is)" >> "$PROJECT_ROOT/logs/drugban_launcher.log"
exec /bin/bash "$PROJECT_ROOT/run_drugban_queue.sh"
