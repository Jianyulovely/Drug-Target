# DTI paper delivery checklist

This checklist defines the evidence required before the DTI manuscript package
is described as complete. Queue logs or an empty GPU alone are not completion
evidence.

**Latest live snapshot (2026-09-02 04:23:16 +08:00):** formal DrugBAN coverage
is 148/180. BioSNAP and Human are complete (60/60 each); BindingDB is 28/60
(random 15/15, cold-drug 13/15, cold-protein 0/15, cold-pair 0/15). The queue,
four workers and all four GPU compute processes are alive; process-matched
task logs report epochs 90, 90, 50 and 80, and the failure list is empty. The
next release action remains blocked on the remaining 32 BindingDB records.

| Gate | Required evidence | Current state |
|---|---|---|
| B1--B4/M8 result integrity | `final_paper_audit.py --methods lr,mlp,gcn,colddti,arnoldi_v4,arnoldi_s1,arnoldi_s2,arnoldi_s12,arnoldi_s12_shuffle --expected-per-group 15` prints `FINAL_AUDIT_COMPLETE`. | Complete: 1,620 results audited. |
| Frozen-split integrity | `verify_split_integrity.py` prints `SPLIT_INTEGRITY_COMPLETE` after checking all 180 NPZ files and each formal result signature. | Complete: 180 splits and 1,620 result signatures audited. |
| Candidate-label exclusion in S1/S2 | `test_side_feature_label_exclusion.py` perturbs each queried candidate label and requires its own seven-dimensional S1/S2 vector to remain unchanged. | Complete: CPU regression test passed on 2026-08-28 for training-entity and cold-start query cases. |
| Shuffled S1/S2 control semantics | `test_side_feature_shuffle_control.py` requires the partition-wise shuffle to be deterministic, to preserve all seven feature marginals and to disrupt the original candidate-pair assignment. | Complete: CPU regression test passed on 2026-08-28. |
| Dataset provenance | `write_dataset_manifest.py` writes the SHA256 and Git-blob hashes. The audit requires all three files to match the pinned DrugBAN commit `9923f8c99959e00263103ff9ac61ba0eaccc8e02`. | Complete: BioSNAP, Human and BindingDB byte-match the pinned public snapshot; original-provider terms still require author confirmation. |
| Post-processing regression | `test_postprocessing_pipeline.py` builds a disposable 1,800-record fixture and must generate aggregate tables, both figures, source-data CSVs, all five LaTeX fragments, a compiled disposable manuscript PDF and a passing full-artifact audit. | Complete: the full synthetic 1,800-record end-to-end run passed locally on 2026-08-28 with `/opt/miniconda3/bin/python3` (Python 3.8.18), including aggregation, Python figures, LaTeX fragments, fixture PDF and `FINAL_AUDIT_COMPLETE`; the same run also passed queue scheduling, cached-dataset equivalence and the nonformal-DrugBAN smoke exclusion regression. An additional all-non-positive S1/S2 fixture confirms that generated prose reports the null effect instead of failing or claiming a gain. |
| LaTeX preflight | The manuscript source must compile with no undefined citations or references; the result-derived manuscript is compiled again only after the final remote audit. | Complete for the pre-B5 template: compiled and visually inspected as a 7-page PDF on 2026-08-29 after the Figure 1 revision; no undefined citations/references or layout defects were found. Figure 1 exports SVG/PDF/600-dpi PNG/600-dpi TIFF, retains editable SVG text, and states the encoder-separation and training-fold label boundary. The current red placeholders are intentional and final result-derived PDF remains pending B5. |
| B5 result integrity | 180 formal DrugBAN records, each with `pipeline_version=paper-benchmark-v2`, `settings.epochs=100`, `settings.input_cache=true`, and `settings.tf32=true`. | Running: the latest 2026-09-02 01:00:29 +08:00 read-only snapshot found 148/180 formal records. BioSNAP and Human are complete (60/60 each); BindingDB random is complete (15/15), cold-drug is 13/15, and cold-protein/cold-pair remain 0/15. The queue, four workers and release post-processing watcher were live; all four GPUs had active DrugBAN compute. Process-matched logs showed epochs 40, 40, 1 and 30; three log files were older but their corresponding Python processes remained in active GPU compute, so this was not treated as a stall. The failure list and recent matched-error scan were empty. This is a liveness snapshot, not final coverage evidence. |
| B5 throughput safety | Any throughput acceleration must preserve the frozen splits, model, seed, 100 epochs, batch size 64 and result identity; task ownership must remain complete and disjoint. | Ready locally: `run_drugban_queue.sh` defaults to one worker per GPU and now supports a staged `DRUGBAN_WORKERS_PER_GPU` setting. `test_drugban_queue_schedule.py` passed for one, two and three virtual workers per GPU (180 unique tasks). The cached input dataset preindexes the same positional SMILES/protein/label rows; its standalone test and a read-only remote check across real BioSNAP, Human and BindingDB training CSVs passed. On 2026-08-28 the optimized runner was deployed after preserving `run_drugban_fold.preindex_backup_20260828T122505.py`; its remote SHA256 matches the tested local copy and compilation passed. Active Python processes continue with their loaded code; only later folds use the optimized data path. The active four-worker scheduler itself remains unmodified. A single non-overlapping BindingDB/cold-pair GPU-0 sidecar was run as a same-configuration throughput observation. It completed epoch 1 in 231.0 s with no error, but raised the concurrent original GPU-0 BioSNAP task from about 163.6 to 202.9 s/epoch while host load was about 122/128 logical CPUs. The sidecar was therefore terminated after one epoch; it wrote no formal JSON, and its logs/split files remain for diagnosis. Its formal fold identity stays missing and will be processed by the unchanged main queue. Do not add sidecars or enable multi-worker-per-GPU mode on this host. |
| GCN numerical equivalence | The memory-safe chunked and sparse GCN aggregations must agree with the original layer for forward output and backward gradients. | Complete: `test_chunked_gcn_equivalence.py` passed again on the remote host on 2026-08-31 at 23:10 with `CUDA_VISIBLE_DEVICES=''`; the 15-node CPU fixture reported matching forward and backward values within `rtol=1e-6`, `atol=1e-7`, without contending with active GPU training. |
| Full benchmark coverage | `final_paper_audit.py --require-artifacts` prints `FINAL_AUDIT_COMPLETE` for B1--B5/M8: 10 methods x 3 datasets x 4 scenarios x 15 folds = 1,800 formal result identities. | Pending B5. |
| Aggregate data and figures | Non-empty `tables/`, `source_data/`, `figure_2_baselines.*`, `figure_3_ablation.*`, and aggregate/plot logs exist; the audit checks these exact paths. | Pending B5. |
| Release-gated post-processing | A background process must wait for the current queue to exit naturally, reject live workers or a non-empty failure list, and run split, coverage, result and artifact audits before generating aggregates, figures and manuscript fragments. | Active: PID 3235770 launched at 2026-08-29 07:31:01 +08:00, logging to `logs/drugban_release_postprocess_20260829T073100+0800.log` and polling every 1,800 seconds. The reviewed local release script now places split-integrity before coverage; the active remote watcher is not modified during monitoring. Remote SHA256 of `postprocess_after_drugban.sh` matches the already-deployed copy (`c1beee28455eac72104ec1aab48cceaf704fc971bbfab128a182d534a4889415`). The remote `write_environment_manifest.py` also matches the local reviewed copy (`b64d4bed41c49b5b50fd3c1187e60348b5cadb5db53b8aa8c1b4d125e39966bf`). The gate now also rejects any remaining same-class queue process; its clean-release, failure-list and remaining-queue rejection regression paths passed locally (`test_postprocess_after_drugban.sh`). It does not start or restart training. |
| Runtime provenance | `source_data/environment_manifest.json` records the interpreter, package versions, GPU query and SHA256 hashes of the key pipeline scripts; final packaging regenerates and copies it. | Ready; generated only from the final remote environment. |
| Password-authenticated finalization | If password authentication is used, `finalize_overleaf_package.sh` must receive `SSHPASS` from its invoking shell and use `sshpass -e`; no credential may appear in the script, manuscript or logs. | Ready; wrapper syntax and help entry verified. |
| Data-derived paper text | `generate_manuscript_results.py` emits Results, Abstract, Discussion, Conclusion and protocol fragments from the audited data. Numerical claims must not be hand-entered. | Pending B5. |
| Finalizer placeholder gate | Inactive `\IfFileExists` fallback TODOs must not reject a complete release; generated result fragments must contain no TODO; author block, declarations and release identifiers must still block submission until supplied. | Ready: the gate was corrected and the full synthetic 1,800-record post-processing regression passed on 2026-08-29, including generated-fragment TODO checks and temporary manuscript compilation. `test_finalizer_placeholder_gate.py` additionally passed both gate paths: unresolved author/release data is rejected, while a completed metadata fixture with inactive fallback TODOs is accepted. |
| Overleaf PDF QA | `finalize_overleaf_package.sh` succeeds, leaving a non-empty `manuscript/build/main.pdf`, no undefined citations/references, and a rendered first-page preview. | Pending B5. |
| Clean Overleaf source export | After final QA, `finalize_overleaf_package.sh --overleaf-zip PATH` writes a non-overwriting ZIP containing the audited manuscript, figures, tables, source data and generated fragments, excluding build directories. | Ready locally: `test_overleaf_zip_export.py` verified required-file inclusion, build-directory exclusion, missing-artifact refusal and overwrite refusal on 2026-09-01. Full export remains gated on B5 and author metadata. |
| Submission metadata | Authors provide affiliations/contributions, target journal format, original data records/versions/licences and an archival code/data release identifier; see [AUTHOR_INPUT_REQUIRED.md](AUTHOR_INPUT_REQUIRED.md). | Author action required. |

The minimal author handoff is a completed
`manuscript/SUBMISSION_METADATA.template.md`: target journal/article type;
author and affiliation block; declarations; code/release/archive fields; and
the data-redistribution decision with provider-terms wording. This is kept
outside the experimental code because those claims cannot be inferred safely.

**Current B5 status takes precedence over the historical row snapshot:** the
latest 2026-09-01 16:20:12 +08:00 read-only count is 143/180 formal DrugBAN records (BioSNAP 60/60,
Human 60/60 and BindingDB 23/60), with 37 BindingDB folds still pending and an
empty active failure list. Earlier timestamps in this checklist preserve
diagnostic history rather than state the current coverage.

Latest B5 status note (2026-09-01 20:04:07 +08:00): a fresh read-only check
found 144/180 formal DrugBAN records, with BindingDB/cold-drug at 9/15 and
BindingDB/cold-protein and cold-pair at 0/15. Four process-matched workers
were computing on GPUs 0--3, and the active failure list was empty. This
supersedes the older 143/180 snapshot above; the historical row is retained
for traceability.

Latest B5 progress note (2026-09-01 22:08:20 +08:00): formal coverage increased
to 145/180. BindingDB/cold-drug reached 10/15; cold-protein and cold-pair
remain 0/15. The queue and four workers were alive, the release watcher was
still waiting, all four GPUs had active DrugBAN compute, and no recent matched
worker/task errors or failure-list entries were found. The queue completed
BindingDB/cold-drug seed 983997847 fold 2 at 21:55:31 and started
BindingDB/cold-protein seed 1941488137 fold 1. No restart or sidecar is
justified.

Latest B5 progress note (2026-09-01 22:35:43 +08:00): formal coverage increased
to 146/180. BindingDB/cold-drug reached 11/15; cold-protein and cold-pair
remain 0/15. The queue and four workers were alive, the release watcher was
still waiting, all four GPUs had active DrugBAN compute, and no recent matched
worker/task errors or failure-list entries were found. The queue completed
BindingDB/cold-drug seed 983997847 fold 0 at 22:18:34 and started fold 4. No
restart or sidecar is justified.

Latest B5 progress note (2026-09-01 22:58:56 +08:00): formal coverage increased
to 147/180. BindingDB/cold-drug reached 12/15; cold-protein and cold-pair
remain 0/15. The queue and four workers were alive, the release watcher was
still waiting, all four GPUs had active DrugBAN compute, and no recent matched
worker/task errors or failure-list entries were found. The queue completed
BindingDB/cold-drug seed 983997847 fold 1 at 22:47:04 and started
BindingDB/cold-protein seed 1941488137 fold 0. No restart or sidecar is
justified.

Local finalizer order note (2026-08-31 08:41:10 +08:00):
`finalize_overleaf_package.sh` now performs the read-only frozen-split audit
first and the complete-result audit second; only after both pass does it write
the dataset/runtime manifests or generate release artifacts. Shell syntax, the
help path, placeholder-gate regression and release-order regression passed.

Pre-B5 regression checkpoint (2026-08-31 23:10 +08:00): seven environment-
independent tests passed with the usable local Conda interpreter, covering
cached-DrugBAN equivalence, queue scheduling, side-feature leakage/shuffle
controls, post-processing, finalizer ordering and placeholder gates. The
sparse-aggregation smoke test was not run to completion because this laptop
has no CUDA; the chunked-GCN equivalence test additionally requires the
remote-only core file and is therefore marked for remote verification. These
checks validate the release path but do not substitute for the pending 48
remote BindingDB folds.

Latest local release regression checkpoint (2026-09-01 00:08 +08:00): the
seven environment-independent Python tests, the clean/failure/remaining-queue
post-processing gate, shell syntax checks and whitespace validation all passed.
The CUDA-only sparse aggregation smoke test remains intentionally deferred on
this laptop; no remote training process or result file was changed.

Latest independent post-processing regression (2026-09-01 10:17:29 +08:00):
the disposable 1,800-record fixture produced all five generated LaTeX
fragments, passed `final_paper_audit.py` with `audit_results=1800` and
`errors=0`, printed `FINAL_AUDIT_COMPLETE`, and ended with
`POSTPROCESSING_PIPELINE_REGRESSION_PASS`. This validates the release chain
only; it is not evidence for the still-incomplete remote B5 benchmark.

Latest release-gate recheck (2026-09-01 10:28:54 +08:00): the clean/failure/
remaining-queue post-processing gate, finalizer release-order regression and
placeholder-gate regression all passed again; shell syntax and whitespace
validation also passed. No remote process or result was changed.

Latest local release-chain recheck (2026-09-01 12:13 +08:00): Python syntax
compilation passed for the audit, aggregation, manuscript-generation, split,
coverage and manifest scripts; shell syntax passed for the finalizer, watcher
and read-only monitor. The post-processing gate and the cached-input,
queue-schedule, side-feature label-exclusion and side-feature shuffle-control
regressions all passed. No remote process or result was changed.

Read-only monitor hardening (2026-09-01): `monitor_drugban_readonly.sh` now
reports the remote watcher SHA256 and the source-order relationship between
`verify_split_integrity.py` and `verify_paper_coverage.py`. If the watcher puts
coverage first, the monitor explicitly records that the independent split audit
is required; it does not modify or restart the watcher.

Latest LaTeX preflight recheck (2026-09-01 10:32:13 +08:00): the bundled
compile workflow selected the existing TeX Live 2024/`latexmk` toolchain and
compiled the current pre-B5 manuscript to a 7-page, letter-size PDF with exit
code 0. The first-page render was visually inspected and showed no clipping or
overflow; red TODOs remain intentionally because result and author metadata
are gated on the final release.

Local release-safety scan (2026-09-01 09:52 +08:00): no actual credential
value was found in scripts, manuscript sources, logs or templates; only the
documented `SSHPASS` environment-variable interface is present. The scan also
confirmed that partial-result and final-audit guard strings remain explicit;
no release-bypass path was introduced.

Read-only monitor hardening (2026-09-01 09:53 +08:00): formal coverage
counting now explicitly requires `method=drugban`, valid seed/fold fields and
unique dataset--scenario--seed--fold identities, in addition to the pinned
pipeline, epoch, cache and TF32 metadata. The embedded coverage block compiled
successfully and its regression assertions passed.

Latest B5 liveness evidence (2026-08-31 23:10 +08:00 local check): formal
coverage remained 132/180 and the failure list remained empty. A 10-second
read-only sample showed all four Python tasks still attached to GPUs 0--3 with
active compute utilization and increasing CPU counters; the cold-drug task
advanced to epoch 50/100 while the other logs were older. No restart was
justified.

Latest B5 liveness evidence (2026-09-01 09:47:37 +08:00): formal coverage
increased to 139/180 and the failure list remained empty. BindingDB random
remained complete at 15/15 and cold-drug reached 4/15. Process-matched
cold-drug tasks were approximately at epochs 0, 70, 1 and 10; GPU 0--3
utilization was approximately 58%, 56%, 55% and 55%, with 3,060--3,062 MiB
allocated per card. One task log was stale, but its corresponding Python
process was alive; no restart was justified from this snapshot.

Latest B5 process-liveness evidence (2026-09-01 09:59:05 +08:00): formal
coverage remained 139/180 and the failure list remained empty. The four live
tasks were all BindingDB/cold-drug, with process-matched epoch lines at roughly
1, 70, 10 and 10; GPU 0--3 utilization was approximately 30%--60%, with
3,060--3,062 MiB allocated per card. Two task logs were stale, but their
matching Python processes remained alive and no recent worker/task errors were
found; no restart was justified.

Latest B5 process-liveness evidence (2026-09-01 10:09:40 +08:00): formal
coverage remained 139/180 and the failure list remained empty. The queue,
four workers and release watcher remained alive; the four process-matched
BindingDB/cold-drug tasks were approximately at epochs 1, 70, 10 and 10.
GPU 0--3 utilization was approximately 67%, 72%, 55% and 61%, with 3,060 MiB
allocated per card. All four task logs exceeded the 15-minute freshness
threshold, but the corresponding Python processes were alive and no recent
worker/task errors were found; no restart was justified.

Latest B5 progress evidence (2026-09-01 10:18:53 +08:00): formal coverage
remained 139/180 because no additional fold had yet written a complete JSON.
The four process-matched BindingDB/cold-drug tasks were approximately at
epochs 1, 80, 10 and 20; two task logs were fresh, two were stale, and no
worker/task errors or failed-task entries were found. GPU utilization was
approximately 48%--61%; GPU 2 and GPU 3 held approximately 25,143 and 24,017
MiB, respectively. The live processes and active GPU work provided no basis
for recovery or restart.

Latest B5 resource-association evidence (2026-09-01 10:21:28 +08:00): a
read-only `nvidia-smi pmon` check found the expected DrugBAN compute processes
plus PID 1968867, `python model_api.py` under
`/mnt/sda/fulaiyi/liuhongbo/ipheno/app`, using about 22,080 MiB on GPU 2 and
20,952 MiB on GPU 3. This unrelated service was not stopped or altered. The
local read-only monitor now reports GPU compute processes explicitly; the
formal count remained 139/180 and no errors were found.

Latest B5 progress evidence (2026-09-01 10:36:49 +08:00): formal coverage
remained 139/180 because no additional fold had yet written a complete JSON.
The process-matched BindingDB/cold-drug tasks were approximately at epochs 10,
80, 20 and 20. GPU 0--3 remained active at approximately 59%, 62%, 30% and
61%; the unrelated `ipheno` service continued to occupy about 22,080 MiB on
GPU 2 and 20,952 MiB on GPU 3. No recent errors or failed-task entries were
found, so the queue was left unchanged.

Latest B5 liveness evidence (2026-09-01 11:02:31 +08:00): formal coverage
remained 139/180. The process-matched BindingDB/cold-drug tasks were
approximately at epochs 10, 90, 20 and 30; GPU 0--3 utilization was
approximately 61%, 57%, 55% and 60%. The queue, four workers and release
watcher remained alive, the failure list was empty, and no recent matched
worker/task errors were found. The unrelated `ipheno` service remained on
GPU 2/3 and was not modified; no restart was justified.

Latest B5 liveness evidence (2026-09-01 11:19:36 +08:00): formal coverage
remained 139/180, while the process-matched BindingDB/cold-drug tasks were
approximately at epochs 20, 90, 30 and 30. GPU 0--3 utilization was
approximately 56%, 57%, 49% and 61%. The queue, four workers and release
watcher remained alive, the failure list was empty, and no recent matched
worker/task errors were found. The unrelated `ipheno` service remained on
GPU 2/3 and was not modified; no restart was justified.

Latest B5 liveness evidence (2026-09-01 11:25:44 +08:00): formal coverage
remained 139/180. The four process-matched BindingDB/cold-drug tasks were
still alive at approximately epochs 20, 90, 30 and 30; GPU 0--3 utilization
was approximately 50%, 51%, 49% and 55%. The queue, four workers and release
watcher remained alive, the failure list was empty, and no recent matched
worker/task errors were found. Several task logs were stale, but the
corresponding Python processes showed active GPU compute, so the snapshot did
not justify a restart; the unrelated `ipheno` service remained unmodified.

Latest B5 diagnostic evidence (2026-09-01 11:28:22 +08:00): a read-only
process/dispatch check found all four DrugBAN workers in running or sleeping
states with 69 threads each, large context-switch counts, open file
descriptors, and active GPU compute. The task logs report every tenth epoch;
with approximately 230--234 seconds per epoch, a 10-epoch reporting interval
is about 38--39 minutes. The observed gaps between epochs 20/30/90 therefore
do not by themselves indicate a hang. Formal coverage remained 139/180, the
failure list and recent error scan were empty, and no restart or modification
was justified.

Latest B5 progress evidence (2026-09-01 11:31:39 +08:00): formal coverage
remained 139/180, while the four process-matched BindingDB/cold-drug tasks
were approximately at epochs 20, 90, 30 and 40. GPU 0--3 utilization was
approximately 52%, 59%, 48% and 64%. The queue, four workers and release
watcher remained alive; the failure list and recent matched-error scan were
empty. One task advanced to the next ten-epoch report, confirming liveness;
no restart or remote modification was justified.

Latest B5 progress evidence (2026-09-01 11:37:14 +08:00): formal coverage
remained 139/180. The process-matched BindingDB/cold-drug tasks were
approximately at epochs 20, 100, 30 and 40; the epoch-100 task was still
alive, so its formal JSON had not yet been counted. GPU 0--3 utilization was
approximately 32%, 48%, 48% and 53%. The queue, four workers and release
watcher remained alive; the failure list and recent matched-error scan were
empty. The task's epoch-100 line was treated as liveness/near-completion
evidence only, not as a completed result, and no restart or remote
modification was justified.

Latest B5 completion evidence (2026-09-01 11:48:43 +08:00): formal coverage
increased to 140/180 after `bindingdb/cold_drug/seed4198936517/fold1`
completed and passed the strict metadata filter. The queue, four workers and
release watcher remained alive; the four process-matched tasks were at
approximately epochs 1, 30, 30 and 40, GPU 0--3 utilization was approximately
67%, 67%, 57% and 56%, and the failure list and recent matched-error scan
were empty. The queue was left running without modification.

Latest B5 liveness evidence (2026-09-01 11:57:39 +08:00): formal coverage
remained 140/180. The four process-matched BindingDB/cold-drug tasks were
approximately at epochs 1, 30, 40 and 40; GPU 0--3 utilization was
approximately 64%, 56%, 54% and 48%. The queue, four workers and release
watcher remained alive, the failure list and recent matched-error scan were
empty, and no restart or remote modification was justified.

Latest B5 liveness evidence (2026-09-01 09:03:44 +08:00): formal coverage
increased to 137/180 and the failure list remained empty. BindingDB random
reached 15/15 and cold-drug reached 2/15. Process-matched cold-drug tasks were
approximately at epochs 60, 80, 90 and 1; GPU 0--3 utilization was
approximately 61%, 49%, 49% and 63%, with 3,060--3,062 MiB allocated per card.
Two task logs were stale, but their corresponding Python processes were alive;
no restart was justified from this snapshot.

Latest B5 liveness evidence (2026-08-31 23:36:44 +08:00): formal coverage
remained 132/180, while the four process-matched tasks advanced to
approximately epochs 10, 50, 50 and 40. GPU utilization was approximately
53%--66% across GPUs 0--3, and the failure list remained empty. The queue and
release watcher remained alive; no recovery action was justified.

Latest B5 liveness evidence (2026-09-01 00:00:35 +08:00): formal coverage
remained 132/180 and the failure list remained empty. Process-matched
BindingDB tasks were approximately at epochs 20, 50, 60 and 50; GPU 0--3
utilization was approximately 70%, 61%, 51% and 51%, with 3,060 MiB allocated
per card. One task log was stale, but the corresponding Python process was
alive; no restart was justified from this snapshot.

Additional pre-B5 manuscript QA (2026-08-31 10:17:43 +08:00): a disposable
TeX Live `latexmk`/pdfLaTeX build produced a seven-page PDF. Every rendered
page was inspected and no overfull-box, undefined-reference or clipping issue
was found. Result-derived and author/release TODOs remain by design; this is a
template preflight and not final release evidence.

Citation/label preflight (2026-08-31 23:17 +08:00): all 11 citation keys used
by the manuscript resolve to the 11 BibTeX entries, with no unused entries;
both manuscript cross-references resolve to declared labels. The compiled log
also contains no LaTeX warning signatures.

Watcher-order audit (2026-08-31 23:38 +08:00): the active remote watcher
SHA256 is the reviewed deployed copy, but its current command order invokes
`verify_paper_coverage.py` before `verify_split_integrity.py`. This is a
read-only ordering discrepancy; no remote process or file was changed. At B5
completion, the independently controlled release path must run
`verify_split_integrity.py` first and use the local finalizer's ordering before
accepting any generated artifact.

Concurrent-release guard (2026-08-31 23:47 +08:00): the local finalizer now
fails closed if any queue, DrugBAN worker or post-processing watcher remains
alive before release. Its release-order, placeholder, synthetic full-release
and post-processing gate regressions all passed after this change. This
prevents the known older remote watcher from writing concurrently with the
controlled finalizer; no remote process was changed.

Latest B5 liveness evidence (2026-08-31 15:07:59 +08:00): formal coverage
remains 127/180 and the failure list remains empty. The queue, four workers and
release watcher remain alive; GPU utilization is approximately 22%--57% with
3,060 MiB allocated per card. The four live task logs are approximately at
epochs 80, 10, 20 and 20; epoch=100 lines in historical logs are not current
worker evidence. No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 15:40:09 +08:00): formal coverage
remains 127/180 and the failure list remains empty. The queue, four workers and
release watcher remain alive; GPU utilization is approximately 48%--64% with
3,060 MiB allocated per card. Process-matched task logs are approximately at
epochs 90, 20, 20 and 30. The local `monitor_drugban_readonly.sh` helper was
syntax-checked and run successfully; it performs no remote writes or process
control and now includes a read-only tail scan for worker/task error signatures.

Latest B5 liveness evidence (2026-08-31 15:47:25 +08:00): formal coverage
remains 127/180 and the failure list remains empty. The queue, four workers and
release watcher remain alive; GPU utilization is approximately 48%--59% with
3,060 MiB allocated per card. Process-matched live task logs are approximately
at epochs 90, 20, 30 and 30; one BindingDB random fold advanced from epoch 20
to 30 since the prior check. No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 16:01:41 +08:00): formal coverage
increased to 128/180 because one BindingDB random fold completed; the failure
list remains empty. The queue, four workers and release watcher remain alive;
GPU utilization is approximately 4%--63% with 3,060 MiB allocated per card.
Process-matched live task logs are approximately at epochs 0, 20, 30 and 40.
The queue completed seed 1941488137 fold 4 at 15:56:55 and started seed
4198936517 fold 3 on GPU 0. No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 16:31:55 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers
and release watcher remain alive; all four GPUs show active utilization
(49%--64%) with 3,060 MiB allocated per card. Process-matched BindingDB random
task logs are approximately at epochs 1, 30, 40 and 40; the newly started fold
3 recorded epoch 1 at 315.8 s. The read-only worker/task tail scan found no
recent error signatures. No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 17:01:37 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers
and release watcher remain alive; GPU utilization is approximately 49%--72%
with 3,060 MiB allocated per card. Process-matched BindingDB random task logs
advanced to approximately epochs 10, 40, 50 and 50. The read-only worker/task
tail scan found no recent error signatures. No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 17:21:51 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers
and release watcher remain alive; GPU utilization is approximately 55%--72%
with 3,060 MiB allocated per card. Process-matched BindingDB random task logs
advanced to approximately epochs 20, 40, 50 and 60. The read-only worker/task
tail scan found no recent error signatures. No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 17:27:47 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers
and release watcher remain alive; GPU utilization was approximately 26%--52%
with 3,060 MiB allocated per card. Process-matched BindingDB random task logs
were approximately at epochs 20, 50, 50 and 60; fold 0 advanced from epoch 40
to 50. The read-only worker/task tail scan found no recent error signatures.
No recovery action is justified.

Latest B5 liveness evidence (2026-08-31 17:39:06 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers
and release watcher remain alive; GPU utilization was approximately 59%--72%
with 3,060 MiB allocated per card. Process-matched BindingDB random task logs
were approximately at epochs 20, 50, 60 and 60; fold 4 wrote epoch 60 at
17:37:48. The monitor now reports task-log age and marks stale logs without
restarting any process. No recent worker/task error signatures were found.

Latest B5 liveness evidence (2026-08-31 18:12:19 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers
and release watcher remain alive; GPU utilization was approximately 53%--66%
with 3,060 MiB allocated per card. Process-matched BindingDB random task logs
were approximately at epochs 30, 60, 60 and 70; fold 3 advanced to epoch 30
and fold 0 wrote epoch 60. No recent worker/task error signatures were found;
stale task-log age is diagnostic only and does not justify a restart.

Latest B5 liveness evidence (2026-08-31 18:41:39 +08:00): formal coverage
remains 128/180 and the failure list remains empty. The queue, four workers and
release watcher remain alive; GPU utilization was approximately 52%--71% with
3,060 MiB allocated per card. Process-matched BindingDB random task logs were
approximately at epochs 40, 60, 70 and 80; fold 3 and fold 1 wrote fresh log
lines around 18:35, while the other two logs were stale but their Python
processes remained alive. No recent worker/task error signatures were found,
so no recovery action is justified.

Latest B5 monitor evidence (2026-08-31 09:40:49 +08:00): formal DrugBAN
coverage is 124/180, with zero failed tasks; the queue has four active workers
and has continued scheduling BindingDB random folds. The remaining B5 target is
56 formal folds.

Latest liveness evidence (2026-08-31 11:12:24 +08:00): formal coverage remains
124/180 and the failure list remains empty, while the four active BindingDB
random task logs advanced to approximately 20/100, 60/100, 50/100 and 60/100
epochs. GPU 0--3 remain active, so no recovery action is justified.

The next read-only check at 2026-08-31 11:26:28 +08:00 still found coverage at
124/180, but the active epoch logs had advanced to approximately 30/100,
60/100, 50/100 and 60/100. This confirms liveness; it is not additional
formal-fold coverage until a result JSON is written and passes the metadata
gate.

At 2026-08-31 11:48:20 +08:00, the active epochs were approximately
30/100, 70/100, 60/100 and 70/100; all four GPUs had active load and the
failure list remained empty. Coverage is still 124/180 until completed JSON
artifacts pass the formal metadata check.

At 2026-08-31 13:32:58 +08:00, the formal count increased to 125/180. The
queue and four workers remained alive, all four GPUs were active, and the
failure list remained empty. BindingDB random reached 5/15; cold-drug,
cold-protein and cold-pair remained 0/15. This is a progress snapshot, not
final coverage evidence.

Release-order note (2026-08-31): the active remote watcher is an older deployed
copy whose command order places coverage before split integrity. During the
read-only training monitor it is not modified or restarted. At queue exit, the
required independent split-integrity check must run first; only then should the
remaining audit and release artifacts be accepted.

Latest B5 liveness evidence (2026-08-31 21:47:03 +08:00): formal coverage
increased to 131/180; BindingDB random reached 11/15 while the other three
BindingDB scenarios remained 0/15. The queue completed three additional random
folds and started BindingDB/cold_drug. The queue, four workers and release
watcher remained alive; GPU utilization was approximately 26%--62% with
3,060 MiB allocated per card. Process-matched task logs were approximately at
epochs 80, 20, 20 and 10. No recent worker/task error signatures were found;
some task-log ages were stale but did not justify a restart.

Latest B5 liveness evidence (2026-08-31 22:18:01 +08:00): formal coverage
remained 131/180 and the failure list remained empty. The queue continued with
three BindingDB/random folds and one BindingDB/cold_drug fold; process-matched
task logs were approximately at epochs 90, 30, 30 and 20. The queue, four
workers and release watcher remained alive; GPU utilization was approximately
54%--63% with 3,060 MiB allocated per card. No recent worker/task error
signatures were found, so no recovery action is justified.

Latest B5 liveness evidence (2026-08-31 22:22:48 +08:00 local check): formal coverage
remained 131/180 and the failure list remained empty. The four active tasks were
three BindingDB/random folds and one BindingDB/cold_drug fold; their logs were
approximately at epochs 90, 30, 30 and 20. All four Python processes remained
alive with GPU utilization of 59%--66% and 3,060 MiB allocated per card. Two
task logs were older than 30 minutes, but the corresponding processes remained
in a running state and no recent worker/task error signatures were found, so no
recovery action is justified.

Latest B5 liveness evidence (2026-08-31 22:31:46 +08:00): formal coverage
increased to 132/180; BindingDB random reached 12/15 while the other three
BindingDB scenarios remained 0/15. The queue completed BindingDB/random seed
4198936517 fold 3 and immediately started seed 983997847 fold 2 on GPU 0. The
queue, four workers and release watcher remained alive; GPU utilization was
approximately 48%--63% with 3,060 MiB allocated per card. Process-matched task
logs were approximately at epochs 0, 20, 30 and 40. No recent worker/task error
signatures were found, so no recovery action is justified.

Latest B5 liveness evidence (2026-08-31 22:50:19 +08:00): formal coverage
remained 132/180 and the failure list remained empty. The four active tasks were
three BindingDB/random folds and one BindingDB/cold_drug fold; their logs were
approximately at epochs 1, 30, 40 and 40. GPU utilization was approximately
52%--67% with 3,060 MiB allocated per card, and all four Python processes
remained alive. No recent worker/task error signatures were found, so no
recovery action is justified.

Latest B5 liveness evidence (2026-09-01 15:00:44 +08:00): formal coverage
remained 140/180. The four process-matched BindingDB/cold-drug tasks were
approximately at epochs 50 (fold 0), 80 (fold 2), 80 (fold 1) and 90 (fold
3). The queue, four workers and release watcher remained alive, all four GPUs
had active DrugBAN compute with approximately 3,060 MiB allocated per card,
and the failure list and recent matched-error scan were empty. Stale task-log
timestamps were outweighed by active process/GPU evidence; no restart or
remote modification was justified.

Latest B5 liveness evidence (2026-09-01 15:09:12 +08:00): formal coverage
remained 140/180. The four process-matched BindingDB/cold-drug tasks were
approximately at epochs 50 (fold 0), 80 (fold 2), 90 (fold 1) and 90 (fold
3). The queue, four workers and release watcher remained alive, all four GPUs
had active DrugBAN compute with approximately 3,060 MiB allocated per card,
and the failure list and recent matched-error scan were empty. The active
processes confirmed liveness; no restart or remote modification was justified.

Latest B5 progress evidence (2026-09-01 15:45:36 +08:00 remote check): formal
coverage increased to 142/180. BindingDB/cold-drug is now 7/15; two folds
completed and the queue advanced to the next seed. The queue, four workers and
release watcher remained alive. Process-matched task logs showed approximately
60/100 and 90/100 epochs for the older seed, plus newly started work for the
next seed. GPUs 0--3 all had active DrugBAN compute, no recent worker/task
error signatures were found, and the failure list was empty. One task log was
stale, but its matching Python process and GPU activity confirmed liveness; no
restart or remote modification was justified.

## Final commands

The release handoff is not triggered by an empty GPU or a queue log alone. It
requires the queue and all workers to have exited naturally, an empty failure
list, and 180/180 formal DrugBAN identities. The first post-queue command is
the frozen-split verifier; only its `SPLIT_INTEGRITY_COMPLETE` marker permits
the result audit and subsequent release generation.

On the remote host, the audit command is:

```bash
/mnt/sda/fulaiyi/aspect_env/bin/python \
  /mnt/sda/fulaiyi/dti_paper_20260826_v2/final_paper_audit.py \
  --root /mnt/sda/fulaiyi/dti_paper_20260826_v2 --require-artifacts
```

After that command prints `FINAL_AUDIT_COMPLETE`, run locally from this
repository:

```bash
./finalize_overleaf_package.sh
```

For an approved password-authenticated session, set `SSHPASS` only in the
calling shell before the same command.  The script delegates authentication to
`sshpass -e` and never stores the value in the repository or the Overleaf
package.

The package script first checks the complete result identities, then rebuilds
the aggregate tables, Python figures and source-data CSVs from that release,
and finally repeats the full artifact audit before copying anything. This
prevents the local Overleaf project from silently mixing partial, stale and
final results.

The release commands also fail closed when the required
`SPLIT_INTEGRITY_COMPLETE` or `FINAL_AUDIT_COMPLETE` marker is absent, even if
the underlying command returns success. The normal and missing-marker paths
are covered by the post-processing regression tests.

Marker-gate regression recheck (2026-09-01 10:43:18 +08:00): shell syntax,
release-order assertions, normal post-processing, failure-list rejection,
remaining-queue rejection and missing-marker rejection all passed.

Full local regression recheck (2026-09-01 10:47:34 +08:00): cached-input
equivalence, 180-task scheduling, S1/S2 label-exclusion and shuffle controls,
post-processing gates, finalizer ordering and placeholder gates all passed;
the disposable 1,800-record pipeline again reached `FINAL_AUDIT_COMPLETE` and
`POSTPROCESSING_PIPELINE_REGRESSION_PASS`.

Finalizer artifact-mapping check (2026-09-01 10:52:25 +08:00): the release
order regression now asserts synchronization of both figure families in four
formats, all required tables and source-data CSVs, the figure legends and all
five generated LaTeX fragments; the assertion and shell checks passed.

Latest local release-chain regression (2026-09-01 23:14:29 +08:00): the
disposable 1,800-record post-processing fixture again generated all five
LaTeX fragments and reached `FINAL_AUDIT_COMPLETE`; queue scheduling,
candidate-label exclusion, shuffled S1/S2 control semantics, finalizer order,
placeholder gates and Overleaf ZIP export all passed. These are release-path
regressions only and do not substitute for the pending remote B5 records.

Latest B5 liveness check (2026-09-01 23:18:22 +08:00): formal coverage remained
147/180, but the process-matched BindingDB/cold-protein worker advanced from
epoch 10 to epoch 20. The other three workers and all four GPUs remained
active, the failure list was empty, and no recent matched worker/task errors
were found. No restart or remote modification was justified.

Latest B5 liveness check (2026-09-01 23:22:17 +08:00): formal coverage remained
147/180 while a process-matched BindingDB/cold-drug worker advanced from epoch
70 to epoch 80 and the cold-protein worker remained at epoch 20. All four GPUs
continued active DrugBAN compute, the failure list was empty, and no recent
matched worker/task errors were found. No restart or remote modification was
justified.

Latest B5 liveness check (2026-09-01 23:49:31 +08:00): formal coverage remained
147/180, while the four process-matched workers were at approximately epochs
20, 20, 80 and 10. All GPUs continued active DrugBAN compute, the failure list
was empty, and no recent matched worker/task errors were found. No restart or
remote modification was justified.

Latest B5 liveness check (2026-09-01 23:58:40 +08:00): formal coverage remained
147/180, while the process-matched BindingDB/cold-protein worker advanced from
epoch 20 to epoch 30; the four workers were approximately at epochs 20, 30, 80
and 10. All GPUs continued active DrugBAN compute, the failure list was empty,
and no recent matched worker/task errors were found. No restart or remote
modification was justified.

Latest B5 liveness check (2026-09-02 00:00:30 +08:00): formal coverage remained
147/180, while process-matched BindingDB workers were approximately at epochs
20, 30, 90 and 10; the cold-drug worker advanced from epoch 80 to epoch 90.
All GPUs continued active DrugBAN compute, the failure list was empty, and no
recent matched worker/task errors were found. No restart or remote modification
was justified.

Latest B5 liveness check (2026-09-02 00:07:04 +08:00): formal coverage remained
147/180, but the process-matched BindingDB/cold-protein worker advanced from
epoch 10 to epoch 20. The four workers remained alive with all GPUs actively
computing, the failure list was empty, and no recent matched worker/task errors
were found. No restart or remote modification was justified.

Latest B5 liveness check (2026-09-02 00:19:12 +08:00): formal coverage remained
147/180, while the process-matched BindingDB/cold-drug worker advanced from
epoch 20 to epoch 30. The queue and four workers remained alive, all GPUs had
active DrugBAN compute, the failure list was empty, and no recent matched
worker/task errors were found. No restart or remote modification was justified.

Latest B5 progress check (2026-09-02 00:45:59 +08:00): formal coverage
increased from 147/180 to 148/180 after BindingDB/cold-drug seed 4198936517
fold 4 completed at 00:39:22. The queue immediately started BindingDB/cold-drug
seed 983997847 fold 3. The four active workers remained on GPUs 0--3, the
failure list was empty, and no recent matched worker/task errors were found.
