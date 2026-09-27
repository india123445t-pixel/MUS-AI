# Agent 03 Checkpoint — 27B Trainer / Control-Plane Audit

Timestamp: 2026-09-27T11:56:00Z
Role: AQLEVON Agent 03
Lane: exact AQLEVON-27B-R0 trainer/control-path audit
Mode: FREE-ONLY
State: ACTIVE

## Start / live state verified

- Repository: `india123445t-pixel/MUS-AI`
- Historical 27B GitHub Actions run: `36307917194`
- Exact historical source SHA used by the execute job: `4e3f1b03cfe77ac4355907ec692574f30d180252`
- Current control head at branch creation: `7ce2422b2592c2fb89d74af4139e17b7c4fca620`
- Dedicated audit branch: `agent/03-27b-control-audit-20260927`
- No paid resource was started. Current sanitized RunPod status reports zero pods.
- The historical single-use authorization is durably marked consumed.

## Verified trainer invariants

The exact historical trainer was inspected at the source SHA, not inferred from the current branch.

Verified:
- base: `Qwen/Qwen3.8-27B`
- revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- BF16 CUDA requirement
- architecture class: `Qwen3_5ForConditionalGeneration`
- LoRA: rank 4, alpha 8, dropout 0, q/v projections only
- expected target modules: 32
- expected trainable parameters: 1,507,328
- AdamW, LR 1e-5, minimum LR 1e-6, cosine schedule, weight decay 0.05
- max updates: 672
- sequence cap: 1024
- prompt tokens masked with -100; target plus EOS receives loss
- public training indices: 4..19 with 3 perturbations
- public dev indices: 0,1; public shadow indices: 2,3
- trainer does not invoke the secret-derived sealed-eval builder
- adapter file SHA and deterministic adapter-state hash are computed
- adapter is reloaded onto a fresh base and state hash equality is required

Historical receipt also records:
- public dev: 2/28 -> 24/28
- public shadow: 1/28 -> 23/28
- adapter SHA256: `c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e`
- adapter-state SHA256: `e5a9b8260e7cfc08f3f9c5b072b617bdafc5ed06a645b15c10ee7937d5465bde`
- reload hash match: true
- sealed eval consumed: false
- pod stopped/deleted: true

## Audit findings

### 1. BASELINE_FINAL_SAMPLING_NOT_PAIRWISE

The evaluator seeds generation with a hash containing `label + ":" + task_id`.

Baseline labels and final labels differ, therefore baseline and final evaluation use different random sampling streams even on the same public tasks. The reported gain is real run evidence, but it is **not a strict same-seed paired before/after comparison**.

No scientific recipe was changed after observing this result.

### 2. CONTROL_SINGLE_FLIGHT_RACE

The exact historical `.github/workflows/runpod-control-v1.yml` has no top-level `concurrency` guard.

The controller checks that the consumed marker is absent and that no equivalent pod is active, but creates the paid pod before it commits/pushes the consumed marker. Two near-simultaneous qualifying workflow runs therefore have a race window in which both can pass the preconditions before either publishes consumption.

No paid rerun was attempted.

### 3. ARTIFACT_DURABILITY_DEFECT — READ-ONLY CONFIRMATION

The historical controller downloaded `evidence.tgz` to ephemeral `/tmp`, then deleted the pod and committed only parsed JSON receipts. GitHub Actions run `36307917194` has zero uploaded artifacts.

Agent 01 independently reached the same durability finding and owns the artifact-recovery/persistence lane. Agent 03 will not patch that overlapping area.

### 4. RUNTIME_VERSION_RECEIPT_GAP

The bootstrap wrote torch/transformers/peft/accelerate versions into `versions.txt`, but that file was only packaged inside the now-nondurable `evidence.tgz`. The durable result JSON does not retain those exact runtime package versions.

## Concurrency reconciliation

Read before this checkpoint:
- Agent 01 artifact recovery checkpoint: owns persistence/recovery hardening.
- Agent 02 sealed-evaluation custody verdict: `EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`; explicitly forbids regenerating or substituting legacy W05 private material.
- No Agent 04 output was present at the latest scan.

No other worker files were modified.

## Mutations

Created dedicated branch:
`agent/03-27b-control-audit-20260927`

Created:
`research/weight_factory/agent03/aqlevon_27b_r0_static_audit_v1.py`

Commit:
`6c238e92abcb7c3ee70113989947cd20377e30e9`

The audit script reads the historical source by exact Git SHA and checks trainer/control invariants, durable receipt hashes, and the four findings above. It does not alter the historical trainer or scientific constants.

## Safety / resource state

- main: unchanged
- paid compute: none
- GPU: none
- historical G1: not rerun
- W05 private/sealed plaintext: not accessed or regenerated
- scientific recipe: unchanged
- final capability promotion: not claimed

## Next safe action

Add CPU-only unit/static tests and a dedicated free GitHub Actions audit workflow on the Agent 03 branch. The workflow will compile and syntax-check the exact historical source files by pinned SHA and execute the audit detector. Then record the exact CI run/result in a new additive report.
