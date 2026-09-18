#!/usr/bin/env bash
# Release-gated post-processing for the DrugBAN queue.  This script never
# starts, restarts, or overwrites a training task.  It waits for an existing
# queue to exit, then proceeds only if the complete, formal release passes all
# coverage and integrity gates.
set -euo pipefail

PROJECT_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
PYTHON_BIN="/mnt/sda/fulaiyi/aspect_env/bin/python"
QUEUE_PID_FILE=""
POLL_SECONDS=1800
# The benchmark imports its ArnoldiGCL core through this path. Preserve it in
# the release-time environment manifest so the external implementation can be
# identified by hash alongside the project scripts.
export DTI_CORE_PATH="${DTI_CORE_PATH:-/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py}"

usage() {
    cat <<'EOF'
Usage: postprocess_after_drugban.sh [options]

Wait for an already-running DrugBAN queue, then generate only audited release
artifacts.  The script exits without post-processing if the queue fails,
workers remain live, a failure list is non-empty, or any audit fails.

Options:
  --root PATH             Experiment root
  --python PATH           Python interpreter
  --queue-pid-file PATH   PID file for the already-running queue (required)
  --poll-seconds N        Queue-state polling interval (default: 1800)
  -h, --help              Show this message
EOF
}

while (($#)); do
    case "$1" in
        --root) PROJECT_ROOT="$2"; shift 2 ;;
        --python) PYTHON_BIN="$2"; shift 2 ;;
        --queue-pid-file) QUEUE_PID_FILE="$2"; shift 2 ;;
        --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$QUEUE_PID_FILE" || ! -r "$QUEUE_PID_FILE" ]]; then
    echo "A readable --queue-pid-file is required" >&2
    exit 2
fi
if ! [[ "$POLL_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
    echo "--poll-seconds must be a positive integer" >&2
    exit 2
fi

queue_pid="$(tr -d '[:space:]' < "$QUEUE_PID_FILE")"
if ! [[ "$queue_pid" =~ ^[1-9][0-9]*$ ]]; then
    echo "Queue PID file does not contain a valid PID: $QUEUE_PID_FILE" >&2
    exit 2
fi

queue_is_expected() {
    local command_line
    command_line="$(ps -p "$queue_pid" -o args= 2>/dev/null || true)"
    [[ "$command_line" == *"run_drugban_queue.sh"* ]]
}

if kill -0 "$queue_pid" 2>/dev/null && ! queue_is_expected; then
    echo "PID $queue_pid is live but is not the expected DrugBAN queue; refusing to wait" >&2
    exit 3
fi

while kill -0 "$queue_pid" 2>/dev/null; do
    if ! queue_is_expected; then
        echo "PID $queue_pid changed command while live; refusing to post-process" >&2
        exit 3
    fi
    printf '[%s] queue PID %s is still running; waiting %ss\n' "$(date -Is)" "$queue_pid" "$POLL_SECONDS"
    sleep "$POLL_SECONDS"
done

if pgrep -af 'run_drugban_fold\.py' >/dev/null; then
    echo "DrugBAN worker process(es) remain after queue exit; refusing to post-process" >&2
    pgrep -af 'run_drugban_fold\.py' >&2 || true
    exit 4
fi
if pgrep -af 'run_drugban_queue\.sh' >/dev/null; then
    echo "A DrugBAN queue process remains after the tracked queue exit; refusing to post-process" >&2
    pgrep -af 'run_drugban_queue\.sh' >&2 || true
    exit 4
fi

failure_log="$PROJECT_ROOT/logs/drugban_failed_tasks.txt"
if [[ -s "$failure_log" ]]; then
    echo "DrugBAN failure list is non-empty; refusing to post-process" >&2
    cat "$failure_log" >&2
    exit 5
fi

cd "$PROJECT_ROOT"
printf '[%s] Queue completed cleanly; starting release-gated post-processing\n' "$(date -Is)"

run_python_with_marker() {
    local marker="$1"
    shift
    local output
    if ! output="$("$PYTHON_BIN" "$@" 2>&1)"; then
        printf '%s\n' "$output"
        return 1
    fi
    printf '%s\n' "$output"
    if ! grep -Fq "$marker" <<<"$output"; then
        echo "Command completed without required marker: $marker" >&2
        return 1
    fi
}

run_python_with_marker "SPLIT_INTEGRITY_COMPLETE" \
    verify_split_integrity.py --root "$PROJECT_ROOT"
"$PYTHON_BIN" verify_paper_coverage.py \
    --root "$PROJECT_ROOT" --methods drugban --expected-per-group 15 \
    --require-drugban-epochs 100 --require-drugban-tf32
run_python_with_marker "FINAL_AUDIT_COMPLETE" \
    final_paper_audit.py --root "$PROJECT_ROOT"
"$PYTHON_BIN" write_dataset_manifest.py --data-dir /mnt/sda/fulaiyi/DTI_datasets \
    --output "$PROJECT_ROOT/source_data/dataset_manifest.json"
"$PYTHON_BIN" write_environment_manifest.py --root "$PROJECT_ROOT"
"$PYTHON_BIN" paper_benchmark.py --aggregate --root "$PROJECT_ROOT"
"$PYTHON_BIN" plot_paper_results.py --root "$PROJECT_ROOT" --expected-per-group 15
run_python_with_marker "FINAL_AUDIT_COMPLETE" \
    final_paper_audit.py --root "$PROJECT_ROOT" --require-artifacts \
    --require-runtime-manifest
"$PYTHON_BIN" generate_manuscript_results.py --root "$PROJECT_ROOT" \
    --manuscript-root "$PROJECT_ROOT/manuscript_generated"

printf '[%s] POSTPROCESSING_RELEASE_COMPLETE\n' "$(date -Is)"
