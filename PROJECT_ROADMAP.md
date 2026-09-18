# DTI paper execution roadmap

This roadmap is an operational companion to `DELIVERY_CHECKLIST.md`.  A stage
is complete only when its stated evidence exists; queue activity alone is not
completion evidence.

| Stage | Objective | Completion evidence | Current status |
|---|---|---|---|
| 1. B5 baseline | Finish DrugBAN on the frozen 3 datasets x 4 scenarios x 15 seed--fold evaluations. | 180 formal DrugBAN JSON files: 100 epochs, cached input enabled and TF32 enabled. | In progress. At the latest 2026-09-02 01:43:41 +08:00 read-only check, 148/180 DrugBAN records passed the formal B5 metadata check: BioSNAP and Human are complete (60/60 each); BindingDB random is complete (15/15), cold-drug is 13/15, and cold-protein/cold-pair remain 0/15. The queue, four workers and all four GPU compute processes were alive. Process-matched task logs reported epochs 50, 50, 10 and 40; three logs were older but their corresponding Python processes remained active in GPU compute. The DrugBAN failure list and recent matched-error scan were empty; no restart was justified. |
| 2. Release integrity | Validate every method uses the frozen held-out data and that all formal metrics are well formed. | `verify_split_integrity.py` reports `SPLIT_INTEGRITY_COMPLETE`; `final_paper_audit.py` reports `FINAL_AUDIT_COMPLETE` for 1,800 identities. | B1--B4/M8 complete; awaits B5. |
| 3. Results and figures | Build aggregate metrics, paired comparisons, Python figures and CSV source data from audited JSON only. | Non-empty `tables/`, `source_data/`, `figure_2_baselines.*`, `figure_3_ablation.*`, and successful aggregate/plot logs. | Pipeline regression-tested; a release-gated remote watcher is live (PID 3235770; `logs/drugban_release_postprocess_20260829T073100+0800.log`). The reviewed local release script now orders split-integrity, coverage, result and artifact audits before generating final aggregates, Python figures and source-data CSVs. It exits without post-processing if the queue, worker or failure-list gates are not clean. `test_postprocess_after_drugban.sh` passed its clean-release and failure-list rejection paths locally. The release-time manifest and watcher scripts were synchronized to the remote root with verified SHA256 matches; timestamped remote backups were retained. |
| 4. Overleaf release | Regenerate data-derived manuscript text and compile/render-check the PDF. | Finalizer succeeds, generated fragments contain no partial-data claims, and `manuscript/build/main.pdf` passes visual QA. | Template preflight complete. Figure 1 was revised for a compact two-lane workflow, explicitly states that encoders are not shared, retains editable SVG text, and was rendered in the 7-page pre-B5 PDF without clipping or overlap. The finalizer now ignores inactive `\IfFileExists` fallbacks, requires generated fragments to contain no TODO, and blocks only genuine author/release metadata TODOs. The same release-gated watcher will generate the numerical LaTeX fragments after full remote audit; local sync/compilation still awaits B5 completion and author metadata. |
| 5. Submission metadata | Supply declarations and release information that cannot be inferred from code. | Author block, contributions, competing interests, target journal, original-data terms, repository/release/DOI and licence confirmed. | Author action required; see `AUTHOR_INPUT_REQUIRED.md`. |

**Current B5 status takes precedence over the historical snapshots in the
table:** the latest 2026-09-02 04:23:16 +08:00 read-only coverage count is
148/180 formal DrugBAN records (BioSNAP 60/60, Human 60/60, BindingDB 28/60:
random 15/15, cold-drug 13/15, cold-protein 0/15, cold-pair 0/15), with 32
BindingDB evaluations remaining and an empty active failure list. The queue,
four workers and release post-processing watcher were alive; process-matched
task logs reported epochs 90, 90, 50 and 80, and all GPUs 0--3 had active
DrugBAN compute. Three task logs were stale but their corresponding processes
remained live, so no restart was justified. The queue is still in the pre-release phase. The dated entries
below retain the queue history and liveness evidence; they are not
current-coverage claims.

The current missing-identity enumeration independently reproduces the same
32-record gap: BindingDB/cold-drug is missing seed 983997847 folds 3--4;
BindingDB/cold-protein is missing all 15 seed--fold identities; and
BindingDB/cold-pair is missing all 15 identities. The four
currently running folds are included in this pending set until their formal
100-epoch JSON artifacts are written.

## Active operating rules

- Run the main DrugBAN queue at one task per GPU.  A one-epoch same-GPU
  sidecar test slowed the original task, so multi-task-per-GPU execution is
  not used.
- The deployed runner preindexes input rows only; its real-data equivalence
  check passed and it does not alter model, split, seed, epoch count, batch
  size or result schema.
- Monitor on the agreed 30-minute cadence.  Do not restart or overwrite a
  queue solely because it is slow; investigate process, GPU, logs and formal
  coverage before any recovery decision.
- Deployment note recorded at 2026-08-31 07:19:47 +08:00: the active remote
  post-processing watcher is the previously deployed SHA256
  `c1beee28455eac72104ec1aab48cceaf704fc971bbfab128a182d534a4889415`, whose
  script order places `verify_paper_coverage.py` before
  `verify_split_integrity.py`. The reviewed local script places split integrity
  first. Because the active monitoring contract is read-only, the remote
  watcher is not modified or restarted; after the queue exits, run the required
  split-integrity check independently before relying on the remaining release
  gates.
- A read-only resource check at 2026-08-29 14:54:47 +08:00 found host load
  around 114/128 logical CPUs, four active DrugBAN processes using roughly 17
  CPU cores each, and PyTorch defaults of 64 intra-op and 128 inter-op threads.
  The GPU memory headroom is therefore not evidence for safe concurrent
  acceleration; do not alter thread affinity or add a sidecar to the active
  queue.
- A read-only GPU-process association check at 2026-09-01 10:21:28 +08:00
  found the unrelated `python model_api.py` service in
  `/mnt/sda/fulaiyi/liuhongbo/ipheno/app` holding about 22,080 MiB on GPU 2
  and 20,952 MiB on GPU 3. It was not stopped or signalled. If a later
  DrugBAN task reports CUDA out-of-memory on either card, the first recovery
  action is to coordinate with that service's owner; no automated termination
  or queue restart is authorized by this project.
- Do not present partial B5 numbers, synthetic post-processing fixtures or
  engineering benchmarks as manuscript performance results.

- A read-only partial baseline preview at 2026-08-31 07:58:26 +08:00 found all
  180 formal records for the existing comparison methods, but only 123 formal
  DrugBAN records. BioSNAP and Human DrugBAN are complete (120 records); the
  remaining three BindingDB records are all from the random scenario. DrugBAN
  is the B5 comparator, not the proposed ArnoldiGCL-S1/S2 model. In the eight
  completed BioSNAP/Human cells, the proposed `arnoldi_s12` variant is
  best or near-best in random and cold-drug settings, while simpler MLP/GCN
  comparators lead in several cold-protein and cold-pair cells. This is a
  generalization boundary to report, not a DrugBAN problem or a final
  superiority claim: after B5, the paired full-result audit must quantify the
  proposed model's gains and losses across every cell. No test-set selective
  tuning or partial-data superiority claim is permitted.

- Latest read-only queue check at 2026-08-31 08:05:50 +08:00 confirmed the
  queue was alive with four workers and no failures. Formal DrugBAN coverage
  remained 123/180 because no fold had completed since 07:31:02, while the
  active BindingDB random seed 1941488137 fold 0 advanced to epoch 80/100.

- The missing-fold matrix was enumerated read-only at 2026-08-31 08:08:29
  +08:00: every BioSNAP and Human cell is complete; only BindingDB remains,
  with random 12/15 missing and cold-drug, cold-protein and cold-pair each
  15/15 missing. This is the exact B5 completion checklist.

- A further read-only check at 2026-08-31 08:14:55 +08:00 found no scheduler
  turnover yet (formal coverage remained 123/180 and the failure list remained
  empty), but all four workers were alive and their task logs had advanced:
  the active BindingDB random folds were at approximately 80/100, 10/100,
  10/100 and 1/100 epochs. GPU 0--3 each retained 3,060 MiB allocation with
  20--55% utilization. The queue log itself records only START/DONE events, so
  worker task-log mtimes and epoch lines are the authoritative liveness signal
  between completions.

- At 2026-08-31 08:15:52 +08:00, the queue remained alive with four active
  workers and no failures. Formal coverage was still 123/180; the newest
  worker log had reached epoch 20/100 for BindingDB random seed 4198936517
  fold 2, while the other active folds were around 80/100, 10/100 and 10/100.
  No post-processing logs had started, as expected before B5 completion.

- The 2026-08-31 08:32:52 +08:00 check still found 123/180 formal records and
  no failures, but confirmed ongoing task-log progress: the active BindingDB
  random folds were approximately at 80/100, 20/100, 20/100 and 10/100
  epochs. The queue remains in the expected pre-release phase; no finalizer or
  post-processing job has started.

- The 2026-08-31 08:37:57 +08:00 read-only check still found 123/180 formal
  records, four fold workers, four active GPUs and zero failures. The queue
  event tail had not yet recorded another completed fold, so no release gate
  was opened; the running workers remain the authoritative liveness evidence.

- At 2026-08-31 08:41:10 +08:00, the local finalizer was hardened so its first
  remote action is the read-only frozen-split audit, followed by the complete
  result audit; dataset/runtime manifests are written only after those gates.
  `bash -n`, the help path and `test_finalizer_placeholder_gate.py` passed.

- The 2026-08-31 08:55:01 +08:00 read-only check still counted 123/180 formal
  records and zero failures, but active task logs had advanced to approximately
  90/100, 30/100, 20/100 and 20/100 epochs for the four BindingDB random folds.
  GPU 0--3 utilization was 59%, 56%, 57% and 61%, with 3,060 MiB allocated on
  each card. The long-running fold is still emitting epoch records and the
  queue/watcher remain alive, so no recovery or extra concurrency is justified.

- The 2026-08-31 09:40:49 +08:00 read-only check recorded the next completed
  fold: formal DrugBAN coverage increased to 124/180, with BindingDB random at
  4/15 and all other BindingDB scenarios still pending. The queue logged
  `DONE dataset=bindingdb scenario=random seed=1941488137 fold=0` at 09:19:36
  and immediately started fold 4; four workers and four GPUs remained active,
  and the failure list was empty. The exact remaining B5 target is now 56
  formal folds.

- The 2026-08-31 10:08:03 +08:00 read-only check found no additional JSON
  completion yet (124/180 formal records, 56 remaining), but confirmed live
  epoch progress: the active BindingDB random tasks were approximately at
  100/100, 40/100, 30/100, 40/100 and 10/100 as logs became available. The
  newly scheduled fold 4 had reached epoch 10/100; the queue had four workers,
  and the failure list remained empty. No post-processing gate was opened.

- The 2026-08-31 10:15:00 +08:00 read-only check confirmed that the four
  BindingDB random workers were still in the expected running state, with
  approximately 3,060 MiB allocated on each GPU and no failed tasks. The
  formal DrugBAN count remained 124/180. The active logs showed the large
  BindingDB folds advancing through epochs (including fold 4 at 10/100), so
  the long wall-clock time is explained by real training throughput rather
  than an idle process; no restart or sidecar is justified.

- A local pre-B5 manuscript compile at 2026-08-31 10:17:43 +08:00 produced a
  seven-page PDF with TeX Live `latexmk`/pdfLaTeX. All rendered pages were
  inspected; no overfull-box, undefined-reference or layout-clipping issue
  was found. Red TODO text remains intentionally because the final numerical
  fragments and author/release metadata are gated on the complete B5 audit.

- The remote CPU-only chunked/sparse GCN equivalence check passed again at
  2026-08-31 23:10:00 +08:00 within `rtol=1e-6`, `atol=1e-7`. The local
  CUDA-dependent sparse-aggregation smoke test remains deferred while the four
  formal DrugBAN workers occupy the GPUs.

- The 2026-08-31 11:12:24 +08:00 read-only check found formal coverage still at
  124/180 with zero failed tasks, but the active BindingDB random logs had
  advanced to approximately 20/100, 60/100, 50/100 and 60/100 epochs across
  the four workers. All four GPUs remained active and the queue/watcher were
  alive; this is continued liveness and epoch progress, not a completed fold.

- A read-only non-final baseline preview at 2026-08-31 11:20:26 +08:00
  summarized the 1,620 completed non-DrugBAN records across all 12
  dataset--scenario cells. ArnoldiGCL-S1/S2 ranked first for AUC in BioSNAP
  random and cold-drug and in BindingDB random, while GCN or MLP led Human and
  several cold-protein/cold-pair cells. This supports scenario-specific claim
  calibration rather than a blanket superiority statement; the preview is not
  used as final manuscript evidence until B5 and the full paired audit pass.

- Runner inspection at 2026-08-31 11:20:26 +08:00 explains the remaining
  throughput limit without implying a failed job: the input cache removes
  repeated RDKit/protein preprocessing, but the runner still uses a main-process
  `DataLoader` (`num_workers=0`) and performs DGL graph collation and
  batch-to-device transfer during every epoch. A faster collate or pre-batched
  path would require a separate input-equivalence and controlled-throughput
  study. It is not applied to the active queue, because changing loaded code or
  restarting folds would compromise the current reproducibility contract.

- The 2026-08-31 11:26:28 +08:00 read-only check found no newly written formal
  JSON, so coverage remained 124/180, but the active BindingDB random task logs
  had advanced to approximately 30/100, 60/100, 50/100 and 60/100 epochs. The
  four workers, four GPUs and empty failure list remained healthy. This is
  progress in training state without yet being a completed-fold increment.

- At the 2026-08-31 11:48:20 +08:00 read-only check, formal coverage remained
  124/180 and the failure list was still empty. The four active BindingDB
  random folds had reached approximately 30/100, 70/100, 60/100 and 70/100
  epochs, with all four GPUs active. Task logs are emitted at the existing
  10-epoch cadence, so the unchanged 30/100 line for fold 4 is interpreted
  alongside its live process and GPU load rather than as a stalled task.

- At the 2026-08-31 13:32:58 +08:00 read-only check, formal coverage increased
  to 125/180: BindingDB random reached 5/15 and the other BindingDB scenarios
  remained 0/15. The queue and release watcher were alive with four active
  workers, GPU utilization was 50%, 66%, 50% and 71%, and each card had about
  3,060 MiB allocated. The failure list remained empty. The queue completed
  seed 4198936517 fold 2 at 13:25:45 and started seed 983997847 fold 1 on GPU
  3. Four current task processes were emitting epoch logs, including one
  large BindingDB task at approximately 60/100; no recovery action is
  justified.

- At the 2026-08-31 14:23:18 +08:00 read-only check, formal coverage increased
  to 127/180: BindingDB random reached 7/15 and the other BindingDB scenarios
  remained 0/15. The queue and release watcher were alive with four active
  workers, all four GPUs had nonzero utilization, and the failure list remained
  empty. The queue completed seed 4198936517 fold 1 at 14:06:36 and started
  seed 983997847 fold 0 on GPU 2. No recovery action is justified.

- At the 2026-08-31 14:36:51 +08:00 read-only liveness check, formal coverage
  remained 127/180 and the failure list remained empty. The queue, four workers
  and release watcher were still alive; GPU utilization was approximately
  51%--72% with 3,060 MiB allocated per card, and an active task log reached
  about epoch 80/100. This confirms liveness without a newly completed formal
  fold; no recovery action is justified.

- At the 2026-08-31 15:07:59 +08:00 read-only check, formal coverage was still
  127/180 and the failure list was empty. The four BindingDB random workers,
  queue and release watcher were alive; GPU utilization was 22%--57% with
  3,060 MiB allocated per card. Their current task logs were approximately at
  epochs 80, 10, 20 and 20. The epoch=100 lines in the recent-log search came
  from completed historical task logs, not the four live processes, so no new
  formal fold was counted. No recovery action is justified.

- At the 2026-08-31 15:40:09 +08:00 read-only check, formal coverage remained
  127/180 and the failure list remained empty. The queue, four workers and
  release watcher were alive; GPU utilization was 48%--64% with 3,060 MiB
  allocated per card. Process-matched task logs were at approximately epochs
  90, 20, 20 and 30, confirming that the 100-epoch lines in older logs were
  not live-worker progress. The new local `monitor_drugban_readonly.sh` helper
  reports this process-to-log mapping and scans current worker/task log tails
  for error signatures without changing remote state.

- At the 2026-08-31 15:47:25 +08:00 read-only check, formal coverage remained
  127/180 and the failure list remained empty. The queue, four workers and
  release watcher were alive; GPU utilization was 48%--59% with 3,060 MiB
  allocated per card. Process-matched live task logs were approximately at
  epochs 90, 20, 30 and 30; the seed 4198936517 fold 4 log advanced from
  epoch 20 to 30 since the prior check. No recovery action is justified.

- At the 2026-08-31 16:01:41 +08:00 read-only check, formal coverage increased
  to 128/180: BindingDB random reached 8/15 and the other BindingDB scenarios
  remained 0/15. The queue, four workers and release watcher were alive;
  GPU utilization was 4%--63% with 3,060 MiB allocated per card, and the
  failure list remained empty. Process-matched live task logs were at
  approximately epochs 0, 20, 30 and 40. The queue completed seed
  1941488137 fold 4 at 15:56:55 and started seed 4198936517 fold 3 on GPU 0.
  No recovery action is justified.

- At the 2026-08-31 16:31:55 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue, four workers and
  release watcher were still alive; all four GPUs showed active utilization
  (49%--64%) with 3,060 MiB allocated per card. Process-matched BindingDB
  random task logs advanced to approximately epochs 1, 30, 40 and 40; the
  newly started fold 3 recorded epoch 1 at 315.8 s. No recent worker/task
  error signatures were found, so no restart or extra concurrency is
  justified.

- At the 2026-08-31 17:01:37 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue, four workers and
  release watcher were alive; GPU utilization was 49%--72% with 3,060 MiB
  allocated per card. Process-matched BindingDB random task logs advanced to
  approximately epochs 10, 40, 50 and 50, confirming continued progress. No
  recent worker/task error signatures were found, so no recovery action is
  justified.

- At the 2026-08-31 17:21:51 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue (PID 497482), four
  workers and release watcher (PID 3235770) were alive; GPU utilization was
  55%--72% with 3,060 MiB allocated per card. Process-matched BindingDB random
  task logs advanced to approximately epochs 20, 40, 50 and 60. No recent
  worker/task error signatures were found, so no recovery action is justified.

- At the 2026-08-31 17:27:47 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue (PID 497482), four
  workers and release watcher (PID 3235770) were alive; GPU utilization was
  26%--52% with 3,060 MiB allocated per card. Process-matched BindingDB random
  task logs were approximately at epochs 20, 50, 50 and 60; fold 0 advanced
  from epoch 40 to 50. No recent worker/task error signatures were found, so
  no recovery action is justified.

- At the 2026-08-31 17:39:06 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue (PID 497482), four
  workers and release watcher (PID 3235770) were alive; GPU utilization was
  59%--72% with 3,060 MiB allocated per card. Process-matched BindingDB random
  task logs were approximately at epochs 20, 50, 60 and 60; fold 4 advanced to
  epoch 60. No recent worker/task error signatures were found, so no recovery
  action is justified.

- At the 2026-08-31 18:12:19 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue (PID 497482), four
  workers and release watcher (PID 3235770) were alive; GPU utilization was
  53%--66% with 3,060 MiB allocated per card. Process-matched BindingDB random
  task logs were approximately at epochs 30, 60, 60 and 70; fold 3 advanced to
  epoch 30 and fold 0 wrote epoch 60. No recent worker/task error signatures
  were found, so no recovery action is justified.

- At the 2026-08-31 22:18:01 +08:00 read-only check, formal coverage remained
  131/180 and the failure list remained empty. The queue continued with four
  active BindingDB tasks: three random folds and one cold-drug fold. The queue,
  four workers and release watcher (PID 3235770) remained alive; GPU
  utilization was 54%--63% with 3,060 MiB allocated per card. Process-matched
  task logs were approximately at epochs 90, 30, 30 and 20, confirming active
  progress even though two log files were stale. No recent worker/task error
  signatures were found, so no recovery action is justified.

- At the 2026-08-31 18:41:39 +08:00 read-only check, formal coverage remained
  128/180 and the failure list remained empty. The queue (PID 497482), four
  workers and release watcher (PID 3235770) were alive; GPU utilization was
  52%--71% with 3,060 MiB allocated per card. Process-matched BindingDB random
  task logs were approximately at epochs 40, 60, 70 and 80; fold 3 and fold 1
  wrote fresh log lines around 18:35, while the other two logs were stale but
  their Python processes remained alive. No recent worker/task error signatures
  were found, so no recovery action is justified.

Latest B5 liveness evidence (2026-08-31 21:47:03 +08:00): formal coverage
increased to 131/180; BindingDB random reached 11/15 while cold-drug,
cold-protein and cold-pair remained 0/15. The queue completed three additional
BindingDB random folds and then started BindingDB/cold_drug. The queue, four
workers and release watcher (PID 3235770) remained alive; GPU utilization was
26%--62% with 3,060 MiB allocated per card. The four process-matched tasks were
around epochs 80, 20, 20 and 10. No recent worker/task error signatures were
found, so no recovery action is justified.

Latest B5 liveness evidence (2026-08-31 22:22:48 +08:00 local check): formal coverage
remained 131/180 and the failure list remained empty. The four active tasks were
three BindingDB/random folds and one BindingDB/cold_drug fold; their logs were
approximately at epochs 90, 30, 30 and 20. All four Python processes remained
alive with GPU utilization of 59%--66% and 3,060 MiB allocated per card. Two
task logs were older than 30 minutes, but the corresponding processes remained
in a running state and no recent worker/task error signatures were found, so no
recovery action is justified.

Latest B5 liveness evidence (2026-08-31 22:31:46 +08:00): formal coverage
increased to 132/180; BindingDB random reached 12/15 while cold-drug,
cold-protein and cold-pair remained 0/15. The queue recorded completion of
BindingDB/random seed 4198936517 fold 3 and immediately started seed 983997847
fold 2 on GPU 0. The queue, four workers and release watcher (PID 3235770)
remained alive; GPU utilization was approximately 48%--63% with 3,060 MiB
allocated per card. Process-matched task logs were approximately at epochs 0,
20, 30 and 40. No recent worker/task error signatures were found, so no
recovery action is justified.

Latest B5 liveness evidence (2026-08-31 22:50:19 +08:00): formal coverage
remained 132/180 and the failure list remained empty. The four active tasks were
three BindingDB/random folds and one BindingDB/cold_drug fold; their logs were
approximately at epochs 1, 30, 40 and 40. GPU utilization was approximately
52%--67% with 3,060 MiB allocated per card, and all four Python processes
remained alive. No recent worker/task error signatures were found, so no
recovery action is justified.

Latest B5 liveness evidence (2026-08-31 23:10:00 +08:00 local check): formal
coverage remained 132/180 and the active failure list remained empty. A
10-second read-only sample showed increasing CPU counters for all four Python
tasks and active compute processes on GPUs 0--3; the BindingDB/cold-drug task
advanced to epoch 50/100. The remaining task logs were older, but their
processes continued to compute, so no restart was justified.

Latest B5 liveness evidence (2026-08-31 23:36:44 +08:00): formal coverage
remained 132/180 and the four process-matched tasks were approximately at
epochs 10, 50, 50 and 40. GPU utilization was approximately 53%--66% across
GPUs 0--3, the failure list was empty, and the queue and release watcher
remained alive. No recovery action is justified.

Release-path warning (2026-08-31 23:38:00 +08:00): a read-only inspection of
the active watcher (PID 3235770) confirmed the deployed SHA256, but also found
that its command order calls `verify_paper_coverage.py` before
`verify_split_integrity.py`. The watcher is not modified or restarted during
the read-only experiment. When B5 exits, the controlled release path must
execute split integrity first, then coverage/result/artifact audits, and only
then allow writes; the reviewed local finalizer already enforces this order.

Release concurrency guard (2026-08-31 23:47:00 +08:00): the local finalizer
now refuses to proceed while a queue, DrugBAN worker or release watcher is
alive. The updated release-order, placeholder, synthetic full-release and
post-processing gate regressions passed locally. This provides a fail-closed
path around the older remote watcher without modifying the active remote run.

Latest B5 liveness evidence (2026-09-01 09:47:37 +08:00): formal coverage
increased to 139/180; BindingDB random is complete at 15/15 and cold-drug is
4/15. The queue, four workers and release watcher remained alive, and the
failure list remained empty. Process-matched cold-drug tasks were approximately
at epochs 0, 70, 1 and 10; all four GPUs were active at approximately
55%--58% utilization. One log was stale while its corresponding process was
alive, so no restart was justified.

Latest B5 process-liveness evidence (2026-09-01 09:59:05 +08:00): formal
coverage remained 139/180 and the failure list remained empty. The four live
tasks were all BindingDB/cold-drug, with process-matched epoch lines at roughly
1, 70, 10 and 10; GPU utilization was approximately 30%--60%, with 3,060--
3,062 MiB allocated per card. Two task logs were stale, but their matching
Python processes remained alive and no recent worker/task errors were found;
no restart was justified.

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

Latest B5 resource-association evidence (2026-09-01 10:21:28 +08:00): the
queue and four DrugBAN processes remained alive with no recent errors, while
the formal count was still 139/180. A read-only `nvidia-smi pmon` check found
the expected DrugBAN compute processes plus PID 1968867, `python model_api.py`
under `/mnt/sda/fulaiyi/liuhongbo/ipheno/app`, using about 22,080 MiB on GPU 2
and 20,952 MiB on GPU 3. This unrelated service was not stopped or altered;
the local monitor now reports GPU compute processes explicitly so future
capacity checks retain this distinction.

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

Latest B5 liveness evidence (2026-09-01 00:00:35 +08:00): formal coverage
remained 132/180 and the failure list remained empty. Process-matched
BindingDB tasks were approximately at epochs 20, 50, 60 and 50; GPU 0--3
utilization was approximately 70%, 61%, 51% and 51%, with 3,060 MiB allocated
per card. One task log was stale, but the corresponding Python process was
alive; no restart was justified from this snapshot.

Latest B5 liveness evidence (2026-09-01 15:00:44 +08:00): formal coverage
remained 140/180, with BindingDB random at 15/15, cold-drug at 5/15 and
cold-protein/cold-pair at 0/15. The four process-matched BindingDB/cold-drug
tasks were approximately at epochs 50 (fold 0), 80 (fold 2), 80 (fold 1) and
90 (fold 3). The queue, four workers and release watcher remained alive; all
four GPUs had active DrugBAN compute with approximately 3,060 MiB allocated
per card. No recent worker/task error signatures were found and the failure
list was empty. Some task logs were stale, but the corresponding Python
processes and GPU activity confirmed liveness, so no restart or remote
modification was justified.

Latest B5 liveness evidence (2026-09-01 15:09:12 +08:00): formal coverage
remained 140/180. The four process-matched BindingDB/cold-drug tasks were
approximately at epochs 50 (fold 0), 80 (fold 2), 90 (fold 1) and 90 (fold
3). The queue, four workers and release watcher remained alive; all four GPUs
had active DrugBAN compute with approximately 3,060 MiB allocated per card.
No recent worker/task error signatures were found and the failure list was
empty. The task processes and GPU activity confirmed continued liveness, so
no restart or remote modification was justified.

Latest B5 progress evidence (2026-09-01 15:45:36 +08:00 remote check): formal
coverage increased to 142/180. BindingDB/cold-drug is now 7/15; two folds
completed and the queue advanced to the next seed. The queue, four workers and
release watcher remained alive. Process-matched task logs showed approximately
60/100 and 90/100 epochs for the older seed, plus newly started work for the
next seed. GPUs 0--3 all had active DrugBAN compute, no recent worker/task
error signatures were found, and the failure list was empty. One task log was
stale, but its matching Python process and GPU activity confirmed liveness; no
restart or remote modification was justified.

## B5 completion handoff

When the queue exits naturally, the handoff is gated by three independent
conditions: no queue/worker/release-watcher process remains, the failure list
is empty, and the strict formal coverage count is 180/180. Only then should
the release path be allowed to run. Its expected success markers, in order,
are `SPLIT_INTEGRITY_COMPLETE`, `FINAL_AUDIT_COMPLETE`,
`POSTPROCESSING_RELEASE_COMPLETE`, and a second
`FINAL_AUDIT_COMPLETE` after tables, source data and figures are generated.
The result-derived LaTeX fragments are copied only after the latter audit;
the local PDF is compiled only after the generated-fragment and author/
release-metadata gates pass.
The local finalizer and release watcher now also require the explicit
`SPLIT_INTEGRITY_COMPLETE` and `FINAL_AUDIT_COMPLETE` output markers, rather
than relying on exit status alone; the missing-marker rejection path is covered
by regression tests.

## B5 planning estimate

At the latest throughput sample, the active BindingDB folds used roughly
227--273 seconds per epoch. At 100 epochs this is roughly 6.5 hours per fold
before initialization and post-processing. At the current 144/180 coverage,
the remaining 36 formal folds represent about 9 four-worker waves plus
transition overhead, or roughly 2.5 days under the same throughput. This is a
scheduling estimate only, not
evidence of completion; the 30-minute monitor remains the authority for actual
progress.  No extra workers or sidecars should be added because the host CPU
was already near saturation in the controlled throughput observation.
