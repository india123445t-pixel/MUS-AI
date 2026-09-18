# AQLEVON Frontier Weight Strategy V5 — Capability Integration Stack

**Status:** ACTIVE / OWNER-DIRECTED FRONTIER RESEARCH
**Date:** 2026-09-18
**Supersedes nothing:** V4 remains valid; V5 adds the strongest current capability-integration path found in 2026 research.

## 1. Core decision

AQLEVON will not try to become frontier by directly splicing unrelated tensors from Kimi, DeepSeek, GLM, Qwen, gpt-oss, or closed models.

The frontier plan is now:

**Base -> specialist genes -> verified RL teachers -> on-policy multi-teacher integration -> merge tournament -> optional MoE upcycling -> consolidated checkpoint -> frozen external evaluation.**

This creates a single AQLEVON checkpoint that accumulates capabilities while minimizing catastrophic forgetting and teacher conflict.

## 2. Why V5 changes the integration strategy

Recent 2026 work shows that post-hoc parameter merging alone is not the strongest way to integrate multiple learned capabilities.

### Multi-Teacher On-Policy Distillation (MOPD)
MOPD trains specialist RL teachers independently, then distills them into one student on the student's own rollouts. This gives dense token-level supervision and reduces exposure bias. The MiMo-V2 work reports capability integration superior to mixed RL, cascade RL, off-policy fine-tuning and parameter merge baselines.

Open-MOPD further shows an important failure mode: naive multi-teacher distillation can remain imbalanced, while routed teacher selection recovers substantially more specialist capability. Therefore AQLEVON must never treat all teachers as equally useful for all prompts.

### Merge-of-Thought Distillation (MoT)
MoT alternates teacher-specific student branches with weight-space merging. It is interesting for long-reasoning distillation where teacher traces conflict. AQLEVON will test it only on same-base student branches and never treat external hidden reasoning as unrestricted training data.

### On-policy self correction
Self-Supervised On-Policy Distillation (SSOPD) shows that correct and failed rollouts from the current model can provide a denser correction signal than terminal reward alone. This is useful for AQLEVON's own verified rollouts.

### Process verification
Verifiable Process Rewards (VPR) gives objective intermediate rewards in environments where actions can be checked. This fits coding, tools, repository editing, planning environments and deterministic research substeps.

## 3. AQLEVON Capability Integration Stack

### Layer 0 — Frozen canonical base
Canonical research base remains:
`Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

No experiment is comparable unless it starts from the exact same revision, tokenizer/template, evaluation harness and decoding settings.

### Layer 1 — Specialist genes
Independent same-base capability branches:
- R0-A coding / repo-agent
- R0-B tool use / function calling
- R0-C research / citations
- R0-D Arabic / Moroccan Darija
- R0-E reasoning-effort control
- R0-F factuality / calibration
- R0-G long-horizon state
- R0-H minimal intervention
- R0-I multi-teacher / adversarial
- R0-J long-context evidence
- R0-K environment world model
- R0-L self-evolving curriculum

Each branch is trained and evaluated independently before it is allowed to teach or merge.

### Layer 2 — Specialist RL teachers
For objectively verifiable domains, promote specialist branches through RLVR before integration.

Primary baseline:
- DAPO / strong current GRPO-family baseline.

Research challengers, only if they beat baseline on AQLEVON harness:
- ACPO — adaptive clipping based on importance-ratio variance;
- REAL — reward-as-label optimization;
- VPR — dense verifiable process rewards for agentic tasks;
- SSOPD — self-supervised on-policy distillation from mixed correct/wrong rollouts.

No RL algorithm is adopted because a paper reports a headline score. Every one must run against the same base, data, token budget and eval harness.

### Layer 3 — Routed Multi-Teacher On-Policy Distillation
This becomes the **primary capability integration candidate** for AQLEVON once at least 3 promotion-eligible specialist teachers exist.

Rule:
`student rollout -> task/domain classifier -> best verified teacher(s) -> token-level on-policy distillation -> student update`

Important AQLEVON additions:
- teacher reliability score by domain;
- per-domain teacher routing, not uniform averaging;
- disagreement logging;
- teacher abstention when outside specialty;
- verifier-weighted teacher signal;
- no teacher signal can override objective verifier truth;
- replay/regression mix to preserve general capability.

The first comparison must include:
1. MixSFT
2. sequential specialist training
3. naive multi-domain RL
4. same-base parameter merge
5. MOPD
6. routed MOPD
7. routed MOPD + replay

Promotion is based on the full regression vector, not average score alone.

## 4. Multi-teacher reasoning conflict protocol

For long-reasoning domains, teacher disagreement is expected.

AQLEVON tests three integration modes:

### A. Routed teacher distillation
Use the best domain teacher only.

### B. Knowledge purification
Multiple teachers produce candidate concise training-intended rationales/checks; an external verifier filters factual/executable disagreement before the student sees them.

### C. Merge-of-Thought branch cycle
- train one same-base student branch per approved teacher;
- evaluate each branch;
- merge only compatible branches;
- repeat only if the merged student improves common-harness performance.

AQLEVON will not store or train on proprietary hidden chain-of-thought. External teachers may provide final answers, tool trajectories, explicit training-intended rationales when their license permits, and verifier evidence.

## 5. Merge tournament V5

Parameter merging remains valuable, but is no longer the only integration mechanism.

Tournament order after >=2 promotion-eligible same-base genes:
1. Task Arithmetic / interpolation baseline
2. TIES
3. DARE-TIES
4. DELLA
5. Iso-C / Iso-CTS
6. Adaptive Projective Gradient Descent style merge
7. Expert Merging / layer-wise learned coefficients with unlabeled calibration data
8. evolutionary coefficient search only after conflict atlas exists

Every method must be constrained by the Interference Atlas and compared at identical evaluation budget.

## 6. New high-ceiling track — Dense-to-MoE AQLEVON

This is V5's biggest architectural addition.

Sparse Upcycling and Upcycling Instruction Tuning show that a dense pretrained checkpoint can be converted into a sparse Mixture-of-Experts model without pretraining a giant MoE from zero.

AQLEVON proposal:
1. start from the same AQLEVON-27B base;
2. create several specialist FFN/expert branches from promotion-eligible genes;
3. initialize an MoE with base/shared experts plus specialist experts;
4. initialize/train a router using domain-labeled skilled data;
5. continue training with replay + balancing losses;
6. verify activated compute, routing quality, catastrophic forgetting and serving compatibility.

Potential upside:
- total parameter capacity can rise substantially while activated compute grows much less;
- coding/Arabic/research/tool specialists can coexist as experts;
- specialization can be added without forcing every token through every expert.

Hard caveat:
Qwen3.8-27B uses a hybrid Qwen3.5-style architecture. Dense-to-MoE conversion requires custom architecture work and separate vLLM/SGLang compatibility validation. Therefore this is **R1 architecture research**, not the first R0 checkpoint.

## 7. Expert diversity is a resource

UpIT research indicates that expert diversity matters. Therefore AQLEVON must not create eight identical experts by cloning one final checkpoint and hope routing fixes everything.

Expert candidates should come from:
- different specialist training domains;
- different accepted curriculum stages;
- different verified teacher branches;
- possibly useful intermediate checkpoints;
- self-evolution branches that pass hard verification.

The router is trained only after expert competence is measured.

## 8. Continual pretraining lane

Some capabilities are better learned through continued pretraining than instruction tuning alone, especially:
- Arabic / Darija lexical and factual coverage;
- technical corpus familiarity;
- code/repository syntax distributions;
- long-form document structure.

V5 adds a selective CPT lane with replay.

Rules:
- never CPT the full project corpus blindly;
- quality scoring + dedup + license provenance first;
- include broad replay data to reduce catastrophic forgetting;
- freeze or reduce learning rate on vulnerable modules if ablations show benefit;
- require post-CPT general benchmark recovery before SFT/RL.

## 9. Teacher frontier registry — current research references

High-value open/local teachers currently tracked:
- DeepSeek-V4-Pro — MIT, open weights; strong long-context/agent/coding research teacher.
- DeepSeek-V4-Flash — MIT, lower active compute than Pro; attractive teacher/eval source where hardware permits.
- GLM-5.2 — MIT; 1M-context and long-horizon emphasis.
- Kimi-K3 — open weights under Kimi-K3 custom license; native multimodal/agentic/1M-context; use subject to license conditions.
- gpt-oss-120b — Apache-2.0 open-weight teacher candidate.
- Qwen3.8-2.4T-A95B — frontier Qwen target under qwen3.8-max license, not tensor-compatible with the dense 27B lab line.

These models are **teachers, architecture references and benchmark targets**, not tensors to paste into AQLEVON-27B.

## 10. Cross-architecture capability transfer law

When teacher and student architectures differ, allowed transfer channels are:
- final-answer distillation;
- tool/action trajectory distillation;
- token/logit distillation when local teacher access and terms allow;
- on-policy distillation;
- verifier-filtered synthetic curriculum;
- error/failure mining;
- architecture idea transfer to a future AQLEVON architecture.

Forbidden shortcut:
- direct tensor splicing across incompatible dimensions/tokenizers/attention families.

## 11. AQLEVON's proposed novel combination

No single paper currently gives the whole AQLEVON recipe. The V5 hypothesis is the combination:

**Defect-first curriculum
+ same-base specialist genes
+ objective RLVR/VPR
+ routed multi-teacher on-policy distillation
+ interference-aware merging
+ self-evolution
+ selective CPT with replay
+ optional specialist MoE upcycling
+ frozen external regression gates.**

This is the research program to test. It is not yet a performance claim.

## 12. Four experimental tiers

### Tier 1 — Cheap / immediate
- specialist LoRA genes;
- data/verifier improvements;
- SFT + small RLVR;
- TIES/DARE/Iso merge experiments;
- failure corpus growth.

### Tier 2 — Moderate compute
- full-rank or higher-rank specialist tuning;
- routed MOPD on 2–4 specialists;
- VPR coding/tool environments;
- selective CPT + replay.

### Tier 3 — Large compute
- MoT cycles;
- full-logit/top-k MOPD comparisons;
- dense checkpoint consolidation;
- dense-to-MoE upcycling prototype.

### Tier 4 — Frontier confirmation
- transfer proven recipes to Qwen3.8-A95B or future approved frontier base;
- large-scale agentic RL;
- long-context post-training;
- multimodal capability transfer;
- independent frontier benchmark suite.

## 13. Mandatory ablations

Every claimed improvement must answer:
- Was the gain data or algorithm?
- Was it teacher quality or distillation method?
- Did it improve target domain but harm Arabic/coding/tools/factuality?
- Did token length inflate without accuracy gain?
- Did a verifier leak benchmark answers?
- Does the gain survive a new seed and unseen private tasks?
- Does it survive merge/consolidation?
- Does it survive quantization?

No ablation -> no frontier claim.

## 14. Promotion metric

AQLEVON optimizes **verified capability density**, not raw benchmark average.

Suggested release scorecard includes:
- task success;
- verifier-confirmed success;
- calibration / unsupported-claim rate;
- regression vector;
- tokens per verified success;
- GPU seconds per verified success;
- latency;
- context efficiency;
- tool recovery rate;
- Arabic/Darija native quality;
- minimal intervention / unnecessary-edit rate.

A model that gains 2 benchmark points while doubling cost or hallucination rate is not automatically better.

## 15. Immediate execution plan

### V5-G0 — method registry
Create a machine-readable registry for:
- MOPD / routed MOPD
- MoT
- SSOPD
- DAPO
- ACPO
- REAL
- VPR
- Iso-CTS
- APGD merge
- Expert Merging
- Sparse Upcycling
- UpIT

Fields:
license, source, code availability, maturity, architecture assumptions, compute class, target AQLEVON gene, verification plan, rejection condition.

### V5-G1 — first real weight artifact
Unchanged priority:
- run one optimizer step on exact 27B base;
- save/reload adapter/checkpoint;
- prove non-zero parameter delta;
- hash artifacts;
- run smoke eval.

### V5-G2 — coding gene
Build R0-A because executable tests give the cleanest reward.

### V5-G3 — second and third genes
Tool-use then Arabic/Darija or research depending measured deficits.

### V5-G4 — integration tournament
Once >=3 verified specialists exist:
- merge baselines;
- routed MOPD;
- MOPD+replay;
- MoT for reasoning subset.

### V5-G5 — architecture-upcycling feasibility
Only after R0 line works:
- prototype 2–4 expert MoE on reduced scale first;
- measure router collapse, expert specialization, serving support;
- abandon if quality/compute ratio is inferior to dense+router alternatives.

## 16. Hard truth boundary

V5 does **not** mean AQLEVON is already stronger than Kimi, ChatGPT, Claude, DeepSeek or GLM.

AQLEVON earns that statement only after:
1. actual new parameters are trained;
2. checkpoint is saved/reloaded and hashed;
3. private and public evals are frozen before testing;
4. contamination checks pass;
5. the model wins broad comparisons, not cherry-picked tasks;
6. reliability and cost remain acceptable.

Until then, AQLEVON is a frontier-directed research system with a stronger integration strategy, not a proven frontier winner.