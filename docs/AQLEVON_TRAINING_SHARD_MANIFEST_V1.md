# AQLEVON Training Shard Manifest V1 — Worker 02

**Task:** `P2-A02-TRAINING-SHARD-MANIFEST`  
**Canonical kind:** `AQLEVON_TRAINING_SHARD_MANIFEST_V1`  
**Authority:** implements `/AQLEVON/Coordination/AQLEVON_P2_INTEGRATION_CONTRACTS_V1.md`; this document does not redefine the Manager-frozen contract.

## Purpose

P1 established fail-closed instance admission. P2 freezes the exact admitted training shard and the evidence that produced it into one deterministic identity that downstream training/evaluation may reference without inventing a second shard truth.

The manifest exports hashes, counts, immutable source revisions, and receipt identities only. It does not export Worker-05 private release-evaluation prompts/answers. Worker 05 can consume identity/evidence without receiving shard plaintext.

## Inputs

The producer consumes:
- P1 `ADMIT`, `QUARANTINE`, and `DENY` JSONL outputs;
- exact admission policy JSON;
- exact trusted source-registry snapshot;
- validated protected-training contamination manifest;
- exact `training_signal_gate_v1.py` bytes;
- non-empty provenance/license evidence bundle JSON.

Current P1 admission uses the protected contamination manifest directly and emits no separate contamination-scan receipt. V1 therefore truthfully emits `protected_training_contamination_receipt_sha256: []` rather than inventing a receipt.

## Strong binding / replay rule

Hash fields are not decorative metadata. Before freezing a shard, the producer:
1. verifies supplied gate-code bytes match the gate module actually executed;
2. validates policy, registry, and protected-contamination manifest;
3. recomputes every admitted record-content hash;
4. requires immutable source revisions and the exact registry snapshot hash;
5. replays the P1 gate for **every ADMIT/QUARANTINE/DENY row** using the supplied policy/registry/protected manifest;
6. requires replayed decision, reason codes, and metrics to equal the recorded admission output exactly;
7. requires provenance/license evidence to be a non-empty object and binds only its SHA-256 into the manifest.

A manifest therefore cannot claim a different valid policy/gate while carrying stale decisions.

## Deterministic, training-safe shard projection

The output shard is **not** a byte-for-byte copy of the rich P1 admission record. Copying every admission field would unnecessarily carry verifier traces, contamination metadata, audit bodies, or arbitrary cross-lane metadata into the trainable artifact.

Each admitted row is projected to the fixed `AQLEVON_TRAINING_SHARD_ROW_V1` plaintext schema:
- `row_kind`;
- `record_id`;
- `prompt`;
- canonical `answer` (also used when P1 input used `response`);
- `record_content_sha256`;
- minimal source lineage: `id`, `revision`, `content_sha256`;
- `language_lane`;
- `synthetic`.

All other metadata is excluded from shard plaintext. Its evidence identity remains bound through the decision log, manifest hashes, provenance bundle, contamination identity, and language-audit receipts.

Rows are ordered by `(record_content_sha256, record_id)` and serialized with the same deterministic JSON primitive used by P1, one row per line with a final newline.

The manifest binds:
- `shard_file_sha256` — SHA-256 of exact shard bytes;
- `byte_size`;
- `row_count`;
- `admitted_record_content_digest_sha256` — domain-separated SHA-256 of the sorted admitted record-content hashes under `AQLEVON_SORTED_RECORD_CONTENT_SHA256_LIST_V1`.

Input ordering therefore cannot change the shard or manifest identity.

## Decision-log binding

`decision_log_sha256` is computed from a domain-separated canonical payload containing:
- exact ADMIT / QUARANTINE / DENY counts;
- sorted SHA-256 digests of every complete decision-output row.

The plaintext decision log is not embedded in the manifest. Any decision-row mutation changes this digest, and decision evidence that does not replay under the supplied gate fails closed before manifest construction.

## Contract field mapping

| Manager contract requirement | V1 field |
|---|---|
| schema / kind / id | `schema_version`, `manifest_kind`, `manifest_id` |
| admission policy | `admission_policy_id`, `admission_policy_sha256` |
| registry snapshot | `source_registry_snapshot_sha256` |
| contamination manifest | `protected_training_contamination_manifest_sha256` |
| contamination receipts actually used | `protected_training_contamination_receipt_sha256` |
| admission gate code | `admission_gate_code_sha256` |
| shard file identity | `shard_file_sha256`, `byte_size`, `row_count` |
| admitted-content root | `admitted_record_content_digest_scheme`, `admitted_record_content_digest_sha256` |
| decision log | `decision_log_scheme`, `decision_log_sha256`, `decision_counts` |
| provenance/license evidence | `provenance_license_evidence_bundle_sha256` |
| language audit receipts | `language_audit_receipt_sha256` |
| immutable source lineage | `created_from` |
| self digest | `manifest_sha256` |

`manifest_id` is deterministic and hashes **all semantic manifest fields except `manifest_id` and `manifest_sha256` themselves**, under `AQLEVON_TRAINING_SHARD_IDENTITY_V1`. This avoids a hand-maintained identity subset silently omitting a future required field. `manifest_sha256` then hashes the complete manifest excluding only its own self-digest.

Unknown top-level manifest fields are rejected so downstream lanes cannot smuggle duplicate correctness/promotion truth into this schema.

## Artifact validator

`validate_training_shard_artifact(manifest, shard_bytes)` validates both the receipt and artifact:
- manifest schema / ID / self-hash;
- exact byte size and SHA-256;
- UTF-8 JSONL parse;
- exact fixed row schema;
- source identity/hash syntax;
- each row's record-content SHA-256;
- duplicate record-content identities;
- aggregate admitted-content digest;
- canonical sort and canonical byte serialization.

This lets downstream training verify that a shard file is exactly the artifact named by the manifest rather than trusting a filename or caller assertion.

## Language-audit boundary

If P1 policy requires language audit for an admitted synthetic lane (Darija, Arabizi, or configured code-switch lanes), P2 requires a valid `language_quality_audit.receipt_sha256` before the shard can be frozen. Receipt plaintext is not exported.

## Cross-lane interface

- Worker 03 / future training consumes the resulting `manifest_sha256` as `training_shard_manifest_sha256` when training occurred and can validate exact shard bytes using the artifact validator.
- Worker 05 may inspect manifest identity/evidence hashes but must not receive this shard as release-eval data and must never send private release prompts/answers into Worker 02.
- Worker 04 and Worker 06 do not redefine shard identity.

## Private-release-eval boundary

The producer cannot infer whether the legitimate `prompt`/`answer` pair itself was secretly copied from a private release set; that remains prevented by P1 contamination controls plus the Manager-enforced Worker-02/Worker-05 separation. P2 adds a separate defense: arbitrary extra fields such as private-eval metadata, verifier debug traces, decision evidence, and audit bodies are never copied into training shard plaintext.

A dedicated regression injects `worker05_private_release_eval_prompt`, `worker05_private_release_eval_answer`, and internal verifier trace metadata into an admitted record and proves none appears in the shard or manifest.

## Assumption challenged

Weak assumption: hashing only the admitted shard is enough.

Stronger result: shard bytes alone cannot prove which admission policy, registry, contamination boundary, decision partitions, gate code, language audits, or provenance/license evidence authorized those rows. V1 binds the shard to the complete reproducible admission evidence chain and replays the gate before freezing identity.

Second weak assumption: copying the complete admission row into the trainable shard is harmless. It is not necessary and increases cross-lane leakage surface. V1 therefore freezes a minimal allowlisted training-row projection and keeps non-training evidence behind immutable hashes/receipts.

## External design references consulted

- RFC 8785, JSON Canonicalization Scheme: cryptographic hashing requires an invariant representation. AQLEVON uses its own versioned canonicalizer and **does not claim RFC 8785/JCS compliance** because P1 intentionally normalizes Unicode/newlines while JCS preserves parsed strings as-is.
- SLSA Provenance v1.2: current provenance guidance models artifact identity together with traceable source/material inputs. AQLEVON borrows the evidence-binding principle only; this manifest is not claimed to be a SLSA attestation.

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

Local isolated suite on exact implementation:
- P1 admission regressions: **38/38 PASS**;
- P2 manifest regressions: **30/30 PASS**;
- combined: **68/68 PASS**;
- Python compilation: PASS;
- policy JSON parse: PASS.

P2 coverage includes determinism under input reordering, record tamper, partition mismatch, admission replay mismatch, policy semantic mismatch, gate-code mismatch, source-registry binding, immutable revisions, language-audit receipts, protected-manifest tamper, provenance binding/type hardening, decision-log binding, self-hash tamper, unknown-field rejection, safe shard projection, exact artifact validation, CLI determinism, and malformed-config fail-closed behavior.

No model training, parameter update, checkpoint creation, capability gain, release decision, paid compute, or merge to `main` is performed or claimed by this artifact.