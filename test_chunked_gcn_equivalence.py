#!/usr/bin/env python3
"""Verify memory-safe paper-baseline GCN aggregations match the core layer.

Usage on the server:
  DTI_CORE_PATH=/mnt/sda/fulaiyi/cross_dataset_v9_cold_aware.py \
    /mnt/sda/fulaiyi/aspect_env/bin/python test_chunked_gcn_equivalence.py
"""

from __future__ import annotations

import torch

import paper_benchmark as benchmark


def compare(device: torch.device) -> None:
    torch.manual_seed(20260827)
    core = benchmark.import_core()
    reference = core.SimpleGCNLayer(7, 5).to(device)
    chunked = benchmark.ChunkedSimpleGCNLayer(7, 5, edge_chunk_size=11).to(device)
    sparse = benchmark.SparseNormalizedGCNLayer(core.SimpleGCNLayer(7, 5).lin).to(device)
    chunked.lin.load_state_dict(reference.lin.state_dict())
    sparse.lin.load_state_dict(reference.lin.state_dict())

    edge_index = torch.tensor(
        [[0, 0, 1, 1, 2, 3, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 12, 13, 14],
         [1, 3, 0, 2, 1, 0, 6, 4, 5, 7, 6, 9, 10, 8, 8, 11, 10, 13, 12, 14]],
        dtype=torch.long,
        device=device,
    )
    reference_x = torch.randn(15, 7, device=device, requires_grad=True)
    chunked_x = reference_x.detach().clone().requires_grad_(True)
    sparse_x = reference_x.detach().clone().requires_grad_(True)
    probe = torch.randn(15, 5, device=device)

    cpu_edge_index = edge_index.detach().to(device="cpu")
    nodes = torch.arange(15, dtype=torch.long, device="cpu")
    all_row = torch.cat((cpu_edge_index[0], nodes))
    all_col = torch.cat((cpu_edge_index[1], nodes))
    degree = torch.bincount(all_row, minlength=15).to(dtype=reference_x.dtype)
    inv_sqrt_degree = degree.clamp(min=1).rsqrt()
    adjacency = torch.sparse_coo_tensor(
        torch.stack((all_row, all_col)).to(device=device),
        (inv_sqrt_degree[all_row] * inv_sqrt_degree[all_col]).to(device=device),
        size=(15, 15),
        device=device,
    )

    reference_out = reference(reference_x, edge_index)
    chunked_out = chunked(chunked_x, edge_index)
    sparse_out = sparse(sparse_x, adjacency)
    reference_loss = (reference_out * probe).sum()
    chunked_loss = (chunked_out * probe).sum()
    sparse_loss = (sparse_out * probe).sum()
    reference_loss.backward()
    chunked_loss.backward()
    sparse_loss.backward()

    tolerance = {"rtol": 5e-5, "atol": 5e-6} if device.type == "cuda" else {"rtol": 1e-6, "atol": 1e-7}
    torch.testing.assert_close(chunked_out, reference_out, **tolerance)
    torch.testing.assert_close(sparse_out, reference_out, **tolerance)
    torch.testing.assert_close(chunked_x.grad, reference_x.grad, **tolerance)
    torch.testing.assert_close(sparse_x.grad, reference_x.grad, **tolerance)
    torch.testing.assert_close(chunked.lin.weight.grad, reference.lin.weight.grad, **tolerance)
    torch.testing.assert_close(chunked.lin.bias.grad, reference.lin.bias.grad, **tolerance)
    torch.testing.assert_close(sparse.lin.weight.grad, reference.lin.weight.grad, **tolerance)
    torch.testing.assert_close(sparse.lin.bias.grad, reference.lin.bias.grad, **tolerance)
    print(f"PASS {device}: chunked and sparse forward/backward agree within {tolerance}")


if __name__ == "__main__":
    compare(torch.device("cpu"))
    if torch.cuda.is_available():
        compare(torch.device("cuda:0"))
