#!/usr/bin/env python3
"""Train the unmodified DrugBAN architecture on one frozen paper fold.

The runner reads CSVs written by ``prepare_drugban_splits.py`` and uses the
project's DrugBAN modules without their built-in split logic.  It selects the
checkpoint by validation AUC and chooses the reported F1 decision threshold on
the validation predictions, matching the main benchmark convention.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score
from torch.utils.data import DataLoader, Dataset


def stable_seed(*items: object) -> int:
    content = "|".join(map(str, items)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(content).digest()[:4], "little")


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def import_drugban(source: Path):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from configs import get_cfg_defaults
    from dataloader import DTIDataset
    from models import DrugBAN, binary_cross_entropy
    from utils import graph_collate_func, integer_label_protein

    return (
        get_cfg_defaults,
        DTIDataset,
        DrugBAN,
        binary_cross_entropy,
        graph_collate_func,
        integer_label_protein,
    )


class CachedDTIDataset(Dataset):
    """Input-equivalent DrugBAN dataset that caches deterministic preprocessing.

    The original DrugBAN loader parses a SMILES string and pads its DGL graph
    for every occurrence of a pair.  In the frozen DTI folds, each molecule is
    repeated many times, while this preprocessing is a pure function of its
    SMILES string.  Caching therefore changes neither the graph, protein
    integer encoding, labels nor the order emitted by the DataLoader; it only
    avoids repeated RDKit/DGL construction.  The DrugBAN architecture and all
    optimization hyperparameters are unchanged.
    """

    def __init__(self, list_ids, frame: pd.DataFrame, reference, integer_label_protein):
        # ``DataFrame.iloc`` in every ``__getitem__`` call is needlessly
        # expensive for the long, repeatedly shuffled training epochs.  Take
        # the same positional rows once, preserving their original order and
        # values exactly, then use plain arrays in the hot path.
        selected = frame.iloc[np.asarray(list_ids)]
        self.smiles = selected["SMILES"].to_numpy(copy=True)
        self.proteins = selected["Protein"].to_numpy(copy=True)
        self.labels = selected["Y"].to_numpy(copy=True)
        self.max_drug_nodes = reference.max_drug_nodes
        self.atom_featurizer = reference.atom_featurizer
        self.bond_featurizer = reference.bond_featurizer
        self.fc = reference.fc
        self.integer_label_protein = integer_label_protein
        self.drug_graph_cache = {}
        self.protein_cache = {}

    def __len__(self):
        return len(self.labels)

    def _graph(self, smiles: str):
        graph = self.drug_graph_cache.get(smiles)
        if graph is None:
            graph = self.fc(
                smiles=smiles,
                node_featurizer=self.atom_featurizer,
                edge_featurizer=self.bond_featurizer,
            )
            actual_node_feats = graph.ndata.pop("h")
            n_actual = actual_node_feats.shape[0]
            n_virtual = self.max_drug_nodes - n_actual
            actual_node_feats = torch.cat(
                (actual_node_feats, torch.zeros([n_actual, 1])), dim=1
            )
            graph.ndata["h"] = actual_node_feats
            virtual_node_feat = torch.cat(
                (torch.zeros(n_virtual, 74), torch.ones(n_virtual, 1)), dim=1
            )
            graph.add_nodes(n_virtual, {"h": virtual_node_feat})
            graph = graph.add_self_loop()
            self.drug_graph_cache[smiles] = graph
        return graph

    def __getitem__(self, item):
        smiles = self.smiles[item]
        protein = self.proteins[item]
        encoded_protein = self.protein_cache.get(protein)
        if encoded_protein is None:
            encoded_protein = self.integer_label_protein(protein)
            self.protein_cache[protein] = encoded_protein
        return self._graph(smiles), encoded_protein, self.labels[item]


def best_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    candidates = np.unique(probabilities)
    if len(candidates) > 512:
        candidates = np.quantile(probabilities, np.linspace(0.01, 0.99, 512))
    scores = [f1_score(labels, probabilities >= threshold, zero_division=0) for threshold in candidates]
    return float(candidates[int(np.argmax(scores))]) if len(candidates) else 0.5


def predict(model, loader, device: torch.device, binary_cross_entropy):
    model.eval()
    labels, probabilities = [], []
    with torch.no_grad():
        for graph, protein, y in loader:
            graph, protein = graph.to(device), protein.to(device)
            _, _, logits, _ = model(graph, protein, mode="eval")
            probability, _ = binary_cross_entropy(logits, y.float().to(device))
            labels.extend(y.numpy().tolist())
            probabilities.extend(probability.detach().cpu().numpy().tolist())
    return np.asarray(labels, dtype=np.int64), np.asarray(probabilities, dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--dataset", required=True, choices=("biosnap", "human", "bindingdb"))
    parser.add_argument("--scenario", required=True, choices=("random", "cold_drug", "cold_protein", "cold_pair"))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--fold", type=int, required=True, choices=range(5))
    parser.add_argument("--drugban-source", default="/mnt/sda/fulaiyi/baseline_repos/DrugBAN")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--profile-epoch-components",
        action="store_true",
        help="Log train and validation durations at the existing epoch reporting cadence.",
    )
    parser.add_argument(
        "--no-tf32",
        dest="tf32",
        action="store_false",
        help="Disable TensorFloat-32 matrix math on compatible CUDA GPUs.",
    )
    parser.add_argument(
        "--no-input-cache",
        dest="input_cache",
        action="store_false",
        help="Use the original per-example SMILES/protein preprocessing (slower).",
    )
    parser.set_defaults(input_cache=True, tf32=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    fold_root = root / "drugban_splits" / args.dataset / args.scenario / f"seed{args.seed}_fold{args.fold}"
    manifest_path = fold_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Run prepare_drugban_splits.py first: {manifest_path}")
    with manifest_path.open(encoding="utf-8") as handle:
        split_manifest = json.load(handle)
    (
        get_cfg_defaults,
        DTIDataset,
        DrugBAN,
        binary_cross_entropy,
        graph_collate_func,
        integer_label_protein,
    ) = import_drugban(Path(args.drugban_source))
    device = torch.device(args.device)
    run_seed = stable_seed("drugban", args.dataset, args.scenario, args.seed, args.fold)
    seed_everything(run_seed)
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = args.tf32
        torch.backends.cudnn.allow_tf32 = args.tf32
        torch.set_float32_matmul_precision("high" if args.tf32 else "highest")
    cfg = get_cfg_defaults()
    cfg.SOLVER.BATCH_SIZE = args.batch_size
    cfg.SOLVER.LR = args.lr
    cfg.SOLVER.MAX_EPOCH = args.epochs
    cfg.RESULT.SAVE_MODEL = False

    frames = {partition: pd.read_csv(fold_root / f"{partition}.csv") for partition in ("train", "val", "test")}
    if args.input_cache:
        reference = {
            partition: DTIDataset(frame.index.values, frame)
            for partition, frame in frames.items()
        }
        datasets = {
            partition: CachedDTIDataset(
                frame.index.values, frame, reference[partition], integer_label_protein
            )
            for partition, frame in frames.items()
        }
    else:
        datasets = {partition: DTIDataset(frame.index.values, frame) for partition, frame in frames.items()}
    loaders = {
        "train": DataLoader(datasets["train"], batch_size=args.batch_size, shuffle=True, drop_last=True, num_workers=0, collate_fn=graph_collate_func),
        "val": DataLoader(datasets["val"], batch_size=args.batch_size, shuffle=False, drop_last=False, num_workers=0, collate_fn=graph_collate_func),
        "test": DataLoader(datasets["test"], batch_size=args.batch_size, shuffle=False, drop_last=False, num_workers=0, collate_fn=graph_collate_func),
    }
    model = DrugBAN(**cfg).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    best_auc = -np.inf
    best_state = None
    best_val_probability = None

    run_started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        epoch_started = time.perf_counter()
        model.train()
        for graph, protein, y in loaders["train"]:
            graph, protein, y = graph.to(device), protein.to(device), y.float().to(device)
            optimizer.zero_grad(set_to_none=True)
            _, _, _, logits = model(graph, protein)
            _, loss = binary_cross_entropy(logits, y)
            loss.backward()
            optimizer.step()
        train_seconds = time.perf_counter() - epoch_started
        validation_started = time.perf_counter()
        val_y, val_probability = predict(model, loaders["val"], device, binary_cross_entropy)
        val_auc = roc_auc_score(val_y, val_probability)
        validation_seconds = time.perf_counter() - validation_started
        if val_auc > best_auc:
            best_auc = float(val_auc)
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            best_val_probability = val_probability.copy()
        if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs:
            component_profile = (
                f" train_s={train_seconds:.1f} val_s={validation_seconds:.1f}"
                if args.profile_epoch_components
                else ""
            )
            print(
                f"[DrugBAN] epoch={epoch}/{args.epochs} val_auc={val_auc:.6f} "
                f"best_val_auc={best_auc:.6f} epoch_s={time.perf_counter() - epoch_started:.1f} "
                f"elapsed_s={time.perf_counter() - run_started:.1f} "
                f"cached_drugs={len(getattr(datasets['train'], 'drug_graph_cache', {}))}"
                f"{component_profile}",
                flush=True,
            )

    if best_state is None or best_val_probability is None:
        raise RuntimeError("DrugBAN did not produce a validation checkpoint.")
    model.load_state_dict(best_state)
    test_y, test_probability = predict(model, loaders["test"], device, binary_cross_entropy)
    threshold = best_threshold(frames["val"]["Y"].to_numpy(), best_val_probability)
    metrics = {
        "auc": float(roc_auc_score(test_y, test_probability)),
        "aupr": float(average_precision_score(test_y, test_probability)),
        "f1": float(f1_score(test_y, test_probability >= threshold, zero_division=0)),
        "accuracy": float(accuracy_score(test_y, test_probability >= threshold)),
        "threshold": threshold,
    }
    source_split = Path(split_manifest["source_split"])
    source_hash = hashlib.sha256(source_split.read_bytes()).hexdigest()
    payload = {
        "pipeline_version": "paper-benchmark-v2",
        "method": "drugban",
        "method_label": "DrugBAN",
        "dataset": args.dataset,
        "scenario": args.scenario,
        "seed": args.seed,
        "fold": args.fold,
        "n_folds": 5,
        "split_signature": split_manifest["split_signature"],
        "split_npz_sha256": source_hash,
        "best_val_auc": best_auc,
        "metrics": metrics,
        "n_train": int(len(frames["train"])),
        "n_val": int(len(frames["val"])),
        "n_test": int(len(frames["test"])),
        "n_train_positive": int(frames["train"]["Y"].sum()),
        "n_val_positive": int(frames["val"]["Y"].sum()),
        "n_test_positive": int(frames["test"]["Y"].sum()),
        "settings": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "input_cache": args.input_cache,
            "tf32": args.tf32,
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
            "validation_selection": "AUC",
            "f1_threshold": "maximal validation F1",
        },
    }
    output = root / "results" / "drugban" / args.dataset / args.scenario / f"seed{args.seed}_fold{args.fold}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    temporary.replace(output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
