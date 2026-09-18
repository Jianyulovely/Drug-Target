#!/usr/bin/env bash
# Read-only status check for the formal DrugBAN queue.  It deliberately never
# starts, stops, signals or modifies remote processes/files.  In particular,
# live worker progress is resolved from each process' dataset/scenario/seed/fold
# arguments, so historical epoch logs cannot be mistaken for live work.
set -euo pipefail

REMOTE_HOST="aspect"
REMOTE_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
REMOTE_PYTHON="/mnt/sda/fulaiyi/aspect_env/bin/python"

usage() {
    cat <<'EOF'
Usage: monitor_drugban_readonly.sh [options]

Read the formal DrugBAN queue without changing the remote host.  The output
reports live queue/worker/watcher processes, GPU use, formal JSON coverage,
each live worker's own epoch log and the failure-list tail.

Options:
  --remote-host HOST      SSH host or configured alias (default: aspect)
  --remote-root PATH      Remote paper-project root
  --remote-python PATH    Remote Python interpreter
  -h, --help              Show this help

The script is intentionally a single read-only snapshot.  Run it on the
agreed 30-minute monitoring cadence; do not use its output to justify a
restart without separately verifying the failure and recovery evidence.
EOF
}

while (($#)); do
    case "$1" in
        --remote-host) REMOTE_HOST="$2"; shift 2 ;;
        --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
        --remote-python) REMOTE_PYTHON="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

command -v ssh >/dev/null 2>&1 || {
    echo "Required command is unavailable: ssh" >&2
    exit 127
}

ssh "$REMOTE_HOST" bash -s -- "$REMOTE_ROOT" "$REMOTE_PYTHON" <<'REMOTE'
set -euo pipefail
root="$1"
python_bin="$2"

printf 'REMOTE '
date '+%Y-%m-%d %H:%M:%S %z'

printf '\n== LIVE QUEUE / WORKERS / WATCHER ==\n'
ps -eo pid,ppid,stat,etime,pcpu,args |
    awk 'NR == 1 || /run_drugban_queue\.sh|run_drugban_fold\.py|postprocess_after_drugban\.sh/' |
    head -40

printf '\n== LIVE-WORKER EPOCHS (PROCESS-MATCHED) ==\n'
worker_lines="$({ ps -eo pid=,args= | grep '[r]un_drugban_fold.py' || true; } | sed -E 's/^[[:space:]]+//')"
active_task_logs=()
snapshot_epoch="$(date +%s)"
stale_log_threshold=900
if [[ -z "$worker_lines" ]]; then
    echo 'NO_LIVE_DRUGBAN_WORKERS'
else
    while IFS= read -r worker_line; do
        pid="${worker_line%% *}"
        args="${worker_line#* }"
        dataset="$(sed -n 's/.*--dataset \([^ ]*\).*/\1/p' <<<"$args")"
        scenario="$(sed -n 's/.*--scenario \([^ ]*\).*/\1/p' <<<"$args")"
        seed="$(sed -n 's/.*--seed \([^ ]*\).*/\1/p' <<<"$args")"
        fold="$(sed -n 's/.*--fold \([^ ]*\).*/\1/p' <<<"$args")"
        log_path="$root/logs/drugban_${dataset}_${scenario}_seed${seed}_fold${fold}.log"
        if [[ -f "$log_path" ]]; then
            active_task_logs+=("$log_path")
            mtime="$(stat -c '%y' "$log_path")"
            log_epoch="$(stat -c '%Y' "$log_path")"
            log_age="$((snapshot_epoch - log_epoch))"
            epoch_line="$(grep -E '\[DrugBAN\].*epoch=' "$log_path" | tail -1 || true)"
            if (( log_age > stale_log_threshold )); then
                log_status='STALE_LOG_NO_RESTART'
            else
                log_status='FRESH_LOG'
            fi
            printf 'PID=%s dataset=%s scenario=%s seed=%s fold=%s log_mtime=%s log_age_s=%s %s\n' \
                "$pid" "$dataset" "$scenario" "$seed" "$fold" "$mtime" "$log_age" "$log_status"
            if [[ -n "$epoch_line" ]]; then
                printf '  %s\n' "$epoch_line"
            else
                echo '  NO_EPOCH_LINE_YET'
            fi
        else
            printf 'PID=%s dataset=%s scenario=%s seed=%s fold=%s LOG_MISSING=%s\n' \
                "$pid" "$dataset" "$scenario" "$seed" "$fold" "$log_path"
        fi
    done <<<"$worker_lines"
fi

printf '\n== RECENT WORKER/TASK ERRORS (READ-ONLY TAIL SCAN) ==\n'
error_found=0
for log_path in "$root"/logs/drugban_workers/worker_*.log "${active_task_logs[@]}"; do
    [[ -f "$log_path" ]] || continue
    matches="$(tail -200 "$log_path" | grep -Eiw 'error|traceback|exception|failed|out[[:space:]]+of[[:space:]]+memory|cuda.*(error|out|oom)' || true)"
    if [[ -n "$matches" ]]; then
        printf -- '--- %s ---\n' "$log_path"
        printf '%s\n' "$matches"
        error_found=1
    fi
done
if (( error_found == 0 )); then
    echo 'NO_RECENT_MATCHED_ERRORS'
fi

printf '\n== RELEASE WATCHER ORDER (READ-ONLY) ==\n'
watcher_path="$root/postprocess_after_drugban.sh"
if [[ -f "$watcher_path" ]]; then
    sha256sum "$watcher_path"
    split_line="$(grep -n 'verify_split_integrity\.py' "$watcher_path" | head -1 | cut -d: -f1 || true)"
    coverage_line="$(grep -n 'verify_paper_coverage\.py' "$watcher_path" | head -1 | cut -d: -f1 || true)"
    if [[ -n "$split_line" && -n "$coverage_line" ]]; then
        printf 'split_integrity_line=%s coverage_line=%s\n' "$split_line" "$coverage_line"
        if (( split_line < coverage_line )); then
            echo 'WATCHER_SPLIT_FIRST'
        else
            echo 'WATCHER_COVERAGE_FIRST_INDEPENDENT_SPLIT_REQUIRED'
        fi
    else
        echo 'WATCHER_ORDER_UNRESOLVED'
    fi
else
    echo "WATCHER_MISSING=$watcher_path"
fi

printf '\n== GPU ==\n'
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total \
    --format=csv,noheader,nounits

printf '\n== GPU COMPUTE PROCESSES (READ-ONLY) ==\n'
# Keep this separate from the aggregate GPU line so an unrelated service
# occupying a card cannot be mistaken for a DrugBAN worker or hidden by the
# worker-process filter above.
nvidia-smi pmon -c 1 -s um 2>/dev/null || true

printf '\n== FORMAL COVERAGE ==\n'
"$python_bin" - "$root" <<'PYCODE'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
datasets = ("biosnap", "human", "bindingdb")
scenarios = ("random", "cold_drug", "cold_protein", "cold_pair")
counts = {(dataset, scenario): 0 for dataset in datasets for scenario in scenarios}
identities = set()
scenario_map = {
    "random": "random",
    "colddrug": "cold_drug",
    "coldprotein": "cold_protein",
    "coldpair": "cold_pair",
}

def normalize(value):
    return re.sub(r"[-_]", "", str(value).lower())

for path in (root / "results").rglob("*.json"):
    try:
        result = json.loads(path.read_text())
    except Exception:
        continue
    settings = result.get("settings") or {}
    if (
        result.get("method") != "drugban"
        or
        result.get("pipeline_version") != "paper-benchmark-v2"
        or settings.get("epochs") != 100
        or settings.get("input_cache") is not True
        or settings.get("tf32") is not True
    ):
        continue
    dataset = normalize(result.get("dataset"))
    scenario = scenario_map.get(normalize(result.get("scenario")))
    seed = result.get("seed")
    fold = result.get("fold")
    if (
        dataset in datasets
        and scenario in scenarios
        and isinstance(seed, int)
        and fold in range(5)
    ):
        identity = (dataset, scenario, seed, fold)
        if identity not in identities:
            identities.add(identity)
            counts[(dataset, scenario)] += 1

print("TOTAL", sum(counts.values()))
for dataset in datasets:
    values = " ".join(f"{scenario}={counts[(dataset, scenario)]}" for scenario in scenarios)
    total = sum(counts[(dataset, scenario)] for scenario in scenarios)
    print(f"{dataset} {values} sum={total}")
PYCODE

printf '\n== FAILURE LIST ==\n'
if [[ -s "$root/logs/drugban_failed_tasks.txt" ]]; then
    tail -30 "$root/logs/drugban_failed_tasks.txt"
else
    echo 'EMPTY_OR_MISSING'
fi

printf '\n== QUEUE LOG TAIL ==\n'
tail -15 "$root/logs/drugban_queue_tf32_20260828T013000+0800.log"
REMOTE
