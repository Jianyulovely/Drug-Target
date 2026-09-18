# Submission metadata required from the authors

The experimental pipeline can produce the result tables, figures and
data-derived manuscript text automatically.  The following publication
metadata cannot be inferred safely and must be confirmed before submission.

For a directly fillable version, copy and complete
[`manuscript/SUBMISSION_METADATA.template.md`](manuscript/SUBMISSION_METADATA.template.md).
For a Chinese fill-in form with the same fields, use
[`manuscript/SUBMISSION_METADATA.zh-CN.md`](manuscript/SUBMISSION_METADATA.zh-CN.md).

## Minimal handoff required to unblock final packaging

The technical pipeline fills all numerical results after B5. The smallest
author-supplied handoff is one completed metadata form containing: (1) target
journal and article type; (2) author order, affiliations and corresponding
author contact; (3) CRediT, competing-interest, funding and acknowledgement
statements; (4) code repository/release and archive location or DOI; and (5)
the input-data redistribution decision and provider-terms wording. The form
deliberately keeps these decisions separate from experimental code so that no
author, licence or archival claim is invented by the release script.

## 1. Author block

- Full author names, author order and institutional affiliations.
- Corresponding author name and email address.
- ORCID identifiers, equal-contribution statements and shared corresponding
  authorship, if applicable.

## 2. Declarations

- CRediT-style author-contribution statement.
- Competing-interest statement (including an explicit ``none'' statement when
  applicable).
- Funding, acknowledgements and institutional-computing acknowledgement text,
  if required by the target journal.
- Confirmation of whether any ethics, consent or data-access statement is
  required for the curated public DTI data used here.

## 3. Dataset provenance

The exact CSV source has now been independently verified: each local file is
byte-identical to the corresponding \texttt{full.csv} in the DrugBAN repository
snapshot at commit \texttt{9923f8c99959e00263103ff9ac61ba0eaccc8e02}. Its dataset
documentation identifies BindingDB, MolTrans/BioSNAP and
TransformerCPI/Human. Please confirm that these source records are acceptable
for the intended venue and provide any required original-provider licence or
terms-of-use wording. Do not assert redistribution rights based only on the
repository's MIT software licence.

### Licence boundary confirmed so far

- The MolTrans repository declares a BSD-3-Clause software licence and the
  TransformerCPI repository declares an Apache-2.0 software licence. These
  repository-level licences do not by themselves establish redistribution
  rights for the upstream BioSNAP or Human data.
- The BindingDB website describes itself as a public molecular-recognition
  database and offers downloads, but the official pages inspected for this
  release did not provide a dataset-specific redistribution licence suitable
  for copying into this manuscript.

Before releasing the input CSV files, confirm the current terms of use or
licence for each original provider. If those terms do not allow redistribution,
archive only the split indices, checksums, data-processing code and result
artifacts, and direct readers to obtain the source data themselves.

## 4. Code and result release

- Public repository URL, release tag or commit hash, and software licence.
- Persistent archive DOI (for example, a Zenodo release) if the target journal
  requires one.
- Destination for complete fold-level results, source-data CSV files and
  frozen split files, together with any access restrictions.

## 5. Journal decision

Confirm the intended venue before final styling.  The current manuscript is a
clean generic LaTeX project; title-page structure, declarations, reference
style, data-availability wording and supplementary-file conventions must then
be adapted to that journal's current author instructions.

## What the pipeline will fill after B5

After all 180 formal DrugBAN records pass audit, the generator will replace
the result, abstract, discussion, conclusion and fold-size placeholders with
data-derived text, tables, source data and figures. The release-time runtime
manifest will record the exact software, GPU/driver and key-script hashes.
Aggregate wall-clock time is deliberately not reported in the manuscript:
per-fold duration is not a standardized field in every formal result artifact.
