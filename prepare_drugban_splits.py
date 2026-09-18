#!/usr/bin/env python3
"""Materialize frozen paper-benchmark folds as DrugBAN-compatible CSV files.

This is intentionally a one-way adapter: it reads the immutable ``.npz``
splits created by ``paper_benchmark.py`` and writes only three CSVs per fold.
Each CSV holds SMILES, Protein and Y, exactly the columns expected by DrugBAN.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def load_core():
    path = Path(os.environ.get("DTI_CORE_PATH", "/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py"))
    spec = importlib.util.spec_from_file_location("dti_project_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pair_frame(pairs: np.ndarray, labels: np.ndarray, drugs: list[str], proteins: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SMILES": [drugs[int(index)] for index in pairs[:, 0]],
            "Protein": [proteins[int(index)] for index in pairs[:, 1]],
            "Y": labels.astype(int),
        }
    )


def write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_signature(split: np.lib.npyio.NpzFile) -> str:
    """Match the split identity used by paper_benchmark.py."""
    digest = hashlib.sha256()
    for key in ("train_pairs", "val_pairs", "test_pairs"):
        array = np.ascontiguousarray(split[key], dtype=np.int64)
        digest.update(key.encode("utf-8"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--dataset", required=True, choices=("biosnap", "human", "bindingdb"))
    parser.add_argument("--scenario", required=True, choices=("random", "cold_drug", "cold_protein", "cold_pair"))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--fold", type=int, required=True, choices=range(5))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    split_path = root / "splits" / args.dataset / args.scenario / f"seed{args.seed}_fold{args.fold}.npz"
    if not split_path.is_file():
        raise FileNotFoundError(f"Frozen split not found: {split_path}")
    core = load_core()
    _, drugs, proteins, _ = core.load_dataset(args.dataset)
    output_root = root / "drugban_splits" / args.dataset / args.scenario / f"seed{args.seed}_fold{args.fold}"
    manifest = {
        "dataset": args.dataset,
        "scenario": args.scenario,
        "seed": args.seed,
        "fold": args.fold,
        "source_split": str(split_path),
        "split_signature": None,
        "files": {},
    }
    with np.load(split_path, allow_pickle=False) as split:
        manifest["split_signature"] = split_signature(split)
        for partition in ("train", "val", "test"):
            frame = pair_frame(split[f"{partition}_pairs"], split[f"{partition}_y"], drugs, proteins)
            destination = output_root / f"{partition}.csv"
            manifest["files"][partition] = {
                "path": str(destination),
                "rows": int(len(frame)),
                "positive": int(frame["Y"].sum()),
                "sha256": write_csv(destination, frame),
            }
    with (output_root / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
