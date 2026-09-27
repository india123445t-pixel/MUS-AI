# AQLEVON W05 Future Sealed Custody Gate V1

**Owner lane:** Agent 02 custody audit  
**Scope:** future candidates only  
**Legacy W05 status:** `EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`

## Purpose

This gate prevents the missing historical W05 custody path from being papered over by regeneration or silent substitution. It provides a fail-closed custody **and chronology** path for future sealed evaluations only.

It does not generate a secret, generate a sealed pack, reveal private contents, select a candidate, score a candidate, change the historical W05 law, or authorize model promotion.

## Chronology model — Git bytes + strict ancestry

Caller-supplied timestamps are not authoritative.

The future path uses two immutable Git anchors:

1. **Preregistration anchor commit A**
   - contains the exact byte sequence of the preregistration JSON;
   - binds future sealed-pack SHA-256, public commitment SHA-256, raw secret-file SHA-256, raw sealed-plaintext-file SHA-256;
   - records `NO_FUTURE_CANDIDATE_SCORES_OBSERVED`;
   - has a canonical self-digest.

2. **Evaluation-start anchor commit B**
   - contains the exact byte sequence of an evaluation-start receipt;
   - binds the preregistration self-hash, commit A, preregistration path, candidate-manifest SHA-256, and evaluation-policy SHA-256;
   - records `evaluation_started=false` and `NO_FUTURE_CANDIDATE_SCORES_OBSERVED`;
   - has its own canonical self-digest.

The verifier requires **A to be a strict Git ancestor of B**. It reads the files directly from the named commits with `git show` and compares them byte-for-byte with the supplied files. A missing object, wrong path, mismatched bytes, changed reference, sibling branch, or reversed/late chronology fails closed.

The verification result explicitly records:
`chronology_authority = GIT_BYTE_ANCHOR_PLUS_STRICT_ANCESTRY`
and:
`caller_supplied_timestamp_authoritative = false`.

## Evaluation-start rule

A future evaluator must run this gate **before any candidate scoring or private evaluation use**.

The single `verify` command performs chronology verification first. It does not proceed to private material validation unless the exact preregistration and evaluation-start receipt have both been found at their immutable commits and the preregistration commit is a strict ancestor of the evaluation-start commit.

Required CLI inputs include:
- Git repository path;
- exact preregistration file + anchor commit + repository path;
- exact evaluation-start receipt file + anchor commit + repository path;
- exact candidate-manifest SHA-256;
- private future secret file;
- private future sealed-plaintext file.

A successful run emits:
- `PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START`;
- then `PASS_FUTURE_MATERIAL_HASH_BOUND_AND_CHRONOLOGY_PROVEN`.

No scoring code should treat a preregistration or private pack as usable without that chronology PASS.

## Why the anchor is not stored inside the preregistration

A Git commit SHA cannot be embedded in the exact file whose bytes create that same commit without a circular identity problem. Therefore the preregistration record is self-hashed, while the immutable commit/path are supplied as the external anchor coordinates and independently verified against Git.

The evaluation-start receipt then binds those exact coordinates and is itself anchored in a later descendant commit.

## Legacy isolation

The frozen historical W05 pack, public commitment, secret-file, and plaintext-file hashes remain deny-listed:
- `b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb`
- `7e0463ddf6068fe66d85b5798b4f8037489c99dcd452376e8144dff0a122f4e5`
- `e61883f5f794ed6e82bb29b5718b09334ed2f29fa60bc5c1b7f7c6e1e86a8db6`
- `ce17cdee667f2a53adf38000f2ace652cc1b4659187640a49f04858dceadbd0e`

This tool cannot certify a reconstruction of the old W05 material and emits:
- `authoritative_for_legacy_w05=false`;
- `authoritative_for_capability_gain=false`.

## Fail-closed cases

The executable tests cover:
- valid Git-anchored chronology;
- legacy W05 identity rejection;
- score-visible preregistration rejection;
- nonexistent preregistration commit;
- anchor that does not contain the exact preregistration bytes;
- preregistration commit that is not an ancestor of the evaluation-start anchor (late/unordered anchor);
- tampered preregistration anchor path in the evaluation-start receipt;
- candidate-manifest mismatch;
- raw secret-file hash mismatch;
- sealed-pack self-digest tamper.

Private task bodies, prompts, answers, canaries, and private paths are never emitted in successful receipts.

## Free verification

The test suite uses only synthetic temporary bytes and temporary local Git repositories. It must never use the original W05 secret/plaintext.

The PR includes a CPU-only GitHub Actions workflow that runs `py_compile` and this unit suite. No GPU or paid external resource is used.
