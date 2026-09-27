# Agent 01 Final — Wave 2 27B Control-Plane Consolidation

Timestamp / evidence cut: 2026-09-27T13:01:17Z  
Role: AQLEVON Agent 01  
Wave: accel-wave2-20260927  
Lane: RunPod / 27B control-plane + artifact preservation  
Mode: FREE-ONLY  
Status: COMPLETE / CONTROL_PLANE_READY_FOR_FRESH_AUTH

## Verdict

**CONTROL_PLANE_READY_FOR_FRESH_AUTH**

The future 27B control path now consolidates the accepted PR #54 artifact-preservation design with the remaining Agent 03 control-plane findings and the Wave 2 frozen scientific contract.

This verdict does **not** authorize a paid run. No fresh paid authorization exists in the branch.

## Live PR state

Draft PR:
`#54 — Agent 01: fail-closed 27B control plane + artifact durability`

URL:
`https://github.com/india123445t-pixel/MUS-AI/pull/54`

Head branch:
`agent/01-27b-artifact-durability-20260927`

Final verified head:
`6fdcfbe4fc66c6292f544c12fff13861d2eeaa2b`

Base:
`ops/runpod-control-v1 @ 7ce2422b2592c2fb89d74af4139e17b7c4fca620`

PR state at final check:
- OPEN
- DRAFT
- mergeable=true
- merged=false
- main merge: NO
- 8 changed files
- 12 commits total in PR

## Wave 2 commits

1. `d024534c1a3a72592546d2015e6ed1249944795e` — consolidate single-flight, pre-create reservation, runtime receipt.
2. `b29e962344f6eddfb0ea81f1e7c71396c771339f` — repair preservation finalizer and strengthen free test.
3. `a836a5cea2dafcb058da445246745ce8b2bf3c77` — require Fresh Authorization V2 and reject historical authorization.
4. `9fb2f836578a85263f21c87f2daf4e360e53c70c` — hard-bind fresh authorization/reservation/result to Agent 03 frozen scientific contract.
5. `6fdcfbe4fc66c6292f544c12fff13861d2eeaa2b` — initialize free-test scratchdir before contract verification.

No force push was used.

## Single-flight / provider-create race closure

Workflow:
`.github/workflows/runpod-control-v1.yml`

Added a fixed workflow concurrency group:
- group: `aqlevon-runpod-control-v1-paid-single-flight`
- `cancel-in-progress: false`

The execution job is serialized after the status job.

Controller:
`.github/runpod-control/run-aqlevon-27b-r0-budget8.sh`

Reservation helper:
`.github/runpod-control/aqlevon-27b-reservation.py`

Before any provider-create action:
1. a fresh authorization is validated;
2. the frozen scientific contract is verified;
3. a reservation and consumption record are created locally;
4. both are committed;
5. an ordinary non-force push publishes the claim to `ops/runpod-control-v1`;
6. a competing stale logical start loses the Git push CAS and exits before provider create;
7. exact remote reservation/consumption identity is re-read and verified;
8. only then can provider create be reached.

Missing, malformed, mismatched, or already-existing reservation/consumption data fails closed.

## Fresh authorization only

The controller no longer points at historical authorization:
`P4-AQLEVON-27B-R0-PRESERVE-20260927-02`.

Future path:
`.github/runpod-control/aqlevon-27b-r0-fresh-authorization.json`

Required authorization schema:
- `kind = AQLEVON_MANAGER_PAID_AUTHORIZATION_V2`
- `control_plane_contract = AQLEVON_27B_CONTROL_PLANE_V2`
- `fresh_authorization = true`
- single-use/training/cleanup/artifact/no-main/no-sealed-eval flags all true
- exact base model/revision and budget caps
- exact frozen scientific-contract SHA256

The helper explicitly rejects legacy authorization V1.

Final branch check:
`aqlevon-27b-r0-fresh-authorization.json` is **ABSENT**.

Therefore the future paid path remains fail-closed until a new single-use authorization is deliberately issued.

## Frozen Agent 03 scientific contract binding

Wave 2 Agent 03 verdict read:
`RERUN_SCIENTIFIC_CONTRACT_READY`

Exact scientific contract SHA256:
`484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`

Pinned Agent 03 release commit:
`4ddb508ea0dc99ab7e02588e19915915fc67976c`

Pinned contract blob:
`6d2424a589af250f878c1a83a3811aa6ccd5b4b0`

Pinned verifier blob:
`990ab86bebcbe69050dc5f644c6ff12f60db75d3`

Before any future provider call/create, the controller:
- verifies the exact pinned contract/verifier Git blobs;
- runs Agent 03's exact released verifier;
- requires contract self-hash PASS;
- requires frozen trainer/W02 source-blob matches;
- requires frozen training constants match;
- requires same-seed paired-public contract validity;
- requires private/sealed source count = 0.

The exact contract SHA is also mandatory in:
- Fresh Authorization V2;
- reservation record;
- consumption record;
- final run receipt.

No scientific training constant was modified by Agent 01.

## Artifact durability / upload-before-delete

The previously accepted PR #54 durability ordering remains intact:
1. evidence archive is retrieved;
2. exact adapter SHA is verified against manifest + receipt;
3. runtime-version receipt is verified;
4. evidence is uploaded with `actions/upload-artifact@v4`;
5. upload must return durable artifact identity + SHA-shaped digest;
6. only the later finalizer may delete the pod.

Any upload/digest/runtime verification failure:
- stops the pod;
- records failure when possible;
- **does not delete the pod**.

The execution controller contains no provider DELETE.

## Runtime reproducibility receipt

Bootstrap now writes:
`runtime_versions.json`

It records:
- Python version;
- torch;
- transformers;
- peft;
- accelerate;
- huggingface-hub;
- safetensors;
- torch CUDA version.

The evidence verifier requires this structured receipt and emits:
- `runtime_versions_sha256`
- exact `runtime_versions`

The final run result durably copies the exact runtime-version receipt.

Pod deletion is blocked if the runtime receipt is absent or invalid.

## Frozen scientific trainer identity

The free test asserts the trainer Git blob remains exactly:
`9085e692d43110600e7bf214ffdab910f4821f1c`

Result:
`AQLEVON_27B_SCIENTIFIC_CONSTANTS_UNCHANGED_PASS`

## Final FREE-only CI evidence

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

Observed PASS markers:
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

The test suite uses GitHub-hosted CPU only and does not issue provider API mutations.

## Development failures caught by FREE CI

Two intermediate FREE-only failures were caught and repaired before final acceptance:
- Run `36320243407`: malformed preservation-finalizer shell condition.
- Run `36320778166`: test scratch directory referenced before initialization.

Both were software/test defects only. No paid provider job was launched.

A prior post-fix free run `36320453767` was also SUCCESS before the later fresh-auth/scientific-contract hardening.

## Broad-push workflow side effect

On the final push, three legacy broad-push workflows reported failure:
- `aqlevon-runpod-capacity-scan.yml` run `36320830773`
- `runpod-runtime-probe.yml` run `36320830308`
- `runpod-retry18h-diagnose.yml` run `36320829982`

Each returned:
`job_count = 0`

Therefore no provider mutation job body ran from those failed workflows.

## Parallel-worker reconciliation

Read before completion:

Agent 02 Wave 2:
- verdict `FUTURE_W05_HARD_BINDING_READY`
- PR #52 remains Draft/unmerged
- no collision with Agent 01 control-plane lane
- no historical W05 material accessed/regenerated

Agent 03 Wave 2:
- verdict `RERUN_SCIENTIFIC_CONTRACT_READY`
- exact contract SHA `484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`
- explicit Agent 01 integration requirement was incorporated before final completion

No Agent 04 Wave 2 output was present in the coordination folder at the final pre-report read.

## Resource / safety receipt

- main changed: NO
- main merged: NO
- paid GPU: NO
- provider pod/job created by Agent 01 Wave 2: NO
- provider mutation in tests: NO
- paid inference: NO
- historical authorization reused: NO
- fresh paid authorization issued: NO
- historical G1 rerun: NO
- historical W05 private material accessed/regenerated: NO
- scientific training constants changed: NO
- historical R0 artifact falsely claimed recovered: NO
- capability gain claimed: NO
- model promotion claimed: NO

## Handoff

The control-plane code is ready for Manager review and, after the surrounding Wave 2 lanes are consolidated, for issuance of a **new** single-use V2 authorization if the owner chooses to fund a future 27B run.

The next paid action is intentionally impossible from the current branch because no fresh authorization file exists.

Completion verdict:

**CONTROL_PLANE_READY_FOR_FRESH_AUTH**

AQLEVON_WORKER_COMPLETION
WORKER_ID: 01
TASK_ID: WAVE2_27B_CONTROL_PLANE_CONSOLIDATION
STATUS: COMPLETE
BRANCH: agent/01-27b-artifact-durability-20260927
COMMIT: 6fdcfbe4fc66c6292f544c12fff13861d2eeaa2b
PR: 54
TESTS: GitHub Actions run 36320831237 / job 108624210079 SUCCESS
MANAGER_REVIEW_REQUIRED: YES
