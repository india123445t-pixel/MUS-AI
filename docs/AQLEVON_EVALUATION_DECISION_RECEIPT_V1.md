# AQLEVON Evaluation Decision Receipt V1

**Worker:** 05 — Evaluation / Truth / Red-Team  
**Task:** `P2-A05-EVAL-DECISION-RECEIPT`  
**Status:** P2 implementation artifact; subordinate to Manager-frozen `/AQLEVON/Coordination/AQLEVON_P2_INTEGRATION_CONTRACTS_V1.md`.

## Purpose

P1 established a fail-closed evaluation gate. P2 turns that gate decision into one immutable cross-lane receipt that Worker 04, Worker 06, and the Manager can consume without retyping evaluation truth as free booleans.

Canonical receipt kind:

`AQLEVON_EVALUATION_DECISION_RECEIPT_V1`

This implementation exports no protected prompt/answer plaintext and no raw paired outcome arrays.

## Receipt bindings

The receipt self-hash binds:
- `candidate_artifact_manifest_sha256` from the Worker-03/Manager contract;
- `experiment_manifest_sha256`;
- preregistration anchor request + Manager-verifiable external anchor identity;
- `evaluation_policy_sha256`;
- exact `evaluation_code_sha256`;
- frozen `harness_manifest_sha256`;
- `provenance_receipt_sha256`;
- `contamination_scan_receipt_sha256`;
- derived `red_team_evidence_root_sha256` over the complete policy-required class set;
- base raw-output and run-trace SHA-256 values;
- candidate raw-output and run-trace SHA-256 values;
- every required target/protected domain metric summary;
- paired uncertainty/significance diagnostics;
- efficiency summaries;
- final `INVALID | REJECTED | PROMOTION_ELIGIBLE` status;
- hash-derived invalid/failure reason codes and sealed reason-set digests;
- final receipt SHA-256.

`PROMOTION_ELIGIBLE` is explicitly not a release declaration. Manager review and an independent rerun remain mandatory.

## One-authority-per-fact rule

Worker 05 does **not** redefine Worker 03's Candidate Artifact Manifest semantics or self-digest canonicalization. At this boundary Worker 05 consumes only:
- canonical manifest kind `AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1`;
- its 64-hex SHA-256 identity.

Worker 03 remains authority for artifact content/layout/tree validity. Worker 05 is authority for evaluation decision truth. Worker 04/06 should consume the Worker-05 receipt identity, not reconstruct evaluation booleans.

## Preregistration anchor interface

A self-hashed experiment manifest is tamper-evident but does not prove *when* it existed. P2 therefore adds two separate objects:

1. `AQLEVON_PREREGISTRATION_ANCHOR_REQUEST_V1`
   - binds experiment manifest, evaluation policy, candidate artifact identity, and requested anchor kind;
   - self-hashed;
   - is **not** chronology proof.

2. `AQLEVON_PREREGISTRATION_ANCHOR_VERIFICATION_V1`
   - allowed `anchor_kind`: `git_commit | immutable_object | append_only_ledger`;
   - binds the exact anchor request;
   - carries an immutable external reference;
   - requires `external_evidence_sha256`;
   - requires `manager_authority_id`;
   - requires `manager_attestation_sha256` for the separately stored Manager-owned attestation artifact;
   - requires RFC3339 UTC `anchored_at_utc` and `verified_at_utc`, with verification not earlier than anchoring;
   - self-hashed for tamper evidence.

The helper that canonicalizes this record does **not** confer Manager authority. The Manager must independently resolve the external immutable reference and verify the external evidence + Manager attestation artifacts. This deliberately prevents `self_hash` or caller-supplied `verified=true` from becoming chronology truth.

No actual production/preregistered evaluation anchor is created by this P2 implementation because no real AQLEVON promotion candidate/output run exists yet.

## Fail-closed behavior

Receipt construction rejects mismatches in:
- candidate artifact identity shape/kind;
- experiment manifest binding;
- policy binding;
- anchor request/verification binding;
- missing external anchor evidence;
- missing Manager attestation evidence;
- anchor timestamp format/order;
- base/candidate harness identity;
- raw outputs/run traces;
- provenance receipt;
- contamination scan receipt;
- complete red-team class set/evidence;
- required domain diagnostics;
- efficiency evidence;
- unsupported final status.

Receipt validation also rejects tampered self-digests and any forbidden prompt/answer/plaintext keys.

## Reason-code privacy

The P1 gate may retain detailed failure text in sealed evaluation artifacts. The cross-lane P2 receipt exports only stable hash-derived codes such as:
- `INVALID_<16 hex>`;
- `FAILURE_<16 hex>`.

It also binds the full sealed reason sets by SHA-256. This lets consumers compare decisions without exporting diagnostic text that could reveal private evaluation details.

## CLI

Create an anchor request:

```text
python evaluation_decision_receipt_v1.py anchor-request \
  --experiment-manifest EXPERIMENT.json \
  --policy release_gate_policy_v1.json \
  --candidate-artifact-manifest CANDIDATE.json \
  --anchor-kind git_commit \
  --output ANCHOR_REQUEST.json
```

Validate a Manager verification record:

```text
python evaluation_decision_receipt_v1.py validate-anchor \
  --anchor-request ANCHOR_REQUEST.json \
  --anchor-verification ANCHOR_VERIFICATION.json
```

Build the decision receipt after P1 evaluation has completed:

```text
python evaluation_decision_receipt_v1.py build-receipt \
  --candidate-artifact-manifest CANDIDATE.json \
  --experiment-manifest EXPERIMENT.json \
  --policy release_gate_policy_v1.json \
  --evaluation-code eval_truth_gate.py \
  --anchor-request ANCHOR_REQUEST.json \
  --anchor-verification ANCHOR_VERIFICATION.json \
  --report REPORT.json \
  --gate-result GATE_RESULT.json \
  --scan-receipt SCAN_RECEIPT.json \
  --output EVALUATION_DECISION_RECEIPT.json
```

Validate receipt identity/bindings:

```text
python evaluation_decision_receipt_v1.py validate-receipt \
  --receipt EVALUATION_DECISION_RECEIPT.json \
  --candidate-artifact-manifest CANDIDATE.json \
  --experiment-manifest EXPERIMENT.json \
  --policy release_gate_policy_v1.json \
  --anchor-request ANCHOR_REQUEST.json \
  --anchor-verification ANCHOR_VERIFICATION.json
```

## Consumer law

### Worker 04
Consume:
- receipt kind;
- receipt SHA-256;
- candidate artifact manifest SHA-256;
- final status;
- metric summaries required by merge policy.

Do not invent evaluation margins or substitute `behavior_pass=true` for this receipt.

### Worker 06
Use receipt identity only as correctness/promotion truth joined to runtime attempt receipts. Runtime measurements remain Worker 06 truth; correctness is not a runtime field.

## Tests

The final local suite runs P1 + P2 together:
- P1 accepted repair regressions: **23/23 PASS**;
- P2 receipt/anchor regressions: **27/27 PASS**;
- combined: **50/50 PASS**;
- `py_compile`: PASS.

P2 regressions include:
- self-hash alone cannot satisfy external anchor evidence;
- missing Manager attestation is invalid;
- anchor request is bound to candidate artifact + experiment + policy;
- anchor tampering / kind mismatch / timestamp errors fail closed;
- incomplete Red-Team class set fails closed even if an old gate result is reused;
- report/experiment, harness, provenance and scan mismatches fail closed;
- receipt tampering and policy/candidate binding mismatch fail closed;
- no raw outcomes or protected prompt/answer keys are exported;
- CLI build + validation end-to-end passes.

## Truth boundary

This P2 artifact does not:
- create new AQLEVON weights;
- prove capability improvement;
- authorize release;
- create a production preregistration anchor;
- change Manager-frozen canonical architecture;
- merge any PR to `main`.