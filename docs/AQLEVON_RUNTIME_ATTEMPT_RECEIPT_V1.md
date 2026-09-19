# AQLEVON Runtime Attempt Receipt V1 — P2 Worker 06

Status: P2 implementation contract consumer/producer. Manager review required.

## Authority boundary
Runtime owns transport outcome, timing/token accounting, configured cost/energy estimates, and immutable attempt identity. Runtime does **not** own correctness.

A runtime attempt can contribute to `verified_successes` only through an explicit immutable join to either:
1. an `AQLEVON_EVALUATION_DECISION_RECEIPT_V1` supplied by the Worker-05/Manager evaluation authority, with `PROMOTION_ELIGIBLE` status and the same Candidate Artifact Manifest identity; or
2. a Manager-approved per-attempt objective-verifier receipt identity, bound to the exact Runtime Attempt Receipt and to a Manager approval receipt identity.

A local/caller `verified: true` field is never authoritative.

## Runtime Attempt Receipt fields
`AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1` contains:
- `schema_version` / `manifest_kind`;
- `attempt_id` + `task_id`;
- `candidate_artifact_manifest_sha256`;
- `request_harness_identity.request_sha256` and `harness_manifest_sha256` only — no request plaintext, API keys, authorization headers, or model URL secrets;
- `transport_outcome.status = success | failure` plus a bounded failure code for failures;
- `runtime_metrics` using `aqlevon-runtime-metrics-v1`;
- `runtime_metric_provenance`, distinguishing measured wall time from configured allocation/energy/cost estimates;
- optional `raw_result_sha256` when a raw provider response/result exists;
- `receipt_sha256`, computed from canonical sorted-key JSON of every preceding receipt field.

Unknown top-level fields make validation fail closed. Modifying metrics, identity, provenance, outcome, or any other receipt field without recomputing the self-digest is detected. The authoritative aggregator also rejects malformed/tampered attempt receipts rather than silently dropping them.

## Commons worker integration
Receipt production is enabled only when both are configured as valid SHA-256 identities:
- `AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256`
- `AQLEVON_RUNTIME_HARNESS_MANIFEST_SHA256`

Neither configured: inference remains compatible but receipt capability is advertised as `unbound`, so the attempt cannot enter authoritative verified-efficiency truth.

Only one/malformed identity: worker exits configuration-failed before serving jobs. This prevents falsely issuing bound receipts.

With both valid identities, success and failure results include `runtime_attempt_receipt`. Failed attempts remain transport failures and retain runtime metrics/cost estimates.

## Verified-efficiency aggregation
`summarizeVerifiedEfficiency()` now accepts Runtime Attempt Receipts. It:
- validates every attempt receipt and fails the authoritative summary closed if any receipt is invalid;
- sums GPU-seconds/energy/cost across **all** valid attempts, including failed/unverified attempts;
- counts a successful attempt in the denominator only after a valid receipt-identity join to accepted evaluation/objective-verifier truth;
- never treats transport success as correctness;
- never treats a caller boolean as correctness.

The evaluation receipt remains upstream truth. Runtime checks only the exact identity fields needed for the join (`receipt_sha256`, candidate manifest identity, final status); it does not reproduce Worker-05 thresholds, metric computation, contamination decisions, or release policy.

## Non-goals / truth limits
- This does not declare any AQLEVON model correct, improved, promotion-eligible, or released.
- This does not create a Candidate Artifact Manifest or Evaluation Decision Receipt; those are owned by Workers 03/05 under the Manager P2 contract.
- This does not apply the pending P1 Commons Supabase failure-accounting migration to Production.
- Cost/energy remain estimates unless a future schema explicitly supplies measured hardware telemetry.
