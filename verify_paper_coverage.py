#!/usr/bin/env python3
"""Verify frozen-fold result coverage before aggregation or plotting.

This checker intentionally works from JSON result artifacts rather than process
logs, so an interrupted queue cannot be mistaken for a completed benchmark.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


DATASETS = ("biosnap", "human", "bindingdb")
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--methods", required=True, help="Comma-separated result method identifiers.")
    parser.add_argument("--expected-per-group", type=int, default=15)
    parser.add_argument("--require-drugban-epochs", type=int)
    parser.add_argument("--require-drugban-tf32", action="store_true")
    args = parser.parse_args()

    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    root = Path(args.root).resolve()
    counts: Counter[tuple[str, str, str]] = Counter()
    identities: set[tuple[str, str, str, int, int]] = set()
    invalid: list[str] = []
    ignored_nonformal_drugban = 0
    for path in root.glob("results/**/*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            invalid.append(f"{path}: unreadable ({error})")
            continue
        method = item.get("method")
        if method not in methods:
            continue
        if item.get("pipeline_version") != "paper-benchmark-v2":
            invalid.append(f"{path}: unexpected pipeline version")
            continue
        if args.require_drugban_epochs is not None and method == "drugban":
            settings = item.get("settings", {})
            epochs = settings.get("epochs")
            if epochs != args.require_drugban_epochs:
                # Keep short execution smoke runs for provenance, but exclude
                # them from the formal fixed-fold coverage calculation.  This
                # must precede duplicate checking because a 100-epoch result
                # can later have the same split identity.
                ignored_nonformal_drugban += 1
                continue
            if settings.get("input_cache") is not True:
                invalid.append(f"{path}: DrugBAN input cache setting is not enabled")
                continue
        if args.require_drugban_tf32 and method == "drugban":
            if item.get("settings", {}).get("tf32") is not True:
                invalid.append(f"{path}: DrugBAN tf32 setting is not enabled")
                continue
        identity = (method, item.get("dataset"), item.get("scenario"), item.get("seed"), item.get("fold"))
        if identity in identities:
            invalid.append(f"{path}: duplicate identity {identity}")
            continue
        identities.add(identity)
        counts[(method, item.get("dataset"), item.get("scenario"))] += 1

    missing = []
    for method in methods:
        for dataset in DATASETS:
            for scenario in SCENARIOS:
                observed = counts[(method, dataset, scenario)]
                if observed != args.expected_per_group:
                    missing.append(f"{method}/{dataset}/{scenario}: {observed}/{args.expected_per_group}")
    expected_total = len(methods) * len(DATASETS) * len(SCENARIOS) * args.expected_per_group
    print(f"validated={sum(counts.values())} expected={expected_total}")
    if ignored_nonformal_drugban:
        print(f"IGNORED_NONFORMAL_DRUGBAN {ignored_nonformal_drugban}")
    for line in missing:
        print(f"INCOMPLETE {line}")
    for line in invalid:
        print(f"INVALID {line}")
    if missing or invalid or sum(counts.values()) != expected_total:
        raise SystemExit(1)
    print("COVERAGE_COMPLETE")


if __name__ == "__main__":
    main()
