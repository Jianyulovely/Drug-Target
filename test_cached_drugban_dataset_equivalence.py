#!/usr/bin/env python3
"""Check the cached DrugBAN dataset preserves legacy positional row inputs."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch

from run_drugban_fold import CachedDTIDataset


class DummyGraph:
    def __init__(self, smiles: str):
        self.smiles = smiles
        self.ndata = {"h": torch.full((2, 74), float(len(smiles)))}
        self.added_nodes: int | None = None

    def add_nodes(self, count, data):
        self.added_nodes = int(count)
        self.ndata.update(data)

    def add_self_loop(self):
        return self


def main() -> None:
    frame = pd.DataFrame(
        {
            "SMILES": ["CC", "CCC", "CC", "C"],
            "Protein": ["P0", "P1", "P0", "P2"],
            "Y": [1, 0, 1, 0],
        },
        index=[10, 11, 12, 13],
    )
    list_ids = np.asarray([2, 0, 3, 1])
    calls: list[str] = []

    def graph_factory(smiles, node_featurizer, edge_featurizer):
        calls.append(smiles)
        return DummyGraph(smiles)

    reference = SimpleNamespace(
        max_drug_nodes=4,
        atom_featurizer=object(),
        bond_featurizer=object(),
        fc=graph_factory,
    )
    dataset = CachedDTIDataset(
        list_ids,
        frame,
        reference,
        lambda protein: torch.tensor([len(protein)], dtype=torch.long),
    )

    assert len(dataset) == len(list_ids)
    for item, row_position in enumerate(list_ids):
        legacy_row = frame.iloc[row_position]
        graph, protein, label = dataset[item]
        assert graph.smiles == legacy_row["SMILES"]
        assert torch.equal(protein, torch.tensor([len(legacy_row["Protein"])], dtype=torch.long))
        assert label == legacy_row["Y"]

    # Repeated SMILES/proteins must retain the old cache semantics.
    assert calls == ["CC", "C", "CCC"]
    assert len(dataset.drug_graph_cache) == 3
    assert len(dataset.protein_cache) == 3
    print("CACHED_DRUGBAN_DATASET_EQUIVALENCE_PASS rows=4 unique_drugs=3 unique_proteins=3")


if __name__ == "__main__":
    main()
