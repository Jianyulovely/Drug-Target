#!/usr/bin/env bash
# Regression coverage for postprocess_after_drugban.sh.  It uses a definitely
# absent queue PID, so no wait or real remote workload is involved.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="$SCRIPT_DIR/postprocess_after_drugban.sh"
FAKE_PYTHON="$SCRIPT_DIR/test_postprocess_fake_python.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dti-postprocess-gate.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT

require() {
    if ! "$@"; then
        echo "TEST_FAILURE: expected command to succeed: $*" >&2
        exit 1
    fi
}

stop_process() {
    local pid="$1"
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}

make_root() {
    local root="$1"
    mkdir -p "$root/logs"
    printf '999999\n' > "$root/logs/queue.pid"
    : > "$root/logs/drugban_failed_tasks.txt"
}

success_root="$TEST_ROOT/success"
make_root "$success_root"
success_calls="$TEST_ROOT/success.calls"
: > "$success_calls"
POSTPROCESS_CALL_LOG="$success_calls" \
    bash "$GATE" --root "$success_root" --python "$FAKE_PYTHON" \
    --queue-pid-file "$success_root/logs/queue.pid" --poll-seconds 1 \
    > "$TEST_ROOT/success.log" 2>&1

expected_calls=(
    verify_split_integrity.py
    verify_paper_coverage.py
    final_paper_audit.py
    write_dataset_manifest.py
    write_environment_manifest.py
    paper_benchmark.py
    plot_paper_results.py
    final_paper_audit.py
    generate_manuscript_results.py
)
observed_calls=()
while IFS= read -r call || [[ -n "$call" ]]; do
    observed_calls+=("$call")
done < "$success_calls"
if [[ "${observed_calls[*]}" != "${expected_calls[*]}" ]]; then
    echo "TEST_FAILURE: unexpected successful post-processing command order" >&2
    printf 'Observed: %s\n' "${observed_calls[*]}" >&2
    printf 'Expected: %s\n' "${expected_calls[*]}" >&2
    exit 1
fi
require grep -Fq 'POSTPROCESSING_RELEASE_COMPLETE' "$TEST_ROOT/success.log"

failure_root="$TEST_ROOT/failure"
make_root "$failure_root"
printf 'biosnap,cold_drug,123,0,worker=0,status=1\n' > "$failure_root/logs/drugban_failed_tasks.txt"
failure_calls="$TEST_ROOT/failure.calls"
: > "$failure_calls"
if POSTPROCESS_CALL_LOG="$failure_calls" \
    bash "$GATE" --root "$failure_root" --python "$FAKE_PYTHON" \
    --queue-pid-file "$failure_root/logs/queue.pid" --poll-seconds 1 \
    > "$TEST_ROOT/failure.log" 2>&1; then
    echo 'TEST_FAILURE: non-empty failure list was accepted' >&2
    exit 1
fi
require grep -Fq 'failure list is non-empty' "$TEST_ROOT/failure.log"
if [[ -s "$failure_calls" ]]; then
    echo 'TEST_FAILURE: failed release invoked post-processing commands' >&2
    exit 1
fi

marker_root="$TEST_ROOT/missing_marker"
make_root "$marker_root"
marker_calls="$TEST_ROOT/missing_marker.calls"
: > "$marker_calls"
if POSTPROCESS_CALL_LOG="$marker_calls" POSTPROCESS_SUPPRESS_MARKER=1 \
    bash "$GATE" --root "$marker_root" --python "$FAKE_PYTHON" \
    --queue-pid-file "$marker_root/logs/queue.pid" --poll-seconds 1 \
    > "$TEST_ROOT/missing_marker.log" 2>&1; then
    echo 'TEST_FAILURE: missing audit marker was accepted' >&2
    exit 1
fi
require grep -Fq 'without required marker: SPLIT_INTEGRITY_COMPLETE' "$TEST_ROOT/missing_marker.log"
if [[ "$(cat "$marker_calls")" != "verify_split_integrity.py" ]]; then
    echo 'TEST_FAILURE: missing-marker path continued past the first audit' >&2
    cat "$marker_calls" >&2
    exit 1
fi

queue_root="$TEST_ROOT/queue_remains"
make_root "$queue_root"
queue_cmd="run_drugban_queue.sh"
bash -c "exec -a $queue_cmd /bin/sleep 1" >/dev/null 2>&1 & tracked_queue="$!"
bash -c "exec -a $queue_cmd /bin/sleep 30" >/dev/null 2>&1 & queue_process="$!"
printf '%s\n' "$tracked_queue" > "$queue_root/logs/queue.pid"
if POSTPROCESS_CALL_LOG="$TEST_ROOT/queue.calls" \
    bash "$GATE" --root "$queue_root" --python "$FAKE_PYTHON" \
    --queue-pid-file "$queue_root/logs/queue.pid" --poll-seconds 1 \
    > "$TEST_ROOT/queue.log" 2>&1; then
    stop_process "$queue_process"
    stop_process "$tracked_queue"
    echo 'TEST_FAILURE: remaining queue process was accepted' >&2
    exit 1
fi
stop_process "$queue_process"
stop_process "$tracked_queue"
require grep -Fq 'queue process remains' "$TEST_ROOT/queue.log"
if [[ -s "$TEST_ROOT/queue.calls" ]]; then
    echo 'TEST_FAILURE: remaining queue process invoked post-processing commands' >&2
    exit 1
fi

echo 'POSTPROCESS_GATE_REGRESSION_PASS'
