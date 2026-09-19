# AQLEVON P2.1 Merge Receipt Integration V1

**Worker:** 04 — Merge / Interference / Architecture  
**Task:** `P2.1-A04-MERGE-RECEIPT-INTEGRATION`  
**Status:** control-plane implementation for Manager review; no model merge or weight claim.

## Purpose

This lane connects the accepted P2.1 Candidate Artifact Manifest and Evaluation Decision Receipt interfaces to Worker-04 merge mechanics without retyping upstream truth.

The authoritative DAG is preserved:

`Candidate Artifact Manifest(s) -> source Evaluation Decision Receipt(s) -> W04 pre-merge admission -> merge construction -> merged Candidate Artifact Manifest -> merged Evaluation Decision Receipt -> W04 post-evaluation promotion decision`.

A merged-candidate Evaluation Decision Receipt is deliberately **not** required by the pre-merge phase because the merged artifact does not exist yet.

## Canonical hash interoperability

Every new Worker-04 P2.1 receipt uses:

`hash_profile = AQLEVON_CANONICAL_JSON_SHA256_V1`

Self-digests follow the Manager-frozen profile: UTF-8 compact JSON, ASCII object keys sorted by byte value, array order preserved, NFKC string normalization, CRLF/CR to LF normalization, ordinary integers only, no direct non-integral numeric objects, and lowercase SHA-256.

Worker-04 regression tests reproduce both accepted interoperability vectors:

- Worker-03 vector SHA-256: `57a289efd889602d76395057bae6f06602308c273fe8b27dbefe78ec65b4ebce`.
- Worker-05/06 vector SHA-256: `1b1580a59f4ae1efdf8ed0fc7a86ffbcf1ee32d9f6d3294840afecd8a55f8b19`.

## Phase 1 — Pre-merge source admission

`pre_merge_source_admission()` requires at least two source Candidate Artifact Manifests and exactly one Evaluation Decision Receipt per source.

For every source it requires:
- shared Candidate Artifact Manifest V1 identity/profile/self-digest integrity;
- non-`probe_only` stage (stage remains workflow metadata, except this restrictive boundary);
- exact merge-policy base repo/revision;
- identical base-manifest identity;
- identical parameter-layout SHA-256;
- identical topology class;
- shared Evaluation Decision Receipt V1 identity/profile/self-digest integrity;
- exact receipt binding to the source `candidate_artifact_manifest_sha256`;
- `final_status = PROMOTION_ELIGIBLE`.

Output is a new self-hashed:

`AQLEVON_MERGE_SOURCE_ADMISSION_RECEIPT_V1`.

It states only `ADMIT_FOR_MERGE_CONSTRUCTION` and explicitly says it is not promotion authority.

## Legacy P1 truth boundary

P1 booleans such as `target_gain`, `global_regression_pass`, `pairwise_behavior_eval_pass`, `quantization_survival_pass`, `license_pass`, `provenance_pass`, and `contamination_pass` are not consulted as authority.

The API accepts optional legacy diagnostics only so callers can carry old metadata during migration. Missing P2.1 Evaluation Decision Receipt identities always fail closed even if every legacy boolean is true.

## Phase 2 — Post-evaluation merge promotion

`post_evaluation_merge_promotion()` requires:
- the exact Worker-04 source-admission receipt;
- the original source manifests/receipts and recomputes admission to prevent receipt substitution;
- merged Candidate Artifact Manifest with `artifact_type=merge`;
- exact parent-manifest list matching the admitted source order;
- exact lineage/layout/topology continuity;
- non-null `merge_recipe_sha256`;
- valid merged Evaluation Decision Receipt bound to the merged manifest and `PROMOTION_ELIGIBLE`;
- interference-report SHA-256;
- merge-roundtrip receipt SHA-256.

Output is a self-hashed:

`AQLEVON_MERGE_PROMOTION_DECISION_RECEIPT_V1`.

Its strongest non-quantized decision is:

`MERGE_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW`.

It never declares final release; `release_authority` is explicitly `MANAGER_ONLY`.

## Quantized survival path

When `request_quantized_release=true`, post-evaluation promotion additionally requires:
- a separate Candidate Artifact Manifest with `artifact_type=quantized_serving_artifact`;
- the merged candidate manifest as its sole parent;
- a separate Worker-05 Evaluation Decision Receipt bound to that quantized manifest;
- `final_status = PROMOTION_ELIGIBLE` on the quantized receipt.

Only then can Worker 04 emit:

`MERGE_AND_QUANTIZED_SURVIVAL_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW`.

This is still not Manager release approval.

## Authority boundaries

Worker 04 validates shared cross-lane identity/integrity fields and the merge-specific compatibility facts it owns. It does **not** duplicate Worker-03 artifact-production semantics or Worker-05 metric thresholds/statistics.

`artifact_stage` never proves quality. `PROMOTION_ELIGIBLE` is consumed from Worker 05 and remains subject to Manager review/independent rerun.

## Remaining limitations

- Self-hash integrity is tamper evidence, not producer authentication/signature. A future Manager-approved signing/attestation layer may strengthen cross-lane provenance.
- P2.1 control-plane tests use synthetic manifests/receipts only. No physical G1 gene, merged checkpoint, quantized artifact, or empirical capability gain exists from this task.
- The P2.1 branch is intentionally stacked on accepted Worker-04 P1 head and retains the inherited PR #12 dependency through that ancestry.
