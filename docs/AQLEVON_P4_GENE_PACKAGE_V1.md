# AQLEVON Gene Package V1 — Worker 04 P4

**Task:** `P4-A04-GENE-PACKAGING-INTEGRATION-READY`  
**Scope:** packaging/identity/runtime-readiness only. This document does not claim Gene #1 exists or has been promoted.

## Authority boundary

A Gene Package is deliberately impossible to seal from a Candidate Artifact alone. `seal_gene_package()` requires all of:

1. a valid P2.1 Candidate Artifact Manifest with `artifact_type=adapter` and a real training shard/run binding;
2. a valid Worker-05 Evaluation Decision Receipt bound to that candidate with `final_status=PROMOTION_ELIGIBLE`;
3. a SHA-256 identity for the Manager acceptance record;
4. at least one self-hashed Worker-06 Runtime Attempt Receipt V1 bound to the same candidate;
5. a declared target capability.

Therefore Worker 04 cannot use packaging to manufacture promotion authority. Until Worker 05 evidence and Manager acceptance exist, no real Gene #1 package may be emitted.

## Exact Gene Package V1 bindings

The package binds:
- **base identity:** repo, exact revision, base manifest, tokenizer and config SHA-256;
- **adapter identity:** Candidate Artifact Manifest SHA-256, adapter-state SHA-256 and artifact-file-tree SHA-256;
- **target capability:** stable capability id + version, with optional ASCII metadata;
- **promotion:** Worker-05 Evaluation Decision Receipt SHA-256 + `PROMOTION_ELIGIBLE` + Manager acceptance-record SHA-256;
- **training:** Training Shard Manifest SHA-256 + Training Run Receipt SHA-256;
- **compute:** sorted unique Runtime Attempt Receipt SHA-256 list + deterministic set SHA-256;
- **compatibility:** topology class, parameter-layout SHA-256 and quantization compatibility state/evidence;
- **rollback:** immutable-base guarantee, adapter-detach rollback action and optional previous Gene Package identity;
- **future integration:** explicit hook eligibility while all multi-gene methods remain unauthorized/dormant.

The package has both a semantic `package_id` and a self-digest `package_sha256` under `AQLEVON_CANONICAL_JSON_SHA256_V1`.

## Loader and byte checks

`load_gene_package()` parses a package from disk and fails closed on ID/self-digest/schema invariants.

`verify_candidate_artifact_tree()` validates exact adapter bytes against Candidate Artifact Manifest file entries and rejects:
- missing files;
- extra unbound files;
- path traversal;
- symlinks/special files;
- size mismatches;
- SHA-256 mismatches.

The package itself does not duplicate adapter bytes; it preserves and binds the authoritative Candidate Artifact identity.

## Base/revision/layout fail-closed activation

`prepare_single_gene_activation()` compares the package against observed runtime identity across:
- model repo;
- exact model revision;
- base-manifest SHA-256;
- tokenizer SHA-256;
- config SHA-256;
- parameter-layout SHA-256;
- topology class.

Any mismatch rejects activation. A successful request always states:
- `activation_mode=SINGLE_ADAPTER_ATTACH_REVERSIBLE`;
- `base_mutation_allowed=false`;
- `multi_gene_routing_authorized=false`;
- rollback is `DETACH_ADAPTER_RESTORE_IMMUTABLE_BASE`.

`SingleGeneRouter` is intentionally incapable of selecting between multiple genes. It routes only to its one bound package and emits a self-hashed route receipt. This provides a smoke path for future runtime integration without creating an implicit multi-gene router.

## Quantization compatibility

Package V1 supports three states:
- `NOT_TESTED`: no quantized/evaluation identities may be claimed;
- `PASS`: both quantized Candidate Artifact Manifest and evaluation receipt SHA-256 are required;
- `FAIL`: the same evidence identities are required so a failed attempt remains auditable.

No `PASS` is produced by Worker 04 itself.

## Gene #2 compatibility hook

`prepare_gene_pair_integration_hook()` accepts >=2 already-valid Gene Packages and checks exact equality of:
- base identity;
- parameter layout;
- topology class.

It canonicalizes package order and emits identity-only compatibility evidence. Its `real_integration_authorized` value is always `false`; TIES/DARE/DELLA/CtM/hard-router/MOPD stay dormant until >=2 Manager-accepted genes and a later Manager execution assignment.

## Current P4 truth

At implementation time, G1 physical truth has passed, but Gene #1 has not yet received Worker-05 27B reality evidence plus Manager promotion acceptance. Therefore this branch contains **no real Gene #1 package** and no real adapter activation. Tests use synthetic identities and temporary dummy adapter bytes only.

## Validation expectation

The P4 test suite must cover:
- Worker-05 rejection cannot be packaged;
- Manager acceptance identity is mandatory;
- compute receipt candidate binding and tamper detection;
- training bindings mandatory;
- quantization evidence rules;
- package tamper detection;
- wrong base revision/base manifest/layout rejected;
- exact adapter byte verification + extra-file rejection;
- reversible single-gene activation and single-gene-only routing;
- one gene cannot open multi-gene tournament;
- compatible Gene #1/#2 hooks stay dormant;
- incompatible layout/revision is rejected;
- repository P2.1 Candidate/Evaluation interop when the full helper module is present.
