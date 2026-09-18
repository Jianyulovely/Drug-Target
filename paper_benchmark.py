#!/usr/bin/env python3
"""Reproducible paper benchmark for the ArnoldiGCL-S1/S2 DTI project.

This runner deliberately does *not* overwrite the exploratory V7/V9 scripts.
It freezes positive splits and unique negative samples once, then evaluates all
methods on exactly the same data.  Each partition uses at most 10 negatives per
positive; in a dense cold-pair block where fewer unique candidates exist, all
available unannotated pairs are used rather than duplicating examples.  The
graph for each neural method contains only training positive DTI edges and
similarity edges among training entities.

Methods
-------
lr                 Logistic regression on [Morgan || ESM-2]
mlp                Plain MLP on [Morgan || ESM-2]
gcn                Supervised GCN with the leak-safe KNN graph
colddti            Supervised threshold-similarity GCN (threshold = 0.3)
arnoldi_v4         ArnoldiGCL structure encoder without S1/S2
arnoldi_s1         ArnoldiGCL + S1 only (S2 zero-padded)
arnoldi_s2         ArnoldiGCL + S2 only (S1 zero-padded)
arnoldi_s12        ArnoldiGCL + S1+S2
arnoldi_s12_shuffle ArnoldiGCL + partition-wise shuffled S1+S2 control

The original research code is imported read-only from DTI_CORE_PATH.  It
supplies dataset loading, cached features, the graph builders and the
ArnoldiGCL layers; all splitting, negative sampling, deterministic seeding,
side-feature construction and reporting are implemented here.
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
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler


PIPELINE_VERSION = "paper-benchmark-v2"
NEG_PER_POS = 10
SEEDS = [1941488137, 4198936517, 983997847]
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")
M8_METHODS = {
    "arnoldi_v4",
    "arnoldi_s1",
    "arnoldi_s2",
    "arnoldi_s12",
    "arnoldi_s12_shuffle",
}
ALL_METHODS = (
    "lr",
    "mlp",
    "gcn",
    "colddti",
    "arnoldi_v4",
    "arnoldi_s1",
    "arnoldi_s2",
    "arnoldi_s12",
    "arnoldi_s12_shuffle",
)
METHOD_LABELS = {
    "lr": "Logistic regression (Morgan+ESM-2)",
    "mlp": "MLP (Morgan+ESM-2)",
    "gcn": "GCN (leak-safe KNN graph)",
    "colddti": "Threshold GCN (similarity threshold 0.3)",
    "arnoldi_v4": "ArnoldiGCL without S1/S2",
    "arnoldi_s1": "ArnoldiGCL + S1",
    "arnoldi_s2": "ArnoldiGCL + S2",
    "arnoldi_s12": "ArnoldiGCL + S1+S2",
    "arnoldi_s12_shuffle": "ArnoldiGCL + shuffled S1+S2",
}


def stable_seed(*items: object) -> int:
    """Return a process-independent 32-bit seed."""
    payload = "|".join(str(item) for item in items).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # CuDNN benchmark selection changes kernels across shapes/runs.
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def import_core():
    core_path = Path(
        os.environ.get("DTI_CORE_PATH", "/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py")
    )
    if not core_path.is_file():
        raise FileNotFoundError(
            f"Cannot find the read-only project core at {core_path}. "
            "Set DTI_CORE_PATH to cross_dataset_v9_cold_aware.py."
        )
    spec = importlib.util.spec_from_file_location("dti_project_core", core_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {core_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _split_positive_pairs(
    A: np.ndarray, seed: int, scenario: str, fold: int, n_folds: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create one outer fold and a fold-local inner validation partition."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    n_drug, n_protein = A.shape
    positives = np.argwhere(A > 0).astype(np.int64, copy=False)
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=seed)
    rng = np.random.default_rng(stable_seed("inner-validation", seed, scenario, fold))

    if scenario == "random":
        train_idx, test_idx = list(kf.split(positives))[fold]
        train_val = positives[train_idx].copy()
        rng.shuffle(train_val)
        n_val = max(1, int(round(len(train_val) * 0.10)))
        return train_val[n_val:], train_val[:n_val], positives[test_idx]

    if scenario == "cold_drug":
        drug_ids = np.arange(n_drug)
        train_idx, test_idx = list(kf.split(drug_ids))[fold]
        train_val_drugs = drug_ids[train_idx].copy()
        rng.shuffle(train_val_drugs)
        n_val = max(1, int(round(len(train_val_drugs) * 0.10)))
        val_drugs, train_drugs = train_val_drugs[:n_val], train_val_drugs[n_val:]
        return (
            positives[np.isin(positives[:, 0], train_drugs)],
            positives[np.isin(positives[:, 0], val_drugs)],
            positives[np.isin(positives[:, 0], drug_ids[test_idx])],
        )

    if scenario == "cold_protein":
        protein_ids = np.arange(n_protein)
        train_idx, test_idx = list(kf.split(protein_ids))[fold]
        train_val_proteins = protein_ids[train_idx].copy()
        rng.shuffle(train_val_proteins)
        n_val = max(1, int(round(len(train_val_proteins) * 0.10)))
        val_proteins, train_proteins = (
            train_val_proteins[:n_val],
            train_val_proteins[n_val:],
        )
        return (
            positives[np.isin(positives[:, 1], train_proteins)],
            positives[np.isin(positives[:, 1], val_proteins)],
            positives[np.isin(positives[:, 1], protein_ids[test_idx])],
        )

    # cold_pair: diagonal blocks of jointly unseen drugs and proteins.  Pairs
    # outside train/validation/test blocks are deliberately not used.
    drug_ids = np.arange(n_drug)
    protein_ids = np.arange(n_protein)
    d_train_idx, d_test_idx = list(kf.split(drug_ids))[fold]
    p_train_idx, p_test_idx = list(kf.split(protein_ids))[fold]
    train_val_drugs = drug_ids[d_train_idx].copy()
    train_val_proteins = protein_ids[p_train_idx].copy()
    rng.shuffle(train_val_drugs)
    rng.shuffle(train_val_proteins)
    n_val_d = max(1, int(round(len(train_val_drugs) * 0.10)))
    n_val_p = max(1, int(round(len(train_val_proteins) * 0.10)))
    val_d, train_d = train_val_drugs[:n_val_d], train_val_drugs[n_val_d:]
    val_p, train_p = train_val_proteins[:n_val_p], train_val_proteins[n_val_p:]

    def in_block(drugs: np.ndarray, proteins: np.ndarray) -> np.ndarray:
        return positives[
            np.isin(positives[:, 0], drugs) & np.isin(positives[:, 1], proteins)
        ]

    return (
        in_block(train_d, train_p),
        in_block(val_d, val_p),
        in_block(drug_ids[d_test_idx], protein_ids[p_test_idx]),
    )


def _sample_unique_negatives(
    A: np.ndarray,
    drug_pool: np.ndarray,
    protein_pool: np.ndarray,
    n_samples: int,
    rng: np.random.Generator,
    used: set[Tuple[int, int]],
) -> np.ndarray:
    """Sample up to ``n_samples`` unique unannotated pairs without replacement."""
    drug_pool = np.asarray(drug_pool, dtype=np.int64)
    protein_pool = np.asarray(protein_pool, dtype=np.int64)
    if n_samples == 0:
        return np.empty((0, 2), dtype=np.int64)
    available = int((A[np.ix_(drug_pool, protein_pool)] == 0).sum())
    # A few dense cold-pair blocks do not contain ten distinct unknown pairs
    # per positive.  Keeping each negative unique is preferable to silently
    # duplicating test observations; the realised partition size is persisted
    # in its result JSON and is common to every compared method.
    requested = n_samples
    n_samples = min(n_samples, available)

    chosen: List[Tuple[int, int]] = []
    chosen_set: set[Tuple[int, int]] = set()
    # Rejection sampling is much faster than materialising a large cartesian
    # product for these sparse DTI matrices.  A deterministic fallback handles
    # unusually dense pools.
    max_attempts = max(n_samples * 100, 10000)
    attempts = 0
    while len(chosen) < n_samples and attempts < max_attempts:
        d = int(drug_pool[rng.integers(len(drug_pool))])
        p = int(protein_pool[rng.integers(len(protein_pool))])
        pair = (d, p)
        if A[d, p] == 0 and pair not in used and pair not in chosen_set:
            chosen.append(pair)
            chosen_set.add(pair)
        attempts += 1

    if len(chosen) < n_samples:
        for d in drug_pool:
            candidates = protein_pool[A[d, protein_pool] == 0]
            for p in candidates:
                pair = (int(d), int(p))
                if pair in used or pair in chosen_set:
                    continue
                chosen.append(pair)
                chosen_set.add(pair)
                if len(chosen) == n_samples:
                    break
            if len(chosen) == n_samples:
                break
    if len(chosen) != n_samples:
        raise RuntimeError("Negative sampling unexpectedly exhausted the candidate pool.")
    if n_samples < requested:
        print(
            f"  negative pool saturated: requested={requested}, available={n_samples}; "
            "using all unique negatives",
            flush=True,
        )
    used.update(chosen_set)
    return np.asarray(chosen, dtype=np.int64)


def _negative_pools(
    positives: np.ndarray, scenario: str, A: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    if scenario == "cold_drug":
        return np.unique(positives[:, 0]), np.arange(A.shape[1])
    if scenario == "cold_protein":
        return np.arange(A.shape[0]), np.unique(positives[:, 1])
    if scenario == "cold_pair":
        return np.unique(positives[:, 0]), np.unique(positives[:, 1])
    return np.arange(A.shape[0]), np.arange(A.shape[1])


def make_split(A: np.ndarray, dataset: str, scenario: str, seed: int, fold: int, n_folds: int) -> Dict[str, np.ndarray]:
    train_pos, val_pos, test_pos = _split_positive_pairs(A, seed, scenario, fold, n_folds)
    if min(len(train_pos), len(val_pos), len(test_pos)) == 0:
        raise RuntimeError(
            f"Empty positive partition for {dataset}/{scenario}/seed={seed}/fold={fold}: "
            f"train={len(train_pos)}, val={len(val_pos)}, test={len(test_pos)}"
        )
    rng = np.random.default_rng(stable_seed("negative-sampling", dataset, scenario, seed, fold))
    used: set[Tuple[int, int]] = set()
    # Test and validation pairs are allocated first.  This makes the held-out
    # negative sets invariant to future changes in training-set size.
    pieces: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for name, pos in (("test", test_pos), ("val", val_pos), ("train", train_pos)):
        d_pool, p_pool = _negative_pools(pos, scenario, A)
        neg = _sample_unique_negatives(A, d_pool, p_pool, len(pos) * NEG_PER_POS, rng, used)
        pieces[name] = (pos, neg)

    result: Dict[str, np.ndarray] = {
        "train_pos": train_pos,
        "val_pos": val_pos,
        "test_pos": test_pos,
    }
    for name, (pos, neg) in pieces.items():
        result[f"{name}_pairs"] = np.concatenate([pos, neg], axis=0)
        result[f"{name}_y"] = np.concatenate(
            [np.ones(len(pos), dtype=np.float32), np.zeros(len(neg), dtype=np.float32)]
        )
    return result


def split_signature(split: Mapping[str, np.ndarray]) -> str:
    h = hashlib.sha256()
    for key in ("train_pairs", "val_pairs", "test_pairs"):
        array = np.ascontiguousarray(split[key], dtype=np.int64)
        h.update(key.encode("utf-8"))
        h.update(array.tobytes())
    return h.hexdigest()


def split_path(root: Path, dataset: str, scenario: str, seed: int, fold: int) -> Path:
    return root / "splits" / dataset / scenario / f"seed{seed}_fold{fold}.npz"


def load_or_make_split(
    root: Path, A: np.ndarray, dataset: str, scenario: str, seed: int, fold: int, n_folds: int
) -> Dict[str, np.ndarray]:
    path = split_path(root, dataset, scenario, seed, fold)
    if path.is_file():
        with np.load(path, allow_pickle=False) as source:
            cached = {name: source[name] for name in source.files}
        required = {"train_pos", "val_pos", "test_pos", "train_pairs", "val_pairs", "test_pairs", "train_y", "val_y", "test_y"}
        if required.issubset(cached):
            return cached
        raise RuntimeError(f"Existing split cache has an incompatible schema: {path}")
    split = make_split(A, dataset, scenario, seed, fold, n_folds)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **split)
    return split


def load_dataset_and_features(core, dataset: str) -> Dict[str, object]:
    A, drug_ids, protein_ids, _ = core.load_dataset(dataset)
    feature_dir = Path(core.DATA_DIR) / f"{dataset}_features"
    morgan_path = feature_dir / "drug_morgan.npy"
    esm_paths = sorted(feature_dir.glob("prot_esm2_*.npy"))
    if not morgan_path.is_file() or not esm_paths:
        raise FileNotFoundError(
            f"Cached features are required for the paper benchmark: {feature_dir}"
        )
    # The project used ESM-2 t30/150M (640 dimensions); fail loudly if a cache
    # from a different encoder is the only available option.
    esm_path = next((p for p in esm_paths if "t30_150M" in p.name), esm_paths[0])
    morgan = np.load(morgan_path).astype(np.float32, copy=False)
    esm2 = np.load(esm_path).astype(np.float32, copy=False)
    if morgan.shape[0] != A.shape[0] or esm2.shape[0] != A.shape[1]:
        raise RuntimeError(f"Feature/cache dimensions do not match {dataset}.")
    Sd, Sp = core.load_similarity(morgan, esm2)
    return {
        "A": A,
        "drug_ids": drug_ids,
        "protein_ids": protein_ids,
        "morgan": morgan,
        "esm2": esm2,
        "Sd": Sd,
        "Sp": Sp,
    }


def _nearest_by_similarity(
    similarity: np.ndarray, queries: np.ndarray, pool: np.ndarray, k: int
) -> Dict[int, np.ndarray]:
    """Top-k in pool for each query, always excluding the candidate itself."""
    pool = np.asarray(pool, dtype=np.int64)
    if len(pool) < 2:
        raise RuntimeError("A side-feature neighbourhood needs at least two training entities.")
    lookup: Dict[int, np.ndarray] = {}
    for query in np.unique(queries):
        scores = similarity[int(query), pool].copy()
        contains_query = bool(np.any(pool == query))
        if contains_query:
            scores[pool == query] = -np.inf
        k_eff = min(k, len(pool) - int(contains_query))
        local = np.argpartition(-scores, k_eff - 1)[:k_eff]
        # Deterministic order for tied fingerprint similarities.
        local = local[np.lexsort((pool[local], -scores[local]))]
        lookup[int(query)] = pool[local]
    return lookup


def compute_side_features(
    pairs: np.ndarray,
    A_train: np.ndarray,
    Sd: np.ndarray,
    Sp: np.ndarray,
    train_drugs: np.ndarray,
    train_proteins: np.ndarray,
    batch_size: int = 16384,
) -> np.ndarray:
    """Compute leakage-safe S1/S2 with self exclusion for both modules.

    S1 contains neighbour rate/rate-variance descriptors (4 dimensions).
    S2 contains d-to-p, p-to-d and cross-neighbour consistency (3 dimensions).
    All values use only positive train DTI edges in ``A_train``.
    """
    if len(pairs) == 0:
        return np.empty((0, 7), dtype=np.float32)
    drugs = pairs[:, 0]
    proteins = pairs[:, 1]
    d_s1 = _nearest_by_similarity(Sd, drugs, train_drugs, 10)
    p_s1 = _nearest_by_similarity(Sp, proteins, train_proteins, 10)
    d_s2 = _nearest_by_similarity(Sd, drugs, train_drugs, 20)
    p_s2 = _nearest_by_similarity(Sp, proteins, train_proteins, 20)
    side = np.empty((len(pairs), 7), dtype=np.float32)

    for start in range(0, len(pairs), batch_size):
        stop = min(start + batch_size, len(pairs))
        d = drugs[start:stop]
        p = proteins[start:stop]
        nd1 = np.stack([d_s1[int(item)] for item in d])
        np1 = np.stack([p_s1[int(item)] for item in p])
        nd2 = np.stack([d_s2[int(item)] for item in d])
        np2 = np.stack([p_s2[int(item)] for item in p])

        d_to_p_s1 = A_train[nd1, p[:, None]]
        cross_s1 = A_train[nd1[:, :, None], np1[:, None, :]]
        d_to_p_s2 = A_train[nd2, p[:, None]]
        p_to_d_s2 = A_train[d[:, None], np2]
        cross_s2 = A_train[nd2[:, :, None], np2[:, None, :]]
        side[start:stop] = np.column_stack(
            [
                d_to_p_s1.mean(axis=1),
                cross_s1.mean(axis=(1, 2)),
                d_to_p_s1.std(axis=1),
                cross_s1.std(axis=(1, 2)),
                d_to_p_s2.mean(axis=1),
                p_to_d_s2.mean(axis=1),
                cross_s2.mean(axis=(1, 2)),
            ]
        )
    return side


def best_threshold(y_true: np.ndarray, probability: np.ndarray) -> float:
    values = np.unique(probability)
    if len(values) > 512:
        values = np.quantile(probability, np.linspace(0.01, 0.99, 512))
    scores = [f1_score(y_true, probability >= value, zero_division=0) for value in values]
    return float(values[int(np.argmax(scores))]) if len(values) else 0.5


def score_predictions(y_true: np.ndarray, probability: np.ndarray, threshold: float) -> Dict[str, float]:
    label = (probability >= threshold).astype(int)
    return {
        "auc": float(roc_auc_score(y_true, probability)),
        "aupr": float(average_precision_score(y_true, probability)),
        "f1": float(f1_score(y_true, label, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, label)),
        "threshold": float(threshold),
    }


def pair_tensor(pairs: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.as_tensor(pairs, dtype=torch.long, device=device)


class RawPairMLP(nn.Module):
    """Plain feature-only baseline with direct Morgan/ESM-2 concatenation."""

    def __init__(self, morgan_dim: int, esm_dim: int, dropout: float = 0.5):
        super().__init__()
        in_dim = morgan_dim + esm_dim
        self.network = nn.Sequential(
            nn.Linear(in_dim, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, 1),
        )

    def forward(self, drug_x: torch.Tensor, protein_x: torch.Tensor, pairs: torch.Tensor) -> torch.Tensor:
        feature = torch.cat([drug_x[pairs[:, 0]], protein_x[pairs[:, 1]]], dim=1)
        return self.network(feature).squeeze(1)


class ChunkedSimpleGCNLayer(nn.Module):
    """Mathematically equivalent, memory-bounded version of ``SimpleGCNLayer``.

    The project-core implementation materializes one ``[n_edges + n_nodes,
    hidden_dim]`` tensor before ``index_add_``.  That is impractical for the
    dense threshold graph used by the threshold-GCN comparator on BindingDB.
    This layer preserves the same self-loop, degree normalization and message
    aggregation equations, but streams edge messages in bounded chunks.
    """

    def __init__(
        self, in_dim: int, out_dim: int, edge_chunk_size: int, linear_layer: nn.Module | None = None
    ):
        super().__init__()
        if edge_chunk_size < 1:
            raise ValueError("edge_chunk_size must be positive")
        # For the benchmark, ``linear_layer`` comes from a freshly constructed
        # project-core SimpleGCNLayer.  This preserves its parameterization and
        # seeded initialization exactly; only aggregation storage changes.
        self.lin = linear_layer if linear_layer is not None else nn.Linear(in_dim, out_dim)
        self.edge_chunk_size = edge_chunk_size

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        n_nodes = x.shape[0]
        # Keep graph metadata on CPU.  A dense threshold graph can contain
        # far more edges than fit on one GPU even when messages are chunked.
        edge_index_cpu = edge_index.detach().to(device="cpu")
        row, col = edge_index_cpu
        degree = torch.ones(n_nodes, dtype=x.dtype, device="cpu")
        degree.scatter_add_(0, row, torch.ones(row.numel(), dtype=x.dtype))
        degree = degree.clamp(min=1)
        inv_sqrt_degree = degree.pow(-0.5)
        edge_norm = inv_sqrt_degree[row] * inv_sqrt_degree[col]
        self_norm = inv_sqrt_degree.square()

        transformed = self.lin(x)
        out = torch.zeros_like(transformed)
        for start in range(0, row.numel(), self.edge_chunk_size):
            stop = min(start + self.edge_chunk_size, row.numel())
            chunk_row = row[start:stop].to(device=x.device)
            chunk_col = col[start:stop].to(device=x.device)
            messages = transformed[chunk_col] * edge_norm[start:stop].to(device=x.device).unsqueeze(-1)
            out.index_add_(0, chunk_row, messages)
        # Add self-loops separately, avoiding a second n-node concatenation.
        for start in range(0, n_nodes, self.edge_chunk_size):
            stop = min(start + self.edge_chunk_size, n_nodes)
            nodes = torch.arange(start, stop, device=x.device)
            out.index_add_(
                0,
                nodes,
                transformed[nodes] * self_norm[start:stop].to(device=x.device).unsqueeze(-1),
            )
        return out


class ChunkedGCNEncoder(nn.Module):
    """Two-layer GCN encoder with the project-core architecture and activation."""

    def __init__(
        self, in_dim: int, hidden_dim: int, out_dim: int, *, dropout: float, n_layers: int,
        edge_chunk_size: int, linear_factory,
    ):
        super().__init__()
        layers = [
            ChunkedSimpleGCNLayer(
                in_dim, hidden_dim, edge_chunk_size, linear_factory(in_dim, hidden_dim)
            )
        ]
        layers.extend(
            ChunkedSimpleGCNLayer(
                hidden_dim, out_dim, edge_chunk_size, linear_factory(hidden_dim, out_dim)
            )
            for _ in range(n_layers - 1)
        )
        self.layers = nn.ModuleList(layers)
        self.dropout = dropout
        self.act = nn.PReLU()

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = x
        for index, layer in enumerate(self.layers):
            h = self.act(layer(h, edge_index))
            if index < len(self.layers) - 1:
                h = F.dropout(h, p=self.dropout, training=self.training)
        return h


class SparseNormalizedGCNLayer(nn.Module):
    """The project-core GCN update implemented as sparse matrix multiplication."""

    def __init__(self, linear_layer: nn.Module):
        super().__init__()
        self.lin = linear_layer

    def forward(self, x: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        return torch.sparse.mm(adjacency, self.lin(x))


class SparseGCNEncoder(nn.Module):
    """Two-layer normalized GCN with a cached, static sparse training graph.

    The cache contains no learnable state.  It is built once for the frozen
    train graph of a fold and replaces the dense ``x[edge_index]`` message
    materialization in the project-core implementation.
    """

    def __init__(self, in_dim: int, hidden_dim: int, out_dim: int, *, dropout: float, n_layers: int, linear_factory):
        super().__init__()
        layers = [SparseNormalizedGCNLayer(linear_factory(in_dim, hidden_dim))]
        layers.extend(
            SparseNormalizedGCNLayer(linear_factory(hidden_dim, out_dim))
            for _ in range(n_layers - 1)
        )
        self.layers = nn.ModuleList(layers)
        self.dropout = dropout
        self.act = nn.PReLU()
        self._cached_edge_key: tuple[int, tuple[int, ...], str, torch.dtype] | None = None
        self._cached_adjacency: torch.Tensor | None = None

    def _normalized_adjacency(self, edge_index: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        key = (edge_index.data_ptr(), tuple(edge_index.shape), str(x.device), x.dtype)
        if self._cached_edge_key == key and self._cached_adjacency is not None:
            return self._cached_adjacency

        n_nodes = x.shape[0]
        cpu_edge_index = edge_index.detach().to(device="cpu")
        row, col = cpu_edge_index
        nodes = torch.arange(n_nodes, dtype=torch.long, device="cpu")
        all_row = torch.cat((row, nodes))
        all_col = torch.cat((col, nodes))
        degree = torch.bincount(all_row, minlength=n_nodes).to(dtype=x.dtype)
        inv_sqrt_degree = degree.clamp(min=1).rsqrt()
        values = inv_sqrt_degree[all_row] * inv_sqrt_degree[all_col]
        adjacency = torch.sparse_coo_tensor(
            torch.stack((all_row, all_col)).to(device=x.device),
            values.to(device=x.device),
            size=(n_nodes, n_nodes),
            device=x.device,
        ).coalesce()
        self._cached_edge_key = key
        self._cached_adjacency = adjacency
        return adjacency

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        adjacency = self._normalized_adjacency(edge_index, x)
        h = x
        for index, layer in enumerate(self.layers):
            h = self.act(layer(h, adjacency))
            if index < len(self.layers) - 1:
                h = F.dropout(h, p=self.dropout, training=self.training)
        return h


class SupervisedGCN(nn.Module):
    """Feature encoder + GCN + residual pair scorer, trained end-to-end."""

    def __init__(self, core, morgan_dim: int, esm_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.feature_encoder = core.FeatureEncoder(morgan_dim, esm_dim, hidden_dim, dropout=dropout)
        # Store the static train graph as a normalized sparse matrix.  This is
        # algebraically the same update as the project-core index-add layer,
        # while avoiding a dense message matrix for every graph edge.
        self.encoder = SparseGCNEncoder(
            hidden_dim,
            hidden_dim,
            hidden_dim,
            dropout=dropout,
            n_layers=2,
            linear_factory=lambda in_dim, out_dim: core.SimpleGCNLayer(in_dim, out_dim).lin,
        )
        self.scorer = core.BaselineEdgeScorer(
            struct_dim=hidden_dim,
            morgan_dim=morgan_dim,
            esm2_dim=esm_dim,
            mlp_hidden=512,
            mlp_layers=3,
            dropout=dropout,
            use_morgan=True,
            use_esm2=True,
        )

    def forward(
        self,
        drug_x: torch.Tensor,
        protein_x: torch.Tensor,
        n_drug: int,
        edge_index: torch.Tensor,
        pairs: torch.Tensor,
    ) -> torch.Tensor:
        x = self.feature_encoder(drug_x, protein_x, n_drug, protein_x.shape[0], drug_x.device)
        h = self.encoder(x, edge_index)
        return self.scorer(
            h[pairs[:, 0]],
            drug_x[pairs[:, 0]],
            h[n_drug + pairs[:, 1]],
            protein_x[pairs[:, 1]],
        )


def train_with_validation(
    model: nn.Module,
    predict,
    train_y: torch.Tensor,
    val_y: np.ndarray,
    test_y: np.ndarray,
    epochs: int,
    lr: float,
    device: torch.device,
    positive_weight: float,
) -> Tuple[Dict[str, float], float]:
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(positive_weight, device=device))
    best_val_auc = -np.inf
    best_test_prob = None
    best_val_prob = None
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(predict("train"), train_y)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_prob = torch.sigmoid(predict("val")).detach().cpu().numpy()
            val_auc = roc_auc_score(val_y, val_prob)
            if val_auc > best_val_auc:
                best_val_auc = float(val_auc)
                best_val_prob = val_prob
                best_test_prob = torch.sigmoid(predict("test")).detach().cpu().numpy()
    if best_test_prob is None or best_val_prob is None:
        raise RuntimeError("No validation checkpoint was produced.")
    threshold = best_threshold(val_y, best_val_prob)
    return score_predictions(test_y, best_test_prob, threshold), float(best_val_auc)


def _score_gcn_pairs(
    model: SupervisedGCN,
    h: torch.Tensor,
    drug_x: torch.Tensor,
    protein_x: torch.Tensor,
    n_drug: int,
    pairs: torch.Tensor,
    pair_batch_size: int,
) -> torch.Tensor:
    """Score candidate pairs in bounded batches using a precomputed GCN state."""
    logits = []
    for start in range(0, len(pairs), pair_batch_size):
        current = pairs[start:start + pair_batch_size]
        logits.append(
            model.scorer(
                h[current[:, 0]],
                drug_x[current[:, 0]],
                h[n_drug + current[:, 1]],
                protein_x[current[:, 1]],
            )
        )
    return torch.cat(logits, dim=0)


def train_gcn_with_validation(
    model: SupervisedGCN,
    drug_x: torch.Tensor,
    protein_x: torch.Tensor,
    n_drug: int,
    edge_index: torch.Tensor,
    pair_map: Mapping[str, torch.Tensor],
    train_y: torch.Tensor,
    val_y: np.ndarray,
    test_y: np.ndarray,
    epochs: int,
    lr: float,
    device: torch.device,
    positive_weight: float,
    pair_batch_size: int,
) -> Tuple[Dict[str, float], float]:
    """Memory-bounded full-batch GCN optimization over pair mini-batches.

    Graph propagation is unchanged.  Pair scores are partitioned only to bound
    the temporary raw-feature tensors used by the residual edge scorer.  The
    per-batch BCE is accumulated as a size-weighted sum, exactly recovering the
    full-partition mean loss and its gradient.
    """
    if pair_batch_size < 1:
        raise ValueError("DTI_GCN_PAIR_BATCH must be positive.")
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(positive_weight, device=device),
        reduction="sum",
    )
    best_val_auc = -np.inf
    best_val_prob = None
    best_test_prob = None
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        x = model.feature_encoder(drug_x, protein_x, n_drug, protein_x.shape[0], drug_x.device)
        h = model.encoder(x, edge_index)
        total = len(pair_map["train"])
        for start in range(0, total, pair_batch_size):
            stop = min(start + pair_batch_size, total)
            logits = _score_gcn_pairs(
                model, h, drug_x, protein_x, n_drug, pair_map["train"][start:stop], pair_batch_size
            )
            # Every pair batch shares the same graph embedding ``h``.  Retain
            # that graph until the final slice, then release it normally.
            (loss_fn(logits, train_y[start:stop]) / total).backward(
                retain_graph=stop < total
            )
        optimizer.step()

        model.eval()
        with torch.no_grad():
            x = model.feature_encoder(drug_x, protein_x, n_drug, protein_x.shape[0], drug_x.device)
            h = model.encoder(x, edge_index)
            val_prob = torch.sigmoid(
                _score_gcn_pairs(model, h, drug_x, protein_x, n_drug, pair_map["val"], pair_batch_size)
            ).cpu().numpy()
            val_auc = roc_auc_score(val_y, val_prob)
            if val_auc > best_val_auc:
                best_val_auc = float(val_auc)
                best_val_prob = val_prob
                best_test_prob = torch.sigmoid(
                    _score_gcn_pairs(model, h, drug_x, protein_x, n_drug, pair_map["test"], pair_batch_size)
                ).cpu().numpy()
    if best_val_prob is None or best_test_prob is None:
        raise RuntimeError("No validation checkpoint was produced.")
    threshold = best_threshold(val_y, best_val_prob)
    return score_predictions(test_y, best_test_prob, threshold), float(best_val_auc)


def train_arnoldi_encoder(
    core,
    drug_x: torch.Tensor,
    protein_x: torch.Tensor,
    n_drug: int,
    edge_index: torch.Tensor,
    hidden_dim: int,
    epochs: int,
    dropout: float,
    dprate: float,
) -> Tuple[nn.Module, nn.Module, torch.Tensor]:
    feature_encoder = core.FeatureEncoder(drug_x.shape[1], protein_x.shape[1], hidden_dim, dropout=dropout).to(drug_x.device)
    model = core.ArnoldiModel(
        in_dim=hidden_dim,
        out_dim=hidden_dim,
        K=10,
        dprate=dprate,
        dropout=dropout,
        is_bns=False,
        act_fn="relu",
        use_alpha=False,
    ).to(drug_x.device)
    optimizer = torch.optim.Adam(
        [
            {"params": model.encoder.lin1.parameters(), "weight_decay": 0.0, "lr": 1e-3},
            {"params": model.disc.parameters(), "weight_decay": 0.0, "lr": 1e-3},
            {"params": model.encoder.prop1.parameters(), "weight_decay": 0.0, "lr": 1e-3},
            {"params": feature_encoder.parameters(), "weight_decay": 0.0, "lr": 1e-3},
        ]
    )
    n_nodes = n_drug + protein_x.shape[0]
    label = torch.cat(
        [torch.ones(n_nodes * 2, device=drug_x.device), torch.zeros(n_nodes * 2, device=drug_x.device)]
    )
    loss_fn = nn.BCEWithLogitsLoss()
    for _ in range(epochs):
        model.train()
        feature_encoder.train()
        optimizer.zero_grad(set_to_none=True)
        x = feature_encoder(drug_x, protein_x, n_drug, protein_x.shape[0], drug_x.device)
        shuffled = x[torch.randperm(n_nodes, device=drug_x.device)]
        output, _ = model(edge_index, x, shuffled)
        loss = loss_fn(output, label)
        loss.backward()
        optimizer.step()
    model.eval()
    feature_encoder.eval()
    with torch.no_grad():
        x = feature_encoder(drug_x, protein_x, n_drug, protein_x.shape[0], drug_x.device)
        embedding = model.get_embedding(edge_index, x)
    return feature_encoder, model, embedding


def evaluate_logistic(
    data: Mapping[str, object], split: Mapping[str, np.ndarray], method_seed: int
) -> Tuple[Dict[str, float], float]:
    morgan = data["morgan"]
    esm2 = data["esm2"]

    def pair_features(pairs: np.ndarray) -> np.ndarray:
        return np.concatenate([morgan[pairs[:, 0]], esm2[pairs[:, 1]]], axis=1)

    scaler = StandardScaler()
    train_x = scaler.fit_transform(pair_features(split["train_pairs"]))
    val_x = scaler.transform(pair_features(split["val_pairs"]))
    test_x = scaler.transform(pair_features(split["test_pairs"]))
    model = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=1000,
        solver="lbfgs",
        random_state=method_seed,
    )
    model.fit(train_x, split["train_y"])
    val_prob = model.predict_proba(val_x)[:, 1]
    test_prob = model.predict_proba(test_x)[:, 1]
    threshold = best_threshold(split["val_y"], val_prob)
    return score_predictions(split["test_y"], test_prob, threshold), float(roc_auc_score(split["val_y"], val_prob))


def evaluate_raw_mlp(
    data: Mapping[str, object], split: Mapping[str, np.ndarray], device: torch.device, seed: int, scorer_epochs: int
) -> Tuple[Dict[str, float], float]:
    seed_everything(seed)
    drug_x = torch.as_tensor(data["morgan"], dtype=torch.float32, device=device)
    protein_x = torch.as_tensor(data["esm2"], dtype=torch.float32, device=device)
    pair_map = {name: pair_tensor(split[f"{name}_pairs"], device) for name in ("train", "val", "test")}
    y = torch.as_tensor(split["train_y"], dtype=torch.float32, device=device)
    model = RawPairMLP(drug_x.shape[1], protein_x.shape[1]).to(device)
    positive_weight = float((len(split["train_y"]) - split["train_y"].sum()) / split["train_y"].sum())
    return train_with_validation(
        model,
        lambda partition: model(drug_x, protein_x, pair_map[partition]),
        y,
        split["val_y"],
        split["test_y"],
        scorer_epochs,
        1e-3,
        device,
        positive_weight,
    )


def evaluate_gcn(
    core,
    graph_kind: str,
    data: Mapping[str, object],
    split: Mapping[str, np.ndarray],
    device: torch.device,
    seed: int,
    scorer_epochs: int,
) -> Tuple[Dict[str, float], float]:
    seed_everything(seed)
    A = data["A"]
    if graph_kind == "knn":
        edge_index, _, _ = core.build_knn_graph_leakproof(A, data["Sd"], data["Sp"], split["train_pos"], 10, 10)
    elif graph_kind == "threshold":
        edge_index, _, _ = core.build_colddti_graph_leakproof(A, data["Sd"], data["Sp"], split["train_pos"], threshold=0.3)
    else:
        raise ValueError(graph_kind)
    drug_x = torch.as_tensor(data["morgan"], dtype=torch.float32, device=device)
    protein_x = torch.as_tensor(data["esm2"], dtype=torch.float32, device=device)
    # The encoder caches a normalized sparse adjacency for this frozen train graph.
    edge_t = torch.as_tensor(edge_index, dtype=torch.long, device="cpu")
    pair_map = {name: pair_tensor(split[f"{name}_pairs"], device) for name in ("train", "val", "test")}
    y = torch.as_tensor(split["train_y"], dtype=torch.float32, device=device)
    model = SupervisedGCN(core, drug_x.shape[1], protein_x.shape[1], 256, 0.5).to(device)
    positive_weight = float((len(split["train_y"]) - split["train_y"].sum()) / split["train_y"].sum())
    # BindingDB partitions can exceed 160,000 pairs.  Evaluating its edge
    # scorer in one tensor materializes very large raw Morgan batches.  Stream
    # score computation by pair mini-batch while reusing a single GCN embedding
    # per model pass; the BCE objective remains the mean over all examples.
    pair_batch_size = int(os.environ.get("DTI_GCN_PAIR_BATCH", "8192"))
    return train_gcn_with_validation(
        model,
        drug_x,
        protein_x,
        A.shape[0],
        edge_t,
        pair_map,
        y,
        split["val_y"],
        split["test_y"],
        scorer_epochs,
        1e-3,
        device,
        positive_weight,
        pair_batch_size,
    )


def _side_variant(
    method: str,
    side: np.ndarray,
    partition: str,
    dataset: str,
    scenario: str,
    seed: int,
    fold: int,
) -> np.ndarray:
    value = side.copy()
    if method == "arnoldi_s1":
        value[:, 4:] = 0.0
    elif method == "arnoldi_s2":
        value[:, :4] = 0.0
    elif method == "arnoldi_s12_shuffle":
        rng = np.random.default_rng(stable_seed("side-shuffle", dataset, scenario, seed, fold, partition))
        value = value[rng.permutation(len(value))]
    elif method != "arnoldi_s12":
        raise ValueError(method)
    return value


def evaluate_arnoldi_group(
    core,
    requested: Sequence[str],
    data: Mapping[str, object],
    split: Mapping[str, np.ndarray],
    dataset: str,
    scenario: str,
    seed: int,
    fold: int,
    device: torch.device,
    encoder_epochs: int,
    scorer_epochs: int,
) -> Dict[str, Tuple[Dict[str, float], float]]:
    """Train exactly one structure encoder and compare scorer-side ablations."""
    seed_everything(stable_seed("arnoldi-encoder", dataset, scenario, seed, fold))
    A = data["A"]
    edge_index, _, _ = core.build_knn_graph_leakproof(A, data["Sd"], data["Sp"], split["train_pos"], 10, 10)
    drug_x = torch.as_tensor(data["morgan"], dtype=torch.float32, device=device)
    protein_x = torch.as_tensor(data["esm2"], dtype=torch.float32, device=device)
    edge_t = torch.as_tensor(edge_index, dtype=torch.long, device=device)
    _, _, embedding = train_arnoldi_encoder(
        core, drug_x, protein_x, A.shape[0], edge_t, 256, encoder_epochs, 0.5, 0.5
    )
    embedding = embedding.detach()
    A_train = np.zeros_like(A, dtype=np.float32)
    A_train[split["train_pos"][:, 0], split["train_pos"][:, 1]] = 1.0
    train_drugs = np.unique(split["train_pos"][:, 0])
    train_proteins = np.unique(split["train_pos"][:, 1])
    side: Dict[str, np.ndarray] = {}
    for partition in ("train", "val", "test"):
        started = time.time()
        side[partition] = compute_side_features(
            split[f"{partition}_pairs"],
            A_train,
            data["Sd"],
            data["Sp"],
            train_drugs,
            train_proteins,
        )
        print(f"    side features: {partition} in {time.time() - started:.1f}s", flush=True)
    pair_map = {name: pair_tensor(split[f"{name}_pairs"], device) for name in ("train", "val", "test")}
    y = torch.as_tensor(split["train_y"], dtype=torch.float32, device=device)
    positive_weight = float((len(split["train_y"]) - split["train_y"].sum()) / split["train_y"].sum())
    results: Dict[str, Tuple[Dict[str, float], float]] = {}
    for method in requested:
        seed_everything(stable_seed("arnoldi-scorer", method, dataset, scenario, seed, fold))
        if method == "arnoldi_v4":
            scorer = core.BaselineEdgeScorer(
                256, drug_x.shape[1], protein_x.shape[1], mlp_hidden=512, mlp_layers=3,
                dropout=0.5, use_morgan=True, use_esm2=True,
            ).to(device)

            def predict(partition: str, scorer=scorer) -> torch.Tensor:
                pairs = pair_map[partition]
                return scorer(
                    embedding[pairs[:, 0]], drug_x[pairs[:, 0]],
                    embedding[A.shape[0] + pairs[:, 1]], protein_x[pairs[:, 1]],
                )
        else:
            scorer = core.ColdAwareEdgeScorerV8(
                256, drug_x.shape[1], protein_x.shape[1], side_feat_dim=7,
                mlp_hidden=512, mlp_layers=3, dropout=0.5,
                use_morgan=True, use_esm2=True, use_side=True, use_mediator=False,
            ).to(device)
            side_t = {
                partition: torch.as_tensor(
                    _side_variant(method, side[partition], partition, dataset, scenario, seed, fold),
                    dtype=torch.float32,
                    device=device,
                )
                for partition in ("train", "val", "test")
            }

            def predict(partition: str, scorer=scorer, side_t=side_t) -> torch.Tensor:
                pairs = pair_map[partition]
                return scorer(
                    embedding[pairs[:, 0]], drug_x[pairs[:, 0]],
                    embedding[A.shape[0] + pairs[:, 1]], protein_x[pairs[:, 1]],
                    side_feat=side_t[partition],
                )
        results[method] = train_with_validation(
            scorer,
            predict,
            y,
            split["val_y"],
            split["test_y"],
            scorer_epochs,
            1e-3,
            device,
            positive_weight,
        )
        del scorer
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return results


def result_path(root: Path, method: str, dataset: str, scenario: str, seed: int, fold: int) -> Path:
    return root / "results" / method / dataset / scenario / f"seed{seed}_fold{fold}.json"


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    temporary.replace(path)


def run_task(args: argparse.Namespace) -> None:
    requested = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    unknown = set(requested) - set(ALL_METHODS)
    if unknown:
        raise ValueError(f"Unknown method(s): {sorted(unknown)}")
    root = Path(args.root).expanduser().resolve()
    core = import_core()
    data = load_dataset_and_features(core, args.dataset)
    split = load_or_make_split(root, data["A"], args.dataset, args.scenario, args.seed, args.fold, args.n_folds)
    signature = split_signature(split)
    device = torch.device(args.device)
    print(
        f"[{PIPELINE_VERSION}] {args.dataset}/{args.scenario} seed={args.seed} fold={args.fold} "
        f"split={signature[:12]} methods={','.join(requested)} on {device}",
        flush=True,
    )
    results: Dict[str, Tuple[Dict[str, float], float]] = {}
    pending = [
        method for method in requested
        if args.overwrite or not result_path(root, method, args.dataset, args.scenario, args.seed, args.fold).is_file()
    ]
    if not pending:
        print("All requested result files already exist; nothing to do.", flush=True)
        return
    if "lr" in pending:
        results["lr"] = evaluate_logistic(
            data, split, stable_seed("lr", args.dataset, args.scenario, args.seed, args.fold)
        )
    if "mlp" in pending:
        results["mlp"] = evaluate_raw_mlp(
            data, split, device,
            stable_seed("mlp", args.dataset, args.scenario, args.seed, args.fold),
            args.scorer_epochs,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if "gcn" in pending:
        results["gcn"] = evaluate_gcn(
            core, "knn", data, split, device,
            stable_seed("gcn", args.dataset, args.scenario, args.seed, args.fold), args.scorer_epochs,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if "colddti" in pending:
        results["colddti"] = evaluate_gcn(
            core, "threshold", data, split, device,
            stable_seed("colddti", args.dataset, args.scenario, args.seed, args.fold), args.scorer_epochs,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    m8_requested = [method for method in pending if method in M8_METHODS]
    if m8_requested:
        results.update(
            evaluate_arnoldi_group(
                core, m8_requested, data, split, args.dataset, args.scenario, args.seed, args.fold,
                device, args.encoder_epochs, args.scorer_epochs,
            )
        )
    for method, (metrics, val_auc) in results.items():
        payload = {
            "pipeline_version": PIPELINE_VERSION,
            "method": method,
            "method_label": METHOD_LABELS[method],
            "dataset": args.dataset,
            "scenario": args.scenario,
            "seed": args.seed,
            "fold": args.fold,
            "n_folds": args.n_folds,
            "split_signature": signature,
            "n_train": int(len(split["train_y"])),
            "n_val": int(len(split["val_y"])),
            "n_test": int(len(split["test_y"])),
            "n_train_positive": int(len(split["train_pos"])),
            "n_val_positive": int(len(split["val_pos"])),
            "n_test_positive": int(len(split["test_pos"])),
            "best_val_auc": val_auc,
            "metrics": metrics,
            "settings": {
                "negative_per_positive": NEG_PER_POS,
                "encoder_epochs": args.encoder_epochs,
                "scorer_epochs": args.scorer_epochs,
                "knn_k_drug": 10,
                "knn_k_protein": 10,
                "colddti_similarity_threshold": 0.3,
                "gcn_aggregation": (
                    "cached sparse, mathematically equivalent normalized GCN"
                    if method in {"gcn", "colddti"} else "not applicable"
                ),
                "gcn_pair_batch_size": (
                    int(os.environ.get("DTI_GCN_PAIR_BATCH", "8192"))
                    if method in {"gcn", "colddti"} else None
                ),
                "side_self_exclusion": True,
                "validation_selection": "AUC",
                "f1_threshold": "maximal validation F1",
            },
        }
        output = result_path(root, method, args.dataset, args.scenario, args.seed, args.fold)
        write_json(output, payload)
        print(
            f"  {method:22s} AUC={metrics['auc']:.4f} AUPR={metrics['aupr']:.4f} "
            f"F1={metrics['f1']:.4f} -> {output}",
            flush=True,
        )


def freeze_splits(args: argparse.Namespace) -> None:
    core = import_core()
    root = Path(args.root).expanduser().resolve()
    datasets = tuple(item.strip() for item in args.datasets.split(",") if item.strip())
    scenarios = tuple(item.strip() for item in args.scenarios.split(",") if item.strip())
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    for dataset in datasets:
        data = load_dataset_and_features(core, dataset)
        for scenario in scenarios:
            for seed in seeds:
                for fold in range(args.n_folds):
                    split = load_or_make_split(root, data["A"], dataset, scenario, seed, fold, args.n_folds)
                    print(
                        f"frozen {dataset}/{scenario}/seed={seed}/fold={fold} "
                        f"{split_signature(split)[:12]}",
                        flush=True,
                    )


def aggregate(args: argparse.Namespace) -> None:
    root = Path(args.root).expanduser().resolve()
    rows: List[Dict[str, object]] = []
    for path in sorted((root / "results").glob("**/*.json")):
        with path.open(encoding="utf-8") as handle:
            item = json.load(handle)
        if item.get("pipeline_version") != PIPELINE_VERSION:
            continue
        # Keep the retained short DrugBAN smoke test out of the formal tables.
        # The formal B5 protocol is fixed at 100 epochs for every fold.
        if item.get("method") == "drugban":
            settings = item.get("settings", {})
            if (
                settings.get("epochs") != 100
                or settings.get("input_cache") is not True
                or settings.get("tf32") is not True
            ):
                continue
        row = {
            key: item[key]
            for key in ("method", "method_label", "dataset", "scenario", "seed", "fold", "split_signature", "best_val_auc", "n_test_positive")
        }
        row.update(item["metrics"])
        rows.append(row)
    if not rows:
        raise RuntimeError(f"No {PIPELINE_VERSION} results under {root / 'results'}.")
    raw = pd.DataFrame(rows)
    table_dir = root / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(table_dir / "fold_metrics.csv", index=False)
    metric_columns = ["auc", "aupr", "f1", "accuracy"]
    grouped = raw.groupby(["method", "method_label", "dataset", "scenario"], sort=True)
    summary = grouped[metric_columns].agg(["mean", "std", "count"])
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary = summary.reset_index()
    summary.to_csv(table_dir / "summary.csv", index=False)
    coverage = grouped.size().rename("n_completed").reset_index()
    coverage.to_csv(table_dir / "coverage.csv", index=False)
    print(f"Wrote {len(raw)} fold-level rows to {table_dir}", flush=True)
    print(summary.to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--dataset", choices=("biosnap", "human", "bindingdb"))
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--fold", type=int, choices=range(5))
    parser.add_argument("--methods", default=",".join(ALL_METHODS))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--encoder-epochs", type=int, default=50)
    parser.add_argument("--scorer-epochs", type=int, default=200)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--freeze-splits", action="store_true")
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--datasets", default="biosnap,human,bindingdb")
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in SEEDS))
    args = parser.parse_args()
    if args.freeze_splits or args.aggregate:
        return args
    required = (args.dataset, args.scenario, args.seed, args.fold)
    if any(value is None for value in required):
        parser.error("--dataset, --scenario, --seed and --fold are required for an evaluation task")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.freeze_splits:
        freeze_splits(arguments)
    elif arguments.aggregate:
        aggregate(arguments)
    else:
        run_task(arguments)
