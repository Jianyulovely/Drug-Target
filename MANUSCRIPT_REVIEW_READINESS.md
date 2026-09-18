# DTI manuscript: pre-submission review readiness

This register separates demonstrated evidence from items that require the
completed DrugBAN baseline or author confirmation. It is not a substitute for
the final result audit.

## Working argument

In binary drug--target interaction prediction, we test whether adding
leakage-safe, training-label-only similarity-neighbour descriptors (S1/S2) to
an ArnoldiGCL structural predictor improves ranking on frozen random and
cold-start splits, while retaining settings where it does not outperform
simpler baselines.

## Evidence already available

| Reviewer question | Evidence | Status |
|---|---|---|
| Are comparisons on identical held-out data? | 180 frozen split files; B1--B4/M8 result signatures checked against their split. | Verified for 1,620 formal B1--B4/M8 records. |
| Is label leakage guarded against? | The verifier checks train-only positive labels, unannotated negative sampling, cold-start isolation and split signatures. | Verified for frozen splits and B1--B4/M8 records. |
| Is the S1/S2 contribution isolated? | Structural-only, S1-only, S2-only and partition-wise shuffled S1/S2 controls are prespecified. | Results available for B1--B4/M8; full comparison awaits B5. |
| Are baseline families diverse? | Logistic regression, MLP, graph GCN, threshold GCN and DrugBAN are prespecified. | B1--B4/M8 complete; formal DrugBAN pending. |
| Can numerical prose be traced to source data? | Plotting and manuscript generation fail closed on complete 15-fold coverage and write CSV source data. | Pipeline verified; full execution awaits B5. |
| Are the current citations bibliographically accurate? | DOI, author order, title, venue and locator were checked against Crossref metadata for all ten BibTeX entries. | Verified; see `REFERENCE_AUDIT.md`. |
| Is the structural encoder's original source identified? | The manuscript now cites ArnoldiGCL directly, and the release-time environment manifest records the external core script hash. | Verified at the source and compile level; final remote manifest is regenerated at release time. |

## Open gates before any performance claim

1. **Formal B5 coverage:** 180 DrugBAN results with 100 epochs,
   `input_cache=true` and `tf32=true`.
2. **Whole-release audit:** 1,800 formal method--dataset--scenario--fold
   identities, aligned split signatures, valid metrics and all tables/figures.
3. **Result-derived prose:** regenerate the Abstract, Results, Discussion and
   Conclusion from the audited artifacts; do not manually insert performance
   values.
4. **Visual QA:** compile the resulting PDF and inspect the figures, tables,
   pagination and references.

## Reviewer-risk controls after B5 completes

| Risk | Required check before submission |
|---|---|
| Selective reporting | Keep every random and cold-start scenario in the generated tables and state non-winning conditions in Results and Discussion. |
| Inflated ablation interpretation | Describe shuffled S1/S2 as evidence about pairwise alignment of a feature, not as biological causality. |
| Comparator overstatement | Call the threshold model ``Threshold GCN''; do not represent it as a complete external-method reproduction. |
| Input-modality confounding | State that frozen partitions align evaluated pairs, but do not make DrugBAN's SMILES/sequence inputs identical to Morgan/ESM-2 inputs. |
| Unannotated-negative interpretation | State that capped unannotated-pair sampling may contain unknown positives and that metrics describe the benchmark sampling distribution, not population interaction prevalence. |
| Weak cold-start claim | Name the split type, dataset, metric, mean difference and 15-fold basis for every claim. |
| Reproducibility ambiguity | Release split files, JSON metrics, source-data CSVs, environment specification and exact code revision. |
| Dataset provenance ambiguity | Confirm original public records, versions and licences for the local BioSNAP, Human and BindingDB files. |

## Author inputs still required

- Author list, affiliations, contribution statement and competing-interest declaration.
- Target journal and its article type, word limits and figure policy.
- Original data-source records, versions and redistribution licences.
- Repository DOI or other durable release identifier, code revision and licence.
