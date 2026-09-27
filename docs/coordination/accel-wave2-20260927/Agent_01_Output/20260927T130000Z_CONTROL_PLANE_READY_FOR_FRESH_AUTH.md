# Agent 01 Final — Wave 2 27B Control-Plane Consolidation

Timestamp: 2026-09-27T13:00:00Z  
Role: AQLEVON Agent 01  
Wave: accel-wave2-20260927  
Lane: RunPod / 27B control-plane + artifact preservation  
Mode: FREE-ONLY  
Status: COMPLETE

## Completion verdict

**CONTROL_PLANE_READY_FOR_FRESH_AUTH**

This verdict means the future-run control path is technically prepared for a **new, explicitly fresh, single-use authorization**. It does **not** authorize or launch a paid run.

## Live PR state

Draft PR: #54  
Head branch: `agent/01-27b-artifact-durability-20260927`  
Verified head: `6fdcfbe4fc66c6292f544c12fff13861d2eeaa2b`  
Base: `ops/runpod-control-v1`  
Merged: NO  
Main changed/merged: NO

During Wave 2 execution, the PR head advanced concurrently from the prior Agent 01 durability head. The collision was detected before overwrite. The newer live branch was reviewed instead of force-pushed or replaced.

## Consolidated control-plane changes verified

### 1. Workflow-level single flight

`.github/workflows/runpod-control-v1.yml` now has a fixed top-level concurrency group:

`aqlevon-runpod-control-v1-paid-single-flight`

with:

`cancel-in-progress: false`

The paid execute job also depends on the status job.

### 2. Durable pre-create reservation / authorization consumption

New helper:

`.github/runpod-control/aqlevon-27b-reservation.py`

The future path requires a fresh V2 authorization and rejects legacy authorization kind/state.

Before `runpodctl pod create`:
- reservation + consumption records are created;
- the exact authorization identity is bound;
- the Wave 2 control-plane contract is bound;
- the frozen scientific contract SHA is bound;
- the reservation/consumption commit is pushed to `ops/runpod-control-v1`;
- non-force push is the cross-run compare-and-swap boundary;
- the durable claim is verified before provider create.

If another logical start already published the claim, the second push fails closed before provider creation.

### 3. Fresh authorization only

The runtime path now expects:

`.github/runpod-control/aqlevon-27b-r0-fresh-authorization.json`

with authorization kind:

`AQLEVON_MANAGER_PAID_AUTHORIZATION_V2`

and control-plane contract:

`AQLEVON_27B_CONTROL_PLANE_V2`

Legacy/historical authorization is explicitly rejected by the free contract test.

No fresh paid authorization currently exists or was consumed by this task.

### 4. Scientific contract binding

Agent 03 Wave 2 contract was read and reconciled.

Frozen scientific contract commit:

`4ddb508ea0dc99ab7e02588e19915915fc67976c`

Frozen scientific contract SHA256:

`484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`

Agent 01 control-plane now requires that exact hash before provider create and persists it in reservation/consumption + final result receipt.

Historical trainer blob remains:

`9085e692d43110600e7bf214ffdab910f4821f1c`

No scientific training constant was changed.

### 5. Durable runtime-version receipt

Bootstrap now emits structured:

`runtime_versions.json`

covering Python, CUDA-visible torch runtime, and exact package versions including:
- torch
- transformers
- peft
- accelerate
- huggingface-hub
- safetensors

The evidence archive includes this structured receipt.

`verify-aqlevon-27b-evidence.py` requires and hashes the runtime receipt.

The finalizer requires a valid runtime-version receipt before pod deletion and persists the receipt identity into the durable final result.

### 6. Artifact upload-before-delete remains fail closed

The accepted PR #54 ordering remains intact:
1. evidence egress + verification;
2. pod stop to end GPU billing;
3. GitHub artifact upload with `if-no-files-found: error`;
4. finalizer validation;
5. only then provider DELETE.

Upload failure, invalid/missing artifact identity, invalid artifact digest, invalid verification marker, or invalid runtime-version receipt keeps the pod stopped but **not deleted**.

## FREE-only executable verification

Workflow:

`Agent 01 27B Control Plane Free Test`

Run:

`36320831237`

Job:

`108624210079`

Head:

`6fdcfbe4fc66c6292f544c12fff13861d2eeaa2b`

Conclusion:

**SUCCESS**

Observed passing contract markers:
- `AQLEVON_27B_CONTROL_ORDER_STATIC_PASS`
- `AQLEVON_27B_SCIENTIFIC_CONSTANTS_UNCHANGED_PASS`
- `AQLEVON_27B_SCIENTIFIC_CONTRACT_BINDING_PASS`
- `AQLEVON_27B_RUNTIME_VERSION_RECEIPT_REQUIRED_PASS`
- `AQLEVON_27B_LEGACY_AUTHORIZATION_REJECTED_PASS`
- `AQLEVON_27B_MISSING_INVALID_RESERVATION_BLOCK_PASS`
- `AQLEVON_27B_SINGLE_FLIGHT_RESERVATION_CAS_PASS`
- `AQLEVON_27B_UPLOAD_FAILURE_NO_DELETE_PASS`
- `AQLEVON_27B_ARTIFACT_DURABILITY_FREE_TEST_PASS`
- `AQLEVON_27B_CONTROL_PLANE_FREE_TEST_PASS`

The concurrent-reservation test uses two stale logical Git clones and proves only one non-force durable claim can publish.

The artifact-failure test uses a fake curl binary; no provider mutation is issued.

## Repository-wide broad-push side effects checked

At the final head, three legacy broad-push workflows reported failure:
- run `36320830773`
- run `36320830308`
- run `36320829982`

Each returned **0 jobs**.

No provider mutation body executed from those failures.

## Safety / governance receipt

- paid GPU launched: NO
- provider pod created: NO
- provider mutation in tests: NO
- paid inference/evaluation: NO
- historical authorization reused: NO
- fresh authorization consumed: NO
- historical G1 rerun: NO
- historical W05 material accessed/regenerated: NO
- scientific training constants changed: NO
- main changed: NO
- main merged: NO
- PR #54 merged: NO
- final capability promotion claimed: NO

## Exact next gate

The control plane should remain idle until the Manager/owner decision packet is complete.

If a new 27B run is still required, the next paid action must begin with one **fresh V2 authorization** bound to:
- `AQLEVON_27B_CONTROL_PLANE_V2`
- scientific contract SHA256 `484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`
- the same model/revision and frozen scientific recipe.

Do not reuse any historical authorization.

## Lane state

Agent 01 Wave 2 lane: **RELEASED**

Final verdict:

**CONTROL_PLANE_READY_FOR_FRESH_AUTH**
