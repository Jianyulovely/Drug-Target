#!/usr/bin/env python3
"""Check that S1/S2 never reads the label of its queried candidate pair.

This is a CPU-only regression test.  It perturbs one candidate-pair entry in
the matrix supplied to :func:`compute_side_features` and requires that the
seven descriptors for that same pair do not change.  A non-training query is
included alongside training-entity queries, because cold-start evaluation
uses both cases.
"""

from __future__ import annotations

import numpy as np

from paper_benchmark import compute_side_features


def symmetric_similarity(rng: np.random.Generator, size: int) -> np.ndarray:
    value = rng.random((size, size), dtype=np.float32)
    value = (value + value.T) / 2
    np.fill_diagonal(value, 1.0)
    return value


def main() -> None:
    # The training pools must contain more than 20 entities, matching the
    # condition required by the formal S2 top-20-neighbour construction.
    n_drugs = n_proteins = 30
    rng = np.random.default_rng(20260828)
    drug_similarity = symmetric_similarity(rng, n_drugs)
    protein_similarity = symmetric_similarity(rng, n_proteins)
    train_adjacency = (rng.random((n_drugs, n_proteins)) < 0.08).astype(np.float32)
    train_drugs = np.arange(25)
    train_proteins = np.arange(25)
    pairs = np.asarray(((0, 0), (24, 24), (25, 25), (29, 29)), dtype=np.int64)

    reference = compute_side_features(
        pairs,
        train_adjacency,
        drug_similarity,
        protein_similarity,
        train_drugs,
        train_proteins,
    )
    assert reference.shape == (len(pairs), 7)
    assert np.all(np.isfinite(reference))

    for row, (drug, protein) in enumerate(pairs):
        perturbed_adjacency = train_adjacency.copy()
        perturbed_adjacency[drug, protein] = 1.0 - perturbed_adjacency[drug, protein]
        perturbed = compute_side_features(
            pairs,
            perturbed_adjacency,
            drug_similarity,
            protein_similarity,
            train_drugs,
            train_proteins,
        )
        np.testing.assert_array_equal(reference[row], perturbed[row])

    print(f"SIDE_FEATURE_CANDIDATE_LABEL_EXCLUSION_PASS pairs={len(pairs)}")


if __name__ == "__main__":
    main()
