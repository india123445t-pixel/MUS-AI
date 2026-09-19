# AQLEVON Training Shard Manifest V1 — Worker 02

**Task:** `P2-A02-TRAINING-SHARD-MANIFEST`  
**Canonical kind:** `AQLEVON_TRAINING_SHARD_MANIFEST_V1`  
**Authority:** implements `/AQLEVON/Coordination/AQLEVON_P2_INTEGRATION_CONTRACTS_V1.md`; this document does not redefine the Manager-frozen contract.

## Purpose

P1 established fail-closed instance admission. P2 freezes the exact admitted training shard and the evidence that produced it into one deterministic identity that downstream training/evaluation may reference without inventing a second shard truth.

The manifest contains hashes, counts, immutable source revisions, and receipt identities only. It does not export Worker-05 private release-evaluation prompts/answers, and Worker 05 does not need the shard plaintext to verify its identity.

## Inputs

The producer consumes:
- P1 `ADMIT`, `QUARANTINE`, and `DENY` JSONL outputs;
- the exact admission policy JSON;
- the exact trusted source-registry snapshot;
- the validated protected-training contamination manifest;
- the exact `training_signal_gate_v1.py` bytes;
- a provenance/license evidence bundle JSON.

Current P1 admission uses the protected contamination manifest directly and emits no separate contamination-scan receipt, so V1 truthfully emits an empty `receipt_sha256` list rather than inventing one.

## Strong binding / replay rule

Hash fields are not accepted as decorative metadata. Before freezing a shard, the producer:
1. verifies the supplied gate-code bytes match the gate module actually executed;
2. validates policy, registry, and protected-contamination manifest;
3. recomputes every admitted row content hash;
4. requires immutable source revisions and the exact registry snapshot hash;
5. replays the P1 gate for **every ADMIT/QUARANTINE/DENY row** using the supplied policy/registry/protected manifest;
6. requires the replayed decision, reason codes, and metrics to equal the recorded admission output exactly.

Therefore a manifest cannot claim binding to a different valid policy or gate implementation while carrying stale decisions.

## Deterministic shard

Admitted rows are ordered by `(record_content_sha256, record_id)` and serialized with the same canonical JSON primitive used by P1, one row per line with a final newline.

The manifest binds:
- `shard_file_sha256` — SHA-256 of those exact shard bytes;
- `byte_size`;
- `row_count`;
- `admitted_record_content_digest_sha256` — domain-separated SHA-256 of the sorted admitted record-content hashes under `AQLEVON_SORTED_RECORD_CONTENT_SHA256_LIST_V1`.

Input ordering therefore cannot change the shard or manifest identity.

## Decision-log binding

`decision_log_sha256` is computed from a domain-separated canonical payload containing:
- exact ADMIT / QUARANTINE / DENY counts;
- sorted SHA-256 digests of every complete decision-output row.

The plaintext decision log is not embedded in the manifest. Any change to a decision row changes the digest, and any change to decision evidence that does not replay under the supplied gate fails closed before manifest construction.

## Contract field mapping

| Manager contract requirement | V1 field |
|---|---|
| schema / kind / id | `schema_version`, `manifest_kind`, `manifest_id` |
| admission policy | `admission_policy_id`, `admission_policy_sha256` |
| registry snapshot | `source_registry_snapshot_sha256` |
| contamination manifest/receipts | `protected_training_contamination_evidence` |
| admission gate code | `admission_gate_code_sha256` |
| shard file identity | `shard_file_sha256`, `byte_size`, `row_count` |
| admitted-content root | `admitted_record_content_digest_scheme`, `admitted_record_content_digest_sha256` |
| decision log | `decision_log_scheme`, `decision_log_sha256`, `decision_counts` |
| provenance/license evidence | `provenance_license_evidence_bundle_sha256` |
| language audit receipts | `language_audit_receipt_sha256` |
| immutable source lineage | `created_from` |
| self digest | `manifest_sha256` |

`manifest_id` is itself deterministic: a full SHA-256 identity over the shard and all upstream evidence bindings. `manifest_sha256` independently hashes the complete manifest excluding only its own self-digest field.

Unknown top-level fields are rejected so downstream lanes cannot smuggle duplicate correctness/promotion truth into the training-shard schema.

## Language audit boundary

If P1 policy requires language audit for an admitted synthetic lane (Darija, Arabizi, or configured code-switch lanes), P2 requires a valid `language_quality_audit.receipt_sha256` before the shard can be frozen. The receipt plaintext is not exported.

## Cross-lane interface

- Worker 03 / future training consumes only the resulting `manifest_sha256` as `training_shard_manifest_sha256` when training occurred.
- Worker 05 may inspect manifest identity/evidence hashes but must not receive this shard as release-eval data and must never send private release prompts/answers into Worker 02.
- Worker 04 and Worker 06 do not redefine shard identity.

## Assumption challenged

Weak assumption: hashing only the admitted shard is enough.

Stronger result: shard bytes alone cannot prove which admission policy, registry, contamination boundary, decision partitions, gate code, language audits, or provenance/license evidence authorized those rows. V1 therefore binds the shard to the entire reproducible admission evidence chain and replays the gate before freezing the identity.

## CLI

```text
python training_shard_manifest_v1.py build \
  --admitted admitted.jsonl \
  --quarantine quarantine.jsonl \
  --denied denied.jsonl \
  --policy training_signal_policy_v1.json \
  --source-registry source_registry_snapshot.json \
  --protected-contamination-manifest protected_manifest.json \
  --admission-gate-code training_signal_gate_v1.py \
  --provenance-license-evidence provenance_license_bundle.json \
  --output-shard training_shard.jsonl \
  --output-manifest training_shard_manifest.json
```

Construction is fail-closed and writes outputs only after all checks pass.

## Validation evidence

Local isolated suite on the exact implementation:
- P1 admission regressions: **38/38 PASS**;
- P2 manifest regressions: **26/26 PASS**;
- combined: **64/64 PASS**;
- Python compilation: PASS;
- policy JSON parse: PASS.

P2 tests cover determinism under input reordering, content tamper, partition mismatch, admission replay mismatch, policy semantic mismatch, gate-code mismatch, source-registry binding, immutable revisions, language-audit receipts, protected-manifest tamper, provenance binding, decision-log binding, self-hash tamper, unknown-field rejection, CLI determinism, and malformed-config fail-closed behavior.

No model training, parameter update, checkpoint creation, capability gain, release decision, paid compute, or merge to `main` is performed or claimed by this artifact.
