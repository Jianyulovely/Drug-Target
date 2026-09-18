#!/usr/bin/env python3
"""Regression test for the partition-wise shuffled S1/S2 control.

The ablation must only disrupt which candidate pair receives a side-information
vector.  It must preserve each of the seven columns' values and be deterministic
for a frozen dataset/scenario/seed/fold/partition identity.
"""

from __future__ import annotations

import numpy as np

from paper_benchmark import _side_variant


def main() -> None:
    # Every row is unique, making an accidental identity permutation visible.
    side = np.arange(28, dtype=np.float32).reshape(4, 7)
    args = ("test", "biosnap", "cold_pair", 4198936517, 3)
    shuffled_a = _side_variant("arnoldi_s12_shuffle", side, *args)
    shuffled_b = _side_variant("arnoldi_s12_shuffle", side, *args)

    np.testing.assert_array_equal(shuffled_a, shuffled_b)
    np.testing.assert_array_equal(np.sort(shuffled_a, axis=0), np.sort(side, axis=0))
    if np.array_equal(shuffled_a, side):
        raise AssertionError("Shuffled control unexpectedly retained candidate-pair alignment.")
    np.testing.assert_array_equal(_side_variant("arnoldi_s12", side, *args), side)
    print("SIDE_FEATURE_SHUFFLE_CONTROL_PASS rows=4 dimensions=7")


if __name__ == "__main__":
    main()
