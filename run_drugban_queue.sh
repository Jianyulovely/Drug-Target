#!/usr/bin/env bash
# Run DrugBAN on the same 180 frozen folds used by the main paper benchmark.
# Completed 100-epoch result files are preserved, so an interrupted queue can
# resume without overwriting valid fold artifacts.
set -euo pipefail

PROJECT_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
PYTHON_BIN="/mnt/sda/fulaiyi/aspect_env/bin/python"
export DTI_CORE_PATH="/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py"
export PYTHONPATH="$PROJECT_ROOT/third_party/drugban${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONHASHSEED=0

datasets=(biosnap human bindingdb)
scenarios=(random cold_drug cold_protein cold_pair)
seeds=(1941488137 4198936517 983997847)
# GPU 0 is excluded from sparse-GCN work but passed a standalone DrugBAN
# forward/backward smoke test before being added to this independent queue.
gpus=(0 1 2 3)
# Keep the release configuration conservative by default.  A validated
# throughput run can raise this value without changing the model, data split,
# seed, epoch count, batch size, or result identity; virtual worker IDs still
# partition the 180 tasks exactly once.
workers_per_gpu="${DRUGBAN_WORKERS_PER_GPU:-1}"
if ! [[ "$workers_per_gpu" =~ ^[1-9][0-9]*$ ]]; then
    printf 'DRUGBAN_WORKERS_PER_GPU must be a positive integer, got: %s\n' "$workers_per_gpu" >&2
    exit 2
fi

mkdir -p "$PROJECT_ROOT/logs/drugban_workers"
failure_log="$PROJECT_ROOT/logs/drugban_failed_tasks.txt"
if [[ -s "$failure_log" ]]; then
    archive="$PROJECT_ROOT/logs/drugban_failed_tasks_$(date +%Y%m%dT%H%M%S%z).txt"
    cp -p "$failure_log" "$archive"
    printf '[%s] Archived previous failure list to %s\n' "$(date -Is)" "$archive" \
        >> "$PROJECT_ROOT/logs/drugban_queue.log"
fi
: > "$failure_log"

task_complete() {
    local dataset="$1" scenario="$2" seed="$3" fold="$4"
    local result="$PROJECT_ROOT/results/drugban/$dataset/$scenario/seed${seed}_fold${fold}.json"
    [[ -f "$result" ]] || return 1
    "$PYTHON_BIN" - "$result" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
ok = (
    value.get("pipeline_version") == "paper-benchmark-v2"
    and value.get("method") == "drugban"
    and value.get("settings", {}).get("epochs") == 100
    and value.get("settings", {}).get("input_cache") is True
    and value.get("settings", {}).get("tf32") is True
)
raise SystemExit(0 if ok else 1)
PY
}

run_worker() {
    local gpu="$1"
    local worker="$2"
    local total_workers="$3"
    local task_index=0
    local dataset scenario seed fold
    local worker_log="$PROJECT_ROOT/logs/drugban_workers/worker_${worker}.log"

    printf '[%s] worker=%s gpu=%s started\n' "$(date -Is)" "$worker" "$gpu" >> "$worker_log"
    for dataset in "${datasets[@]}"; do
        for scenario in "${scenarios[@]}"; do
            for seed in "${seeds[@]}"; do
                for fold in 0 1 2 3 4; do
                    if (( task_index % total_workers == worker )) && ! task_complete "$dataset" "$scenario" "$seed" "$fold"; then
                        local task_log="$PROJECT_ROOT/logs/drugban_${dataset}_${scenario}_seed${seed}_fold${fold}.log"
                        printf '[%s] START dataset=%s scenario=%s seed=%s fold=%s gpu=%s\n' \
                            "$(date -Is)" "$dataset" "$scenario" "$seed" "$fold" "$gpu" | tee -a "$worker_log"
                        set +e
                        "$PYTHON_BIN" "$PROJECT_ROOT/prepare_drugban_splits.py" \
                            --root "$PROJECT_ROOT" --dataset "$dataset" --scenario "$scenario" \
                            --seed "$seed" --fold "$fold" > "$PROJECT_ROOT/logs/drugban_split_${dataset}_${scenario}_seed${seed}_fold${fold}.log" 2>&1
                        status=$?
                        if (( status == 0 )); then
                            CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON_BIN" "$PROJECT_ROOT/run_drugban_fold.py" \
                                --root "$PROJECT_ROOT" --dataset "$dataset" --scenario "$scenario" \
                                --seed "$seed" --fold "$fold" --epochs 100 --batch-size 64 --device cuda:0 \
                                > "$task_log" 2>&1
                            status=$?
                        fi
                        set -e
                        if (( status != 0 )) || ! task_complete "$dataset" "$scenario" "$seed" "$fold"; then
                            printf '%s,%s,%s,%s,worker=%s,status=%s\n' "$dataset" "$scenario" "$seed" "$fold" "$worker" "$status" \
                                >> "$PROJECT_ROOT/logs/drugban_failed_tasks.txt"
                            printf '[%s] FAILED dataset=%s scenario=%s seed=%s fold=%s status=%s\n' \
                                "$(date -Is)" "$dataset" "$scenario" "$seed" "$fold" "$status" | tee -a "$worker_log"
                        else
                            printf '[%s] DONE dataset=%s scenario=%s seed=%s fold=%s\n' \
                                "$(date -Is)" "$dataset" "$scenario" "$seed" "$fold" | tee -a "$worker_log"
                        fi
                    fi
                    ((task_index += 1))
                done
            done
        done
    done
    printf '[%s] worker=%s finished\n' "$(date -Is)" "$worker" >> "$worker_log"
}

total_workers=$((${#gpus[@]} * workers_per_gpu))
printf '[%s] workers_per_gpu=%s total_workers=%s gpus=%s\n' \
    "$(date -Is)" "$workers_per_gpu" "$total_workers" "${gpus[*]}" \
    >> "$PROJECT_ROOT/logs/drugban_queue.log"

worker=0
for gpu in "${gpus[@]}"; do
    for ((slot = 0; slot < workers_per_gpu; slot += 1)); do
        run_worker "$gpu" "$worker" "$total_workers" &
        ((worker += 1))
    done
done
wait

if [[ -s "$PROJECT_ROOT/logs/drugban_failed_tasks.txt" ]]; then
    printf 'Some DrugBAN folds remain incomplete:\n' >&2
    cat "$PROJECT_ROOT/logs/drugban_failed_tasks.txt" >&2
    exit 1
fi

"$PYTHON_BIN" "$PROJECT_ROOT/verify_paper_coverage.py" \
    --root "$PROJECT_ROOT" --methods drugban --expected-per-group 15 --require-drugban-epochs 100 --require-drugban-tf32 \
    > "$PROJECT_ROOT/logs/drugban_coverage.log" 2>&1

"$PYTHON_BIN" "$PROJECT_ROOT/paper_benchmark.py" --aggregate --root "$PROJECT_ROOT" \
    > "$PROJECT_ROOT/logs/aggregate_final.log" 2>&1

"$PYTHON_BIN" "$PROJECT_ROOT/plot_paper_results.py" --root "$PROJECT_ROOT" \
    > "$PROJECT_ROOT/logs/plot_final.log" 2>&1
