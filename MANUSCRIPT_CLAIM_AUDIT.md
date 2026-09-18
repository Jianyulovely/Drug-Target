# Manuscript claim--evidence audit

**Scope.** Algorithmic DTI-prediction manuscript, generic journal format,
reviewed before final DrugBAN (B5) coverage. This is a claim-discipline audit,
not a substitute for the final result audit.

## One-sentence argument

In binary DTI prediction, this work tests whether seven training-label-only,
similarity-neighbour descriptors (S1/S2) add reliable ranking value to an
ArnoldiGCL structural predictor across frozen random and cold-start splits,
using ablations and shuffled controls, while reporting settings where they do
not outperform simpler matched-partition comparators.

## Terminology ledger

| Canonical term | First-use definition | Decision |
|---|---|---|
| DTI | drug--target interaction | Use `DTI` after first expansion. |
| ArnoldiGCL-S1/S2 | structural ArnoldiGCL predictor plus all seven side-information descriptors | Use this only for the full model; use `ArnoldiGCL structural-only`, `+S1`, `+S2` for ablations. |
| S1/S2 side information | seven candidate-pair descriptors calculated from feature neighbours and positive training DTI edges | Do not call these DTI scores or biological similarities. |
| Threshold GCN | GCN comparator with a 0.3 within-type similarity threshold | Do not call it an external ColdDTI reproduction. |
| DrugBAN | matched-partition SMILES-graph/protein-sequence comparator | Do not describe its inputs as identical to Morgan/ESM-2 inputs. |
| cold-drug / cold-protein / cold-pair | frozen held-out evaluation scenarios | Name the split on every scenario-specific claim. |

## Claim audit

| Priority | Reviewer question | Current evidence | Required resolution |
|---|---|---|---|
| P0 | Do S1/S2 improve performance, and where do they fail? | B1--B4/M8 complete; B5 incomplete. | Generate all performance prose only after the 1,800-identity audit. Include ties/losses in the main Results and Discussion. |
| P0 | Was the full architecture chosen without test-set selection? | The manuscript describes ArnoldiGCL-S1/S2 as the ``full model'' and does not claim that a test-set search selected it. | Resolved at the wording level on 2026-08-29. If a separate architecture-selection study is later reported, authors must document its pre-specified selection rule and data boundary. |
| P0 | Are all labels and graph-derived features fold-local? | Fold-local graph, train-positive S1/S2 construction and candidate-label exclusion tests are documented. | Retain the split audit and candidate-label-exclusion test in the release; state the exact treatment of held-out entities in the graph if reviewers request implementation detail. |
| P1 | Are the baselines fairly framed? | Frozen pairs align all comparators; DrugBAN's modality difference and Threshold GCN limitation are stated. | Keep the new scope sentence: this is a controlled baseline panel, not exhaustive SOTA reproduction. Do not claim superiority over the DTI literature generally. |
| P1 | Are statistical claims calibrated? | 15 seed--fold evaluations; paired effect sizes, Wilcoxon summaries and BH adjustment are specified. | Report paired effect sizes and descriptive inference together; do not treat folds as independent biological replicates. |
| P1 | Can numerical text be traced? | Generator, source-data pipeline and synthetic full-release regression are available. | Regenerate Abstract/Results/Discussion/Conclusion only from final audited CSVs. |
| P2 | Are data and code reusable? | Dataset byte provenance, frozen splits and runtime manifests are prepared. | Authors must confirm upstream data terms and code/result release identifier before submission. |

## Manuscript changes made in this audit

- Standardized the comparator name as **Threshold GCN** in Methods.
- Added an explicit controlled-baseline scope statement in Experimental
  protocol; this prevents the manuscript from implying an exhaustive SOTA
  comparison.
- Replaced ``selected model'' with ``full model'' in the Introduction and
  Figure~1 caption, avoiding an unsupported implication of test-set-driven
  architecture selection.

## 2026-08-29 Methods--protocol source audit

The Methods and Experimental protocol were checked against
`paper_benchmark.py`, the S1/S2 regression tests and the result-generation
pipeline. The following manuscript statements match the current implementation:

- Morgan radius-2, 1,024-bit drug inputs and mean-pooled ESM-2 t30/150M,
  640-dimensional protein inputs are separate feature modalities and pass
  through distinct, non-shared learned projections.
- Drug and protein similarities are cosine similarities of cached feature
  vectors, rather than values computed from DTI labels or predictions.
- The seven side features are calculated only from the training-positive
  adjacency: S1 contains top-10 drug-neighbour support and cross-neighbour
  support means and standard deviations; S2 contains top-20 drug-to-protein,
  protein-to-drug and cross-neighbour means. Candidate self-neighbours are
  excluded.
- The stated ablations correspond to the runner: structural-only, S1-only,
  S2-only, full S1+S2 and a deterministic partition-wise shuffle that
  preserves the seven marginal columns while breaking candidate-pair
  alignment.
- The protocol correctly treats DrugBAN as a matched-partition comparator with
  distinct SMILES-graph/protein-sequence inputs, not a reproduction of its
  published numbers.
- The ArnoldiGCL structural encoder is now linked to its original publication
  (`coskun2025arnoldigcl`); this citation identifies the encoder family and does
  not claim that the present DTI benchmark reproduces the original task or
  evaluation.

This check does not establish any performance claim. Formal DrugBAN coverage,
the 1,800-identity audit, data-derived Results text and author-supplied
submission metadata remain the release gates.

## 2026-08-31 partial performance preview

A read-only aggregation of the `paper-benchmark-v2` JSONs at the 2026-08-31
11:20:26 +08:00 snapshot was used only to plan claim wording. The existing
comparison methods each had 15 folds in all 12 dataset--scenario cells, while
formal DrugBAN had 128/180 cells filled at that historical snapshot; the
current coverage is tracked in `DELIVERY_CHECKLIST.md` and `PROJECT_ROADMAP.md`.
The proposed `arnoldi_s12` model has 15 folds in all 12 cells. Its preliminary
pattern is strongest in the random and cold-drug settings, whereas MLP or GCN
leads in several cold-protein and cold-pair settings. These observations are
not release results until the remaining DrugBAN B5 records, split audit and
paired statistics are complete; the final manuscript must report both wins and
non-wins rather than claim uniform superiority.

The fail-closed result audit was also tightened: only the retained 2-epoch
DrugBAN smoke artifact is excluded as nonformal; any other non-100-epoch
DrugBAN artifact is now reported as an audit error rather than silently
ignored. The disposable full-release regression still passes after this
change.

## Final pre-submission gate

Before claims are released, require all of the following: complete B5 coverage,
passing split and final artifact audits, regenerated result-derived text,
rendered-PDF inspection, and author confirmation of the metadata listed in
`AUTHOR_INPUT_REQUIRED.md`.
