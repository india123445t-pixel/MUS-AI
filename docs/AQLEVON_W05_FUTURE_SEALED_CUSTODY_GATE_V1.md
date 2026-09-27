# AQLEVON W05 Future Sealed Custody Gate V1

**Owner lane:** Agent 02 custody audit  
**Scope:** future candidates only  
**Legacy W05 status:** `EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`

## Purpose

This gate prevents a missing historical custody path from being papered over by regenerating or silently substituting W05 material. It provides a fail-closed path for **future** sealed evaluations only.

It does not generate a secret, generate a sealed pack, reveal private contents, select a candidate, score a candidate, change the frozen evaluation law, or authorize promotion.

## Required chronology

Before any future candidate score/output is observed, an immutable preregistration must bind:
- future-only scope;
- `NO_FUTURE_CANDIDATE_SCORES_OBSERVED`;
- future sealed-pack SHA-256;
- future public-commitment SHA-256;
- raw future secret-file SHA-256;
- raw future sealed-plaintext-file SHA-256;
- immutable anchor kind/reference and UTC timestamp;
- self-digest under `AQLEVON_CANONICAL_JSON_SHA256_V1`.

At evaluation time, the private files stay outside Git/training storage. The verifier reads them only to compute hashes and to validate the sealed pack self-digest. Its output is metadata-only.

## Legacy isolation

The frozen historical W05 pack, public commitment, secret-file, and plaintext-file hashes are deny-listed. If a future preregistration supplies any of those identities, the gate rejects it with `legacy_w05_identity_forbidden`.

This is intentional: this tool cannot be used to claim that the missing historical custody path was recovered and cannot certify a reconstruction of old W05 material.

## Verification result

A valid run may emit only `PASS_FUTURE_MATERIAL_HASH_BOUND` plus hashes/authority flags. It explicitly records:
- `private_content_emitted=false`;
- `authoritative_for_legacy_w05=false`;
- `authoritative_for_capability_gain=false`.

Any missing/tampered hash, malformed preregistration, post-score registration marker, legacy identity, symlink/non-regular private file, invalid JSON, or sealed-pack self-digest mismatch fails closed.

## Free tests

The unit suite uses synthetic temporary bytes only. It must never use the original W05 secret/plaintext.
