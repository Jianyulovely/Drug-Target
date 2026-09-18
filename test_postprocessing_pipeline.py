#!/usr/bin/env python3
"""Regression test for result aggregation, plotting and manuscript fragments.

The fixture has the same formal shape as the paper release: 10 methods,
3 datasets, 4 scenarios and 15 fixed seed--fold evaluations.  It intentionally
uses only disposable synthetic values; it validates the post-processing
contract, not model performance.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


METHODS = (
    "lr",
    "mlp",
    "gcn",
    "colddti",
    "drugban",
    "arnoldi_v4",
    "arnoldi_s1",
    "arnoldi_s2",
    "arnoldi_s12",
    "arnoldi_s12_shuffle",
)
DATASETS = ("biosnap", "human", "bindingdb")
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")
SEEDS = (1941488137, 4198936517, 983997847)


def write_fixture(root: Path, arnoldi_s12_aupr_offset: float = 0.0) -> None:
    method_offset = {method: index * 0.005 for index, method in enumerate(METHODS)}
    scenario_offset = {"random": 0.15, "cold_drug": 0.09, "cold_protein": 0.05, "cold_pair": 0.01}
    for method in METHODS:
        for dataset_index, dataset in enumerate(DATASETS):
            for scenario in SCENARIOS:
                for seed_index, seed in enumerate(SEEDS):
                    for fold in range(5):
                        aupr = 0.30 + scenario_offset[scenario] + method_offset[method] + 0.01 * dataset_index
                        aupr += 0.002 * seed_index + 0.001 * fold
                        if method == "arnoldi_s12":
                            aupr += arnoldi_s12_aupr_offset
                        auc = min(0.99, aupr + 0.28)
                        item = {
                            "pipeline_version": "paper-benchmark-v2",
                            "method": method,
                            "method_label": method,
                            "dataset": dataset,
                            "scenario": scenario,
                            "seed": seed,
                            "fold": fold,
                            "split_signature": f"fixture-{dataset}-{scenario}-{seed}-{fold}",
                            "best_val_auc": auc - 0.01,
                            "n_train": 1000 + dataset_index,
                            "n_val": 200 + fold,
                            "n_test": 400 + fold,
                            "n_test_positive": 40 + fold,
                            "metrics": {
                                "auc": auc,
                                "aupr": aupr,
                                "f1": aupr - 0.08,
                                "accuracy": min(0.99, aupr + 0.16),
                            },
                        }
                        if method == "drugban":
                            item["settings"] = {"epochs": 100, "input_cache": True, "tf32": True}
                        destination = root / "results" / method / dataset / scenario / f"{seed}_{fold}.json"
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_text(json.dumps(item), encoding="utf-8")


def write_audit_fixture_manifests(root: Path) -> None:
    """Write non-scientific fixtures for the audit artifact contract only."""
    from final_paper_audit import EXPECTED_DATASET_PROVENANCE

    dataset_manifest = {
        "fixture_only": True,
        "datasets": [
            {
                "dataset": dataset,
                "git_blob_sha1": blob,
                "provenance": {"exact_upstream_snapshot_match": True},
            }
            for dataset, blob in EXPECTED_DATASET_PROVENANCE.items()
        ],
    }
    source_data = root / "source_data"
    source_data.mkdir(parents=True, exist_ok=True)
    (source_data / "dataset_manifest.json").write_text(
        json.dumps(dataset_manifest), encoding="utf-8"
    )
    (source_data / "environment_manifest.json").write_text(
        json.dumps(
            {
                "fixture_only": True,
                "external_core": {
                    "environment_variable": "DTI_CORE_PATH",
                    "path": "/fixture/core.py",
                    "sha256": "fixture-core-hash",
                },
            }
        ),
        encoding="utf-8",
    )


def require_nonempty(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise AssertionError(f"missing or empty artifact: {path}")


def compile_fixture_manuscript(repository: Path, root: Path, generated_root: Path) -> None:
    """Compile a disposable copy of the manuscript with generated fixtures.

    This checks path wiring and LaTeX/table capacity only.  The fixture values
    are synthetic and the temporary PDF is never a release artifact.
    """
    package = root / "overleaf_fixture"
    shutil.copytree(
        repository / "manuscript",
        package,
        ignore=shutil.ignore_patterns("build", "build_preflight", "generated", "source_data", "tables"),
    )
    shutil.copytree(root / "figures", package / "figures", dirs_exist_ok=True)
    shutil.copytree(generated_root / "generated", package / "generated")
    if not shutil.which("pdflatex") or not shutil.which("bibtex"):
        raise RuntimeError("Fixture manuscript test requires pdflatex and bibtex.")
    build = package / "build_fixture"
    build.mkdir()
    latex = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(build), "main.tex"]
    subprocess.run(latex, cwd=package, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    subprocess.run(
        ["bibtex", str(Path("build_fixture") / "main")],
        cwd=package,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    subprocess.run(latex, cwd=package, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    subprocess.run(latex, cwd=package, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    require_nonempty(build / "main.pdf")
    log = (build / "main.log").read_text(encoding="utf-8", errors="replace")
    if re.search(r"(^!|Fatal error|Emergency stop|undefined references|undefined citations)", log, flags=re.MULTILINE):
        raise AssertionError("Fixture manuscript has an unresolved LaTeX diagnostic.")


def assert_null_effect_prose(root: Path) -> None:
    """Require the generator to report a valid all-non-positive ablation.

    A paper-writing pipeline must not fail, or write a positive conclusion, if
    S1/S2 does not improve its structural-only predecessor in the final data.
    """
    import generate_manuscript_results as manuscript_results
    import plot_paper_results as plotted_results

    null_root = root / "null_effect_fixture"
    # The ordinary fixture gives M8+S1/S2 a +0.015 AUPR offset over the
    # structural-only variant.  This makes its contrast negative everywhere.
    write_fixture(null_root, arnoldi_s12_aupr_offset=-0.04)
    raw = plotted_results.load_rows(null_root)
    plotted_results.validate_complete(raw, expected_per_group=15)
    summary = plotted_results.aggregate(raw)

    result_text = manuscript_results.result_fragment(summary, raw)
    abstract_text = manuscript_results.abstract_fragment(summary, raw)
    discussion_text = manuscript_results.discussion_fragment(summary, raw)
    conclusion_text = manuscript_results.conclusion_fragment(summary, raw)
    required = (
        "higher mean AUPR in 0/12 conditions",
        "no positive mean AUPR difference was observed",
        "did not exceed its structural-only variant in any of the 12 AUPR comparisons",
        "do not support a predictive benefit from the S1/S2 branch",
        "does not support a general predictive contribution",
        "does not support a contribution from pairwise alignment",
        "does not support a general predictive benefit",
    )
    combined = "\n".join((result_text, abstract_text, discussion_text, conclusion_text))
    for phrase in required:
        if phrase not in combined:
            raise AssertionError(f"Missing null-effect wording: {phrase}")


def assert_nonformal_drugban_is_excluded(repository: Path, root: Path) -> None:
    """Ensure a retained short DrugBAN smoke file cannot count as B5."""
    smoke_root = root / "nonformal_drugban_fixture"
    write_fixture(smoke_root)
    target = (
        smoke_root
        / "results"
        / "drugban"
        / "biosnap"
        / "random"
        / f"{SEEDS[0]}_0.json"
    )
    item = json.loads(target.read_text(encoding="utf-8"))
    item["settings"]["epochs"] = 2
    target.write_text(json.dumps(item), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(repository / "verify_paper_coverage.py"),
            "--root",
            str(smoke_root),
            "--methods",
            "drugban",
            "--expected-per-group",
            "15",
            "--require-drugban-epochs",
            "100",
            "--require-drugban-tf32",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if completed.returncode == 0:
        raise AssertionError("A nonformal DrugBAN smoke file was counted as complete.")
    if "validated=179 expected=180" not in completed.stdout:
        raise AssertionError(f"Unexpected nonformal coverage accounting:\n{completed.stdout}")
    if "IGNORED_NONFORMAL_DRUGBAN 1" not in completed.stdout:
        raise AssertionError(f"Nonformal DrugBAN marker missing:\n{completed.stdout}")


def assert_unexpected_drugban_epochs_fail_audit(repository: Path, root: Path) -> None:
    """Only the retained 2-epoch smoke artifact may be excluded from audit.

    A shorter accidental run must not receive the smoke-run exemption, because
    otherwise its fold identity could disappear from the release without a
    visible configuration error.
    """
    malformed_root = root / "malformed_drugban_epochs_fixture"
    write_fixture(malformed_root)
    target = (
        malformed_root
        / "results"
        / "drugban"
        / "biosnap"
        / "random"
        / f"{SEEDS[0]}_0.json"
    )
    item = json.loads(target.read_text(encoding="utf-8"))
    item["settings"]["epochs"] = 50
    target.write_text(json.dumps(item), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(repository / "final_paper_audit.py"), "--root", str(malformed_root)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if completed.returncode == 0:
        raise AssertionError("A non-smoke 50-epoch DrugBAN artifact passed the final audit.")
    expected = "AUDIT_ERROR nonformal DrugBAN epochs=50"
    if expected not in completed.stdout:
        raise AssertionError(f"Unexpected malformed-epoch audit output:\n{completed.stdout}")


def main() -> None:
    repository = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="dti-postprocessing-test-") as temp_dir:
        root = Path(temp_dir)
        write_fixture(root)
        write_audit_fixture_manifests(root)
        log_dir = root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "aggregate_final.log").open("w", encoding="utf-8") as handle:
            subprocess.run(
                [sys.executable, str(repository / "paper_benchmark.py"), "--aggregate", "--root", str(root)],
                check=True,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
        with (log_dir / "plot_final.log").open("w", encoding="utf-8") as handle:
            subprocess.run(
                [sys.executable, str(repository / "plot_paper_results.py"), "--root", str(root)],
                check=True,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
        manuscript_root = root / "manuscript_generated"
        subprocess.run(
            [
                sys.executable,
                str(repository / "generate_manuscript_results.py"),
                "--root",
                str(root),
                "--manuscript-root",
                str(manuscript_root),
            ],
            check=True,
        )
        compile_fixture_manuscript(repository, root, manuscript_root)
        assert_null_effect_prose(root)
        assert_nonformal_drugban_is_excluded(repository, root)
        assert_unexpected_drugban_epochs_fail_audit(repository, root)
        subprocess.run(
            [
                sys.executable,
                str(repository / "final_paper_audit.py"),
                "--root",
                str(root),
                "--require-artifacts",
                "--require-runtime-manifest",
            ],
            check=True,
        )
        for stem in ("figure_2_baselines", "figure_3_ablation"):
            for extension in ("svg", "pdf", "png", "tiff"):
                require_nonempty(root / "figures" / f"{stem}.{extension}")
        for filename in ("fold_metrics.csv", "summary_metrics.csv", "paired_wilcoxon_statistics.csv"):
            require_nonempty(root / "source_data" / filename)
        for filename in (
            "results_autogenerated.tex",
            "abstract_autogenerated.tex",
            "discussion_autogenerated.tex",
            "conclusion_autogenerated.tex",
            "protocol_autogenerated.tex",
        ):
            fragment = manuscript_root / "generated" / filename
            require_nonempty(fragment)
            if r"\todo{" in fragment.read_text(encoding="utf-8"):
                raise AssertionError(f"Generated manuscript fragment contains a TODO: {filename}")
    print("POSTPROCESSING_PIPELINE_REGRESSION_PASS")


if __name__ == "__main__":
    main()
