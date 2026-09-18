"""Smoke-test sparse normalized GCN aggregation on a real BindingDB fold.

This intentionally exercises the largest graph before the benchmark queue is
resumed.  It is diagnostic only: no benchmark outputs are written.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import torch

import paper_benchmark as benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="bindingdb", choices=["biosnap", "human", "bindingdb"])
    parser.add_argument("--scenario", default="random", choices=["random", "cold_drug", "cold_protein", "cold_pair"])
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--hidden-dim", type=int, default=256)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("This smoke test requires CUDA.")

    core = benchmark.import_core()
    data = benchmark.load_dataset_and_features(core, args.dataset)
    split = benchmark.make_split(
        data["A"],
        dataset=args.dataset,
        scenario=args.scenario,
        fold=args.fold,
        n_folds=5,
        seed=42,
    )
    edge_index, _, _ = core.build_colddti_graph_leakproof(
        data["A"], data["Sd"], data["Sp"], split["train_pos"], threshold=0.3
    )

    n_nodes = data["A"].shape[0] + data["A"].shape[1]
    row = torch.as_tensor(edge_index[0], dtype=torch.long, device="cpu")
    col = torch.as_tensor(edge_index[1], dtype=torch.long, device="cpu")
    nodes = torch.arange(n_nodes, dtype=torch.long, device="cpu")
    all_row = torch.cat((row, nodes))
    all_col = torch.cat((col, nodes))
    degree = torch.bincount(all_row, minlength=n_nodes).to(dtype=torch.float32)
    values = degree.rsqrt()[all_row] * degree.rsqrt()[all_col]

    device = torch.device("cuda")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    adjacency = torch.sparse_coo_tensor(
        torch.stack((all_row, all_col)).to(device=device),
        values.to(device=device),
        size=(n_nodes, n_nodes),
        device=device,
    ).coalesce()
    build_seconds = time.perf_counter() - started

    features = torch.randn(n_nodes, args.hidden_dim, device=device, requires_grad=True)
    started = time.perf_counter()
    output = torch.sparse.mm(adjacency, features)
    forward_seconds = time.perf_counter() - started
    started = time.perf_counter()
    output.square().mean().backward()
    backward_seconds = time.perf_counter() - started

    peak_mib = torch.cuda.max_memory_allocated(device) / 1024**2
    print(
        "sparse aggregation smoke passed "
        f"dataset={args.dataset} scenario={args.scenario} fold={args.fold} "
        f"nodes={n_nodes} edges={edge_index.shape[1]} nnz={adjacency._nnz()} "
        f"build_s={build_seconds:.2f} forward_s={forward_seconds:.2f} "
        f"backward_s={backward_seconds:.2f} peak_mib={peak_mib:.1f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
