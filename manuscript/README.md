# ArnoldiGCL-S1/S2 DTI manuscript workspace

This directory is an Overleaf-ready manuscript scaffold. Numerical Results,
Abstract, Discussion and Conclusion are generated only after the fixed-fold
benchmark is complete and independently aggregated.

## One-sentence argument (working, evidence-bounded)

In binary drug--target interaction (DTI) prediction, we evaluate whether an
ArnoldiGCL structural encoder augmented with leakage-safe, training-label-only
similarity-neighbour statistics (S1/S2) improves prediction across frozen
random and cold-start splits, while reporting settings in which it does not
outperform simpler baselines.

## Terminology ledger

| Canonical term | First-use definition | Decision |
|---|---|---|
| DTI | drug--target interaction | Use `DTI` after first expansion. |
| ArnoldiGCL-S1/S2 | working name for ArnoldiGCL plus S1/S2 | Publication name not fixed. |
| S1 | four 10-neighbour rate and dispersion descriptors | Defined from `A_train` only. |
| S2 | three 20-neighbour consistency descriptors | Defined from `A_train` only. |
| Morgan fingerprint | 1,024-bit radius-2 Morgan bit vector | Cached drug feature. |
| ESM-2 | mean-pooled ESM-2 t30/150M protein embedding | Cached 640-dimensional feature. |
| Random / cold drug / cold protein / cold pair | four frozen split scenarios | Use exact labels throughout. |
| AUC / AUPR | ROC area / precision--recall area | Primary discrimination metrics. |

## Evidence gates before replacing placeholders

1. Every B1--B5 and ablation method has 15 results for every dataset--scenario group.
2. Coverage, duplicate identities and DrugBAN's 100-epoch setting pass `verify_paper_coverage.py`.
   DrugBAN results must also record the enabled input cache and the common TF32
   execution setting.
3. Tables, source data, paired comparisons and Python figures are regenerated from result JSON files.
4. `generate_manuscript_results.py` writes the five generated LaTeX fragments
   (`results`, `abstract`, `discussion`, `conclusion` and fold-size `protocol`)
   from the same complete results; the source never contains hand-entered
   performance claims.
5. Every claim states dataset, split, metric, comparator and fold count; mixed results stay in the main text.
6. References are added only after their original publications are checked.

## Source of truth

- `paper_benchmark.py` freezes splits and runs B1--B4/M8.
- `run_drugban_fold.py` adapts DrugBAN to those identical frozen splits.
- `plot_paper_results.py` fails closed until complete result coverage is present.
- `generate_manuscript_results.py` writes numerical and evidence-bounded prose
  fragments only after the same complete-coverage check passes.
- `final_paper_audit.py` independently validates result identities, shared split
  signatures, formal DrugBAN metadata and the required aggregate artifacts.
- `verify_split_integrity.py` independently validates the 180 frozen split
  files, cold-start entity isolation, unannotated negative labels and every
  formal result JSON's split signature.
- `write_dataset_manifest.py` records the exact CSV hashes, Git-blob hashes,
  observed dataset sizes and the verified pinned DrugBAN source snapshot.  It
  records provenance without claiming rights to redistribute the original data.
- `write_environment_manifest.py` records the final interpreter, package and
  GPU environment, together with SHA256 hashes of the key pipeline scripts;
  it also records the external ArnoldiGCL core path and hash when
  `DTI_CORE_PATH` is set.
- A preserved short DrugBAN smoke run is execution provenance only. The coverage
  verifier, final audit and plotting code exclude it before formal fold-identity
  accounting; only 100-epoch, cached, TF32 DrugBAN artifacts enter B5 results.
- Do not hand-edit numerical tables; generate them from the frozen artifacts.

## Finalization command

Run the repository-level `finalize_overleaf_package.sh` from the local
repository root (`/Users/fly/Documents/ChatGPT/Drug-Target` in the current
workspace) after the formal DrugBAN queue finishes. The script first requires
the remote split-integrity gate (`SPLIT_INTEGRITY_COMPLETE`) and the complete
result-identity gate (`FINAL_AUDIT_COMPLETE`), then regenerates the aggregate
tables, paired statistics, source-data CSVs and Python figures from those
results. It performs a second complete-release audit including those artifacts,
generates the result-derived fragments, synchronizes only the audited release
and compiles a local PDF. The script does not contain credentials; use an
approved SSH authentication method.
The audit commands must emit their named completion markers as well as return
success; a missing marker stops the release before any release-time write.

To additionally create a clean ZIP for direct Overleaf upload, pass a new
destination path, for example `--overleaf-zip /path/to/dti-overleaf.zip`.
The exporter refuses to overwrite an existing ZIP and excludes local build
directories. It runs only after the remote audits, artifact synchronization,
placeholder gate and local PDF QA have succeeded.

For a manual remote-only generation step, use:

```bash
/mnt/sda/fulaiyi/aspect_env/bin/python \
  /mnt/sda/fulaiyi/dti_paper_20260826_v2/generate_manuscript_results.py \
  --root /mnt/sda/fulaiyi/dti_paper_20260826_v2 \
  --manuscript-root /mnt/sda/fulaiyi/dti_paper_20260826_v2/manuscript_generated
```

Only after the second artifact-inclusive audit succeeds should
`figure_2_baselines.*`, `figure_3_ablation.*`, `source_data/`, `tables/` and the
generated `.tex` fragments be copied from that same audited remote root and
used to compile `main.tex` for Overleaf.

## Author confirmation required before submission

1. Author list, affiliations and contribution statement.
2. Target journal and its article-format requirements.
3. The original public records, versions and licences of the local BioSNAP,
   Human and BindingDB CSV files.
4. A durable repository, release identifier and licence for the frozen splits,
   source data and code package.
