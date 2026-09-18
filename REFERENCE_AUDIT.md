# Reference metadata audit

## Scope and method

This audit covers every one of the eleven entries in
`manuscript/references.bib` used by the current manuscript. On 2026-08-28, the
DOI, title, journal, year, volume, issue, locator, and author-family-name order
were compared against Crossref's DOI metadata for the original ten entries.
The ArnoldiGCL entry was added and checked against Crossref metadata on
2026-08-29. For the Nature Communications record, DOI content negotiation was
also used because Crossref stores its locator as an `article-number` rather
than a page range.

## Result

All eleven entries passed. No bibliographic metadata needs to be changed before
the final result-derived manuscript is generated.

| BibTeX key | DOI | Metadata check | Notes |
|---|---|---|---|
| `bai2023drugban` | `10.1038/s42256-022-00605-1` | Passed | Authors, title, *Nature Machine Intelligence* 5(2), 126--136 match. |
| `liu2007bindingdb` | `10.1093/nar/gkl999` | Passed | Authors, title, *Nucleic Acids Research* 35(Database), D198--D201 match. |
| `huang2021moltrans` | `10.1093/bioinformatics/btaa880` | Passed | Authors, title, *Bioinformatics* 37(6), 830--836 match. |
| `chen2020transformercpi` | `10.1093/bioinformatics/btaa524` | Passed | Authors, title, *Bioinformatics* 36(16), 4406--4414 match. |
| `liu2016nrlmf` | `10.1371/journal.pcbi.1004760` | Passed | Authors, title, *PLOS Computational Biology* 12(2), e1004760 match. |
| `luo2017dtinet` | `10.1038/s41467-017-00680-8` | Passed | The locator `573` is the publisher/Crossref article number; retaining it in the `pages` field is appropriate for this BibTeX style. |
| `ozturk2018deepdta` | `10.1093/bioinformatics/bty593` | Passed | Authors, title, *Bioinformatics* 34(17), i821--i829 match. |
| `nguyen2021graphdta` | `10.1093/bioinformatics/btaa921` | Passed | Authors, title, *Bioinformatics* 37(8), 1140--1147 match. |
| `lin2023esm` | `10.1126/science.ade2574` | Passed | All fifteen authors, title, *Science* 379(6637), 1123--1130 match. |
| `rogers2010ecfp` | `10.1021/ci100050t` | Passed | Authors, title, *Journal of Chemical Information and Modeling* 50(5), 742--754 match. |
| `coskun2025arnoldigcl` | `10.1145/3711896.3736847` | Passed | Authors, title, *Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2*, 380--391 match. |

## Boundary

This is a bibliographic-metadata audit, not evidence that each cited method
supports every manuscript interpretation.  Final scientific claims remain
constrained by the audited B1--B5/M8 experimental artifacts and should be
regenerated only after B5 coverage is complete.
