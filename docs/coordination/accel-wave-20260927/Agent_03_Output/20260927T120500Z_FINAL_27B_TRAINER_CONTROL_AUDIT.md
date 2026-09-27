# Agent 03 Final — 27B Trainer / Control-Plane Hardening Audit

Timestamp: 2026-09-27T12:05:00Z
Role: AQLEVON Agent 03
Lane: exact AQLEVON-27B-R0 trainer/control-path audit
Mode: FREE-ONLY
Status: COMPLETE / MANAGER REVIEW REQUIRED

## Exact audited run

- GitHub Actions run: `36307917194`
- Exact historical source SHA: `4e3f1b03cfe77ac4355907ec692574f30d180252`
- Frozen trainer blob: `9085e692d43110600e7bf214ffdab910f4821f1c`
- Frozen W02 commit: `abb94ef134e2e97036b6959dbc9db4278d3736b6`
- Frozen W02 verifier/generator blob: `bcdf1326a891dc082a6843f764c052f9192187b8`
- Base: `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

Historical receipt remains:
- public dev: 2/28 -> 24/28
- public shadow: 1/28 -> 23/28
- trainable LoRA parameters: 1,507,328
- optimizer updates: 672
- adapter SHA256: `c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e`
- adapter-state SHA256: `e5a9b8260e7cfc08f3f9c5b072b617bdafc5ed06a645b15c10ee7937d5465bde`
- save/reload state hash match: true
- sealed eval consumed: false
- pod stopped/deleted: true

This is public-run evidence only. It is not a final independent W05 capability-promotion claim.

## Trainer invariants independently checked

PASS:
- model/revision pins
- BF16 CUDA gate
- `Qwen3_5ForConditionalGeneration`
- LoRA r=4, alpha=8, dropout=0
- q/v projection targets only
- expected 32 target modules
- expected 1,507,328 trainable parameters
- AdamW + weight decay 0.05
- LR 1e-5 -> minimum 1e-6 cosine schedule
- 672 maximum updates
- sequence cap 1024
- prompt-loss masking with `-100`
- target includes EOS
- train indices 4..19
- dev indices 0..1
- shadow indices 2..3
- no sealed-eval builder invoked by the trainer
- adapter file SHA256
- deterministic adapter-state hash
- fresh-base adapter reload + exact state-hash equality
- controller budget ceilings/timeouts
- stop/delete cleanup path
- historical authorization single-use check
- historical no-active-equivalent-pod preflight

Hugging Face repository metadata independently identifies `Qwen/Qwen3.8-27B` as qwen3_5 with approximately 27.78B parameters, consistent with the audited architecture target.

## Free executable audit delivered

Dedicated branch:
`agent/03-27b-control-audit-20260927`

Commits:
1. `6c238e92abcb7c3ee70113989947cd20377e30e9` — exact historical static audit detector
2. `4abf701b954e442b54d6bc2f15c671ca0ad71ef3` — unit tests
3. `3518705224e0ce536aad7fc8b5cdaf77f7916f78` — CPU-only GitHub Actions audit workflow

Files added:
- `research/weight_factory/agent03/aqlevon_27b_r0_static_audit_v1.py`
- `tests/test_aqlevon_27b_r0_static_audit.py`
- `.github/workflows/agent03-27b-free-static-audit.yml`

The audit reads the historical source through exact Git SHAs, so later control-plane edits cannot silently rewrite what is being audited.

## Free CI evidence

Workflow:
`Agent03 27B Free Static Audit`

Run:
`36317606164`

Head:
`3518705224e0ce536aad7fc8b5cdaf77f7916f78`

Conclusion:
**SUCCESS**

Job:
`108615161011`

All steps passed:
- pinned historical commits available
- exact historical trainer/W02 Python syntax
- exact historical controller/bootstrap Bash syntax
- audit/test compilation
- unit/static audit tests
- exact audit report emission

Unit tests:
**2/2 PASS**

Detector result:
- `all_invariants_pass=true`
- `all_receipt_checks_pass=true`

## Material findings

### FINDING A — BASELINE_FINAL_SAMPLING_NOT_PAIRWISE

`eval_tasks()` derives the generation seed from `label + ":" + task_id`.

Baseline and final labels differ, so baseline/final generation on the same public tasks does not use the same random stream. The large public score change remains a recorded run result, but it is not a strict same-seed paired before/after estimate.

This was independently corroborated by Agent 04. No post-result recipe change was made.

### FINDING B — CHECKPOINT / DEV STOCHASTIC CONFOUND

The same label-dependent seed mechanism changes the sampling stream at each `dev_after_<step>` checkpoint. Dev also participates in the frozen early-stop logic.

The run reached all 672 updates and did not select an earlier checkpoint, so there is no evidence of a post-hoc earlier-checkpoint pick. The limitation is stochastic comparability and reuse of the dev family, not proof of cherry-picking.

Agent 04 owns the new independent public generalization challenge lane, so Agent 03 did not duplicate it.

### FINDING C — CONTROL_SINGLE_FLIGHT_RACE

The historical `runpod-control-v1.yml` contains no top-level GitHub Actions `concurrency` guard.

The historical controller:
1. checks that the consumed marker is absent;
2. checks no equivalent pod is active;
3. creates the paid pod;
4. only then commits/pushes the consumed marker.

Therefore concurrent qualifying runs had a race window before durable consumption publication.

Recommended future-only hardening:
- serialize control workflow runs with a fixed concurrency group and `cancel-in-progress: false`; and/or
- implement a durable fail-closed reservation/lease before provider pod creation.

Do not reuse any historical authorization to test this.

### FINDING D — ARTIFACT_DURABILITY_DEFECT

Historical run `36307917194` downloaded `evidence.tgz` only to the ephemeral Actions runner and uploaded zero GitHub Actions artifacts before deleting the pod.

Agent 01 independently owns the artifact persistence/recovery lane.

### FINDING E — RUNTIME_VERSION_RECEIPT_GAP

The bootstrap captured torch/transformers/peft/accelerate versions in `versions.txt`, but that file lived only inside the nondurable evidence archive. The durable result receipt does not preserve those exact runtime package versions.

## COLLISION / BLOCKED

A direct Agent 03 patch to `.github/workflows/runpod-control-v1.yml` was intentionally **NOT** made.

Reason:
- Agent 01 now has active branch `agent/01-27b-artifact-durability-20260927`
- Agent 01 head at final reconciliation: `59b976e61242b426a7429d4cc1c61c73b1983594`
- that branch modifies the exact same workflow/control area for artifact preservation

Applying Agent 03 concurrency changes simultaneously would violate the one-owner-per-mutation-lane rule and create a merge/collision risk.

Therefore Agent 03 leaves the concurrency fix as an evidence-backed hardening requirement for Manager/Agent 01 reconciliation, rather than overwriting Agent 01's active work.

## Repository-wide workflow side effect observed

Pushing the Agent 03 audit branch caused three old repository workflows with broad push triggers to report failure:
- `runpod-runtime-probe.yml`
- `aqlevon-runpod-capacity-scan.yml`
- `runpod-retry18h-diagnose.yml`

For the inspected latest failures, GitHub returned **zero jobs** for each run. No job body executed and no paid resource was started by those failed runs.

The dedicated Agent 03 audit workflow itself used only `ubuntu-latest` CPU GitHub Actions.

## Parallel reconciliation

Latest relevant reports read before closure:
- Agent 01: artifact recovery/persistence active.
- Agent 02 final: legacy W05 verdict `EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`; future-only custody gate completed on separate branch/PR. Historical W05 material was not regenerated.
- Agent 04: independent evidence audit confirms seed mismatch/template-family limitations and is freezing a new public challenge pack.

No other worker's files were modified.

## Resource / safety receipt

- main modified: NO
- main merged: NO
- paid GPU launched by Agent 03: NO
- paid authorization consumed by Agent 03: NO
- historical G1 rerun: NO
- W05 private plaintext/secret accessed: NO
- W05 private material regenerated: NO
- scientific trainer constants changed: NO
- historical metric recipe changed after results: NO
- final model promotion claimed: NO

## End state / handoff

Agent 03 lane is **RELEASED after audit**.

Manager should reconcile two separate future hardenings before any new paid 27B attempt:
1. Agent 01 artifact-preservation changes.
2. Agent 03 single-flight requirement (workflow concurrency / durable pre-create lease).

For model quality evidence, treat the existing 2/28 -> 24/28 and 1/28 -> 23/28 results as strong in-family public-run evidence but not as a same-seed paired estimate or final independent sealed/generalization proof.
