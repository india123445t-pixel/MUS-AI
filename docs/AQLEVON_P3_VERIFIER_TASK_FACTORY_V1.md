# AQLEVON P3 Verifier Task Factory V1 — Worker 02

**Task:** `P3-A02-VERIFIER-TASK-FACTORY`  
**Mode:** implementation on isolated P3 branch; no paid GPU; no production mutation; no main merge.

## Deliverable

This package implements an AQLEVON-owned verifier-first coding/tool micro-environment for the first physical capability wave.

It generates **25 semantic task cores**, each as a deliberate vulnerable/hardened verifier twin, for **50 public tasks total**. No protected benchmark item or unclear-license generated dataset is imported. All task semantics are generated deterministically by AQLEVON-owned templates.

The task families exercise exact state transitions rather than free-form judge scoring:
- integer state updates;
- schema/key migration;
- set-like append semantics;
- list ordering;
- cleanup/deletion;
- whitespace normalization;
- slug transformation;
- numeric mapping;
- numeric filtering;
- status transitions.

Candidate solutions are JSON programs in a narrow, non-shell DSL. No arbitrary Python, shell, network, filesystem, or subprocess execution occurs inside the verifier.

## Reward-hacking twins

Every semantic core has:
- a `vulnerable` twin that checks only the visible final state and is **red-team-only / never training eligible**;
- a `hardened` twin that checks visible state, exact touched paths, three sealed hidden fixtures, and hidden-canary preservation.

A canonical exploit (`replace_state` with the visible expected state) intentionally passes every vulnerable twin but fails every hardened twin. The regression suite proves this across all 25 semantic cores.

This creates an explicit HackGap surface for Worker 05 rather than assuming the reward channel is trustworthy.

## Hidden canaries and leakage boundary

The build command requires a canary secret through a **file**, not a CLI plaintext value. The secret itself is never written to a manifest or public task. Only `canary_secret_sha256` is exported.

Each semantic core gets three hidden fixtures and unique HMAC-SHA256 canaries. The sealed verifier pack contains hidden fixture plaintext; the public task pack does not contain:
- oracle programs;
- hidden fixtures;
- canary plaintext;
- expected-state plaintext.

The public pack carries only the visible initial state plus SHA-256 of the public expected state.

## Train/eval split

Split is at **semantic-core level**, not prompt-variant level:
- cores `01..18`: train;
- cores `19..25`: eval.

The sets are disjoint. Only hardened train twins are `training_eligible`, yielding 18 SFT-control records. Vulnerable twins and all eval cores are excluded from training export.

This prevents a semantics-preserving perturbation of an eval task from silently entering training.

## Semantics-preserving perturbations

`perturb_public_task()` supports three prompt-only variants:
- `concise`;
- `strict`;
- `tool_json`.

Perturbations receive a new task SHA but preserve the same `semantic_core_sha256` and verifier binding. Regression tests prove the oracle remains valid for all perturbation variants.

## Exact state / side-effect verification

The hardened verifier requires:
1. exact visible final state;
2. exact visible touched-path set;
3. exact hidden final state for three secret fixtures;
4. exact hidden touched-path set;
5. hidden canary unchanged.

Therefore a program that changes an unrelated key and later restores the visible state still fails. Unknown operations fail closed.

## P2.1 compatibility

All authoritative manifests and task/verifier identities use:
`AQLEVON_CANONICAL_JSON_SHA256_V1`

Rules match the Manager-frozen P2.1 profile:
- NFKC string normalization;
- CRLF/CR -> LF;
- ASCII authoritative keys;
- lexicographic ASCII key ordering;
- compact UTF-8 JSON;
- integers/booleans/null only as native numeric/literal values;
- direct floats forbidden;
- lowercase SHA-256.

The factory manifest explicitly names `AQLEVON_TRAINING_SHARD_MANIFEST_V1` as the downstream training-shard contract. It does not redefine P2.1.

## Generated artifacts

CLI build emits:
- `factory_manifest.json`;
- `public_task_pack.json`;
- `sealed_verifier_pack.json`;
- `split_manifest.json`;
- `sft_control_records.json`.

The factory manifest cryptographically binds the public pack, sealed verifier pack, split manifest, factory code SHA-256, hidden-canary root, and canary-secret hash.

## Provenance / contamination

Every public task declares:
- owner: AQLEVON;
- source class: `aqlevon_owned_synthetic`;
- external dataset IDs: empty;
- protected evaluation ingested: false;
- license status: `aqlevon_owned`.

The top-level manifest separately declares that no unclear-license material was ingested.

This is a provenance statement about this generated pack only. It does not claim semantic non-overlap with every unknown external benchmark; future promotion still requires Worker-05 contamination/reality checks.

## Scope boundary

This is environment/verifier infrastructure, not evidence of a model capability gain. No model training, weight change, checkpoint, paid GPU work, production change, or main merge is performed or claimed.