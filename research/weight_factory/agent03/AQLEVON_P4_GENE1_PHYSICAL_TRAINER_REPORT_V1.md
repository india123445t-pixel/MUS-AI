# AQLEVON Worker 03 — P4 Gene #1 Physical Trainer

**Task:** `P4-A03-GENE1-PHYSICAL-TRAINER`  
**Worker:** `03`  
**Status:** SURROGATE PREPARATION COMPLETE — A1 PHYSICAL RUN AWAITS EXACT MANAGER PAID AUTHORIZATION  
**Branch:** `agent/03-p4-gene1-physical-trainer`  
**PR:** #30  
**Parent:** Worker-03 P3 `4a7a5fa2c2c4ba5f291564251c290e2c416ce6ec`

## Starting truth

G1 already passed physically and is frozen as `ALREADY_PASSED_DO_NOT_RERUN`. This P4 lane contains no G1 rerun.

## Real P4 inputs consumed

Worker 01:
- spec kind `AQLEVON_P4_METHOD_TOURNAMENT_SPEC_V1`
- canonical SHA256 `7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d`
- arms: A0 SFT control / A1 RLVR control / A2 SDPO rich-feedback
- order: A1 seed1701 -> A0 seed1701 -> A2 seed1701 if preflight passes
- same-architecture student: `Qwen/Qwen3.5-4B-Base@daa9c16f...`
- common adapter: BF16 LoRA r4/alpha4, full-attention q/v only.

Worker 02:
- 56 canonical training rows
- shard SHA256 `59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49`
- manifest SHA256 `f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f`
- training-visible pack SHA256 `35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b`
- split SHA256 `3cd1c0d32cad8cc7edf55c9392292828d54d2b4bd16ad50d0e70e26ba3dd9202`
- sealed eval remains hash-only/forbidden to Worker03.

Worker 05:
- candidate-blind law frozen before scores
- law SHA256 `70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0`
- sampling SHA256 `4dde4741da4c1c469ee6fe555ea9041ad985de829eefb76b702ff0c82e528903`.

Worker 06:
- surrogate compute profile `p4-surrogate-1x24`
- paid execution requires explicit Manager authorization.

## Implemented / repaired in this PR

- real W01/W02/W05 contract consumer (old blocked placeholder contract removed);
- exact P2.1-style canonical hashes and immutable frozen plan;
- sanitized AQLEVON-owned objective reward for A1/A2;
- no expected state/oracle/canary text in rich feedback;
- SDPO/GRPO launcher pinned to `lasgroup/SDPO@7c457fc1...`;
- W01 package versions enforced (`transformers 5.17.0 / peft 0.21.0 / accelerate 1.15.0`);
- LoRA only: r4/alpha4, `self_attn.q_proj/v_proj` only;
- A0 SFT control bound to the same exact training shard;
- 12-update screen budget / 4 prompts / 4 RL rollouts / frozen sampling;
- no automatic fallback, no QLoRA, no model revision mutation;
- paid run gate binds exact plan SHA + command SHA + profile.

## Frozen run preparation

Frozen plan:
- `plan_sha256 = 2ad7de02027e7b4eb1546486c1f02999b361585a38fc8316c17efbea9e1993c2`

First run per W01 order:
- arm: `P4_A1_RLVR_CONTROL`
- seed: `1701`
- profile: `p4-surrogate-1x24`
- `command_sha256 = 267ad42d23f4fd0dafb86dd669414de37becbb22aa4dc24cf1c144767e7eec95`
- `lock_sha256 = e37e5f4be9002c152aa4daead72c84a8ee6d6645b71520b2075aa0465d28e0d0`
- automatic fallback: false
- G1 rerun: false.

The exact plan and exact A1 command lock are checked into this branch.

## Verification

Local exact-source verification before publication:
- `py_compile`: PASS
- schema JSON parse: PASS
- contract/unit suite: **17/17 PASS**
- real W01/W02/W05 `freeze-plan`: PASS
- 56-row train-visible data conversion: PASS
- A1 command generation/lock: PASS
- no local/free GPU exists in this Worker environment (`nvidia-smi` unavailable).

## Physical truth

No P4 GPU run has occurred yet.
No paid compute has been used in P4.
No surrogate candidate exists yet.
No 27B Gene #1 run exists.
No capability-gain claim is made.

The next action is exactly one A1 seed1701 run after Manager authorizes the frozen paid command/profile/budget. Its measured Worker06-attributed GPU-seconds becomes `C12`, the ceiling for A0/A2.

No merge to `main`, no production mutation, no sealed-eval plaintext access.
