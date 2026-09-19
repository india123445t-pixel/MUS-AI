# AQLEVON Evaluation Decision Receipt V1 — P2.1 Interoperability

**Worker:** 05 — Evaluation / Truth / Red-Team  
**Task:** `P2.1-R05-EVAL-HASH-INTEROP`  
**Status:** P2.1 repair artifact; subordinate to Manager-frozen `/AQLEVON/Coordination/AQLEVON_P2_INTEGRATION_CONTRACTS_V1.md` amendment.

## Purpose

P1 established the fail-closed evaluation gate. P2 introduced one immutable cross-lane Evaluation Decision Receipt. P2.1 repairs its cross-lane identity so Workers 03/04/06 and Manager verify exactly the same self-hash bytes and do not infer authority that the receipt does not possess.

Canonical receipt kind:

`AQLEVON_EVALUATION_DECISION_RECEIPT_V1`

Canonical P2.1 hash profile:

`AQLEVON_CANONICAL_JSON_SHA256_V1`

The receipt exports no protected prompt/answer plaintext and no raw paired outcome arrays.

## P2.1 canonical self-hash profile

All Worker-05 P2.1 self-hashed cross-lane records carry:

`hash_profile: AQLEVON_CANONICAL_JSON_SHA256_V1`

This applies to:
- `AQLEVON_EVALUATION_DECISION_RECEIPT_V1` / `receipt_sha256`;
- `AQLEVON_PREREGISTRATION_ANCHOR_REQUEST_V1` / `request_sha256`;
- `AQLEVON_PREREGISTRATION_ANCHOR_VERIFICATION_V1` / `verification_record_sha256`.

The implementation follows the Manager-frozen profile:
- SHA-256 over UTF-8 compact JSON with only the exact self-digest field omitted;
- authoritative object keys must be non-empty ASCII and are sorted lexicographically by ASCII byte value;
- arrays preserve order;
- strings are Unicode NFKC-normalized and `CRLF` / `CR` normalize to `LF` before serialization;
- booleans/null use JSON literals;
- integers remain ordinary base-10 JSON integers;
- direct non-integral numeric values are forbidden in authoritative self-hash payloads;
- producer-side non-integral metrics are converted to canonical decimal strings with no exponent, no leading `+`, no unnecessary leading zero, no trailing fractional zero, and `-0` normalized to `0`;
- self-digest and all cross-lane SHA-256 lexemes are lowercase 64-hex.

The accepted Worker-06 cross-language vector is reproduced in Worker-05 tests:

```text
{"10":"ten","2":"two","text":"é\nline","tiny":"0.0000001"}
SHA-256 = 1b1580a59f4ae1efdf8ed0fc7a86ffbcf1ee32d9f6d3294840afecd8a55f8b19
```

Worker-05 validation rejects missing/unknown hash profiles rather than guessing another canonicalizer.

## Candidate Artifact Manifest boundary

Worker 03 remains authority for Candidate Artifact Manifest semantics: artifact type/stage, layout, topology, file tree, lineage, and G1 `probe_only` restrictions.

P2.1 standardizes only shared integrity. Worker 05 therefore verifies:
- `manifest_kind = AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1`;
- `hash_profile = AQLEVON_CANONICAL_JSON_SHA256_V1`;
- lowercase `manifest_sha256`;
- the shared P2.1 canonical self-digest.

Worker 05 does **not** reinterpret `artifact_stage` as promotion authorization. `promotion_candidate`, `merge_candidate`, and `release_candidate` remain workflow intent only.

## Receipt bindings

The receipt self-hash binds:
- `candidate_artifact_manifest_sha256`;
- `experiment_manifest_sha256`;
- preregistration anchor identity/evidence;
- inherited P1 `evaluation_policy_sha256`;
- exact `evaluation_code_sha256`, verified against the P1 gate file actually executed;
- frozen `harness_manifest_sha256`;
- `provenance_receipt_sha256`;
- `contamination_scan_receipt_sha256`;
- complete `red_team_evidence_root_sha256`;
- base and candidate raw-output/run-trace SHA-256 values;
- required target/protected domain metric summaries and uncertainty/significance diagnostics;
- evaluation-efficiency scope + population identity;
- efficiency metric summary;
- runtime-attempt authority boundary;
- final `INVALID | REJECTED | PROMOTION_ELIGIBLE` status;
- hash-derived invalid/failure reason codes and sealed reason-set digests;
- final receipt SHA-256.

`PROMOTION_ELIGIBLE` remains **candidate-level evaluation truth only**. It is not final release authorization and it is not arbitrary runtime-attempt correctness.

## Evaluation-efficiency population/scope identity

P2.1 makes Worker-05 efficiency evidence population explicit and distinct from Worker-06 operational/runtime economics.

Every receipt carries:
- `efficiency_scope.hash_profile = AQLEVON_CANONICAL_JSON_SHA256_V1`;
- `efficiency_scope_kind = AQLEVON_EVALUATION_HARNESS_EFFICIENCY_SCOPE_V1`;
- `population_kind = AQLEVON_FROZEN_EVALUATION_ITEM_POPULATION_V1`;
- experiment + harness identities;
- base/candidate raw-output SHA-256 values;
- base/candidate run-trace SHA-256 values;
- per-required-domain item counts;
- deterministic `population_root_sha256`;
- `metric_evidence_kind = AQLEVON_EVALUATION_REPORT_AGGREGATE_EFFICIENCY_V1`;
- `runtime_evidence_consumed = false`;
- `runtime_attempt_set_sha256 = null`;
- explicit boundary `FROZEN_EVALUATION_HARNESS_ONLY_NOT_OPERATIONAL_RUNTIME_ATTEMPTS`.

This prevents equal metric names from implying equal evidence populations. If a future Manager-approved Worker-05 extension consumes Worker-06 runtime receipts, it must bind that exact runtime receipt/root; this implementation does not claim such consumption.

## Runtime-attempt authority boundary

Every receipt explicitly carries:
- `authority_kind = AQLEVON_CANDIDATE_LEVEL_EVAL_NOT_ATTEMPT_AUTHORITY_V1`;
- `authoritative_for_arbitrary_runtime_attempts = false`;
- `attempt_set_root_sha256 = null`;
- per-attempt truth requirement pointing to a Manager-approved per-attempt objective verifier or a future Manager-approved exact-attempt-set extension.

Therefore Worker 06 may accept a valid P2.1 receipt as candidate-level truth metadata, but may not count arbitrary attempts as verified successes from `PROMOTION_ELIGIBLE` alone.

## Preregistration chronology interface

A self-hashed experiment manifest is tamper-evident but does not prove *when* it existed. Worker 05 keeps two separate P2.1 self-hashed objects:

1. `AQLEVON_PREREGISTRATION_ANCHOR_REQUEST_V1`
   - binds candidate artifact, experiment manifest, policy and requested anchor kind;
   - carries the canonical P2.1 hash profile;
   - is not chronology proof by itself.

2. `AQLEVON_PREREGISTRATION_ANCHOR_VERIFICATION_V1`
   - carries the canonical P2.1 hash profile;
   - allowed anchor kind: `git_commit | immutable_object | append_only_ledger`;
   - binds the exact anchor request;
   - requires immutable external reference;
   - requires external evidence SHA-256;
   - requires Manager authority identity;
   - requires separately stored Manager-attestation SHA-256;
   - requires RFC3339 UTC anchor/verification timestamps with valid ordering;
   - is self-hashed for tamper evidence.

The helper does not confer Manager authority. Manager must independently resolve the immutable reference and verify evidence/attestation. Self-hash, caller boolean, or caller-controlled timestamp alone remains non-authoritative.

No production preregistration anchor is fabricated because no real AQLEVON promotion-candidate evaluation exists yet.

## Decision-integrity hardening retained

Receipt construction freshly reruns P1 `evaluate_release()` and rejects a supplied `gate_result` unless it exactly matches fresh P1 recomputation. This prevents stale/fabricated downstream decisions from being wrapped in a valid P2.1 receipt.

It also rejects:
- wrong evaluation-code identity;
- experiment/policy mismatch;
- base/candidate harness mismatch;
- provenance mismatch;
- contamination receipt mismatch;
- incomplete Red-Team class coverage/evidence;
- malformed domain/statistical diagnostics;
- malformed efficiency evidence;
- unsupported final status;
- protected/raw plaintext keys.

## Reason-code privacy

Detailed P1 failure text remains sealed. Cross-lane receipts export stable hash-derived reason codes plus SHA-256 roots of complete reason sets, not private diagnostic prose.

## CLI

The existing commands remain:

```text
python evaluation_decision_receipt_v1.py anchor-request ...
python evaluation_decision_receipt_v1.py validate-anchor ...
python evaluation_decision_receipt_v1.py build-receipt ...
python evaluation_decision_receipt_v1.py validate-receipt ...
```

Generated P2.1 anchor and evaluation receipt objects now carry the frozen hash profile automatically.

## Consumer law

### Worker 04
Consume the P2.1 receipt identity/status under the Manager phase split. Do not recreate evaluation truth from legacy booleans or artifact-stage labels.

### Worker 06
A valid candidate-level P2.1 Evaluation Decision Receipt may be consumed as candidate truth metadata. It cannot blanket-verify runtime attempts. P2.1 attempt-level verified-success requires Manager-approved per-attempt objective-verifier receipts until a future exact-attempt-set extension is approved.

## Tests

Final local suite after P2.1 repair:
- accepted P1 suite: **23/23 PASS**;
- Worker-05 P2/P2.1 suite: **45/45 PASS**;
- combined: **68/68 PASS**;
- `py_compile`: PASS;
- policy JSON validation: PASS.

Independent cross-language verification was also run against a generated P2.1 Evaluation Decision Receipt using a Node verifier that mirrors the accepted Worker-06 `verifyP2SelfDigest` profile. Result: **PASS** — Python receipt SHA `ff823ca12dd01365c0b7ee64168357662c56cc4aae20966ba6b3c678a0eee151` exactly matched the Node-computed digest and contained no direct float. This is fixture evidence only, not a production receipt.

New P2.1 coverage includes:
- exact cross-language canonical JSON/hash vector shared with accepted Worker 06;
- NFKC + newline normalization;
- non-ASCII authoritative key rejection;
- direct float rejection;
- decimal canonicalization / negative-zero normalization;
- anchor request + verification hash-profile enforcement;
- Candidate Artifact Manifest hash-profile/self-digest enforcement;
- Evaluation Decision Receipt hash-profile/self-digest enforcement;
- exact digest-field exclusion rule;
- explicit evaluation-efficiency population/scope root;
- explicit separation from Worker-06 runtime population/scope;
- no direct floats in the authoritative receipt payload;
- candidate-level receipt non-authority for arbitrary runtime attempts;
- fail-closed runtime-authority laundering attempt;
- population-root tamper detection even after outer receipt rehash.

P1/P2 regressions for chronology, stale gate-result laundering, red-team completeness, provenance/scan/harness mismatch, no protected plaintext, and CLI end-to-end validation remain green.

## Truth boundary

This P2.1 repair does not:
- create or improve model weights;
- prove capability gain;
- authorize release;
- authorize arbitrary runtime-attempt correctness;
- create a production preregistration anchor;
- change Manager-frozen canonical architecture;
- modify another worker branch;
- merge any PR to `main`.