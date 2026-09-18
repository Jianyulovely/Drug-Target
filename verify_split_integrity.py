#!/usr/bin/env python3
"""Read-only integrity audit for every frozen DTI evaluation split.

The checker validates the cached ``.npz`` splits directly rather than trusting
the result queue: binary labels agree with the positive/unannotated pairs,
within- and cross-partition pairs are unique, cold-start entity groups are
disjoint, and every formal result JSON carries the signature of its frozen
split.  It never creates or modifies a split or result file.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import paper_benchmark as benchmark


DATASETS = ("biosnap", "human", "bindingdb")
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")
SEEDS = (1941488137, 4198936517, 983997847)
PARTITIONS = ("train", "val", "test")


def as_pair_set(pairs: np.ndarray) -> set[tuple[int, int]]:
    return {(int(drug), int(protein)) for drug, protein in np.asarray(pairs, dtype=np.int64)}


def formal_result(value: dict) -> bool:
    if value.get("pipeline_version") != "paper-benchmark-v2":
        return False
    if value.get("method") != "drugban":
        return True
    settings = value.get("settings", {})
    return (
        settings.get("epochs") == 100
        and settings.get("input_cache") is True
        and settings.get("tf32") is True
    )


def audit_split(
    A: np.ndarray, split: dict[str, np.ndarray], scenario: str, location: str
) -> tuple[list[str], str]:
    errors: list[str] = []
    groups: dict[str, set[tuple[int, int]]] = {}
    for partition in PARTITIONS:
        pairs = np.asarray(split[f"{partition}_pairs"], dtype=np.int64)
        labels = np.asarray(split[f"{partition}_y"], dtype=np.float32)
        positives = np.asarray(split[f"{partition}_pos"], dtype=np.int64)
        if pairs.ndim != 2 or pairs.shape[1] != 2:
            errors.append(f"{location}/{partition}: invalid pair shape {pairs.shape}")
            continue
        if labels.shape != (len(pairs),):
            errors.append(f"{location}/{partition}: labels shape {labels.shape} != ({len(pairs)},)")
            continue
        expected_labels = np.concatenate(
            [np.ones(len(positives), dtype=np.float32), np.zeros(len(pairs) - len(positives), dtype=np.float32)]
        )
        if not np.array_equal(labels, expected_labels):
            errors.append(f"{location}/{partition}: labels are not positive-first binary values")
        if len(pairs) != len(as_pair_set(pairs)):
            errors.append(f"{location}/{partition}: duplicate pair within partition")
        if not np.array_equal(pairs[: len(positives)], positives):
            errors.append(f"{location}/{partition}: positive prefix does not match {partition}_pos")
        if len(positives) and not np.all(A[positives[:, 0], positives[:, 1]] > 0):
            errors.append(f"{location}/{partition}: a declared positive is absent from A")
        negatives = pairs[len(positives) :]
        if len(negatives) and not np.all(A[negatives[:, 0], negatives[:, 1]] == 0):
            errors.append(f"{location}/{partition}: a declared negative is annotated positive in A")
        groups[partition] = as_pair_set(pairs)

    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        if groups.get(left, set()) & groups.get(right, set()):
            errors.append(f"{location}: {left}/{right} pair overlap")

    if scenario == "cold_drug":
        entity_sets = [set(np.asarray(split[f"{part}_pairs"])[:, 0].tolist()) for part in PARTITIONS]
    elif scenario == "cold_protein":
        entity_sets = [set(np.asarray(split[f"{part}_pairs"])[:, 1].tolist()) for part in PARTITIONS]
    elif scenario == "cold_pair":
        drug_sets = [set(np.asarray(split[f"{part}_pairs"])[:, 0].tolist()) for part in PARTITIONS]
        protein_sets = [set(np.asarray(split[f"{part}_pairs"])[:, 1].tolist()) for part in PARTITIONS]
        for kind, entity_sets in (("drug", drug_sets), ("protein", protein_sets)):
            for left, right in ((0, 1), (0, 2), (1, 2)):
                if entity_sets[left] & entity_sets[right]:
                    errors.append(f"{location}: cold-pair {kind} entity overlap")
        entity_sets = []
    else:
        entity_sets = []
    for left, right in ((0, 1), (0, 2), (1, 2)):
        if entity_sets and entity_sets[left] & entity_sets[right]:
            errors.append(f"{location}: cold-start entity overlap")
    return errors, benchmark.split_signature(split)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--n-folds", type=int, default=5)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    core = benchmark.import_core()
    signatures: dict[tuple[str, str, int, int], str] = {}
    errors: list[str] = []
    checked = 0

    for dataset in DATASETS:
        A, _, _, _ = core.load_dataset(dataset)
        for scenario in SCENARIOS:
            for seed in SEEDS:
                for fold in range(args.n_folds):
                    path = benchmark.split_path(root, dataset, scenario, seed, fold)
                    if not path.is_file():
                        errors.append(f"missing frozen split: {path}")
                        continue
                    with np.load(path, allow_pickle=False) as source:
                        split = {key: source[key] for key in source.files}
                    location = f"{dataset}/{scenario}/seed={seed}/fold={fold}"
                    split_errors, signature = audit_split(A, split, scenario, location)
                    errors.extend(split_errors)
                    signatures[(dataset, scenario, seed, fold)] = signature
                    checked += 1

    results_by_identity: defaultdict[tuple[str, str, int, int], list[Path]] = defaultdict(list)
    for path in sorted((root / "results").glob("**/*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"unreadable result JSON {path}: {error}")
            continue
        if not formal_result(value):
            continue
        identity = (value.get("dataset"), value.get("scenario"), value.get("seed"), value.get("fold"))
        expected = signatures.get(identity)
        if expected is None:
            errors.append(f"{path}: result points to an unknown split identity {identity}")
            continue
        if value.get("split_signature") != expected:
            errors.append(f"{path}: result split signature differs from frozen split")
        results_by_identity[identity].append(path)

    print(f"checked_splits={checked} expected={len(DATASETS) * len(SCENARIOS) * len(SEEDS) * args.n_folds}")
    print(f"checked_formal_result_json={sum(map(len, results_by_identity.values()))}")
    for error in errors:
        print(f"SPLIT_AUDIT_ERROR {error}")
    if errors or checked != len(DATASETS) * len(SCENARIOS) * len(SEEDS) * args.n_folds:
        raise SystemExit(1)
    print("SPLIT_INTEGRITY_COMPLETE")


if __name__ == "__main__":
    main()
