# AQLEVON P4.1 — Surrogate Evaluation Hot Path V1

**Worker:** 05 — Evaluation / Truth / Red-Team  
**Task:** `P4.1-A05-SURROGATE-EVAL-HOTPATH`  
**Parent:** `P4-A05-GENE1-REALITY-TOURNAMENT`  
**Purpose:** eliminate avoidable delay between Worker 03 producing a valid A1 surrogate candidate and Worker 05 returning frozen-law reality evidence.

## Non-negotiable truth boundary

P4.1 does **not** create a new evaluation policy and does not alter any P4 threshold. The authoritative frozen P4 law remains:

- law self-digest: `70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0`
- frozen law file SHA-256: `37a1c630b2f0b48ac5ab7273ddb2820d511203190d08eb7a8892a615562d052e`
- sampling profile SHA-256: `4dde4741da4c1c469ee6fe555ea9041ad985de829eefb76b702ff0c82e528903`

No threshold, metric, decoding budget, hidden-harness identity, or selection rule may be changed after a candidate appears.

Worker 05 may emit evaluation evidence. Only the Manager may accept a recipe for the next paid stage or accept/promote a Gene #1 capability result.

## Current A1 producer identity

The hot path is pinned to the current P4.1 Worker-03 A1 contract:

- Worker-03 executable source head: `a3abc957f7b81a4dc4e8e20ecb1bb0de3047f783`
- task: `P4-A03-GENE1-PHYSICAL-TRAINER`
- arm: `P4_A1_RLVR_CONTROL`
- seed: `1701`
- profile: `p4-surrogate-1x24`
- frozen training-plan SHA-256: `3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095`
- run-manifest SHA-256: `7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45`
- command SHA-256: `3ad2fd2cd5303e1eb4ea71f3e25edf07d38269df1b5b3c8b6e98c8553e017400`
- command-lock SHA-256: `f1d05b53d0e00b07f7f4d60c90a6bf489f4cd2bd118b2b6a6b38c66026cee44e`
- model: `Qwen/Qwen3.5-4B-Base`
- revision: `daa9c16f371249f9ad1c75a9ed6f956c08ea08f5`
- precision: BF16
- quantization: none
- optimizer updates: 12
- prompts/update: 4
- rollouts/prompt: 4

Pinned Worker-03 Git blobs checked during P4.1 audit:

- run manifest: `7e7196ba3e040e58eb307d28e7062e5d24ce8642`
- command lock: `09a3bc32edc52d6676ba94eb0b05ed4f321c4b09`
- Candidate Artifact Manifest producer: `b3c38950b2e591e412726e49ef580129e74dd5c1`
- Candidate Artifact Manifest schema: `247832f5212860111ddff2d9e565f8ddc9b6402e`

These bindings are pre-evaluation compatibility facts only. They do not prove that a physical candidate exists.

## Why a structurally valid checkpoint is not automatically evaluable

A candidate can have a valid P2.1 Candidate Artifact Manifest self-digest and still be unusable for the frozen A1 evaluation. Hidden evaluation must not be spent if any of the following is wrong:

1. base repo or exact base revision;
2. artifact type or required adapter state identity;
3. Worker-02 Training Shard Manifest binding;
4. raw training-receipt SHA-256 binding;
5. training receipt does not bind the exact A1 run manifest, plan, arm and seed;
6. training receipt reports fewer/more than the frozen 12 optimizer updates;
7. zero parameter delta, failed save/reload equality, or candidate/receipt adapter-state mismatch;
8. run manifest or command lock is not the frozen A1 identity;
9. sealed evaluation material or forbidden hidden/protected data appears anywhere in the training evidence path;
10. evaluation stage binding uses the wrong frozen sampling/decoding budget, harness, task factory, canary manifest, anti-shortcut manifest, metamorphic manifest, or Reality Gate policy.

P4.1 validates these conditions **before hidden evaluation compute**.

## Candidate-ingestion hot path

When Worker 03 delivers A1 artifacts, Worker 05 executes the following order without policy changes:

1. Validate the exact Worker-03 A1 run manifest self-digest and frozen identity.
2. Validate the exact command-lock self-digest, argv hash, plan/run binding, no-fallback flag and `g1_rerun=false`.
3. Validate the Candidate Artifact Manifest under the accepted P2.1 hash profile.
4. Require `artifact_type=adapter`, exact Qwen3.5-4B base identity, exact Worker-02 training-shard binding and a non-null training-run receipt identity.
5. Validate the raw training receipt bytes against `training_run_receipt_sha256` from the Candidate Artifact Manifest.
6. Require the receipt to bind the exact A1 run manifest, frozen plan, arm and seed, exactly 12 optimizer updates, nonzero parameter delta, successful save/reload equality, and the same adapter-state identity as the candidate manifest.
7. Recursively reject sealed/private/protected evaluation leakage, including nested debug/metadata/error structures and private evaluation file hashes.
8. Validate the frozen P4 surrogate stage binding and exact sampling/harness identities.
9. Emit a self-hashed `AQLEVON_P4_1_SURROGATE_CANDIDATE_INGEST_RECEIPT_V1` with status `READY_TO_REGISTER_PRE_SCORE` only if every pre-score check passes.
10. Create a single-candidate A1 registration for **reality evidence only**, before hidden score unsealing.
11. Require a Manager-verifiable immutable preregistration anchor whose chronology predates hidden score unsealing.
12. Only then return `READY_FOR_HIDDEN_EVALUATION`.
13. Run the already-frozen hidden harness and build the ordinary P3/P4 reality evidence under unchanged RawPass/CleanPass/HackGap/TransferPass, canary, invariance, anti-shortcut and weakest-domain rules.
14. Return one of the frozen operational result classes: invalid candidate/evaluation, rejected arm, or evidence supporting a Manager recipe decision.

## P4.1 single-candidate overlay — authority boundary

The original P4 tournament registration requires the comparative surrogate set. P4.1 needs immediate A1 truth before the Manager decides which next arm is worth spending on.

Therefore P4.1 adds a **single-candidate preregistration/chronology overlay only**. It does not change `min_surrogate_arms`, the P4 tournament law, or the future comparative receipt.

The single-candidate overlay carries:

`selection_authority = NONE_SINGLE_CANDIDATE_REALITY_EVIDENCE_ONLY`

It can authorize hidden evaluation chronology for A1, but it cannot:

- name a surrogate winner;
- select a 27B recipe;
- alter tournament ranking;
- authorize paid compute;
- promote a model;
- replace the later comparative P4 tournament receipt.

## Zero-delay CLI surface

The P4.1 implementation exposes the complete handoff path so no code changes are needed when A1 arrives:

```text
validate-a1-ingest
build-a1-registration
check-hidden-eval-readiness
classify-score-card
```

`validate-a1-ingest` is the only step that accepts raw Worker-03 candidate/training evidence. `build-a1-registration` records the single A1 candidate without any winner authority. `check-hidden-eval-readiness` requires the Manager-verifiable immutable chronology before hidden evaluation. `classify-score-card` maps only an already-valid frozen P4 score card to `REJECTED_ARM` or `EVIDENCE_SUPPORTS_MANAGER_RECIPE_DECISION`; it does not rank arms or select a 27B recipe.

## Exact hot-path output states

- `INVALID_CANDIDATE` — candidate/run/training identity failed before hidden evaluation.
- `INVALID_EVALUATION` — preregistration, chronology, harness, sampling, or evidence validation failed.
- `READY_TO_REGISTER_PRE_SCORE` — candidate ingestion passed; hidden evaluation is not yet authorized.
- `READY_FOR_HIDDEN_EVALUATION` — pre-score registration + Manager chronology are valid.
- `REJECTED_ARM` — frozen P4/P3 reality law rejected the evaluated arm.
- `EVIDENCE_SUPPORTS_MANAGER_RECIPE_DECISION` — the candidate survived the frozen reality law; this is not a winner or capability-gain claim.

## Test evidence

Final local Worker-05 lineage rerun for this P4.1 snapshot:

- P1 truth gate: **23/23 PASS**
- P2/P2.1 Evaluation Decision Receipt: **45/45 PASS**
- P4 Gene #1 Reality Tournament: **55/55 PASS**
- P4.1 Surrogate Eval Hot Path: **25/25 PASS**
- total: **148/148 PASS**
- Python compilation: PASS
- JSON validation: PASS

P4.1 regression coverage specifically includes:

- exact Manager A1 identity constants;
- frozen-law identity unchanged;
- valid pre-score candidate ingest;
- wrong base revision rejected even after candidate is re-sealed;
- wrong training shard rejected;
- candidate self-hash tamper rejected;
- raw training-receipt SHA mismatch rejected;
- missing/foreign run-manifest binding rejected;
- wrong seed rejected;
- nested hidden-answer leakage rejected;
- private sealed-eval file-hash leakage rejected;
- zero-delta candidate rejected before hidden evaluation;
- run-manifest sealed-eval consumption rejected;
- command-lock automatic fallback rejected;
- wrong frozen sampling/stage binding rejected;
- single-candidate registration has no selection authority;
- Manager-verifiable chronology required;
- anchor after hidden-score unseal rejected;
- registration tamper rejected;
- frozen 12-update budget preserved;
- frozen `REJECTED` reality result maps to `REJECTED_ARM`;
- frozen `REALITY_PASS` maps only to evidence supporting Manager decision;
- authority laundering invalidates the self-hash;
- CLI build-registration end-to-end;
- CLI hidden-evaluation readiness end-to-end;
- CLI frozen score-card classification end-to-end.

## Current physical truth

At P4.1 hot-path freeze time:

- A1 physical candidate: **NONE**
- A1 hidden evaluation: **NOT RUN**
- surrogate winner: **NONE**
- 27B Gene #1 candidate: **NONE**
- capability gain: **NOT CLAIMED**
- Worker-05 GPU/paid compute: **NONE**

Worker 03 remains the physical A1 critical path. When a valid candidate appears, Worker 05 continues the same parent P4 evaluation task with this hot path and the unchanged P4 law.