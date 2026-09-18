#!/usr/bin/env python3
"""Generate publication-ready quantitative DTI figures from audited summaries.

Figure contract
---------------
Core conclusion: the ArnoldiGCL-S1/S2 model provides split-dependent gains in
DTI discrimination, while the complete benchmark also exposes settings in
which it is not the best method.
Archetype: quantitative grid.
Evidence hierarchy: Figure 2 is the primary multi-method comparison; Figure 3
is supporting ablation/control evidence.
Statistics: means +/- sample standard deviation across 15 fixed seed-fold
evaluations per method, dataset and split scenario.
Source data: manuscript/source_data/summary_metrics.csv.

The script fails closed if the summary does not contain the expected complete
method x dataset x scenario grid with 15 evaluations per cell. It writes a
separate output bundle so existing manuscript figures remain untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

# Required publication settings: keep SVG text editable and use one backend.
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams.update(
    {
        "font.size": 7.2,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.75,
        "axes.labelpad": 3,
        "legend.frameon": False,
        "xtick.major.width": 0.65,
        "ytick.major.width": 0.65,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }
)

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

DATASET_LABELS = {"biosnap": "BioSNAP", "human": "Human", "bindingdb": "BindingDB"}
SCENARIO_LABELS = {
    "random": "Random",
    "cold_drug": "Cold drug",
    "cold_protein": "Cold protein",
    "cold_pair": "Cold pair",
}
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

# A restrained, print-tolerant palette. The proposed full model is the accent.
COLORS = {
    "lr": "#5F6368",
    "mlp": "#3775BA",
    "gcn": "#7884B4",
    "colddti": "#9A4D8E",
    "drugban": "#42949E",
    "arnoldi_v4": "#9DA9D0",
    "arnoldi_s1": "#8BCF8B",
    "arnoldi_s2": "#4F9E78",
    "arnoldi_s12": "#B64342",
    "arnoldi_s12_shuffle": "#B6B6B6",
}


def locate_summary(root: Path) -> Path:
    candidates = [
        root / "manuscript" / "source_data" / "summary_metrics.csv",
        root / "source_data" / "summary_metrics.csv",
        root / "summary_metrics.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find summary_metrics.csv under the supplied root.")


def load_summary(root: Path, expected_per_group: int) -> pd.DataFrame:
    path = locate_summary(root)
    summary = pd.read_csv(path)
    required = {
        "method",
        "dataset",
        "scenario",
        "auc_mean",
        "auc_std",
        "auc_count",
        "aupr_mean",
        "aupr_std",
        "aupr_count",
    }
    missing = sorted(required.difference(summary.columns))
    if missing:
        raise RuntimeError(f"Summary is missing required columns: {', '.join(missing)}")

    expected_methods = set(BASELINE_METHODS) | set(ABLATION_METHODS)
    observed_methods = set(summary["method"].dropna().astype(str))
    if not expected_methods.issubset(observed_methods):
        raise RuntimeError(f"Summary is missing methods: {sorted(expected_methods - observed_methods)}")

    counts = summary.groupby(["method", "dataset", "scenario"], dropna=False).size()
    expected_index = pd.MultiIndex.from_product(
        [sorted(expected_methods), DATASETS, SCENARIOS],
        names=["method", "dataset", "scenario"],
    )
    observed = counts.reindex(expected_index, fill_value=0)
    bad_groups = observed[observed != 1]
    if not bad_groups.empty:
        raise RuntimeError(
            "Summary must contain exactly one aggregate row per method/dataset/scenario; "
            f"bad groups: {bad_groups.to_dict()}"
        )

    for count_column in ("auc_count", "aupr_count"):
        bad = summary[summary[count_column].astype(int) != expected_per_group]
        if not bad.empty:
            raise RuntimeError(
                f"{count_column} is incomplete; expected {expected_per_group} per cell."
            )
    return summary


def row_limits(summary: pd.DataFrame, metric: str) -> tuple[float, float]:
    values = summary[f"{metric}_mean"].to_numpy(float)
    errors = summary[f"{metric}_std"].fillna(0).to_numpy(float)
    low = max(0.0, float(np.nanmin(values - errors)) - 0.025)
    high = min(1.02, float(np.nanmax(values + errors)) + 0.025)
    # Round to stable, readable ticks without collapsing a narrow range.
    low = np.floor(low * 20) / 20
    high = np.ceil(high * 20) / 20
    if high - low < 0.20:
        center = (high + low) / 2
        low = max(0.0, center - 0.10)
        high = min(1.02, center + 0.10)
    return float(low), float(high)


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.14,
        1.04,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
        color="#272727",
    )


def draw_panel(
    ax: plt.Axes,
    summary: pd.DataFrame,
    methods: tuple[str, ...],
    dataset: str,
    metric: str,
    row_limits_: tuple[float, float],
    show_legend: bool,
) -> list[Line2D]:
    subset = summary[(summary["dataset"] == dataset) & summary["method"].isin(methods)]
    x = np.arange(len(SCENARIOS), dtype=float)
    handles: list[Line2D] = []
    for method in methods:
        current = subset[subset["method"] == method].set_index("scenario").reindex(SCENARIOS)
        values = current[f"{metric}_mean"].to_numpy(float)
        errors = current[f"{metric}_std"].fillna(0).to_numpy(float)
        proposed = method == "arnoldi_s12"
        line = ax.plot(
            x,
            values,
            color=COLORS[method],
            lw=2.0 if proposed else 1.05,
            marker="o",
            ms=4.0 if proposed else 3.0,
            markeredgewidth=0.45,
            markeredgecolor="white",
            alpha=1.0 if proposed else 0.92,
            zorder=5 if proposed else 3,
            label=METHOD_LABELS[method],
        )[0]
        ax.fill_between(
            x,
            np.maximum(row_limits_[0], values - errors),
            np.minimum(row_limits_[1], values + errors),
            color=COLORS[method],
            alpha=0.075 if not proposed else 0.11,
            linewidth=0,
            zorder=1,
        )
        handles.append(line)

    ax.set_xlim(-0.12, len(SCENARIOS) - 0.88)
    ax.set_ylim(*row_limits_)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS], rotation=24, ha="right")
    ax.tick_params(axis="both", labelsize=6.7, pad=2)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(DATASET_LABELS[dataset], fontsize=8.4, fontweight="bold", pad=4)
    if not show_legend:
        ax.set_xlabel("")
    return handles


def make_figure(summary: pd.DataFrame, methods: tuple[str, ...], output: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.20), sharex=True)
    auc_limits = row_limits(summary[summary.method.isin(methods)], "auc")
    aupr_limits = row_limits(summary[summary.method.isin(methods)], "aupr")

    all_handles: list[Line2D] = []
    panel_labels = iter("abcdef")
    for row, (metric, limits) in enumerate((("auc", auc_limits), ("aupr", aupr_limits))):
        for col, dataset in enumerate(DATASETS):
            ax = axes[row, col]
            handles = draw_panel(
                ax,
                summary,
                methods,
                dataset,
                metric,
                limits,
                show_legend=(row == 0 and col == 0),
            )
            if not all_handles:
                all_handles = handles
            add_panel_label(ax, next(panel_labels))
            if col == 0:
                ax.set_ylabel("AUC" if metric == "auc" else "AUPR", fontsize=7.5, fontweight="bold")
            if row == 1:
                ax.set_xlabel("Evaluation split", fontsize=7.2)

    fig.legend(
        all_handles,
        [METHOD_LABELS[m] for m in methods],
        loc="upper center",
        bbox_to_anchor=(0.5, 1.015),
        ncol=3,
        fontsize=6.8,
        handlelength=2.0,
        columnspacing=1.2,
        handletextpad=0.45,
    )
    fig.text(
        0.99,
        1.015,
        "mean ± s.d.; n = 15",
        ha="right",
        va="bottom",
        fontsize=6.6,
        color="#606060",
    )
    fig.subplots_adjust(left=0.075, right=0.995, bottom=0.16, top=0.82, wspace=0.25, hspace=0.30)
    output.parent.mkdir(parents=True, exist_ok=True)
    for extension in ("svg", "pdf", "png", "tiff"):
        kwargs = {"bbox_inches": "tight", "facecolor": "white"}
        if extension in {"png", "tiff"}:
            kwargs["dpi"] = 600
        fig.savefig(output.with_suffix(f".{extension}"), **kwargs)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory; defaults to manuscript/figures/scientific.",
    )
    parser.add_argument("--expected-per-group", type=int, default=15)
    args = parser.parse_args()

    root = args.root.resolve()
    summary = load_summary(root, args.expected_per_group)
    output_dir = (args.output_dir or root / "manuscript" / "figures" / "scientific").resolve()
    make_figure(summary, BASELINE_METHODS, output_dir / "figure_2_baselines_scientific")
    make_figure(summary, ABLATION_METHODS, output_dir / "figure_3_ablation_scientific")
    print(f"Generated Figure 2 and Figure 3 under {output_dir}")


if __name__ == "__main__":
    main()
