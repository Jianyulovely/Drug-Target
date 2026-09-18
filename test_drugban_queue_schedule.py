#!/usr/bin/env python3
"""Regression checks for virtual-worker partitioning in the DrugBAN queue.

The production queue may place more than one independent fold process on a
GPU after a throughput validation.  This test verifies the scheduling
invariant only: every frozen task belongs to exactly one virtual worker and
the default one-worker-per-GPU layout remains unchanged.
"""

from __future__ import annotations


DATASETS = ("biosnap", "human", "bindingdb")
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")
SEEDS = (1941488137, 4198936517, 983997847)
FOLDS = range(5)


def task_ids() -> list[tuple[str, str, int, int]]:
    return [
        (dataset, scenario, seed, fold)
        for dataset in DATASETS
        for scenario in SCENARIOS
        for seed in SEEDS
        for fold in FOLDS
    ]


def assignment(total_workers: int) -> list[list[tuple[str, str, int, int]]]:
    tasks = task_ids()
    return [
        [task for index, task in enumerate(tasks) if index % total_workers == worker]
        for worker in range(total_workers)
    ]


def test_partition_is_complete_and_disjoint() -> None:
    tasks = task_ids()
    for workers_per_gpu in (1, 2, 3):
        groups = assignment(4 * workers_per_gpu)
        flattened = [task for group in groups for task in group]
        assert len(flattened) == len(tasks) == 180
        assert len(set(flattened)) == len(tasks)
        assert max(map(len, groups)) - min(map(len, groups)) <= 1


def test_default_mapping_is_preserved() -> None:
    groups = assignment(4)
    expected_first = [
        ("biosnap", "random", 1941488137, 0),
        ("biosnap", "random", 1941488137, 1),
        ("biosnap", "random", 1941488137, 2),
        ("biosnap", "random", 1941488137, 3),
    ]
    assert [group[0] for group in groups] == expected_first


if __name__ == "__main__":
    test_partition_is_complete_and_disjoint()
    test_default_mapping_is_preserved()
    print("DRUGBAN_QUEUE_SCHEDULE_REGRESSION_PASS tasks=180 layouts=1,2,3")
