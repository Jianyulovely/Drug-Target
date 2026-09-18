#!/usr/bin/env bash
# Launch the reproducible B1-B4 + ArnoldiGCL ablation benchmark on four GPUs.
# Each worker owns a disjoint deterministic subset of the 180 frozen folds.
set -euo pipefail

PROJECT_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
PYTHON_BIN="/mnt/sda/fulaiyi/aspect_env/bin/python"
export DTI_CORE_PATH="/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py"
export PYTHONHASHSEED=0

datasets=(biosnap human bindingdb)
scenarios=(random cold_drug cold_protein cold_pair)
seeds=(1941488137 4198936517 983997847)
methods="lr,mlp,gcn,colddti,arnoldi_v4,arnoldi_s1,arnoldi_s2,arnoldi_s12,arnoldi_s12_shuffle"

mkdir -p "$PROJECT_ROOT/logs/workers"

run_worker() {
    local gpu="$1"
    local worker="$2"
    local total_workers="$3"
    local task_index=0
    local dataset scenario seed fold
    local worker_log="$PROJECT_ROOT/logs/workers/worker_${worker}.log"

    printf '[%s] worker=%s gpu=%s started\n' "$(date -Is)" "$worker" "$gpu" >> "$worker_log"
    for dataset in "${datasets[@]}"; do
        for scenario in "${scenarios[@]}"; do
            for seed in "${seeds[@]}"; do
                for fold in 0 1 2 3 4; do
                    if (( task_index % total_workers == worker )); then
                        local task_log="$PROJECT_ROOT/logs/${dataset}_${scenario}_seed${seed}_fold${fold}.log"
                        printf '[%s] START dataset=%s scenario=%s seed=%s fold=%s gpu=%s\n' \
                            "$(date -Is)" "$dataset" "$scenario" "$seed" "$fold" "$gpu" | tee -a "$worker_log"
                        CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON_BIN" "$PROJECT_ROOT/paper_benchmark.py" \
                            --root "$PROJECT_ROOT" \
                            --dataset "$dataset" \
                            --scenario "$scenario" \
                            --seed "$seed" \
                            --fold "$fold" \
                            --methods "$methods" \
                            --device cuda:0 \
                            --encoder-epochs 50 \
                            --scorer-epochs 200 \
                            > "$task_log" 2>&1
                        printf '[%s] DONE dataset=%s scenario=%s seed=%s fold=%s\n' \
                            "$(date -Is)" "$dataset" "$scenario" "$seed" "$fold" | tee -a "$worker_log"
                    fi
                    ((task_index += 1))
                done
            done
        done
    done
    printf '[%s] worker=%s finished\n' "$(date -Is)" "$worker" >> "$worker_log"
}

for gpu in 0 1 2 3; do
    run_worker "$gpu" "$gpu" 4 &
done
wait

"$PYTHON_BIN" "$PROJECT_ROOT/paper_benchmark.py" --aggregate --root "$PROJECT_ROOT" \
    > "$PROJECT_ROOT/logs/aggregate_after_queue.log" 2>&1
