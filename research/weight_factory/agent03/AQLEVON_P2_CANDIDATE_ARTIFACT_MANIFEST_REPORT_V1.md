# AQLEVON Worker 03 — P2/P2.1 Candidate Artifact Manifest V1

**Original task:** `P2-A03-CANDIDATE-ARTIFACT-MANIFEST`  
**P2.1 repair task:** `P2.1-R03-CANDIDATE-HASH-INTEROP`  
**Worker:** `03`  
**Authority:** `/AQLEVON/Coordination/AQLEVON_P2_INTEGRATION_CONTRACTS_V1.md` including the Manager-frozen P2.1 amendment  
**Branch/PR:** `agent/03-p2-candidate-artifact-manifest-v1` / PR #18  

## Purpose

Implement the generic producer/validator for `AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1` without originating evaluation, promotion, release, or runtime truth, and repair its self-hash semantics for cross-lane P2.1 interoperability.

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

`artifact_stage` is workflow/intent metadata only. `probe_only` is restrictive, but later-looking stage labels do **not** prove quality, promotion eligibility, or release authorization. Those facts remain Worker-05/Manager authority.

## P2.1 canonical hash profile

Every Candidate Artifact Manifest now carries:

`hash_profile: AQLEVON_CANONICAL_JSON_SHA256_V1`

Missing or unknown profiles fail closed; the validator never guesses a fallback canonicalizer.

For authoritative P2 self-hash payloads the implementation now applies the Manager profile exactly:
- UTF-8 compact JSON;
- authoritative object keys must be non-empty ASCII strings and are ordered lexicographically by ASCII byte value;
- arrays preserve input order;
- string values are Unicode NFKC-normalized;
- CRLF and bare CR normalize to LF before serialization;
- booleans/null use JSON literals;
- integers serialize as ordinary base-10 JSON integers;
- direct non-integral numeric objects are rejected, including float, NaN, Infinity, Decimal/Fraction-class numeric objects;
- lanes needing a fractional identity value must first represent it as a canonical decimal string: no exponent, no leading `+`, no unnecessary leading zero, no trailing fractional zero, with negative zero normalized to `0`;
- SHA-256 evidence fields remain canonical lowercase 64-hex.

Candidate Artifact Manifest V1 currently has no authoritative fractional numeric field. The implementation nevertheless exposes and tests `canonical_decimal_string()` so a future field cannot invent an incompatible formatter silently.

### Frozen interoperability vector

The regression suite freezes this Manager-profile vector:

Input semantic variants normalize to canonical UTF-8 JSON bytes equivalent to:

`{"a":[1,true,null,{"line":"x\ny"}],"hash_profile":"AQLEVON_CANONICAL_JSON_SHA256_V1","z":"A\nCafé"}`

Expected SHA-256:

`57a289efd889602d76395057bae6f06602308c273fe8b27dbefe78ec65b4ebce`

The test proves full-width `Ａ` -> `A`, decomposed `Cafe + combining acute` -> `Café`, CRLF/CR -> LF, and input object-key order does not alter the canonical bytes.

## Exact identity / self-digest rule

P2.1 removes the old P2 ambiguity where Candidate Manifest used one digest for both `manifest_id` and `manifest_sha256`.

The repaired V1 follows the same authority pattern as accepted Worker-02 P2.1:

1. `manifest_id` is derived from a domain-separated identity payload under `AQLEVON_CANDIDATE_ARTIFACT_IDENTITY_V1`. That payload binds every semantic manifest field except `manifest_id` and `manifest_sha256`.
2. `manifest_sha256` is then computed over the complete canonical manifest with **only `manifest_sha256` omitted**. Therefore it includes `manifest_id` and `hash_profile`.

`manifest_id` remains formatted as:

`aqlevon-candidate-artifact-v1:sha256:<identity_sha256>`

The validator independently recomputes both identities. Metadata tamper breaks both as appropriate. A regression explicitly proves that removing `manifest_id` from the self-hash payload changes the digest, enforcing the exact exclusion rule.

## Artifact byte identity

The producer walks the artifact root and emits a lexicographically ordered tree of:
- relative POSIX path;
- byte size;
- SHA-256.

Symlinks and special files fail closed. Absolute/traversal/noncanonical paths fail closed. `artifact_file_tree_sha256` binds the ordered file list, and the validator can re-read the artifact root and require exact byte-tree equality. Manifest output is forbidden inside the artifact root to avoid self-reference.

## Authority / truth separation

The V1 producer rejects fields that would duplicate downstream truth, including:
- `verified`
- `quality_pass`
- `promotion_eligible`
- `release_approved`
- `evaluation_status`
- `evaluation_decision`
- `correctness`

Candidate Artifact Manifest owns artifact identity/lineage only. A `release_candidate` stage label remains non-authoritative without the required Worker-05 Evaluation Decision Receipt and final Manager decision.

## Applicability rules

### Adapter
Requires adapter-state SHA-256, no checkpoint-state identity, and no merge recipe. Training Shard Manifest + training-run receipt bindings are atomic: both present when training occurred, or both `null` for imported/non-training artifacts.

### Full checkpoint
Requires checkpoint-state identity and cannot claim adapter-state or merge-recipe identity. Training bindings use the same atomic rule.

### Merge
Requires merge-recipe SHA-256, at least two unique parent Candidate Artifact Manifest SHA-256 values, exactly one resulting state identity, and no retyping of parent training receipts.

### Quantized serving artifact
Requires exactly one parent Candidate Artifact Manifest identity plus checkpoint-state identity and does not duplicate parent training/merge receipts.

This producer never decides whether a merge or quantized candidate is promotion-safe.

## G1 integration remains probe_only

`from-g1` accepts only canonical BF16 status:
`PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL`.

It verifies canonical BF16 policy state, saved/reloaded adapter state identity, reload hash equality, exact artifact-file hashes, and external SHA-256 bindings. It then forces:
- `artifact_type=adapter`;
- `artifact_stage=probe_only`;
- `topology_class=CUSTOM_EXPERIMENTAL` for the q/v-only smoke layout.

Experimental QLoRA status is rejected by the canonical G1 importer. An upstream Worker-02 `training_shard_manifest_sha256` remains mandatory; Worker 03 does not mint that truth.

No physical G1 report exists yet, so this path remains fixture-tested only. No trained checkpoint/adapter or model improvement is claimed.

## P2.1 regression evidence

Local exact-source checks after repair:
- `python -m py_compile candidate_artifact_manifest.py test_candidate_artifact_manifest.py` — PASS;
- `python -m json.tool candidate_artifact_manifest.schema.json` — PASS;
- `python -m unittest -v test_candidate_artifact_manifest.py` — **28/28 PASS** before final CLI rerun;
- Manager-profile interop vector bytes/hash — PASS;
- old P2 tests remain covered, including artifact tamper, type confusion, lineage, path safety, G1 probe-only, QLoRA rejection and reload-hash mismatch.

New P2.1 regressions prove:
- known `hash_profile` required; missing/unknown profile fails closed;
- NFKC/newline canonicalization;
- ASCII authoritative keys and byte-order sorting;
- array-order preservation;
- direct non-integral numeric rejection;
- canonical decimal-string vectors;
- exact self-digest exclusion of only `manifest_sha256`;
- `manifest_id` is a separate domain-separated identity digest;
- uppercase/noncanonical SHA-256 rejected;
- artifact stage remains non-authoritative metadata;
- G1 output remains `adapter + probe_only` and carries the canonical hash profile.

## Deliberately not done

- no GPU run or paid compute;
- no model-weight mutation or new AQLEVON checkpoint;
- no quality/promotion/release claim;
- no evaluation thresholds or Worker-05 truth invented;
- no runtime correctness/economics truth invented;
- no modification to accepted P1 PR #15;
- no replacement P2 PR;
- no merge to `main`.