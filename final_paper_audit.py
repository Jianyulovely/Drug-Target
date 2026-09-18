#!/usr/bin/env python3
"""Fail-closed audit for the complete DTI manuscript result package.

The audit reads result JSONs rather than trusting queue logs.  It validates
fixed-fold identity coverage, method-aligned split signatures, metric sanity,
the formal DrugBAN execution metadata, and (when requested) the aggregate
tables, source data and figure exports required for manuscript generation.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


DATASETS = ("biosnap", "human", "bindingdb")
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")
DEFAULT_METHODS = (
    "lr",
    "mlp",
    "gcn",
    "colddti",
    "arnoldi_v4",
    "arnoldi_s1",
    "arnoldi_s2",
    "arnoldi_s12",
    "arnoldi_s12_shuffle",
    "drugban",
)
METRICS = ("auc", "aupr", "f1", "accuracy")
EXPECTED_DATASET_PROVENANCE = {
    "biosnap": "8075689605257768b88eacb361b8ee7c2e7c3be5",
    "human": "711273c6f6da565ade72ad9ef615521f6743f293",
    "bindingdb": "a9aad592e945505bf22c5bd606e700b189181ba1",
}


def add_artifact_errors(root: Path, errors: list[str], require_runtime_manifest: bool) -> None:
    for relative in (
        "tables/fold_metrics.csv",
        "tables/summary.csv",
        "tables/coverage.csv",
        "source_data/fold_metrics.csv",
        "source_data/summary_metrics.csv",
        "source_data/paired_wilcoxon_statistics.csv",
        "source_data/dataset_manifest.json",
        "figure_legends.txt",
        "logs/aggregate_final.log",
        "logs/plot_final.log",
    ):
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty artifact: {relative}")
    manifest_path = root / "source_data" / "dataset_manifest.json"
    if manifest_path.is_file() and manifest_path.stat().st_size:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"unreadable dataset manifest: {error}")
        else:
            records = {entry.get("dataset"): entry for entry in manifest.get("datasets", [])}
            for dataset, expected_blob in EXPECTED_DATASET_PROVENANCE.items():
                record = records.get(dataset, {})
                provenance = record.get("provenance", {})
                if record.get("git_blob_sha1") != expected_blob:
                    errors.append(f"dataset manifest Git blob mismatch: {dataset}")
                if provenance.get("exact_upstream_snapshot_match") is not True:
                    errors.append(f"dataset provenance was not verified: {dataset}")
    if require_runtime_manifest:
        path = root / "source_data" / "environment_manifest.json"
        if not path.is_file() or path.stat().st_size == 0:
            errors.append("missing or empty artifact: source_data/environment_manifest.json")
    for stem in ("figure_2_baselines", "figure_3_ablation"):
        for extension in ("svg", "pdf", "png", "tiff"):
            path = root / "figures" / f"{stem}.{extension}"
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"missing or empty figure: figures/{stem}.{extension}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    parser.add_argument("--expected-per-group", type=int, default=15)
    parser.add_argument("--require-artifacts", action="store_true")
    parser.add_argument(
        "--require-runtime-manifest",
        action="store_true",
        help="Also require the final packaging-time runtime manifest.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    methods = tuple(value.strip() for value in args.methods.split(",") if value.strip())
    counts: Counter[tuple[str, str, str]] = Counter()
    identities: set[tuple[str, str, str, int, int]] = set()
    signatures: defaultdict[tuple[str, str, int, int], dict[str, str]] = defaultdict(dict)
    errors: list[str] = []
    ignored_nonformal_drugban = 0
    result_paths = sorted((root / "results").glob("**/*.json"))

    for path in result_paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"unreadable JSON: {path}: {error}")
            continue
        method = value.get("method")
        if method not in methods:
            continue
        # The project intentionally retains one short 2-epoch DrugBAN smoke
        # run as an execution-provenance artifact. It is not a formal B5 result
        # and can share a split identity with the later 100-epoch result, so
        # exclude that explicitly identified run before duplicate/coverage
        # accounting. Any other non-100-epoch DrugBAN artifact is a malformed
        # result and must remain visible to the fail-closed audit.
        if method == "drugban":
            epochs = value.get("settings", {}).get("epochs")
            if epochs == 2:
                ignored_nonformal_drugban += 1
                continue
            if epochs != 100:
                errors.append(f"nonformal DrugBAN epochs={epochs!r}: {path}")
                continue
        identity = (
            method,
            value.get("dataset"),
            value.get("scenario"),
            value.get("seed"),
            value.get("fold"),
        )
        if identity in identities:
            errors.append(f"duplicate result identity: {identity} ({path})")
            continue
        identities.add(identity)
        if value.get("pipeline_version") != "paper-benchmark-v2":
            errors.append(f"unexpected pipeline version: {path}")
            continue
        _, dataset, scenario, seed, fold = identity
        if dataset not in DATASETS or scenario not in SCENARIOS or not isinstance(seed, int) or fold not in range(5):
            errors.append(f"invalid identity fields: {identity} ({path})")
            continue
        metrics = value.get("metrics", {})
        for metric in METRICS:
            score = metrics.get(metric)
            if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0.0 <= score <= 1.0:
                errors.append(f"invalid {metric}={score!r}: {path}")
        signature = value.get("split_signature")
        if not isinstance(signature, str) or len(signature) < 16:
            errors.append(f"missing split signature: {path}")
        else:
            signatures[(dataset, scenario, seed, fold)][method] = signature
        if method == "drugban":
            settings = value.get("settings", {})
            required = {
                "epochs": 100,
                "input_cache": True,
                "tf32": True,
            }
            for key, expected in required.items():
                if settings.get(key) != expected:
                    errors.append(f"DrugBAN {key}={settings.get(key)!r}, expected {expected!r}: {path}")
        counts[(method, dataset, scenario)] += 1

    for method in methods:
        for dataset in DATASETS:
            for scenario in SCENARIOS:
                observed = counts[(method, dataset, scenario)]
                if observed != args.expected_per_group:
                    errors.append(
                        f"incomplete coverage: {method}/{dataset}/{scenario} "
                        f"{observed}/{args.expected_per_group}"
                    )
    for fold_identity, per_method in signatures.items():
        if set(per_method) == set(methods) and len(set(per_method.values())) != 1:
            errors.append(f"split-signature mismatch across methods: {fold_identity}: {per_method}")

    if args.require_artifacts:
        add_artifact_errors(root, errors, args.require_runtime_manifest)

    expected = len(methods) * len(DATASETS) * len(SCENARIOS) * args.expected_per_group
    print(f"audit_results={len(identities)} expected={expected} errors={len(errors)}")
    if ignored_nonformal_drugban:
        print(f"IGNORED_NONFORMAL_DRUGBAN {ignored_nonformal_drugban}")
    for error in errors:
        print(f"AUDIT_ERROR {error}")
    if errors or len(identities) != expected:
        raise SystemExit(1)
    print("FINAL_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
