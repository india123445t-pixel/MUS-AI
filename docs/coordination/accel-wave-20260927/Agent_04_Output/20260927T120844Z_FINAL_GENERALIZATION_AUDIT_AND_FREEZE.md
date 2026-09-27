# Agent 04 Final — Independent 27B Evidence Audit + Frozen Public Generalization Challenge

Timestamp: 2026-09-27T12:08:44Z
Role: AQLEVON Agent 04
Lane: independent public evidence interpretation + structural generalization challenge
Mode: FREE-ONLY
Status: COMPLETE / CHALLENGE FROZEN / INFERENCE NOT RUN

## Historical 27B evidence verdict

GitHub Actions run `36307917194` is valid public-run evidence for a real parameter-changing 27B LoRA run:
- exact source SHA: `4e3f1b03cfe77ac4355907ec692574f30d180252`
- trainer blob: `9085e692d43110600e7bf214ffdab910f4821f1c`
- W02 source commit: `abb94ef134e2e97036b6959dbc9db4278d3736b6`
- W02 blob: `bcdf1326a891dc082a6843f764c052f9192187b8`
- base: `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- 672 optimizer updates
- 1,507,328 trainable LoRA parameters
- public dev: 2/28 -> 24/28
- public shadow: 1/28 -> 23/28
- recorded adapter SHA256: `c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e`
- adapter-state SHA256: `e5a9b8260e7cfc08f3f9c5b072b617bdafc5ed06a645b15c10ee7937d5465bde`
- candidate manifest SHA256: `cf1d3b4c31a2d5396986099f2663cf3ce7d18c15cac695dfe1379e25da7d45b2`

The candidate manifest SHA was independently recomputed from its canonical body and matched exactly.

## Important interpretation limits

1. Training/dev/shadow are index-disjoint but come from the same W02 14-family atomic task generator, prompt renderer, and verifier. Existing scores are strong **in-family held-out evidence**, not a strong structural-generalization proof.
2. Historical baseline and final samples are not same-seed paired. The evaluator derives sampling seed from `label + ":" + task_id`; baseline/final labels differ.
3. Each historical public task has one sampled generation only; no repeated common-seed variance estimate exists.
4. Checkpoint dev labels also change the seed, so the checkpoint trajectory mixes model evolution and sampling-stream change.
5. Dev participates in frozen early-stop logic. R0 nevertheless reached all 672 updates and never hit 28/28, so no evidence was found of a post-hoc earlier-checkpoint selection.
6. Shadow is cleaner with respect to stopping, but still structurally close to training.
7. Original R0 adapter bytes are not proven durably available after the pod deletion. Agent 01 owns that recovery/persistence lane.

Agent 03 independently corroborated the baseline/final seed mismatch and checkpoint stochastic confound.

## New public structural-generalization challenge

Dedicated branch:
`agent/04-27b-generalization-audit-20260927`

Frozen commit:
`5809a44eb7384c2b5af7229e326c01f757bd1b9e`

Files:
1. `research/weight_factory/agent04/aqlevon_27b_public_generalization_challenge_v1.py`
2. `research/weight_factory/agent04/test_aqlevon_27b_public_generalization_challenge_v1.py`
3. `research/weight_factory/agent04/aqlevon_27b_public_generalization_freeze_v1.json`

Exact Git blob identities, independently matched against locally tested bytes:
- generator/verifier: `61c54ff296da0baa58384e0149a684e6c799b0fe`
- unit tests: `f969dd39126541a6ada4f8749e1fd7b35bdb399a`
- freeze manifest: `82194e42a7c7164ef90019c2b1366ab092068427`

SHA256 identities:
- generator/verifier: `06bb54774830918bc1f9b3254186f139b442b334e7e7ac328100db437e39ad83`
- unit tests: `410b2786334f88a0c7c830db834c0fadc6b1712f418dab4ed5fb1b68778e2e9c`
- freeze JSON raw file: `e23849e123a100b79502c363d3e1a3f210e47e03b2d191702710473f008bf001`
- logical generated pack: `10e049fa86fb034023bfa7e93a9dc0cfa58b3cff35718ef32b26533a18ff2b3b`
- freeze-manifest self hash: `5d1e848c5609874d0f1e184f285f4202538fab4a0456828e008f77ba9914c7fd`

The public pack is deterministically derived with:
`python3 aqlevon_27b_public_generalization_challenge_v1.py > pack.json`

No future candidate answer to this new challenge was observed before the above hashes/protocol were frozen.

## Structural shift

The challenge keeps the same public DSL capability domain for comparability, but changes the task structure:
- 16 tasks
- 8 scenario types
- every task requires 2 or 3 composed operations
- original W02 train/dev/shadow tasks are atomic one-operation tasks
- contract/state-snapshot prompt layout instead of W02 prompt template
- no train/eval/trXX core IDs reused
- semantic final-state verification
- exact action-budget verification
- side-effect-path verification
- generated public pack contains no oracle program
- no W05 sealed/private material is used

## CPU test evidence

Exact committed bytes were tested locally:
- `python -m py_compile`: PASS
- unit tests: **5/5 PASS**
- logical pack self-hash recomputation: PASS
- freeze-manifest self-hash recomputation: PASS
- all reference oracle programs pass: PASS
- dropped final operation fails: PASS
- forbidden `replace_state` shortcut fails: PASS
- structural-template checks pass: PASS
- public generated pack contains no `oracle_program`: PASS

## Frozen future inference/scoring protocol

Before any answers were observed, the freeze manifest fixed:
- systems: canonical base vs candidate adapter on the same base
- common seeds for both systems: `27092026, 27092027, 27092028, 27092029`
- 4 samples/task/system = 64 attempts/system
- temperature 0.7, top-p 0.8, top-k 20
- max_new_tokens 256
- thinking disabled
- no retry on parse failure
- no seed/task dropping
- no early stopping
- no prompt/threshold changes after answers
- primary metric: paired total-success delta
- paired evidence test: one-sided exact sign/binomial test on discordant paired attempts
- public-generalization support threshold: positive delta and exact one-sided p <= 0.05
- secondary metric: robust tasks with >=3/4 seed successes

This protocol is public evidence only. Passing it cannot substitute for W05 and cannot by itself authorize final capability promotion.

## GitHub status note

The Agent 04 commit currently shows a Vercel combined status failure whose target reports `upgradeToPro=build-rate-limit`. This is a repository-wide deployment quota/status and is not a CPU test of these research files. No paid upgrade or paid resource was started.

## Parallel reconciliation / correction

- Agent 01 latest checkpoint: artifact recovery/persistence lane; no collision.
- Agent 02 final: legacy W05 verdict `EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`; future gate remains under Manager review; no collision.
- Agent 03 final: trainer/control audit complete; independently corroborates seed mismatch; no collision.
- Manager latest review concerns Agent 02 future custody chronology only; no collision with Agent 04.

The earlier Agent 04 checkpoint said no Agent 03 output was present at that checkpoint. Agent 03's first report appeared concurrently around that write. It was subsequently read in full before Agent 04 freeze completion; no conflicting mutation was found.

## Resource / safety receipt

- main modified: NO
- main merged: NO
- paid compute used by Agent 04: NO
- GPU used by Agent 04: NO
- old paid authorization reused: NO
- historical G1 rerun: NO
- W05 private/sealed material accessed or regenerated: NO
- historical scientific trainer constants changed: NO
- post-result evaluation threshold tuning: NO
- final capability promotion claimed: NO

## Stop boundary / next safe action

Agent 04 stops before inference as required by the FREE-ONLY task.

A future authorized evaluator can execute the already-frozen common-seed protocol only after a durable candidate adapter is available. The resulting public challenge score would be additional independent generalization evidence, not a replacement for the blocked historical W05 sealed evaluation.
