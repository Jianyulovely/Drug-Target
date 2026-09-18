#!/usr/bin/env python3
"""Create manuscript-ready DTI benchmark figures from frozen-fold JSON results.

Figure contract
---------------
Core question: Does adding leakage-safe S1+S2 side information improve the
ArnoldiGCL predictor across fixed DTI benchmark splits, and under which splits
does it fail to improve? The script does not assume the direction of the
effect; that conclusion is generated only from complete result artifacts.
Archetype: quantitative grid.  Hero evidence is the M8-vs-baseline comparison
across datasets and cold-start settings; ablations and paired tests supply
supporting evidence.  Each point is a fixed seed/fold result, summaries report
mean +/- sample SD across 15 fixed folds.  Paired Wilcoxon tests are descriptive
and are not used until all folds are present.

The script fails closed unless every method has 15 results for each dataset and
scenario.  This prevents partial runs from becoming manuscript figures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

# Required for editable publication vector output.
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams.update(
    {
        "font.size": 8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
    }
)

PIPELINE_VERSION = "paper-benchmark-v2"
DATASETS = ("biosnap", "human", "bindingdb")
SCENARIOS = ("random", "cold_drug", "cold_protein", "cold_pair")
BASELINE_METHODS = ("lr", "mlp", "gcn", "colddti", "drugban", "arnoldi_s12")
ABLATION_METHODS = (
    "arnoldi_v4",
    "arnoldi_s1",
    "arnoldi_s2",
    "arnoldi_s12",
    "arnoldi_s12_shuffle",
)
ALL_METHODS = tuple(dict.fromkeys((*BASELINE_METHODS, *ABLATION_METHODS)))
METHOD_LABELS = {
    "lr": "Logistic regression",
    "mlp": "MLP",
    "gcn": "GCN",
    "colddti": "Threshold GCN",
    "drugban": "DrugBAN",
    "arnoldi_v4": "M8 w/o S1/S2",
    "arnoldi_s1": "M8 + S1",
    "arnoldi_s2": "M8 + S2",
    "arnoldi_s12": "M8 + S1+S2",
    "arnoldi_s12_shuffle": "M8 + shuffled S1+S2",
}
SCENARIO_LABELS = {
    "random": "Random",
    "cold_drug": "Cold drug",
    "cold_protein": "Cold protein",
    "cold_pair": "Cold pair",
}
DATASET_LABELS = {"biosnap": "BioSNAP", "human": "Human", "bindingdb": "BindingDB"}
COLORS = {
    "lr": "#767676",
    "mlp": "#3775BA",
    "gcn": "#7884B4",
    "colddti": "#9A4D8E",
    "drugban": "#42949E",
    "arnoldi_v4": "#B4C0E4",
    "arnoldi_s1": "#DDF3DE",
    "arnoldi_s2": "#8BCF8B",
    "arnoldi_s12": "#B64342",
    "arnoldi_s12_shuffle": "#CFCECE",
}


def load_rows(root: Path) -> pd.DataFrame:
    rows = []
    for result_path in sorted((root / "results").glob("**/*.json")):
        with result_path.open(encoding="utf-8") as handle:
            item = json.load(handle)
        if item.get("pipeline_version") != PIPELINE_VERSION:
            continue
        if item.get("method") not in ALL_METHODS:
            continue
        # A short DrugBAN smoke run is retained on the server for provenance,
        # but it is not a formal benchmark result.  Fail closed on the
        # prescribed 100-epoch setting so that it cannot create an apparent
        # sixteenth fold in the Human/cold-pair group.
        if item.get("method") == "drugban":
            settings = item.get("settings", {})
            if (
                settings.get("epochs") != 100
                or settings.get("input_cache") is not True
                or settings.get("tf32") is not True
            ):
                continue
        row = {
            "method": item["method"],
            "method_label": METHOD_LABELS[item["method"]],
            "dataset": item["dataset"],
            "scenario": item["scenario"],
            "seed": int(item["seed"]),
            "fold": int(item["fold"]),
            "split_signature": item.get("split_signature", ""),
            "best_val_auc": float(item["best_val_auc"]),
            "n_train": int(item["n_train"]),
            "n_val": int(item["n_val"]),
            "n_test": int(item["n_test"]),
            "n_test_positive": int(item["n_test_positive"]),
        }
        row.update({key: float(value) for key, value in item["metrics"].items()})
        rows.append(row)
    if not rows:
        raise RuntimeError(f"No {PIPELINE_VERSION} results were found under {root / 'results'}.")
    return pd.DataFrame(rows)


def validate_complete(raw: pd.DataFrame, expected_per_group: int) -> None:
    """Fail closed for any missing or duplicate fixed fold result."""
    needed = pd.MultiIndex.from_product(
        [ALL_METHODS, DATASETS, SCENARIOS], names=["method", "dataset", "scenario"]
    ).to_frame(index=False)
    count = (
        raw.groupby(["method", "dataset", "scenario"], as_index=False)
        .size()
        .rename(columns={"size": "n"})
    )
    coverage = needed.merge(count, how="left", on=["method", "dataset", "scenario"])
    coverage["n"] = coverage["n"].fillna(0).astype(int)
    bad = coverage[coverage["n"] != expected_per_group]
    duplicate = raw.duplicated(["method", "dataset", "scenario", "seed", "fold"])
    if not bad.empty or duplicate.any():
        details = bad.to_string(index=False) if not bad.empty else "none"
        raise RuntimeError(
            "Results are incomplete or duplicated; figures were not generated.\n"
            f"Expected {expected_per_group} folds per method/dataset/scenario.\n{details}\n"
            f"Duplicate rows: {int(duplicate.sum())}"
        )


def aggregate(raw: pd.DataFrame) -> pd.DataFrame:
    metrics = ["auc", "aupr", "f1", "accuracy"]
    # ``as_index=False`` combined with a selected-column aggregation drops the
    # grouping keys in older pandas releases (including the remote environment).
    # Aggregate first, then reset the index so method/dataset/scenario always
    # remain available to plotting and manuscript generation.
    output = (
        raw.groupby(["method", "method_label", "dataset", "scenario"], sort=True)[metrics]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    output.columns = [
        "_".join(column).rstrip("_") if isinstance(column, tuple) else column for column in output.columns
    ]
    return output


def save_figure(fig: plt.Figure, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=1.1)
    for extension, dpi in (("svg", 600), ("pdf", 600), ("png", 600), ("tiff", 600)):
        fig.savefig(destination.with_suffix(f".{extension}"), dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def add_panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(-0.15, 1.04, label, transform=axis.transAxes, fontweight="bold", fontsize=9)


def plot_metric_grid(
    summary: pd.DataFrame,
    methods: Iterable[str],
    title: str,
    output: Path,
) -> None:
    methods = tuple(methods)
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 3.7), sharex=True)
    x = np.arange(len(SCENARIOS))
    for row, metric in enumerate(("auc", "aupr")):
        for col, dataset in enumerate(DATASETS):
            axis = axes[row, col]
            slice_ = summary[(summary["dataset"] == dataset) & (summary["method"].isin(methods))]
            for method in methods:
                current = (
                    slice_[slice_["method"] == method]
                    .set_index("scenario")
                    .reindex(SCENARIOS)
                )
                values = current[f"{metric}_mean"].to_numpy()
                errors = current[f"{metric}_std"].fillna(0.0).to_numpy()
                linewidth = 2.1 if method == "arnoldi_s12" else 1.0
                zorder = 10 if method == "arnoldi_s12" else 2
                axis.plot(
                    x,
                    values,
                    marker="o",
                    ms=4.0 if method == "arnoldi_s12" else 3.2,
                    lw=linewidth,
                    color=COLORS[method],
                    label=METHOD_LABELS[method],
                    zorder=zorder,
                )
                axis.fill_between(x, values - errors, values + errors, color=COLORS[method], alpha=0.09, zorder=1)
            axis.set_title(DATASET_LABELS[dataset], fontsize=9, pad=5)
            axis.set_ylim(0.0, 1.02)
            axis.set_xticks(x, [SCENARIO_LABELS[scenario] for scenario in SCENARIOS], rotation=27, ha="right")
            if col == 0:
                axis.set_ylabel("AUC" if metric == "auc" else "AUPR")
            axis.grid(axis="y", color="#DDDDDD", lw=0.5, zorder=0)
            add_panel_label(axis, chr(ord("a") + row * 3 + col))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.11), fontsize=7)
    fig.suptitle(title, x=0.01, ha="left", y=1.20, fontsize=10, fontweight="bold")
    save_figure(fig, output)


def paired_statistics(raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    target = "arnoldi_s12"
    comparators = [method for method in ALL_METHODS if method != target]
    for metric in ("auc", "aupr"):
        for dataset in DATASETS:
            for scenario in SCENARIOS:
                target_values = raw[
                    (raw["method"] == target)
                    & (raw["dataset"] == dataset)
                    & (raw["scenario"] == scenario)
                ][["seed", "fold", metric]].rename(columns={metric: "target"})
                for method in comparators:
                    comparator_values = raw[
                        (raw["method"] == method)
                        & (raw["dataset"] == dataset)
                        & (raw["scenario"] == scenario)
                    ][["seed", "fold", metric]].rename(columns={metric: "baseline"})
                    paired = target_values.merge(comparator_values, on=["seed", "fold"], how="inner")
                    difference = paired["target"] - paired["baseline"]
                    if len(difference) < 2 or np.allclose(difference, 0.0):
                        statistic, p_value = np.nan, np.nan
                    else:
                        test = wilcoxon(difference, alternative="two-sided", method="auto")
                        statistic, p_value = float(test.statistic), float(test.pvalue)
                    records.append(
                        {
                            "metric": metric,
                            "dataset": dataset,
                            "scenario": scenario,
                            "target_method": target,
                            "baseline_method": method,
                            "n_paired_folds": int(len(difference)),
                            "mean_difference": float(difference.mean()),
                            "sd_difference": float(difference.std(ddof=1)),
                            "wilcoxon_statistic": statistic,
                            "wilcoxon_p_two_sided": p_value,
                        }
                    )
    output = pd.DataFrame(records)
    output["wilcoxon_p_fdr_bh"] = benjamini_hochberg(output["wilcoxon_p_two_sided"].to_numpy())
    return output


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Adjust finite p-values over the complete paired-test family."""
    p_values = np.asarray(p_values, dtype=float)
    adjusted = np.full(p_values.shape, np.nan, dtype=float)
    finite = np.isfinite(p_values)
    if not finite.any():
        return adjusted
    indices = np.flatnonzero(finite)
    order = indices[np.argsort(p_values[finite], kind="mergesort")]
    ranked = p_values[order]
    values = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    values = np.minimum.accumulate(values[::-1])[::-1]
    adjusted[order] = np.minimum(values, 1.0)
    return adjusted


def write_legends(output: Path) -> None:
    output.write_text(
        "Fig. 2 | Performance comparison across fixed DTI benchmark splits. "
        "Each point is the mean of 15 fixed seed-fold evaluations (three random seeds and five outer folds); "
        "shaded bands denote the sample standard deviation. a-c, AUC on BioSNAP, Human and BindingDB, respectively. "
        "d-f, corresponding AUPR values. All methods use the same frozen positive partitions and partition-specific "
        "negative samples. Source data are provided as CSV files.\n\n"
        "Fig. 3 | Contribution of the leakage-safe side-information modules. "
        "Each point is the mean of 15 fixed seed-fold evaluations and shaded bands denote the sample standard deviation. "
        "The shuffled control preserves the marginal values of S1+S2 within each partition but breaks their alignment to "
        "drug-protein pairs. Paired Wilcoxon p-values are descriptive and BH-adjusted over the complete comparison family. "
        "Source data are provided as CSV files.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--expected-per-group", type=int, default=15)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    raw = load_rows(root)
    validate_complete(raw, args.expected_per_group)
    source_dir = root / "source_data"
    source_dir.mkdir(parents=True, exist_ok=True)
    raw.sort_values(["method", "dataset", "scenario", "seed", "fold"]).to_csv(source_dir / "fold_metrics.csv", index=False)
    summary = aggregate(raw)
    summary.to_csv(source_dir / "summary_metrics.csv", index=False)
    paired = paired_statistics(raw)
    paired.to_csv(source_dir / "paired_wilcoxon_statistics.csv", index=False)
    figure_dir = root / "figures"
    plot_metric_grid(summary, BASELINE_METHODS, "Baseline comparison", figure_dir / "figure_2_baselines")
    plot_metric_grid(summary, ABLATION_METHODS, "Ablation of S1/S2 side information", figure_dir / "figure_3_ablation")
    write_legends(root / "figure_legends.txt")
    print(f"Generated figures and source data under {root}")


if __name__ == "__main__":
    main()
