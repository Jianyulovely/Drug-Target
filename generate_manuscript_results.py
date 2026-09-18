#!/usr/bin/env python3
"""Generate Overleaf LaTeX result fragments from complete frozen-fold JSONs.

The script deliberately fails before writing any manuscript result fragment if
the required B1--B5 and ablation coverage is incomplete.  It is intended to
run after ``plot_paper_results.py`` and uses the same result parser and
fixed-fold validation rules.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

import plot_paper_results as results


METHODS_MAIN = ("lr", "mlp", "gcn", "colddti", "drugban", "arnoldi_s12")
METHODS_ABLATION = ("arnoldi_v4", "arnoldi_s1", "arnoldi_s2", "arnoldi_s12", "arnoldi_s12_shuffle")


def latex_escape(value: str) -> str:
    return value.replace("_", "\\_")


def cell(summary: pd.DataFrame, method: str, dataset: str, scenario: str, metric: str) -> str:
    row = summary[
        (summary["method"] == method)
        & (summary["dataset"] == dataset)
        & (summary["scenario"] == scenario)
    ]
    if len(row) != 1:
        raise RuntimeError(f"Expected exactly one summary row for {method}/{dataset}/{scenario}.")
    item = row.iloc[0]
    if int(item[f"{metric}_count"]) != 15:
        raise RuntimeError(f"Unexpected fold count for {method}/{dataset}/{scenario}.")
    return f"{item[f'{metric}_mean']:.3f} $\\pm$ {item[f'{metric}_std']:.3f}"


def tabular(
    summary: pd.DataFrame,
    methods: Iterable[str],
    metric: str,
    caption: str,
    label: str,
) -> str:
    methods = tuple(methods)
    columns = "ll" + "c" * len(methods)
    header = "Dataset & Split & " + " & ".join(latex_escape(results.METHOD_LABELS[m]) for m in methods) + r" \\"
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\scriptsize",
        r"\resizebox{\textwidth}{!}{%",
        rf"\begin{{tabular}}{{{columns}}}",
        r"\toprule",
        header,
        r"\midrule",
    ]
    for dataset in results.DATASETS:
        for scenario in results.SCENARIOS:
            values = " & ".join(cell(summary, method, dataset, scenario, metric) for method in methods)
            lines.append(
                f"{results.DATASET_LABELS[dataset]} & {results.SCENARIO_LABELS[scenario]} & {values} " + r"\\"
            )
        if dataset != results.DATASETS[-1]:
            lines.append(r"\midrule")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}%",
            r"}",
            rf"\caption{{{caption} Values are mean $\pm$ sample standard deviation across 15 fixed seed--fold evaluations.}}",
            rf"\label{{{label}}}",
            r"\end{table*}",
        ]
    )
    return "\n".join(lines)


def figure_block(filename: str, caption: str, label: str) -> str:
    return "\n".join(
        [
            r"\begin{figure*}[t]",
            r"\centering",
            rf"\includegraphics[width=\textwidth]{{figures/{filename}.pdf}}",
            rf"\caption{{{caption}}}",
            rf"\label{{{label}}}",
            r"\end{figure*}",
        ]
    )


def condition_name(dataset: str, scenario: str) -> str:
    return f"{results.DATASET_LABELS[dataset]} {results.SCENARIO_LABELS[scenario]}"


def formatted_conditions(conditions: list[tuple[str, str]]) -> str:
    return ", ".join(condition_name(dataset, scenario) for dataset, scenario in conditions)


def comparison_context(summary: pd.DataFrame, raw: pd.DataFrame) -> dict[str, object]:
    """Derive manuscript claims only from the complete frozen-fold data."""
    principal = summary[summary["method"].isin(METHODS_MAIN)].copy()
    winners: list[tuple[str, str]] = []
    non_winners: list[tuple[str, str]] = []
    for dataset in results.DATASETS:
        for scenario in results.SCENARIOS:
            subset = principal[(principal["dataset"] == dataset) & (principal["scenario"] == scenario)]
            highest = float(subset["aupr_mean"].max())
            target = float(subset.loc[subset["method"] == "arnoldi_s12", "aupr_mean"].iloc[0])
            (winners if target >= highest - 1e-12 else non_winners).append((dataset, scenario))

    paired = results.paired_statistics(raw)

    def contrast(baseline: str) -> dict[str, object]:
        table = paired[(paired["metric"] == "aupr") & (paired["baseline_method"] == baseline)]
        higher = table[table["mean_difference"] > 0]
        lower_or_tied = table[table["mean_difference"] <= 0]
        significant_higher = higher[higher["wilcoxon_p_fdr_bh"] < 0.05]
        return {
            "higher": higher,
            "lower_or_tied": lower_or_tied,
            "significant_higher": significant_higher,
            "lower_conditions": [
                (row.dataset, row.scenario) for row in lower_or_tied.itertuples(index=False)
            ],
        }

    structural = contrast("arnoldi_v4")
    shuffled = contrast("arnoldi_s12_shuffle")
    structural_higher = structural["higher"]
    return {
        "winners": winners,
        "non_winners": non_winners,
        "structural": structural,
        "shuffled": shuffled,
        # A result generator must not assume that the full model wins.  Keep
        # these absent when no positive contrast exists and let the prose make
        # that null result explicit rather than failing after a valid audit.
        "structural_difference_min": (
            float(structural_higher["mean_difference"].min()) if not structural_higher.empty else None
        ),
        "structural_difference_max": (
            float(structural_higher["mean_difference"].max()) if not structural_higher.empty else None
        ),
    }


def result_fragment(summary: pd.DataFrame, raw: pd.DataFrame) -> str:
    context = comparison_context(summary, raw)
    winners = context["winners"]
    non_winners = context["non_winners"]
    structural = context["structural"]
    higher = structural["higher"]
    significant_higher = structural["significant_higher"]
    lower_conditions = structural["lower_conditions"]

    if higher.empty:
        structural_sentence = (
            "Relative to the structural-only variant, the full S1/S2 model had higher mean AUPR in 0/12 conditions; "
            "no positive mean AUPR difference was observed in this comparison."
        )
    else:
        structural_sentence = (
            rf"Relative to the structural-only variant, the full S1/S2 model had higher mean AUPR in {len(higher)}/12 conditions; "
            rf"among these, {len(significant_higher)} had a descriptive paired Wilcoxon contrast with BH-adjusted $p<0.05$. "
            rf"The positive mean differences ranged from {context['structural_difference_min']:.3f} to {context['structural_difference_max']:.3f} AUPR."
        )
    if lower_conditions:
        structural_sentence += rf" The full model was not higher than the structural-only variant in {formatted_conditions(lower_conditions)}."

    text = [
        r"\section{Results}",
        r"\subsection{Complete benchmark comparison}",
        r"Tables~\ref{tab:benchmark-aupr} and \ref{tab:benchmark-auc} report test performance from the complete frozen-fold benchmark. "
        r"The accompanying source-data CSV records every seed--fold value and the paired-comparison file contains raw and Benjamini--Hochberg-adjusted Wilcoxon $p$-values.",
        figure_block(
            "figure_2_baselines",
            "Comparison of feature-only, graph-based, bilinear-attention and full S1/S2 models across the four fixed split scenarios. Each point is the mean of 15 seed--fold evaluations and the shaded band denotes the sample standard deviation.",
            "fig:baseline-comparison",
        ),
        rf"Across the 12 prespecified dataset--split conditions, ArnoldiGCL-S1/S2 had the highest mean AUPR among the principal baselines in {len(winners)}/12 conditions. "
        + (rf"The conditions without the highest mean AUPR were {formatted_conditions(non_winners)}." if non_winners else ""),
        tabular(
            summary,
            METHODS_MAIN,
            "aupr",
            "Test AUPR for the principal baseline comparison.",
            "tab:benchmark-aupr",
        ),
        tabular(
            summary,
            METHODS_MAIN,
            "auc",
            "Test AUC for the principal baseline comparison.",
            "tab:benchmark-auc",
        ),
        r"\subsection{Contribution of S1 and S2}",
        r"Table~\ref{tab:ablation-aupr} reports the prespecified structural-only, single-module and shuffled controls. "
        + structural_sentence,
        figure_block(
            "figure_3_ablation",
            "Ablation of S1/S2 side information. The shuffled control preserves the marginal values of the seven descriptors within each partition but disrupts their association with candidate drug--protein pairs. Each point is the mean of 15 seed--fold evaluations and the shaded band denotes the sample standard deviation.",
            "fig:side-information-ablation",
        ),
        tabular(
            summary,
            METHODS_ABLATION,
            "aupr",
            "Test AUPR for the S1/S2 ablations and shuffled control.",
            "tab:ablation-aupr",
        ),
        r"\subsection{Where the method does not improve}",
        r"The complete source data, rather than a selected subset of splits, are used for all comparative statements. "
        + (rf"In particular, the principal-baseline comparison did not place the full model first in {formatted_conditions(non_winners)}. " if non_winners else "")
        + r"These settings are retained in the figures, tables and Discussion rather than being omitted from the main comparison.",
    ]
    return "\n\n".join(text) + "\n"


def abstract_fragment(summary: pd.DataFrame, raw: pd.DataFrame) -> str:
    context = comparison_context(summary, raw)
    structural = context["structural"]
    non_winners = context["non_winners"]
    if structural["higher"].empty:
        structural_summary = "The full model did not exceed its structural-only variant in any of the 12 AUPR comparisons. "
        closing_sentence = (
            "These results demonstrate a leakage-safe evaluation framework for similarity-neighbour information, "
            "but do not support a predictive benefit from the S1/S2 branch under the tested protocol."
        )
    else:
        structural_summary = (
            f"The latter gains ranged from {context['structural_difference_min']:.3f} to "
            f"{context['structural_difference_max']:.3f} AUPR; "
            f"{len(structural['significant_higher'])} descriptive paired contrasts had "
            "Benjamini--Hochberg-adjusted $p<0.05$. "
        )
        closing_sentence = (
            "These results support leakage-safe similarity-neighbour summaries as a useful, but split-dependent, "
            "source of evidence for computational DTI prioritization; they do not establish prospective or experimental target binding."
        )
    text = [
        "Predicting drug--target interactions (DTIs) from molecular and protein information can prioritize candidate mechanisms, but apparent accuracy can depend on what information crosses an evaluation split. "
        "We developed ArnoldiGCL-S1/S2, a graph-based DTI predictor that combines separate drug and protein projections with seven similarity-neighbour descriptors computed only from positive training-fold interactions. "
        "Across BioSNAP, Human and BindingDB under random, cold-drug, cold-protein and cold-pair splits, the full model had the highest mean AUPR among the principal baselines in "
        f"{len(context['winners'])}/12 prespecified conditions and exceeded its structural-only variant in {len(structural['higher'])}/12 conditions. "
        + structural_summary
        + (f"The model was not the highest-AUPR principal baseline in {formatted_conditions(non_winners)}, demonstrating that the side information does not confer a uniform advantage. " if non_winners else "")
        + closing_sentence
    ]
    return "\n".join(text) + "\n"


def discussion_fragment(summary: pd.DataFrame, raw: pd.DataFrame) -> str:
    context = comparison_context(summary, raw)
    structural = context["structural"]
    shuffled = context["shuffled"]
    non_winners = context["non_winners"]
    if structural["higher"].empty:
        structural_interpretation = (
            "The fixed-fold benchmark did not show a higher mean AUPR for the full S1/S2 model than for the structural-only variant in any condition. "
            "Under this result pattern, the study does not support a general predictive contribution from the side-information branch."
        )
    else:
        structural_interpretation = (
            "The fixed-fold benchmark indicates that similarity-neighbour information can add predictive signal beyond the training-fold structural encoder, but only when its construction is constrained to the training partition. The full S1/S2 model had higher mean AUPR than the structural-only variant in "
            f"{len(structural['higher'])}/12 conditions, and {len(structural['significant_higher'])} descriptive paired contrasts had a Benjamini--Hochberg-adjusted $p<0.05$. This pattern is consistent with the interpretation that local neighbourhood support and drug--protein consistency can complement graph-derived pair representations."
        )
    if shuffled["higher"].empty:
        shuffled_interpretation = (
            "The full model did not have a higher mean AUPR than the shuffled S1/S2 control in any condition. "
            "Accordingly, this shuffled comparison does not support a contribution from pairwise alignment of the side information under the tested protocol."
        )
    else:
        shuffled_interpretation = (
            "The shuffled control provides a narrower interpretation of this association. The full model had higher mean AUPR than the shuffled S1/S2 control in "
            f"{len(shuffled['higher'])}/12 conditions, including {len(shuffled['significant_higher'])} descriptive paired contrasts with FDR-adjusted $p<0.05$. Because shuffling preserves the marginal side-feature values while breaking their alignment with each candidate pair, the comparison suggests that aligned side information, rather than only feature scale or dimensionality, contributes to the observed differences. It does not by itself establish a biological mechanism for any predicted interaction."
        )
    text = [
        r"\section{Discussion}",
        structural_interpretation,
        shuffled_interpretation,
        ("The result is not a claim of uniform superiority. The full model was not the highest-AUPR principal baseline in " + formatted_conditions(non_winners) + ". These settings should be treated as part of the method boundary: a similarity-neighbour summary may be less informative when representation coverage, dataset composition or the held-out entity structure differs from the conditions in which it is advantageous." if non_winners else "Even where the full model has the highest mean AUPR, the benchmark remains a retrospective comparison and should not be interpreted as a guarantee of prospective utility under a new distribution."),
        "Several limitations follow directly from the evaluation design. The labels are curated DTIs, and the capped samples of unannotated pairs may include unknown positives; the reported metrics therefore describe the specified benchmark sampling distributions rather than the prevalence of interactions in a complete chemical--proteomic space. The study uses fixed molecular and protein feature caches, rather than learning representations from raw structures or sequences within each fold. Finally, the benchmark evaluates ranking and classification against annotated labels; experimental binding assays and prospective candidate selection are required before a prediction can support a pharmacological claim.",
    ]
    return "\n\n".join(text) + "\n"


def conclusion_fragment(summary: pd.DataFrame, raw: pd.DataFrame) -> str:
    context = comparison_context(summary, raw)
    structural = context["structural"]
    if structural["higher"].empty:
        evidence_sentence = (
            "Under the complete fixed-fold benchmark, the full model did not exceed its structural-only counterpart in any AUPR comparison. "
            "This result does not support a general predictive benefit from adding the S1/S2 branch under the tested protocol."
        )
    else:
        evidence_sentence = (
            "Under the complete fixed-fold benchmark, the full model exceeded its structural-only counterpart in "
            f"{len(structural['higher'])}/12 AUPR comparisons and was the highest-AUPR principal baseline in {len(context['winners'])}/12 conditions. "
            "The evidence supports the use of fold-local neighbour information as a split-dependent computational prioritization signal, while preserving the observed non-winning settings and the need for prospective experimental validation."
        )
    text = [
        r"\section{Conclusion}",
        "ArnoldiGCL-S1/S2 integrates separate drug and protein projections, a training-fold graph encoder and leakage-safe S1/S2 similarity-neighbour descriptors for DTI prediction. "
        + evidence_sentence,
    ]
    return "\n\n".join(text) + "\n"


def protocol_fragment(raw: pd.DataFrame) -> str:
    """Summarize fold sizes after checking they are method-invariant."""
    identity = ["dataset", "scenario", "seed", "fold"]
    columns = ["n_train", "n_val", "n_test", "n_test_positive"]
    consistency = raw.groupby(identity, sort=True)[columns].nunique(dropna=False).reset_index()
    if (consistency[columns] != 1).any(axis=None):
        raise RuntimeError("Fold sample counts are inconsistent across methods.")
    folds = raw.sort_values([*identity, "method"]).drop_duplicates(identity)[identity + columns]
    summary = folds.groupby(["dataset", "scenario"], sort=True)[columns].agg(["mean", "std", "count"]).reset_index()
    summary.columns = [
        "_".join(column).rstrip("_") if isinstance(column, tuple) else column for column in summary.columns
    ]

    def count_cell(dataset: str, scenario: str, column: str) -> str:
        row = summary[(summary["dataset"] == dataset) & (summary["scenario"] == scenario)]
        if len(row) != 1 or int(row.iloc[0][f"{column}_count"]) != 15:
            raise RuntimeError(f"Unexpected fold-size summary for {dataset}/{scenario}/{column}.")
        value = row.iloc[0]
        return f"{value[f'{column}_mean']:.0f} $\\pm$ {value[f'{column}_std']:.0f}"

    lines = [
        r"\subsection{Fold-level dataset sizes}",
        r"Table~\ref{tab:fold-sizes} reports realized sample counts across the frozen folds. "
        r"Counts may vary across cold-start folds because entities and eligible unannotated pairs are partition-specific.",
        r"\begin{table}[t]",
        r"\centering",
        r"\scriptsize",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Dataset & Split & Train pairs & Validation pairs & Test pairs & Test positives \\",
        r"\midrule",
    ]
    for dataset in results.DATASETS:
        for scenario in results.SCENARIOS:
            values = " & ".join(count_cell(dataset, scenario, column) for column in columns)
            lines.append(f"{results.DATASET_LABELS[dataset]} & {results.SCENARIO_LABELS[scenario]} & {values} " + r"\\")
        if dataset != results.DATASETS[-1]:
            lines.append(r"\midrule")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{Realized fold sizes (mean $\pm$ sample standard deviation across 15 fixed seed--fold evaluations).}",
            r"\label{tab:fold-sizes}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument(
        "--manuscript-root",
        default="manuscript",
        help="Local Overleaf manuscript directory that receives generated fragments.",
    )
    parser.add_argument("--expected-per-group", type=int, default=15)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    raw = results.load_rows(root)
    results.validate_complete(raw, args.expected_per_group)
    summary = results.aggregate(raw)
    manuscript_root = Path(args.manuscript_root).resolve()
    generated_dir = manuscript_root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "results_autogenerated.tex": result_fragment(summary, raw),
        "abstract_autogenerated.tex": abstract_fragment(summary, raw),
        "discussion_autogenerated.tex": discussion_fragment(summary, raw),
        "conclusion_autogenerated.tex": conclusion_fragment(summary, raw),
        "protocol_autogenerated.tex": protocol_fragment(raw),
    }
    for filename, content in outputs.items():
        output = generated_dir / filename
        output.write_text(content, encoding="utf-8")
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
