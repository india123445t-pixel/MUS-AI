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
- `plan_sha256 = 3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095`

First run per W01 order:
- arm: `P4_A1_RLVR_CONTROL`
- seed: `1701`
- profile: `p4-surrogate-1x24`
- `command_sha256 = 3c898f3ff29619200b0792c9d19be9381e5b3bb2cd286a4ea86f121cb947e372`
- `lock_sha256 = 3aeb611ebdf1eeb168820eba954305e8688b5beebad6463f01b3421ca4d588f6`
- automatic fallback: false
- G1 rerun: false.

The exact plan and exact A1 command lock are checked into this branch.

## Verification

Local exact-source verification before publication:
- `py_compile`: PASS
- schema JSON parse: PASS
- contract/unit suite: **20/20 PASS**
- real W01/W02/W05 `freeze-plan`: PASS
- 56-row train-visible data conversion: PASS
- A1 command generation/lock: PASS
- exact GitHub Actions gate: PASS — run `35427624417`, job `105856211855`; all contract/real-input/parquet/lock/56-oracle steps PASS
- no local/free GPU exists in this Worker environment (`nvidia-smi` unavailable).

## Physical truth

No P4 GPU run has occurred yet.
No paid compute has been used in P4.
No surrogate candidate exists yet.
No 27B Gene #1 run exists.
No capability-gain claim is made.

The next action is exactly one A1 seed1701 run after Manager authorizes the frozen paid command/profile/budget. Its measured Worker06-attributed GPU-seconds becomes `C12`, the ceiling for A0/A2.

No merge to `main`, no production mutation, no sealed-eval plaintext access.


# P4 Resume — W01/W02 consumed; A1 exact paid-authorization gate — 2026-09-19

## Dependency resolution

The earlier W01/W02 dependency blocker is closed.

Consumed authoritative public inputs:
- Worker 01 P4 method freeze, mirrored by Worker 05 at `f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae`;
- Worker 02 Gene #1 data/verifier pack at `abb94ef134e2e97036b6959dbc9db4278d3736b6`;
- Worker 05 candidate-blind frozen evaluation law at PR #34;
- Worker 06 compute profile / paid authorization contract at `7204c7ae84eb6d246603fda960cffe02c2b6279e`.

G1 remains complete and was not rerun.

## Frozen surrogate screen contract

Execution order is frozen from Worker 01:
1. `P4_A1_RLVR_CONTROL` seed 1701 to establish measured `C12`;
2. `P4_A0_SFT_LORA_CONTROL` seed 1701;
3. `P4_A2_SDPO_RICH_FEEDBACK` seed 1701 only if its frozen rich-feedback preflight passes;
4. Worker 05 evaluates all screen candidates before any confirmation seeds.

Frozen surrogate model:
- `Qwen/Qwen3.5-4B-Base`
- revision `daa9c16f371249f9ad1c75a9ed6f956c08ea08f5`
- BF16, no quantization
- LoRA r=4 / alpha=4
- full-attention q/v only.

Authoritative frozen plan:
`3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095`

The plan binds exact W01/W02/W05 identities. During exact-head CI a provenance mismatch in the previously checked snapshot was discovered: the old snapshot used a Library-materialized raw-file hash for the W02 Training Shard Manifest. The authoritative Git commit bytes hash is:
`43ea89e461c6f3033f549f5018eab2be26fb3f7e07736f0dcf918539969e3e90`.
The manifest's authoritative self-hash remains unchanged:
`f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f`.
The snapshot was corrected before any GPU spend.

## Pre-spend defects discovered and repaired

Exact-source review and CI found and repaired all of the following before a paid run:
1. the initial data-prep helper wrote JSON while the pinned SDPO/veRL stack requires Parquet;
2. pinned SDPO `user.yaml` defaults to four GPUs while Worker 06's frozen cheapest profile is one 24GB-class GPU;
3. rollout tensor parallel default was 2, incompatible with the one-GPU profile;
4. default model length exceeded the frozen W01 2048+2048 token law; it is now explicitly 4096;
5. Worker 03's placeholder paid-authorization schema differed from Worker 06's final `AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1`;
6. the A0 SFT runner still referenced placeholder field names instead of W01's final `algorithm/schedule` fields;
7. the old frozen plan carried the wrong raw W02 manifest file-byte hash;
8. unit fixtures lagged behind the stricter real P4 A1/A2 contracts.

None of these defects reached a GPU run.

## Executable A1 identity

Exact profile:
`p4-surrogate-1x24`

A1 command:
- arm: `P4_A1_RLVR_CONTROL`
- seed: `1701`
- 12 valid optimizer updates maximum;
- train batch 4;
- 4 rollouts/prompt;
- BF16;
- LoRA r4/alpha4;
- full-attention q/v only;
- 1 visible GPU;
- tensor parallel size 1;
- prompt ceiling 2048;
- response ceiling 2048;
- max model length 4096;
- no QLoRA;
- no automatic fallback;
- no G1 rerun;
- no sealed-eval plaintext.

Exact command SHA:
`3c898f3ff29619200b0792c9d19be9381e5b3bb2cd286a4ea86f121cb947e372`

Exact command-lock SHA:
`3aeb611ebdf1eeb168820eba954305e8688b5beebad6463f01b3421ca4d588f6`

## Exact-head CPU/public-evidence CI

GitHub Actions:
- workflow: `P4 Agent03 Exact Contract`
- successful run: **35427622594**
- tested source head: `5d17ae3c473a9c29b145be571070dee23ece3263`
- job: `105856206743`
- conclusion: **SUCCESS**

Evidence:
- Python syntax: PASS;
- unit contract suite: **20/20 PASS**;
- W01/W02/W05 frozen plan regenerated from exact commits: PASS;
- regenerated plan byte-for-byte equals checked snapshot: PASS;
- Worker02 56 training rows converted to pinned veRL Parquet schema: PASS;
- `train.parquet` and `test.parquet`: 56 rows each and exact required columns: PASS;
- sealed evaluation consumed by data prep: false;
- A1 argv regenerated from source and equals frozen command lock: PASS;
- command SHA / lock SHA match the exact identities above: PASS;
- public objective reward accepts all **56/56** Worker02 training-visible oracle solutions: PASS.

Earlier CI failures are retained as evidence. They exposed fixture drift and stale frozen-plan provenance before the final green run; they were not hidden or reclassified as success.

## Current physical execution boundary

Current Worker 03 execution environment is CPU-only:
- PyTorch runtime observed: `2.10.0+cpu`;
- CUDA unavailable;
- `nvidia-smi` unavailable.

Therefore:
- A1 physical surrogate: NOT RUN;
- A0 physical surrogate: NOT RUN;
- A2 physical surrogate/preflight: NOT RUN;
- 27B Gene #1: NOT RUN;
- paid GPU used in this resume: NO.

The next legal step is the exact A1 screen run above on Worker06 profile `p4-surrogate-1x24`.

Because no owned/donated/free compatible GPU is available in this Worker environment, any paid execution must first receive Manager authorization under Worker06's exact `AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1`, bound to:
- run task `P4-A03-GENE1-PHYSICAL-TRAINER`;
- run manifest SHA `3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095`;
- profile `p4-surrogate-1x24`;
- explicit billing-time/rate/total-cost/egress ceilings.

Worker 03 additionally freezes the exact argv through command SHA
`3c898f3ff29619200b0792c9d19be9381e5b3bb2cd286a4ea86f121cb947e372`
and command-lock SHA
`3aeb611ebdf1eeb168820eba954305e8688b5beebad6463f01b3421ca4d588f6`.

No candidate or capability gain exists yet. Worker 05 remains evaluation authority and Manager remains acceptance authority.
