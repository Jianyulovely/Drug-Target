# DTI benchmark report-readiness summary

## Current state

**Technical result release: complete and audited (2026-09-04).**

- Formal DrugBAN coverage: 180/180, with 100 epochs, cached inputs and TF32 enabled.
- Full benchmark coverage: 1,800/1,800 result identities (10 methods × 3 datasets × 4 scenarios × 15 folds).
- Frozen split audit: `SPLIT_INTEGRITY_COMPLETE` (180/180 splits).
- Full coverage audit: `COVERAGE_COMPLETE` (1,800/1,800 results).
- Artifact-inclusive audit: `FINAL_AUDIT_COMPLETE`, `audit_results=1800`, `errors=0`.
- Runtime-manifest audit: `FINAL_AUDIT_COMPLETE`, `errors=0`.
- Aggregate tables, paired statistics, source-data CSVs, Figure 2 and Figure 3 in SVG/PDF/PNG/TIFF are non-empty.
- Five data-derived LaTeX fragments were generated without TODO placeholders.

The technical report PDF was compiled locally to 10 pages. The final LaTeX pass has no errors, undefined references/citations, or overfull/underfull box diagnostics; all 10 pages were rendered for QA. The author and release placeholders remain intentionally visible.

## Evidence-bounded result summary

The proposed ArnoldiGCL-S1/S2 model had the highest mean AUPR among the principal baselines in **7/12** dataset–scenario conditions. Relative to the structural-only ArnoldiGCL variant, it had higher mean AUPR in **11/12** conditions; the positive differences ranged from **0.013 to 0.396 AUPR**, with 11 descriptive paired contrasts below the BH-adjusted 0.05 threshold.

It was not the highest-AUPR principal baseline in BioSNAP/cold-protein, Human/cold-protein, Human/cold-pair, BindingDB/cold-protein or BindingDB/cold-pair. The report therefore supports a split-dependent generalization result, not universal SOTA or uniform superiority. It does not establish experimental target binding or prospective pharmacological utility.

## Goals moved forward

1. **Experiment completion:** B5 DrugBAN and all 180 formal folds are complete.
2. **Integrity and reproducibility:** frozen splits, signatures, metadata and all 1,800 result identities pass the independent gates.
3. **Results package:** tables, source data, paired tests, figures and generated manuscript fragments are complete.
4. **Technical report:** a locally compiled and rendered 10-page report is available for internal review.
5. **Submission package:** remains gated on author names/affiliations, contributions and declarations, target journal, code/archive identifier, and confirmed original-data terms.

## Remaining author-controlled goals

- Complete `manuscript/SUBMISSION_METADATA.template.md`.
- Confirm whether the input CSVs may be redistributed; if not, release checksums, split indices and processing code while directing readers to the original providers.
- Supply the public code/release/DOI and choose the target journal format.
- After those confirmations, rerun the finalizer, compile the submission PDF, render-check every page, and create a new non-overwriting Overleaf ZIP.

## Local deliverables

- Technical PDF: `manuscript/build_report_20260904T1150/main.pdf`
- Generated Results/Abstract/Discussion/Conclusion/Protocol: `manuscript/generated/`
- Tables: `manuscript/tables/`
- Source data and manifests: `manuscript/source_data/`
- Main figures: `manuscript/figures/figure_2_baselines.pdf` and `manuscript/figures/figure_3_ablation.pdf`
- Submission metadata form: `manuscript/SUBMISSION_METADATA.template.md`
