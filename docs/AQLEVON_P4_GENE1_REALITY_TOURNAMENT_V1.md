# AQLEVON P4 Gene #1 Reality Tournament V1

## Scope

Worker 05 implementation for `P4-A05-GENE1-REALITY-TOURNAMENT`.

This layer freezes the Coding + Tool Use evaluation law before candidate scores are inspected, binds later candidates to exact training/evaluation identities, derives tournament score cards from P3 Reality Evidence rather than caller assertions, and emits fail-closed surrogate/27B decision receipts.

It does **not** train a model, confer promotion authority, merge to `main`, mutate production, or prove a capability gain by itself.

## Frozen evaluation law

Canonical artifact: `research/evaluation/gene1_evaluation_law_v1.json`.

- kind: `AQLEVON_GENE1_EVALUATION_LAW_V1`
- target: `CODING_TOOL_USE`
- law SHA-256 (P2.1 canonical self-digest): `b88669bf69d35bb5694236302b07277d6dd7cc473e099936da3d3ac738eed448`
- hash profile: `AQLEVON_CANONICAL_JSON_SHA256_V1`
- P3 Reality Gate code bound by SHA-256: `b2ca3d5b1b959b29d2fa0587cc4b10b21a617e7a55e483b12847580cb6299e40`
- surrogate arms: exactly the Worker-01 frozen identities map `control=P4_A0_SFT_LORA_CONTROL`, `challenger_a=P4_A1_RLVR_CONTROL`, `challenger_b=P4_A2_SDPO_RICH_FEEDBACK`; screen permits 2–3 registered arms
- k values: 1 and 4
- samples per task: 4, one deterministic greedy + three stochastic
- stochastic profile: temperature `0.7`, top-p `0.95`, max new tokens 2048
- deterministic seed derivation: `SHA256(experiment_id|task_id|candidate_slot|sample_index)_LOW64`

Hard gates require:
- P3 `REALITY_PASS`;
- strict primary CleanPass@1 improvement;
- primary CleanPass@4 non-regression;
- TransferPass@1 non-regression;
- hidden-canary non-regression;
- anti-shortcut non-regression;
- HackGap non-increase at every configured k;
- metamorphic/isomorphic invariance non-regression at every k;
- paired-slot invariance non-regression;
- every required domain CleanPass@1 non-regression;
- rejection of any proxy/reward improvement without clean-truth improvement;
- intact authority boundaries.

Survivors are compared lexicographically under the frozen selection order. Exact ties do not get an arbitrary winner: `NO_UNIQUE_WINNER_MORE_EVIDENCE_REQUIRED`.

## Cross-lane frozen inputs

The committed law does not use placeholder arm/data identities. It binds the exact current Worker-01 canonical method-spec object and a hash-only Worker-02 public/sealed-pack binding. The repository intentionally contains **no sealed evaluation plaintext or secret**. Cross-file regression tests recompute these canonical hashes from the committed snapshots and reject drift.

## Score-blind preregistration protocol

P4 separates chronology into four tamper-evident objects:

1. **Frozen Evaluation Law** — contains no candidate identities or scores.
2. **Stage Binding** — binds the W01 method freeze, W02 Gene #1 pack, sealed evaluation pack, hidden-canary pack, anti-shortcut pack, metamorphic pack, harness, task factory, Reality policy, matched sampling profile, matched training budget, and baseline artifact identity.
3. **Candidate Registration** — after training artifacts exist but before score inspection, binds exact candidate artifact, recipe, training-run receipt, compute receipt, and matched-budget identity for each frozen arm slot.
4. **Freeze Verification Record** — requires Manager-verifiable immutable evidence showing that law + stage binding + candidate registration existed before `scores_unsealed_at_utc`.

A self-hash, caller timestamp, or Worker-05 assertion alone is not chronology proof.

## P3 semantic evidence bridge

`AQLEVON_GENE1_SCORE_CARD_V1` is not accepted from caller-supplied metric summaries as authoritative tournament evidence.

The implementation validates the exact P3 `AQLEVON_REALITY_GATE_EVIDENCE_V1` envelope and checks:
- P2.1 canonical self-digest;
- exact frozen P3 Reality Gate code SHA;
- candidate and baseline Candidate Artifact identities;
- Reality policy identity;
- harness identity;
- task-factory identity;
- hidden-canary identity;
- promotion/runtime authority remains false;
- expected P3 truth boundary;
- no direct floating point / protected plaintext.

The score card is then derived from P3 baseline/candidate metrics plus a separately self-hashed `AQLEVON_GENE1_ANTI_SHORTCUT_OUTCOME_RECEIPT_V1`.

Before a tournament decision is authoritative, `build_tournament_decision()` semantically recomputes every baseline/candidate score card from those underlying evidence objects and requires byte-for-byte object equality. Rehashing a forged metric summary therefore cannot launder it into a valid decision.

All candidate P3 evidences must also share the same baseline outcome-pack and baseline raw-log identities.

## Anti-shortcut evidence

The anti-shortcut receipt binds:
- candidate artifact identity;
- frozen anti-shortcut manifest;
- frozen harness;
- raw outcome-log SHA-256;
- exact task population;
- CleanPass counts at k=1 and k=4.

Anti-shortcut CleanPass may not regress from baseline.

## Surrogate decision semantics

A surrogate arm must first survive every hard gate. Only survivors enter the frozen lexicographic comparison.

Surrogate evaluation has two frozen phases. Each seed round first emits `SURROGATE_SCREEN_RANKING_READY` only after full P3 semantic recomputation. Seed `1701` determines the top two survivors. Only those two may appear in confirmation seeds `1702` and `1703`.

The final three-seed recipe decision uses Worker-01's exact frozen order: median TransferPass@4, worst-seed TransferPass@4, median CleanPass@4, worst-seed CleanPass@4, median HackGap@4, median training GPU-milliseconds, then simplicity. It also enforces the frozen SDPO displacement rule.

Final surrogate statuses:
- `INVALID` — malformed, unanchored, identity-mismatched, semantically unreproducible, wrong seed/candidate set, or authority-invalid evidence;
- `REJECTED` — valid evidence but no usable route;
- `SURROGATE_MORE_EVIDENCE_REQUIRED` — the frozen ambiguity rule fired and the predeclared 24-update extension is required;
- `SURROGATE_RECIPE_SELECTED` — one recipe selected from three frozen-seed evidence bundles.

`SURROGATE_RECIPE_SELECTED` is recipe-selection evidence only. It is not a capability claim and does not authorize a 27B run; Manager authorization remains mandatory.

## Canonical 27B semantics

For the canonical 27B stage, exactly one registered candidate is permitted. Passing P3/P4 evidence is still insufficient for model promotion.

The candidate can reach `READY_FOR_MANAGER_PROMOTION_REVIEW` only when:
- all P4 hard gates pass;
- the exact candidate has a valid authoritative P2 `AQLEVON_EVALUATION_DECISION_RECEIPT_V1`;
- that P2 receipt itself is `PROMOTION_ELIGIBLE`;
- the P2 receipt candidate identity equals the P4 selected candidate identity.

Even then:
- P4 `authoritative_for_model_promotion = false`;
- Manager acceptance is mandatory;
- no deployment/merge is implied.

## Tests and falsification coverage

P4 tests explicitly cover:
- candidate-blind frozen law and self-digest;
- rehashed score injection into law rejected;
- stage-binding law mismatch;
- registration ordering/duplicates/matched-budget mismatch;
- immutable-anchor chronology ordering;
- score-card arithmetic tamper;
- RawPass improvement with CleanPass flat rejected;
- proxy-clean divergence rejected;
- HackGap worsening rejected;
- transfer regression rejected;
- hidden-canary regression rejected;
- anti-shortcut regression rejected;
- metamorphic invariance regression rejected;
- weakest-domain regression rejected;
- screen ties remain deterministic only under the frozen Worker-01 screen order; final near-ties trigger `SURROGATE_MORE_EVIDENCE_REQUIRED` under the predeclared ambiguity law;
- missing registered evidence invalid;
- P3 envelope exact binding and authority laundering;
- anti-shortcut receipt tamper;
- score-card derivation from P3 evidence;
- direct-float injection rejected;
- rehashed metric laundering detected by semantic recomputation;
- canonical 27B missing/foreign/non-promotion P2 receipt blocked;
- only a matching valid P2 promotion-eligible receipt can reach Manager review status;
- P4 authority cannot be laundered to promotion authority.

Fresh exact-source run before publication:
- P1: 23/23 PASS
- P2/P2.1: 45/45 PASS
- P4: 49/49 PASS
- combined fresh P1 + P2/P2.1 + P4: 117/117 PASS
- `py_compile`: PASS
- release policy JSON: PASS
- frozen P4 law JSON: PASS

## Current execution boundary

At final publication time, Worker 05 had inspected **no real P4 candidate score/output**. Worker 01 and Worker 02 have now completed their P4 inputs and are frozen into the law by canonical hash:
- Worker-01 method tournament spec canonical SHA-256: `7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d`;
- Worker-02 public pack binding SHA-256: `d9a81a9730e1dac02ecf8b032191a8d878e00d9a25547712168afb0a725095e5`;
- Worker-02 sealed evaluation pack commitment identity: `b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb`.

The remaining written dependency is real: **Worker 03 has produced no surrogate candidate artifacts yet**. Its current P4 record is `BLOCKED`, with surrogate runs `NOT RUN`. In addition, the private sealed-evaluation plaintext/secret is deliberately not in Git/Library and must be delivered by Manager only to Worker 05 before live hidden evaluation.

Therefore this branch freezes and tests the complete evaluation/tournament machinery, but emits no real surrogate winner and no 27B capability evidence. Once W03 artifacts exist, they must be candidate-registered and Manager-verifiably anchored before score unsealing.

G1 is already complete and is not rerun by this work.