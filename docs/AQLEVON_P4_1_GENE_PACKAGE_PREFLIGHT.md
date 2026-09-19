# AQLEVON P4.1 — Gene Package Zero-Wait Preflight

**Worker:** 04  
**Task:** `P4.1-A04-GENE-PACKAGE-PREFLIGHT`  
**Scope:** synthetic/control-plane preflight only. No real Gene #1 package is created here.

## Authoritative interfaces rechecked

This preflight is bound to the already-accepted contracts rather than inventing parallel truth:

- Candidate Artifact Manifest V1 from accepted Worker-03/P2.1 lineage.
- Evaluation Decision Receipt V1 from accepted Worker-05/P2.1 lineage.
- Runtime Attempt Receipt V1 identity contract from accepted Worker-06/P2.1 lineage.
- Worker-04 Gene Package V1 from PR #31.

Worker 04 does not redefine evaluation correctness, training truth, or runtime economics. It only verifies that the identities it consumes cannot be silently swapped.

## P4.1 hardening added

`seal_gene_package()` now requires the caller to provide the exact:
- `training_shard_manifest_sha256`;
- `training_run_receipt_sha256`.

Both must equal the corresponding identities already sealed into the Candidate Artifact Manifest. This is an identity cross-check only; Worker 04 does not define the upstream training receipt schema.

This closes a preflight ambiguity: previously the package preserved Candidate training hashes but could not detect that a caller was presenting a different training receipt identity at packaging time.

## Exact synthetic cases

The P4.1 preflight suite uses the real P2.1 Candidate/Evaluation helper contract and exercises:

1. valid promoted adapter identity;
2. wrong runtime base revision;
3. wrong runtime parameter layout;
4. stale but structurally valid Evaluation Decision Receipt from a different candidate;
5. mismatched training-run receipt identity;
6. mismatched training-shard manifest identity;
7. Runtime Attempt Receipt bound to a different candidate;
8. invalid rollback metadata, even after package ID/self-digest are recomputed;
9. invalid quantization declaration;
10. single-gene route with no multi-gene authority;
11. one Gene Package cannot open the future integration tournament.

## Packaging can corrupt truth — false-success attacks

Packaging is not “just bookkeeping.” At least these false-success modes are dangerous:

- **Quality receipt swap:** attach an old/promoted evaluation receipt to a new candidate and falsely inherit quality. Closed by exact evaluation-to-candidate binding.
- **Training lineage swap:** present a different training shard/run receipt while packaging a candidate. Closed by the new explicit training identity cross-checks.
- **Compute attribution swap:** attach runtime/cost evidence from another candidate and falsely attribute execution/cost. Closed by Runtime Attempt Receipt candidate binding.
- **Wrong-base activation:** load a valid adapter on a different base revision/layout and mistake successful loading for valid behavior. Closed before activation by exact base/revision/base-manifest/tokenizer/config/layout/topology checks.
- **Unsafe rollback metadata:** make a package appear reversible while allowing destructive base mutation. Closed by semantic rollback validation, not only package hashing.

## Ready-to-package-real-gene checklist

A future real Gene #1 package is ready only when every item below is available and identity-consistent:

1. Worker-03 Candidate Artifact Manifest V1 is valid and `artifact_type=adapter`.
2. Candidate is not `probe_only`.
3. Candidate binds non-null Training Shard Manifest SHA-256.
4. Candidate binds non-null Training Run Receipt SHA-256.
5. The exact training shard identity supplied to packaging equals the Candidate binding.
6. The exact training run receipt identity supplied to packaging equals the Candidate binding.
7. Worker-05 Evaluation Decision Receipt validates and is bound to the exact Candidate.
8. Worker-05 final status is `PROMOTION_ELIGIBLE`.
9. Manager acceptance-record SHA-256 exists for that exact gene/candidate decision.
10. At least one valid Worker-06 Runtime Attempt Receipt V1 is supplied and bound to the exact Candidate.
11. Base repo, exact revision, base-manifest, tokenizer, config, topology and parameter layout are present.
12. Adapter artifact tree/bytes can be checked against Candidate file hashes before runtime activation.
13. Quantization status is either `NOT_TESTED` with no fake evidence, or `PASS/FAIL` with explicit quantized candidate + evaluation identities.
14. Rollback states immutable base + adapter detach and forbids destructive base mutation.
15. Single-gene activation passes exact runtime base/layout identity checks.
16. `multi_gene_routing_authorized=false`.
17. Fewer than two Manager-accepted Gene Packages cannot activate the integration hook.
18. No TIES/DARE/DELLA/CtM/dynamic-routing execution is authorized by packaging.
19. No capability claim is made by Worker 04.
20. Real packaging occurs only after Worker-05 27B evidence plus Manager acceptance.

## Unresolved interface ambiguity

No blocking schema ambiguity remains for Worker-04 packaging itself.

The full semantic validity of upstream Training Run and Runtime Attempt Receipt content remains owned by the producing lanes. Worker 04 checks the identities/bindings it must preserve and requires upstream-approved receipts; it does not fork their schemas.

## Truth boundary

This P4.1 work:
- does not rerun G1;
- does not use paid GPU;
- does not train/evaluate/promote;
- does not create a real Gene #1 package;
- does not activate a real adapter;
- does not enable multi-gene merge/routing;
- does not modify production or `main`.
