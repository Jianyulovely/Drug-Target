#!/usr/bin/env bash
# Build a local, Overleaf-ready manuscript package only from an audited remote
# DTI result release.  No password, result values, or destructive operations
# are embedded here; SSH authentication is delegated to the caller.  If the
# caller has already supplied SSHPASS, the script uses sshpass -e without ever
# persisting or printing that credential.
set -euo pipefail

# macOS installs MacTeX outside the default PATH used by some non-interactive
# shells.  Prefer it when present, while leaving Linux/Overleaf-compatible PATH
# resolution unchanged.
if [[ -d /Library/TeX/texbin ]]; then
    export PATH="/Library/TeX/texbin:$PATH"
fi

for required_command in ssh scp pdflatex bibtex pdftoppm pdfinfo grep; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        echo "Required command is unavailable: $required_command" >&2
        exit 127
    fi
done

ssh_auth_prefix=()
ssh_auth_options=()
if [[ -n "${SSHPASS:-}" ]]; then
    if ! command -v sshpass >/dev/null 2>&1; then
        echo "SSHPASS is set, but sshpass is unavailable on PATH" >&2
        exit 127
    fi
    ssh_auth_prefix=(sshpass -e)
    # Match the password-only, bounded connection setup used for the remote
    # experiments.  These options are deliberately conditional: users who
    # authenticate with a key or an SSH agent keep their normal SSH behavior.
    ssh_auth_options=(
        -o StrictHostKeyChecking=accept-new
        -o ConnectTimeout=15
        -o IdentitiesOnly=yes
        -o PubkeyAuthentication=no
        -o PreferredAuthentications=password
        -o NumberOfPasswordPrompts=1
    )
fi

REMOTE_HOST="fulaiyi@frp-arm.com"
REMOTE_PORT="20752"
REMOTE_ROOT="/mnt/sda/fulaiyi/dti_paper_20260826_v2"
REMOTE_PYTHON="/mnt/sda/fulaiyi/aspect_env/bin/python"
LOCAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/manuscript"
CHECK_LOCAL_PLACEHOLDERS=0
OVERLEAF_ZIP=""

usage() {
    cat <<'EOF'
Usage: finalize_overleaf_package.sh [options]

Require a complete audited remote benchmark, generate data-derived manuscript
fragments remotely, then copy the release artifacts into the local Overleaf
directory and compile a local PDF.

Options:
  --remote-host USER@HOST  SSH destination (default: fulaiyi@frp-arm.com)
  --remote-port PORT       SSH port (default: 20752)
  --remote-root PATH       Remote experiment root
  --remote-python PATH     Remote Python interpreter
  --local-root PATH        Local manuscript directory
  --check-local-placeholders  Validate generated and publication TODO gates only
  --overleaf-zip PATH      Write a clean, non-overwriting Overleaf source ZIP after final QA
  -h, --help               Show this message

Authentication is intentionally not handled by this script. Configure SSH or
provide credentials through your approved SSH workflow before invoking it.
For a password-authenticated run, provide SSHPASS only in the calling shell;
the script will use sshpass -e and never writes that value to disk.
EOF
}

while (($#)); do
    case "$1" in
        --remote-host) REMOTE_HOST="$2"; shift 2 ;;
        --remote-port) REMOTE_PORT="$2"; shift 2 ;;
        --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
        --remote-python) REMOTE_PYTHON="$2"; shift 2 ;;
        --local-root) LOCAL_ROOT="$2"; shift 2 ;;
        --check-local-placeholders) CHECK_LOCAL_PLACEHOLDERS=1; shift ;;
        --overleaf-zip) OVERLEAF_ZIP="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! -f "$LOCAL_ROOT/main.tex" ]]; then
    echo "Local manuscript root does not contain main.tex: $LOCAL_ROOT" >&2
    exit 2
fi

remote_ssh() {
    "${ssh_auth_prefix[@]}" ssh "${ssh_auth_options[@]}" -p "$REMOTE_PORT" "$REMOTE_HOST" "$@"
}

remote_scp() {
    "${ssh_auth_prefix[@]}" scp "${ssh_auth_options[@]}" -P "$REMOTE_PORT" "$@"
}

remote_ssh_with_marker() {
    local marker="$1"
    shift
    local output
    if ! output="$(remote_ssh "$@")"; then
        printf '%s\n' "$output" >&2
        return 1
    fi
    printf '%s\n' "$output"
    if ! grep -Fq "$marker" <<<"$output"; then
        echo "Remote command completed without required marker: $marker" >&2
        return 1
    fi
}

check_submission_placeholders() {
    local manuscript_root="$1"
    if [[ ! -d "$manuscript_root/generated" ]]; then
        echo "Generated-fragment directory is missing: $manuscript_root/generated" >&2
        return 1
    fi

    # Dynamic fallbacks in results.tex, experiments.tex and main.tex are
    # wrapped in \IfFileExists and are intentionally present before the
    # result-derived fragments arrive.  Do not reject those inactive fallbacks.
    if grep -R -n -F '\todo{' "$manuscript_root/generated"; then
        echo "A generated result fragment contains an unresolved TODO placeholder." >&2
        return 1
    fi

    local metadata_todo=0
    local metadata_source
    for metadata_source in \
        "$manuscript_root/sections/data_availability.tex" \
        "$manuscript_root/main.tex"; do
        case "$metadata_source" in
            "$manuscript_root/sections/data_availability.tex")
                if grep -n -F '\todo{' "$metadata_source"; then metadata_todo=1; fi
                ;;
            "$manuscript_root/main.tex")
                if grep -n -F '\author{\todo{' "$metadata_source"; then metadata_todo=1; fi
                if grep -n -F '\textbf{Author contributions.} \todo{' "$metadata_source"; then metadata_todo=1; fi
                if grep -n -F '\textbf{Competing interests.} \todo{' "$metadata_source"; then metadata_todo=1; fi
                ;;
        esac
    done
    if (( metadata_todo )); then
        echo "Publication metadata or release identifiers remain unresolved; see AUTHOR_INPUT_REQUIRED.md." >&2
        return 1
    fi
}

write_overleaf_zip() {
    local requested_path="$1"
    local destination_dir
    local destination_name
    local destination_path
    local staging_root
    local package_root
    local required_path
    local source_path
    local relative_path
    local -a required_paths=(
        "main.tex"
        "README.md"
        "references.bib"
        "sections/methods.tex"
        "sections/experiments.tex"
        "sections/results.tex"
        "sections/data_availability.tex"
        "figures/figure_1_method_schematic.pdf"
        "figures/figure_2_baselines.pdf"
        "figures/figure_3_ablation.pdf"
        "source_data/fold_metrics.csv"
        "source_data/summary_metrics.csv"
        "source_data/paired_wilcoxon_statistics.csv"
        "source_data/dataset_manifest.json"
        "source_data/environment_manifest.json"
        "tables/fold_metrics.csv"
        "tables/summary.csv"
        "tables/coverage.csv"
        "figure_legends.txt"
        "generated/results_autogenerated.tex"
        "generated/abstract_autogenerated.tex"
        "generated/discussion_autogenerated.tex"
        "generated/conclusion_autogenerated.tex"
        "generated/protocol_autogenerated.tex"
    )

    if ! command -v zip >/dev/null 2>&1; then
        echo "Required command is unavailable for Overleaf export: zip" >&2
        return 127
    fi
    for required_path in "${required_paths[@]}"; do
        if [[ ! -f "$LOCAL_ROOT/$required_path" ]]; then
            echo "Audited manuscript artifact is missing: $LOCAL_ROOT/$required_path" >&2
            return 1
        fi
    done

    destination_dir="$(dirname "$requested_path")"
    destination_name="$(basename "$requested_path")"
    mkdir -p "$destination_dir"
    destination_dir="$(cd "$destination_dir" && pwd)"
    destination_path="$destination_dir/$destination_name"
    if [[ -e "$destination_path" ]]; then
        echo "Refusing to overwrite existing Overleaf ZIP: $destination_path" >&2
        return 1
    fi

    staging_root="$(mktemp -d "${TMPDIR:-/tmp}/dti-overleaf-export.XXXXXX")"
    package_root="$staging_root/ArnoldiGCL-S1-S2-DTI"
    mkdir -p "$package_root"
    while IFS= read -r -d '' source_path; do
        relative_path="${source_path#./}"
        mkdir -p "$package_root/$(dirname "$relative_path")"
        cp "$LOCAL_ROOT/$relative_path" "$package_root/$relative_path"
    done < <(
        cd "$LOCAL_ROOT"
        find . \
            \( -path './build' -o -path './build/*' -o -path './build_*' -o -path './build_*/*' -o -name '.DS_Store' \) -prune \
            -o -type f -print0
    )
    (
        cd "$staging_root"
        zip -q -r "$destination_path" "$(basename "$package_root")"
    )
    rm -rf "$staging_root"
    echo "OVERLEAF_SOURCE_ZIP_COMPLETE $destination_path"
}

if (( CHECK_LOCAL_PLACEHOLDERS )); then
    check_submission_placeholders "$LOCAL_ROOT"
    echo "LOCAL_PLACEHOLDER_GATE_COMPLETE $LOCAL_ROOT"
    exit 0
fi

remote_audit=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/final_paper_audit.py"
    --root "$REMOTE_ROOT" --require-artifacts --require-runtime-manifest
)
remote_result_audit=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/final_paper_audit.py"
    --root "$REMOTE_ROOT"
)
remote_split_audit=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/verify_split_integrity.py"
    --root "$REMOTE_ROOT"
)
remote_environment_manifest=(
    env "DTI_CORE_PATH=/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py"
    "$REMOTE_PYTHON" "$REMOTE_ROOT/write_environment_manifest.py" --root "$REMOTE_ROOT"
)
remote_aggregate=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/paper_benchmark.py"
    --aggregate --root "$REMOTE_ROOT"
)
remote_plot=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/plot_paper_results.py"
    --root "$REMOTE_ROOT" --expected-per-group 15
)

echo "[1/10] Confirming no training or background release process remains"
remote_ssh "if pgrep -af '[r]un_drugban_queue\\.sh|[r]un_drugban_fold\\.py|[p]ostprocess_after_drugban\\.sh' >/dev/null; then pgrep -af '[r]un_drugban_queue\\.sh|[r]un_drugban_fold\\.py|[p]ostprocess_after_drugban\\.sh' >&2 || true; echo 'Concurrent DrugBAN or release process remains; refusing to finalize.' >&2; exit 4; fi"

echo "[2/10] Verifying frozen split integrity before any release-time writes"
remote_ssh_with_marker "SPLIT_INTEGRITY_COMPLETE" \
    "$(printf '%q ' "${remote_split_audit[@]}")"

echo "[3/10] Verifying complete remote result release before post-processing"
remote_ssh_with_marker "FINAL_AUDIT_COMPLETE" \
    "$(printf '%q ' "${remote_result_audit[@]}")"

remote_dataset_manifest=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/write_dataset_manifest.py"
    --data-dir /mnt/sda/fulaiyi/DTI_datasets
    --output "$REMOTE_ROOT/source_data/dataset_manifest.json"
)
echo "[4/10] Writing the pinned remote dataset-provenance manifest"
remote_ssh "$(printf '%q ' "${remote_dataset_manifest[@]}")"

echo "[5/10] Writing the remote runtime manifest"
remote_ssh "$(printf '%q ' "${remote_environment_manifest[@]}")"

echo "[6/10] Aggregating the audited fold metrics"
remote_ssh "mkdir -p $(printf '%q' "$REMOTE_ROOT/logs") && $(printf '%q ' "${remote_aggregate[@]}") > $(printf '%q' "$REMOTE_ROOT/logs/aggregate_final.log") 2>&1"

echo "[7/10] Regenerating Python figures and source-data CSVs"
remote_ssh "$(printf '%q ' "${remote_plot[@]}") > $(printf '%q' "$REMOTE_ROOT/logs/plot_final.log") 2>&1"

echo "[8/10] Verifying the complete result-and-artifact release"
remote_ssh_with_marker "FINAL_AUDIT_COMPLETE" \
    "$(printf '%q ' "${remote_audit[@]}")"

remote_generate=(
    "$REMOTE_PYTHON" "$REMOTE_ROOT/generate_manuscript_results.py"
    --root "$REMOTE_ROOT" --manuscript-root "$REMOTE_ROOT/manuscript_generated"
)
echo "[9/10] Generating data-derived manuscript fragments"
remote_ssh "$(printf '%q ' "${remote_generate[@]}")"

mkdir -p "$LOCAL_ROOT/figures" "$LOCAL_ROOT/generated" "$LOCAL_ROOT/source_data" "$LOCAL_ROOT/tables"
echo "[10/10] Synchronizing audited artifacts and compiling the local manuscript"
if ! remote_ssh "test -d $(printf '%q' "$REMOTE_ROOT/manuscript/figures")"; then
    echo "Remote manuscript figures directory is missing: $REMOTE_ROOT/manuscript/figures" >&2
    exit 1
fi
remote_scp -rp \
    "$REMOTE_HOST:$REMOTE_ROOT/manuscript/figures/." \
    "$LOCAL_ROOT/figures/"
for extension in svg pdf png tiff; do
    remote_scp -p \
        "$REMOTE_HOST:$REMOTE_ROOT/figures/figure_2_baselines.$extension" \
        "$REMOTE_HOST:$REMOTE_ROOT/figures/figure_3_ablation.$extension" \
        "$LOCAL_ROOT/figures/"
done
for filename in fold_metrics.csv summary_metrics.csv paired_wilcoxon_statistics.csv dataset_manifest.json environment_manifest.json; do
    remote_scp -p "$REMOTE_HOST:$REMOTE_ROOT/source_data/$filename" "$LOCAL_ROOT/source_data/$filename"
done
for filename in fold_metrics.csv summary.csv coverage.csv; do
    remote_scp -p "$REMOTE_HOST:$REMOTE_ROOT/tables/$filename" "$LOCAL_ROOT/tables/$filename"
done
remote_scp -p "$REMOTE_HOST:$REMOTE_ROOT/figure_legends.txt" "$LOCAL_ROOT/figure_legends.txt"
for filename in results_autogenerated.tex abstract_autogenerated.tex discussion_autogenerated.tex conclusion_autogenerated.tex protocol_autogenerated.tex; do
    remote_scp -p "$REMOTE_HOST:$REMOTE_ROOT/manuscript_generated/generated/$filename" "$LOCAL_ROOT/generated/$filename"
done

if ! check_submission_placeholders "$LOCAL_ROOT"; then
    exit 1
fi

(
    cd "$LOCAL_ROOT"
    mkdir -p build/render_final
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
    bibtex build/main
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
    if grep -En '(^!|Fatal error|Emergency stop|undefined references|undefined citations)' build/main.log; then
        exit 1
    fi
    test -s build/main.pdf
    pdftoppm -png -r 150 -f 1 -l 1 build/main.pdf build/render_final/page
    pdfinfo build/main.pdf | grep -E '^(Pages|Page size|Title):'
)

if [[ -n "$OVERLEAF_ZIP" ]]; then
    write_overleaf_zip "$OVERLEAF_ZIP"
fi
echo "OVERLEAF_PACKAGE_COMPLETE $LOCAL_ROOT"
