#!/usr/bin/env python3
"""Draw a compact, publication-ready schematic of the selected DTI model."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})


COLORS = {
    "input": "#EAF2FB",
    "encoder": "#EDEAF7",
    "graph": "#E6F3F1",
    "side": "#EEF6E9",
    "score": "#F8EAEA",
    "ink": "#26313A",
    "muted": "#5F6B73",
    "accent": "#B64342",
}


def add_box(ax, x, y, width, height, title, body, color, *, title_size=8.4, body_size=6.8):
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=0.9, edgecolor=COLORS["ink"], facecolor=color,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * 0.67, title, ha="center", va="center",
            fontsize=title_size, fontweight="bold", color=COLORS["ink"])
    ax.text(x + width / 2, y + height * 0.32, body, ha="center", va="center",
            fontsize=body_size, color=COLORS["muted"], linespacing=1.25)
    return patch


def add_arrow(ax, start, end, *, color=None, rad=0.0, lw=1.1):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=10, linewidth=lw,
        color=color or COLORS["muted"], connectionstyle=f"arc3,rad={rad}",
    ))


def draw(output: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.15))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.02, 0.965, "Leakage-safe ArnoldiGCL with similarity-neighbour side information",
            ha="left", va="top", fontsize=10.2, fontweight="bold", color=COLORS["ink"])
    ax.text(0.02, 0.915, "The drug and protein pathways remain separate; only training-fold evidence enters graph and side-information construction.",
            ha="left", va="top", fontsize=6.9, color=COLORS["muted"])

    # Main structural pathway.
    add_box(ax, 0.025, 0.66, 0.135, 0.105, "Drug input", "Morgan fingerprint\n1,024 bits", COLORS["input"], title_size=7.7, body_size=5.9)
    add_box(ax, 0.025, 0.505, 0.135, 0.105, "Protein input", "ESM-2 t30/150M\n640 dimensions", COLORS["input"], title_size=7.7, body_size=5.9)
    add_box(ax, 0.205, 0.555, 0.155, 0.16, "Separate projections", "drug encoder ≠ protein encoder\nlearned representations", COLORS["encoder"], title_size=7.25, body_size=5.35)
    add_box(ax, 0.395, 0.555, 0.175, 0.16, "Training-fold graph", "drug/protein similarities\n+ positive training DTI edges", COLORS["graph"], title_size=7.25, body_size=5.05)
    add_box(ax, 0.605, 0.555, 0.155, 0.16, "ArnoldiGCL", "structural node embeddings\n256-dimensional", COLORS["graph"], title_size=7.5, body_size=5.35)

    add_arrow(ax, (0.16, 0.712), (0.195, 0.66))
    add_arrow(ax, (0.16, 0.557), (0.195, 0.61))
    add_arrow(ax, (0.36, 0.635), (0.385, 0.635))
    add_arrow(ax, (0.57, 0.635), (0.595, 0.635))

    # Side-information pathway.
    add_box(ax, 0.025, 0.16, 0.155, 0.15, "Candidate pair", "drug d + protein p", COLORS["input"])
    add_box(ax, 0.22, 0.16, 0.19, 0.15, "S1 local support", "4 descriptors; k = 10\nrate + dispersion", COLORS["side"])
    add_box(ax, 0.45, 0.16, 0.19, 0.15, "S2 consistency", "3 descriptors; k = 20\ndrug–protein agreement", COLORS["side"])
    add_box(ax, 0.70, 0.16, 0.13, 0.15, "Side vector", "7 values\ntraining labels only", COLORS["side"], body_size=5.7)
    add_arrow(ax, (0.18, 0.235), (0.22, 0.235))
    add_arrow(ax, (0.41, 0.235), (0.45, 0.235))
    add_arrow(ax, (0.64, 0.235), (0.70, 0.235))

    # Merge and prediction.
    add_box(ax, 0.845, 0.385, 0.13, 0.20, "Edge scorer", "pair structural\n+ projected raw\n+ S1/S2", COLORS["score"], title_size=8.0, body_size=6.6)
    add_box(ax, 0.845, 0.16, 0.13, 0.13, "Output", "DTI probability", COLORS["score"], title_size=8.1, body_size=6.8)
    add_arrow(ax, (0.76, 0.635), (0.845, 0.53), rad=-0.06, color=COLORS["accent"], lw=1.25)
    add_arrow(ax, (0.83, 0.235), (0.845, 0.44), rad=0.0, color=COLORS["accent"], lw=1.25)
    add_arrow(ax, (0.91, 0.385), (0.91, 0.29), color=COLORS["accent"], lw=1.25)

    ax.text(0.025, 0.065, "Leakage control: graph edges and S1/S2 statistics use positive labels from the training fold only; validation/test labels are excluded.",
            ha="left", va="center", fontsize=5.8, color=COLORS["muted"])
    ax.text(0.975, 0.028, "Encoders are not shared", ha="right", va="center", fontsize=6.2,
            color=COLORS["accent"], fontweight="bold")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.35)
    for extension in ("svg", "pdf", "png", "tiff"):
        fig.savefig(output.with_suffix(f".{extension}"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    draw(Path(args.output).resolve())


if __name__ == "__main__":
    main()
