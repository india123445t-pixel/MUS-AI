# AQLEVON Worker 03 — P2 Candidate Artifact Manifest V1

**Task:** `P2-A03-CANDIDATE-ARTIFACT-MANIFEST`  
**Worker:** `03`  
**Authority:** `/AQLEVON/Coordination/AQLEVON_P2_INTEGRATION_CONTRACTS_V1.md`  
**P2 branch base:** accepted Worker 03 P1 head `1cb3083cab65379c9d7fa2c260a6a46c92f5f872`

## Purpose

Implement the generic producer/validator for `AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1` without originating evaluation, promotion, release, or runtime truth.

The manifest supports:
- `adapter`
- `full_checkpoint`
- `merge`
- `quantized_serving_artifact`

and the frozen stages:
- `probe_only`
- `reproducible_gene`
- `promotion_candidate`
- `merge_candidate`
- `release_candidate`

The stage is an artifact lifecycle label only. It is **not** an evaluation verdict. Worker 05 / Manager receipts remain authoritative for evaluation and promotion truth.

## Deterministic identity

`manifest_sha256` is SHA-256 over canonical JSON of all manifest content except the two circular self-identity fields `manifest_id` and `manifest_sha256`.

`manifest_id` is then exactly:

`aqlevon-candidate-artifact-v1:sha256:<manifest_sha256>`

Canonical JSON uses UTF-8, sorted keys, compact separators, and rejects NaN.

## Artifact byte identity

The producer walks the artifact root and emits a lexicographically ordered tree of:
- relative POSIX path
- byte size
- SHA-256

Symlinks and special files fail closed. Paths containing absolute/traversal/noncanonical syntax fail closed. `artifact_file_tree_sha256` is a canonical hash of the complete ordered file list.

The validator can optionally re-read the artifact root and requires exact byte-tree equality.

## Authority / truth separation

The V1 producer rejects candidate fields that would duplicate downstream truth, including:
- `verified`
- `quality_pass`
- `promotion_eligible`
- `release_approved`
- `evaluation_status`
- `evaluation_decision`
- `correctness`

Candidate Artifact Manifest owns identity/lineage, not quality or correctness.

## Applicability rules

### Adapter
Requires adapter-state SHA-256, no checkpoint-state identity, and no merge recipe. Training Shard Manifest + training-run receipt bindings are **atomic**: both must be present when training occurred, or both may be `null` for an imported/non-training artifact.

### Full checkpoint
Requires checkpoint-state identity and cannot claim an adapter-state identity. Training Shard Manifest + training-run receipt bindings follow the same atomic applicability rule.

### Merge
Requires:
- merge-recipe SHA-256;
- at least two unique parent Candidate Artifact Manifest SHA-256 values;
- exactly one resulting state identity (adapter or checkpoint);
- no direct training-shard/run fields, because those remain reachable through parent lineage.

### Quantized serving artifact
Requires:
- exactly one parent Candidate Artifact Manifest SHA-256;
- checkpoint-state identity;
- no direct training/merge receipt retyping.

This schema does not decide whether any merge or quantized candidate is promotion-safe. Worker 04/05 consume the identities under their own frozen gates.

## G1 integration

`from-g1` consumes a physical G1 JSON report plus adapter bytes and external identity bindings.

It accepts only canonical BF16 status:
`PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL`.

It verifies:
- G1 mode is BF16 and canonical-preferred;
- saved/reloaded adapter state hashes match;
- `reload_hash_match=true`;
- G1 artifact file SHA-256 map exactly equals current adapter bytes;
- required external bindings are valid SHA-256 values.

It then **forces**:
- `artifact_type=adapter`
- `artifact_stage=probe_only`
- `topology_class=CUSTOM_EXPERIMENTAL` for the q/v-only smoke layout.

It computes:
- training-run receipt identity = SHA-256 of the immutable G1 report file;
- environment/toolchain identity = canonical SHA-256 of the G1 `environment` object.

It refuses the experimental QLoRA success status as canonical G1 integration. QLoRA can still be represented through the generic producer as an experimental artifact, but it cannot be silently relabeled as canonical G1.

A Training Shard Manifest SHA-256 is mandatory even for G1 integration. Worker 03 does not mint that identity; it must come from the Worker 02 / Manager-controlled training-data authority.

## Deliberately not done

- no GPU run;
- no paid compute;
- no model-weight mutation;
- no new AQLEVON checkpoint;
- no quality or promotion claim;
- no evaluation thresholds or receipts invented;
- no runtime/economics truth invented;
- no modification to accepted P1 PR #15;
- no merge to `main`.