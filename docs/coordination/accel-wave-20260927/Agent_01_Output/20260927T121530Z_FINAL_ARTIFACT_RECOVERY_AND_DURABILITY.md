# Agent 01 Final — 27B Artifact Recovery + Fail-Closed Durability Hardening

Timestamp: 2026-09-27T12:15:30Z
Role: AQLEVON Agent 01
Lane: 27B candidate artifact recovery/persistence
Mode: FREE-ONLY
Status: COMPLETE / ORIGINAL ARTIFACT NOT RECOVERABLE / FUTURE PATH HARDENED

## Exact historical target

GitHub Actions run:
- 36307917194

Historical public-pass adapter identity:
- adapter SHA256: c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e
- adapter-state SHA256: e5a9b8260e7cfc08f3f9c5b072b617bdafc5ed06a645b15c10ee7937d5465bde
- evidence archive SHA256 recorded by controller: eca1b1023f000fc49e9c5c3579aa330bb73121cd54a00b16327d068e74de1bb6
- candidate manifest SHA256: cf1d3b4c31a2d5396986099f2663cf3ce7d18c15cac695dfe1379e25da7d45b2

## Recovery verdict

**IRRECOVERABLE_AFTER_POD_DELETE**

Reason:
1. Historical run 36307917194 has zero GitHub Actions artifacts.
2. The controller log proves /evidence.tgz was downloaded from the pod to /tmp/aq27-evidence.tgz on the ephemeral GitHub-hosted runner.
3. The bootstrap package_evidence() included the entire candidate directory, including adapter_model.safetensors.
4. The historical controller parsed the manifest/receipt from that temporary archive, then stopped/deleted the pod.
5. No upload-artifact, Release asset, Git blob, or Library binary preserving that exact archive/adapter was performed before deletion.
6. Current GitHub Releases contain Auth16 4B assets only, not the historical 27B R0 adapter.
7. Repository branch/tree searches and AQLEVON Library searches did not locate byte-identical adapter storage.
8. A later preservation rerun records a different adapter SHA256 (ad487f091a0fdce81f0d16f9b966dd7b89f0cb54504fb4469509e130d147d611); it is a different stochastic training artifact and is not recovery of c91f007a....

Therefore the historical receipt/hash evidence remains valid evidence that the original adapter existed and save/reload matched during that run, but the exact original bytes are not durably recoverable from currently accessible sources.

## Root defect

Historical control order was:

1. train/package on pod
2. GET evidence.tgz to ephemeral Actions runner
3. stop/delete pod
4. parse JSON hashes/receipts
5. commit JSON result only

There was no durable binary upload gate between steps 2 and 3.

An intermediate later patch added upload-artifact after the execution script, but the execution script still deleted the pod first and the upload used if-no-files-found: ignore. That remained non-fail-closed.

## Dedicated implementation branch

Branch:
agent/01-27b-artifact-durability-20260927

Base:
ops/runpod-control-v1 @ 7ce2422b2592c2fb89d74af4139e17b7c4fca620

Current head:
716a7d0f3a1ebf32c6576d08b4e6efa796bd8295

Commits:
1. 68016e1c2533b732be857cb454875a72bb5affa1 — ops(agent01): add 27B evidence SHA verifier
2. 80b3614e533f10280a91b1f0c573b2b58b85fb2e — ops(agent01): gate pod deletion on durable artifact
3. f21bc1ac919b8612bfe98f47d18e14de6a433fd5 — test(agent01): add free 27B artifact durability contract
4. 97a44566f4f6972797fae07a5582831eac16feab — fix(agent01): defer pod deletion until durable 27B upload
5. 59b976e61242b426a7429d4cc1c61c73b1983594 — fix(agent01): upload 27B artifact before pod deletion
6. 3d9ebe237130abae59fcc352d8c45009ac5f7235 — ci(agent01): test 27B artifact durability free-only
7. 716a7d0f3a1ebf32c6576d08b4e6efa796bd8295 — fix(agent01): repair artifact gate shell syntax

Changed files relative to ops/runpod-control-v1:
- .github/runpod-control/finalize-aqlevon-27b-preservation.sh
- .github/runpod-control/run-aqlevon-27b-r0-budget8.sh
- .github/runpod-control/test-aqlevon-27b-artifact-durability.sh
- .github/runpod-control/verify-aqlevon-27b-evidence.py
- .github/workflows/agent01-27b-artifact-durability-free.yml
- .github/workflows/runpod-control-v1.yml

Compare at completion:
- ahead: 7
- behind: 0

## New fail-closed behavior

Before pod deletion:
1. evidence.tgz must exist and be non-empty;
2. required candidate manifest/receipt/adapter files must exist in the archive;
3. actual adapter_model.safetensors SHA256 is computed from the bytes;
4. actual SHA must equal candidate manifest adapter_sha256;
5. actual SHA must equal training receipt adapter_sha256;
6. save/reload hash match must be true;
7. GPU pod is stopped after egress to stop compute billing, but retained;
8. actions/upload-artifact@v4 uploads the archive with if-no-files-found: error;
9. finalizer requires upload outcome=success, artifact ID, artifact digest, and SHA-verification marker;
10. only then is pod deletion permitted;
11. if upload/digest/verification fails, the pod remains stopped and is NOT deleted;
12. durable result receipt records preservation state and GitHub artifact identity.

No scientific training constants or evaluation thresholds were modified.

## Free test evidence

Dedicated free-only workflow:
- Agent 01 27B Artifact Durability Free Test
- run: 36318285694
- job: 108617048761
- head: 716a7d0f3a1ebf32c6576d08b4e6efa796bd8295
- conclusion: SUCCESS

Passed markers:
- AQLEVON_27B_ARTIFACT_ORDER_STATIC_PASS
- AQLEVON_27B_ARTIFACT_SHA_VERIFIED
- AQLEVON_27B_ARTIFACT_DURABILITY_FREE_TEST_PASS

The test:
- bash syntax-checks both control shell scripts;
- py_compiles the SHA verifier;
- verifies upload-before-finalizer ordering;
- proves the execution script contains no pod DELETE;
- builds a synthetic adapter archive;
- verifies its byte SHA through the real verifier;
- mutates the adapter bytes and proves verification rejects the tampered archive.

A first free CI run correctly caught a shell rewrite defect (fiif) before use; commit 716a7d0 fixed it, and the second run passed.

Repository-wide legacy broad-push workflows also reported failures on branch pushes, but their inspected jobs lists were empty; no job body ran and no paid resource was started.

## Pull request

Draft PR:
- #54
- title: Agent 01: fail-closed 27B artifact durability before pod delete
- head: agent/01-27b-artifact-durability-20260927
- base: ops/runpod-control-v1
- state: OPEN / DRAFT / NOT MERGED

No merge was performed.

## Parallel-worker reconciliation

Read before closure:
- Agent 02 final: legacy W05 material EXISTS_BUT_ACCESS_PATH_UNAVAILABLE; no regeneration.
- Agent 03 final: historical trainer/control audit passed many invariants and independently confirmed ARTIFACT_DURABILITY_DEFECT. Agent 03 deliberately did not modify this workflow because Agent 01 owns this mutation lane.
- Agent 03 separately identified CONTROL_SINGLE_FLIGHT_RACE. That concurrency/lease hardening is not silently folded into this artifact-only patch and remains a Manager reconciliation item.
- Agent 04 final: original adapter bytes not proven durable; new public structural challenge frozen; no inference run.

No other worker report/file was modified.

## Resource / safety receipt

- main modified: NO
- main merged: NO
- paid GPU/resource launched by Agent 01: NO
- paid authorization consumed/reused: NO
- historical G1 rerun: NO
- W05 sealed/private plaintext accessed: NO
- W05 secret regenerated: NO
- scientific recipe changed after results: NO
- final model promotion claimed: NO

## Final handoff

Original historical adapter c91f007a... cannot be truthfully delivered because its bytes were lost with the ephemeral runner/pod lifecycle.

The future control path is now patched and FREE-CI verified so that a future authorized candidate cannot be marked durably preserved and have its pod deleted unless the actual adapter archive is SHA-verified and successfully uploaded first.

Manager action:
1. review draft PR #54;
2. reconcile Agent 03 single-flight/concurrency hardening separately;
3. do not rerun paid training under any old authorization;
4. do not claim final promotion from the historical public run alone.
