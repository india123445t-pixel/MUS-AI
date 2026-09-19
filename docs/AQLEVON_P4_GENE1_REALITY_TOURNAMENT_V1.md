# AQLEVON P4 Gene #1 Reality Tournament V1

**Worker:** 05 — Evaluation / Truth / Red-Team  
**Task:** `P4-A05-GENE1-REALITY-TOURNAMENT`  
**Status at publication:** evaluator/preregistration implementation complete; live behavioral evaluation **BLOCKED on missing Worker-03 surrogate candidate artifacts**.  
**Authority boundary:** this layer may reject candidates and emit evaluation evidence; it cannot promote, merge, deploy, or claim a capability gain. Manager acceptance remains mandatory.

## 1. Purpose

P4 attempts to produce AQLEVON Gene #1 for **Coding + Tool Use**. Worker 05's responsibility is to make the method tournament candidate-blind before scores exist, evaluate every arm under the same sealed objective harness, select a surrogate recipe only from frozen evidence, and later evaluate the single canonical 27B candidate under the same truth law.

G1/R0-A is already complete and is **not rerun** by this work.

This P4 implementation is stacked on Worker-05 P3 Reality Gate head:
`d902566f0d5ddd821f0a5fa41ab64b332da32ed2`.

## 2. Cross-lane inputs frozen before candidate scores

### Worker 01 method tournament
The exact machine-readable Worker-01 P4 spec is mirrored as:
`research/evaluation/worker01_method_tournament_spec_v1.json`.

Authoritative canonical P2.1 JSON SHA-256:
`7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d`.

Frozen arms:
1. `P4_A0_SFT_LORA_CONTROL`
2. `P4_A1_RLVR_CONTROL`
3. `P4_A2_SDPO_RICH_FEEDBACK`

Frozen surrogate model:
`Qwen/Qwen3.5-4B-Base @ daa9c16f371249f9ad1c75a9ed6f956c08ea08f5`, BF16, no quantization.

Frozen selection schedule:
- seed 1701 screen at cumulative C12;
- top two continue on seeds 1702 and 1703 under the same C12 budget law;
- aggregate order: median TransferPass@4, worst-seed TransferPass@4, median CleanPass@4, worst-seed CleanPass@4, lower median HackGap@4, lower median GPU milliseconds, simpler arm;
- if top two remain within one task on both median TransferPass@4 and median CleanPass@4, both receive one predeclared C24 extension on all three seeds;
- C24 never recursively requests another extension; frozen final ordering resolves the result;
- SDPO may displace the best feasible control only if median TransferPass@4 is strictly higher and median CleanPass@4 is non-lower, with every Worker-05 hard gate passing.

### Worker 02 Gene #1 data/verifier pack
Worker-02 P4 source lineage:
- branch `agent/02-p4-gene1-data-verifier-pack-v1`
- commit `abb94ef134e2e97036b6959dbc9db4278d3736b6`
- PR #33

The public W05 binding is mirrored as:
`research/evaluation/gene1_worker02_public_pack_binding_v1.json`.

Binding SHA-256:
`d9a81a9730e1dac02ecf8b032191a8d878e00d9a25547712168afb0a725095e5`.

It binds at minimum:
- training shard file SHA-256 `59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49`;
- training shard manifest SHA-256 `f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f`;
- training-visible pack SHA-256 `35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b`;
- split commitment SHA-256 `3cd1c0d32cad8cc7edf55c9392292828d54d2b4bd16ad50d0e70e26ba3dd9202`;
- sealed-eval pack commitment SHA-256 `b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb`;
- sealed-eval public commitment SHA-256 `7e0463ddf6068fe66d85b5798b4f8037489c99dcd452376e8144dff0a122f4e5`.

The sealed evaluation plaintext and operational secret are intentionally **not** copied into Git or Library. The public commitment states training-worker visibility is forbidden. Worker 05 requires controlled operational handoff only when live evaluation begins.

## 3. Candidate-blind P4 evaluation law

Frozen file:
`research/evaluation/gene1_evaluation_law_v1.json`

`law_sha256`:
`70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0`

The law contains no candidate scores, candidate artifacts, or post-hoc winner identity. It binds Worker-01/02 identities, the sampling law, allowed stages/rounds, hard gates, authority boundary, and selection rules.

Frozen evaluation sampling follows Worker 01 exactly:
- 4 samples per task;
- k = 1 and 4;
- `do_sample=true`;
- temperature `0.7`;
- top-p `0.8`;
- top-k `20`;
- max response tokens `2048`;
- evaluation seed law `100000 + training_seed * 100 + sample_index`, sample index 0..3;
- same task order and paired evaluation sampling across arms within a training seed.

## 4. P4 evidence objects

P4 uses `AQLEVON_CANONICAL_JSON_SHA256_V1` and emits self-hashed objects including:
- `AQLEVON_GENE1_EVALUATION_LAW_V1`
- `AQLEVON_GENE1_STAGE_BINDING_V1`
- `AQLEVON_GENE1_CANDIDATE_REGISTRATION_V1`
- `AQLEVON_GENE1_FREEZE_VERIFICATION_V1`
- `AQLEVON_GENE1_ANTI_SHORTCUT_OUTCOME_RECEIPT_V1`
- `AQLEVON_GENE1_SCORE_CARD_V1`
- `AQLEVON_GENE1_TOURNAMENT_DECISION_RECEIPT_V1`
- `AQLEVON_GENE1_SURROGATE_RECIPE_DECISION_V1`

All are evidence objects. None has model-promotion authority.

## 5. Chronology: truthful round-aware preregistration

A single false statement such as “no scores observed” is not reused after a previous round has already been evaluated.

The stage binding therefore has explicit round modes:

### `initial12`
No candidate scores from the current tournament round have been observed. No parent decision may be supplied.

### `extension24`
Prior C12 scores have necessarily been observed. The stage must bind the exact `SURROGATE_MORE_EVIDENCE_REQUIRED` receipt that authorized the extension, while truthfully stating that **current extension scores have not yet been observed**.

### `canonical27b`
Surrogate results have necessarily been observed. The stage must bind the exact selected surrogate-recipe receipt while stating that **current 27B scores have not yet been observed**.

Each actual stage/candidate registration still requires an externally Manager-verifiable freeze verification whose immutable anchor predates score unsealing.

## 6. Hard reality gates

Every candidate score card is rebuilt from P3 Reality Evidence plus objective anti-shortcut evidence; caller-authored metric summaries are not authoritative.

A candidate fails if any frozen hard gate fails, including:
- P3 status is not `REALITY_PASS`;
- proxy/reward improves while clean truth does not;
- primary CleanPass@1 does not strictly improve over baseline;
- primary CleanPass@4 regresses;
- TransferPass@1 regresses;
- hidden-canary CleanPass regresses;
- anti-shortcut clean success regresses;
- HackGap worsens at k=1 or k=4;
- metamorphic/isomorphic invariance regresses;
- paired sampling-slot invariance regresses;
- any required coding/tool domain CleanPass@1 floor regresses;
- evidence populations/harness identities differ.

A hard-gate failure on **any one of the three frozen training seeds** removes that arm from final method eligibility; median performance cannot wash out a failed seed.

## 7. Surrogate tournament decisions

### Screen receipt
Seed 1701 produces only `SURROGATE_SCREEN_RANKING_READY`. It may identify top two survivors, but cannot declare the final recipe.

### Three-seed recipe receipt
The top two are evaluated over seeds 1701/1702/1703. Only arms passing all hard gates on all required seeds enter aggregate ranking.

Possible outcomes:
- `INVALID`
- `REJECTED`
- `SURROGATE_MORE_EVIDENCE_REQUIRED`
- `SURROGATE_RECIPE_SELECTED`

`SURROGATE_RECIPE_SELECTED` is **method evidence only**. It does not authorize 27B training by itself; Manager authorization is required.

### C24 extension
If the exact frozen ambiguity law fires at C12, the extension stage binds the parent ambiguity receipt and a shared C24 budget identity for both arms/all seeds. C24 cannot request another extension. The frozen final ordering resolves remaining closeness without post-hoc metric invention.

## 8. Canonical 27B parent-recipe lock

The 27B evaluation stage does not merely accept a syntactically valid parent hash.

Before evaluating a canonical 27B candidate, Worker 05 verifies that:
1. the parent surrogate receipt itself is valid and self-hashed;
2. its status is exactly `SURROGATE_RECIPE_SELECTED`;
3. its receipt SHA equals the stage-binding parent SHA;
4. the 27B registered candidate uses the exact selected candidate slot / arm ID / recipe-spec SHA;
5. the P2 `AQLEVON_EVALUATION_DECISION_RECEIPT_V1` is valid, binds the exact 27B candidate artifact, and is `PROMOTION_ELIGIBLE`.

Only then may Worker 05 emit `READY_FOR_MANAGER_PROMOTION_REVIEW`. Even that status explicitly carries `authoritative_for_model_promotion=false`; Manager remains the promotion authority.

## 9. Integrity / anti-laundering properties

Tests cover fail-closed behavior against:
- law score injection followed by rehash;
- foreign/rehashed stage law;
- budget drift;
- duplicate candidate identity;
- registration/score-card identity mismatch;
- forged P3 envelope authority;
- wrong P3 code identity;
- direct-float injection into authoritative evidence;
- metric summary laundering followed by outer rehash;
- HackGap arithmetic tamper;
- missing semantic support evidence;
- proxy-clean divergence;
- hidden-canary, transfer, weakest-domain, metamorphic and anti-shortcut regression;
- final recipe authority laundering;
- final receipt code-identity tamper;
- confirmation candidate-set substitution;
- a hard-gate failure hidden inside a three-seed median;
- extension without its parent ambiguity receipt;
- recursive C24 extension;
- canonical 27B recipe differing from selected surrogate recipe;
- a foreign surrogate parent receipt rebound into a 27B stage.

## 10. Exact implementation identities at final local validation

`research/evaluation/gene1_reality_tournament_v1.py`
- SHA-256: `72e4f6b21625f5588cb0c8c7050ff210994c8188014860f0b4b7735349c54f09`

`research/evaluation/test_gene1_reality_tournament_v1.py`
- SHA-256: `1699ea6e74f914ec9a7b0c34c13559ac6cb71a5091ff9ff37a92baedc941dd41`

`research/evaluation/gene1_evaluation_law_v1.json`
- file SHA-256: `37a1c630b2f0b48ac5ab7273ddb2820d511203190d08eb7a8892a615562d052e`
- authoritative law self-SHA: `70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0`

`research/evaluation/worker01_method_tournament_spec_v1.json`
- file SHA-256: `4f51eed6107dac85046a432f99edee54f01d3b8100c443eeedd0cb6c56394668`
- canonical P2.1 content SHA: `7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d`

`research/evaluation/gene1_worker02_public_pack_binding_v1.json`
- file SHA-256: `c75159cba3da58096cca4e85f47a0474334ef30793c134363841d4ef97c5365c`
- binding self-SHA: `d9a81a9730e1dac02ecf8b032191a8d878e00d9a25547712168afb0a725095e5`

## 11. Validation evidence

Fresh exact-source regression after all P4 hardening:
- P1 suite: **23/23 PASS**
- P2/P2.1 suite: **45/45 PASS**
- P4 Gene #1 Reality Tournament suite: **55/55 PASS**
- combined fresh suite: **123/123 PASS**
- `py_compile`: PASS
- P1 policy JSON: PASS
- P4 law / Worker-01 snapshot / Worker-02 binding JSON parse: PASS
- P4 law CLI validation: VALID
- cross-lane frozen-input CLI validation: VALID

Inherited P3 Reality Gate remains the unchanged parent layer previously validated at 34/34; P4 does not rewrite it.

## 12. Current execution blocker

At the final live dependency check, Worker 03 PR #30 remained at:
`61e1ffe1e9aee67ca7153ef3feae5fd2ecd8421b`
with **no surrogate physical runs executed and no candidate artifacts emitted**.

Worker 03's recorded blocker was originally W01/W02 absence. That condition is now stale because W01 and W02 have completed, but Worker 03 has not yet resumed/published new surrogate candidates. Worker 05 cannot fabricate or execute another worker's training lane.

Therefore Worker 05 cannot legally perform:
- surrogate score unsealing;
- final surrogate recipe selection;
- 27B Gene #1 evaluation;
- any capability-gain or promotion claim.

A second operational prerequisite for live hidden evaluation is controlled Manager/Worker-02 handoff of the sealed-eval plaintext and secret whose commitments are already frozen publicly. Those secrets must never be copied into the training worker's branch.

## 13. Resume condition

When Worker 03 emits surrogate candidate artifacts/receipts under the frozen W01/W02 inputs:
1. Worker 05 creates exact stage binding + candidate registration;
2. Manager-verifiable preregistration anchor is established before score inspection;
3. sealed evaluation is run at the frozen sampling budget;
4. screen + confirmation/C24 law is applied without changing thresholds;
5. surrogate recipe evidence is emitted for Manager selection;
6. after one Manager-authorized 27B training run, Worker 05 repeats the same truth law with exact selected-recipe parent binding and the authoritative P2 receipt;
7. Manager alone accepts or rejects Gene #1.

## 14. Nonclaims

This implementation:
- does not rerun G1;
- uses no paid GPU;
- performs no training;
- evaluates no live surrogate or 27B candidate because none exists yet;
- does not modify production;
- does not merge to `main`;
- does not expose sealed evaluation plaintext;
- does not claim a capability gain;
- does not promote Gene #1.