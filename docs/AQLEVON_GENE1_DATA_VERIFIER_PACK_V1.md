# AQLEVON Gene #1 — Data + Verifier Pack V1

**Worker:** 02 — Data + Verifier + Curriculum Architect  
**Task:** `P4-A02-GENE1-DATA-VERIFIER-PACK`  
**Target:** Coding + Tool Use  
**Status:** executable data/verifier substrate only; **not capability evidence**.

## 1. Purpose
This package freezes the first Gene #1 training-visible task family and a cryptographically committed, separately held sealed evaluation family. It extends the P3 verifier-first micro-environment without using protected benchmarks, external generated datasets, or unclear-license data.

## 2. Diversity and split
The pack contains **14 objective tool/state transformation families**:
`increment`, `rename`, `append_unique`, `sort_list`, `delete`, `normalize_ws`, `slugify`, `map_add`, `filter_ge`, `toggle_bool`, `dedupe_list`, `replace_text`, `dict_put`, and `move_item`.

Training-visible side:
- 56 semantic cores = 14 families × 4 distinct cores.
- 112 public tasks = vulnerable/hardened twin for every core.
- exactly 56 hardened tasks are training eligible.
- vulnerable twins are red-team-only and carry no oracle in the public pack.
- the canonical training shard has 56 prompt/answer JSONL rows.

Sealed evaluation side:
- 28 held-out semantic cores = 14 families × 2 secret-derived cores.
- 56 tasks = vulnerable/hardened twins.
- three semantics-preserving prompt perturbations per task.
- secret-derived identifiers/values and hidden canaries.
- exact expected state, oracle program, and touched-path truth live only in the sealed plaintext pack.

Training/eval semantic core IDs are disjoint by construction and by regression test.

## 3. Objective verification / reward-hacking boundary
The DSL executor supports the 14 operations above. Hardened verification requires:
1. exact final state;
2. exact touched-path set / side-effect discipline;
3. no `replace_state` shortcut.

The vulnerable verifier intentionally accepts a whole-state replacement attack. Regression tests prove that the visible-state hardcode exploit passes vulnerable twins and fails hardened twins. This gives Worker 05 a direct HackGap probe rather than assuming the reward channel is safe.

## 4. Anti-shortcut / transfer design
Each semantic core has three prompt forms with identical semantics. The sealed evaluation pack uses secret-derived keys, values, decoys and canaries, so Worker 03 cannot reconstruct the exact held-out instances from the training-visible pack. Evaluation uses the same operation families but new semantic cores and parameterizations, making exact record memorization insufficient.

## 5. Sealed evaluation handling
Committed to Git:
- `gene1_sealed_eval_commitment_v1.json` only.
- It contains the sealed pack SHA, secret SHA, 56 task hashes, and 56 exact protected-content hashes.
- It explicitly records `plaintext_committed_to_git=false` and `training_worker_visibility=FORBIDDEN`.

Never committed to Git or Library:
- `gene1_sealed_eval_pack_PRIVATE_v1.json` plaintext.
- `gene1_eval_secret_v1.key`.

Those two files must be transferred only by Manager to Worker 05/evaluation authority. If the plaintext or secret reaches Worker 03 or a training process, the affected sealed pack must be invalidated and regenerated with a new secret before candidate evaluation.

## 6. Training shard manifest / P2.1 rules
`AQLEVON_GENE1_TRAINING_SHARD_MANIFEST_V1` uses the Manager-frozen hash profile:
`AQLEVON_CANONICAL_JSON_SHA256_V1`.

It preserves:
- ASCII authoritative keys;
- NFKC + CRLF/CR→LF string normalization;
- direct float rejection in authoritative hashes;
- compact canonical JSON;
- lowercase SHA-256;
- exact shard byte hash/size/row count;
- sorted record-content digest using `AQLEVON_SORTED_RECORD_CONTENT_SHA256_LIST_V1`;
- source registry snapshot binding;
- provenance/license evidence binding;
- source admission evidence binding;
- sealed-eval contamination commitment binding;
- train/eval split commitment binding.

Important truth boundary: Worker 02 has **not** fabricated `baseline.attempts/successes`. Empirical model learnability is marked `NOT_MEASURED_BY_WORKER_02_NO_GPU_CLAIM` and belongs to the surrogate tournament. Therefore this P4 manifest is a static data-integrity/provenance/contamination admission manifest, not a false claim that P1 student-success measurements occurred.

## 7. Provenance / license
There is exactly one training source:
`aqlevon-gene1-owned-synthetic-v1`.

Evidence states:
- owner: AQLEVON;
- source class: AQLEVON-owned synthetic;
- external dataset IDs: empty;
- protected eval ingested: false;
- unclear-license material ingested: false;
- source registry is default-deny;
- admission decision is `ADMIT_STATIC_DATA_INTEGRITY` under the P4 static data-integrity basis;
- empirical student baseline is explicitly deferred, not invented.

## 8. Frozen operational identities
For the frozen P4 pack generated during Worker-02 execution:
- training shard SHA-256: `59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49`
- training manifest self-SHA-256: `f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f`
- sealed eval pack self-SHA-256: `b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb`
- sealed eval commitment self-SHA-256: `7e0463ddf6068fe66d85b5798b4f8037489c99dcd452376e8144dff0a122f4e5`
- split commitment self-SHA-256: `3cd1c0d32cad8cc7edf55c9392292828d54d2b4bd16ad50d0e70e26ba3dd9202`

These are data/evaluation identities only. They do not imply a model capability gain.

## 9. Handoff
### Worker 03 — training-visible only
Worker 03 may consume:
- `gene1_training_shard_v1.jsonl`
- `gene1_training_shard_manifest_v1.json`
- `gene1_training_visible_pack_v1.json`
- source/provenance/admission evidence files
- split + sealed commitment hashes

Worker 03 must **not** receive the sealed plaintext or eval secret.

### Worker 05 — evaluation authority
Worker 05 receives from Manager:
- `gene1_sealed_eval_pack_PRIVATE_v1.json`
- optionally the secret for regeneration/audit
- the public commitment files from Git
- the verifier code from this branch

Worker 05 remains the only worker allowed to emit behavioral evaluation evidence. Worker 02 makes no gain claim.

## 10. Tests
The P4 suite covers deterministic generation, source/provenance boundaries, semantic split isolation, hidden canaries, secret rotation, exact-content commitments, P2.1 hash laws, shard byte binding, oracle success, vulnerable exploit success, hardened exploit rejection, side-effect attacks, tamper rejection, and public/private output separation.