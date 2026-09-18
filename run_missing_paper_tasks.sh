#!/usr/bin/env bash
# Resume incomplete B1-B4/ablation folds without overwriting completed JSONs.
set -uo pipefail

PROJECT_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
PYTHON_BIN="/mnt/sda/fulaiyi/aspect_env/bin/python"
export DTI_CORE_PATH="/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py"
export DTI_GCN_PAIR_BATCH="${DTI_GCN_PAIR_BATCH:-8192}"
export PYTHONHASHSEED=0

datasets=(biosnap human bindingdb)
scenarios=(random cold_drug cold_protein cold_pair)
seeds=(1941488137 4198936517 983997847)
methods=(lr mlp gcn colddti arnoldi_v4 arnoldi_s1 arnoldi_s2 arnoldi_s12 arnoldi_s12_shuffle)
method_csv="$(IFS=,; echo "${methods[*]}")"
gpus=(1 2 3)

mkdir -p "$PROJECT_ROOT/logs/resume_workers" "$PROJECT_ROOT/results_pre_chunked_gcn"
failure_log="$PROJECT_ROOT/logs/resume_failed_tasks.txt"
if [[ -s "$failure_log" ]]; then
    archive="$PROJECT_ROOT/logs/resume_failed_tasks_$(date +%Y%m%dT%H%M%S%z).txt"
    cp -p "$failure_log" "$archive"
    printf '[%s] Archived previous failure list to %s\n' "$(date -Is)" "$archive" \
        >> "$PROJECT_ROOT/logs/resume_chunked_gcn_20260827.log"
fi
: > "$failure_log"

# Earlier completed GCN JSONs use the independently tested chunked normalized
# aggregation.  They are mathematically equivalent to the current cached
# sparse aggregation, so preserve those completed folds and run only missing
# work.  The original dense baseline files remain under results_pre_chunked_gcn.

task_complete() {
    local dataset="$1" scenario="$2" seed="$3" fold="$4" method
    for method in "${methods[@]}"; do
        [[ -f "$PROJECT_ROOT/results/$method/$dataset/$scenario/seed${seed}_fold${fold}.json" ]] || return 1
    done
    return 0
}

resume_worker() {
    local gpu="$1" worker="$2" total_workers="$3"
    local task_index=0 dataset scenario seed fold status
    local worker_log="$PROJECT_ROOT/logs/resume_workers/worker_${worker}.log"
    printf '[%s] resume worker=%s gpu=%s started\n' "$(date -Is)" "$worker" "$gpu" >> "$worker_log"
    for dataset in "${datasets[@]}"; do
        for scenario in "${scenarios[@]}"; do
            for seed in "${seeds[@]}"; do
                for fold in 0 1 2 3 4; do
                    if (( task_index % total_workers == worker )) && ! task_complete "$dataset" "$scenario" "$seed" "$fold"; then
                        local task_log="$PROJECT_ROOT/logs/resume_${dataset}_${scenario}_seed${seed}_fold${fold}.log"
                        printf '[%s] RESUME dataset=%s scenario=%s seed=%s fold=%s gpu=%s\n' \
                            "$(date -Is)" "$dataset" "$scenario" "$seed" "$fold" "$gpu" | tee -a "$worker_log"
                        set +e
                        CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON_BIN" "$PROJECT_ROOT/paper_benchmark.py" \
                            --root "$PROJECT_ROOT" --dataset "$dataset" --scenario "$scenario" \
                            --seed "$seed" --fold "$fold" --methods "$method_csv" --device cuda:0 \
                            --encoder-epochs 50 --scorer-epochs 200 > "$task_log" 2>&1
                        status=$?
                        set -e
                        if (( status != 0 )) || ! task_complete "$dataset" "$scenario" "$seed" "$fold"; then
                            printf '%s,%s,%s,%s,worker=%s,status=%s\n' "$dataset" "$scenario" "$seed" "$fold" "$worker" "$status" \
                                >> "$PROJECT_ROOT/logs/resume_failed_tasks.txt"
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
    printf '[%s] resume worker=%s finished\n' "$(date -Is)" "$worker" >> "$worker_log"
}

worker=0
for gpu in "${gpus[@]}"; do
    resume_worker "$gpu" "$worker" "${#gpus[@]}" &
    ((worker += 1))
done
wait

if [[ -s "$PROJECT_ROOT/logs/resume_failed_tasks.txt" ]]; then
    printf 'Some B1-B4/ablation folds remain incomplete:\n' >&2
    cat "$PROJECT_ROOT/logs/resume_failed_tasks.txt" >&2
    exit 1
fi

"$PYTHON_BIN" "$PROJECT_ROOT/paper_benchmark.py" --aggregate --root "$PROJECT_ROOT" \
    > "$PROJECT_ROOT/logs/aggregate_after_resume.log" 2>&1
