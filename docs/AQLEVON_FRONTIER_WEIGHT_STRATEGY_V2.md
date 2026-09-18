# AQLEVON Frontier Weight Strategy V2

**Status:** ACTIVE / OWNER PRIORITY / SUPERSEDES V1 WHERE CONFLICTING  
**Date:** 2026-09-18  
**Mission:** Build genuinely new AQLEVON weights that become progressively stronger across reasoning, coding, research, tool use, Arabic/Darija, multimodal work, long context, factuality, long-horizon agents, and cost efficiency.

## 0. Non-negotiable truth rule

AQLEVON may target frontier competitiveness, but no blanket claim such as “stronger than ChatGPT / Claude / Kimi” is allowed without a predeclared common harness, same tool/context allowances, dated model versions, and reproducible evidence.

A model is not an AQLEVON checkpoint unless parameters changed and the resulting artifact was saved, hashed, and evaluated.

## 1. Core idea: collect capabilities, not incompatible tensors

Do not splice unrelated Kimi/GLM/DeepSeek/gpt-oss/Qwen tensors. Instead acquire capabilities through:
- legally usable open-weight teacher behavior;
- same-base specialist LoRAs/task deltas;
- objective RLVR and process rewards;
- adaptive self-play environments;
- self-verified synthetic data;
- architecture ideas reimplemented independently;
- compatible task-vector/LoRA merging;
- test-time search used to generate better verified training targets;
- periodic consolidation into one release checkpoint.

## 2. Two-brain development architecture

### 2.1 Research Brain
Research Brain is not the public release model. It contains:
- frozen canonical Qwen3.8-27B base;
- independent specialist LoRAs;
- experimental LoRA routers;
- verifier bank;
- Teacher Council;
- self-play environment generator;
- test-time search/reranking;
- failure memory and curriculum generator.

Purpose: maximize experimentation speed and minimize catastrophic forgetting.

### 2.2 Release Brain
Release Brain is the single AQLEVON checkpoint served to users.

It is produced periodically by:
1. selecting only independently verified specialists;
2. measuring pairwise interference;
3. task-vector/TIES/DARE/CoMerge experiments;
4. short consolidation SFT/RL;
5. complete common-harness regression test;
6. full-precision approval;
7. quantization and re-evaluation.

Research Brain may be modular. Release Brain should remain operationally simple.

## 3. Canonical laboratory base

Base: `Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.

Why:
- 27B dense size permits repeated experiments;
- native multimodal design;
- native long context;
- Apache-2.0 lineage according to current official repository;
- existing AQLEVON topology lock/preflight already targets this family.

Do not silently swap the base revision.

## 4. Teacher/reference constellation

Teachers are not automatically mergeable weights. Each is used only through mechanisms permitted by its license and deployment terms.

### Qwen3.8-27B
Roles: base, self-play learner, recovery baseline, multimodal lab model.

### GLM-5.2 / GLM-5.x open weights
Roles: long-horizon engineering, 1M-context behavior reference, flexible reasoning effort, coding teacher where license permits.
Ideas to study independently: IndexShare, speculative/MTP behavior, long-horizon agent training.

### Kimi K3 open weights
Roles: long-horizon/multimodal teacher/reference subject to Kimi license conditions.
Ideas: KDA, Attention Residuals, sparse MoE, 1M context, multimodal agentic workflows.

### DeepSeek open-weight family
Roles: reasoning/coding teacher, RL/reasoning recipe reference where licensing permits.

### gpt-oss-120b
Roles: reasoning-control, structured outputs, tool-use teacher/reference under Apache-2.0 open-weight use.

### Closed hosted models
ChatGPT/Claude/Gemini hosted outputs are not AQLEVON training harvest sources when their terms prohibit competitive-model development. They may be used only for external evaluation/product comparison where allowed.

## 5. Capability acquisition engines

### Engine A — Verified Teacher Distillation
Use Teacher Council to sample N candidates from legally usable local/open teachers. Keep only outputs that pass objective verifiers.

Artifact format:
`task -> teacher -> answer/tool trajectory -> checks -> verifier -> provenance -> accepted/rejected`.

### Engine B — Self-Verified Distillation (SVD)
Use unlabeled prompt pools. AQLEVON generates multiple candidates and filters them with a multi-stage verifier cascade. Only unanimous/high-confidence verified outputs become SFT targets.

Use self-verification only where it is independently calibrated. For executable domains, external verifiers dominate self-judgment.

### Engine C — Adaptive Executable Self-Play (AQLEVON-SPADE lane)
A separate Environment Designer creates executable Python/Gym-style environments near the learner's competence frontier.

Required gates:
- syntax/runtime validation;
- deterministic seed;
- solvability check;
- anti-duplicate check;
- environment provenance hash;
- no protected benchmark cloning.

The Agent learns in these environments. Difficulty adapts using regret/hint-gap style signals.

### Engine D — EnvFactory-style Tool World Synthesis
Generate stateful tool environments from authentic/open resources, synthesize natural multi-turn intents, and train multi-step tool use with robust executable rewards.

Use for R0-B tools and R0-G long-horizon state.

### Engine E — RLVR
Objective rewards for:
- math exact solvers;
- code tests/builds;
- function schema/execution;
- deterministic planning constraints;
- citation/source checks;
- structured data tasks;
- repository repair.

### Engine F — Verifiable Process Rewards
Do not reward only terminal success for long trajectories.
Where intermediate actions are objectively checkable, add turn/step-level rewards.

Examples:
- file localization before patch;
- test reproduction before fix;
- correct tool selection before tool result;
- citation evidence selection before final synthesis;
- constraint satisfaction at each planning step.

### Engine G — LongRLVR-style context grounding
For long-context tasks, reward evidence/chunk selection and grounding in addition to final answer correctness.

Target: avoid a model that answers correctly from parametric memory while ignoring supplied context.

### Engine H — Test-Time Scaling -> Distillation
At training-data generation time, spend more inference compute than we can afford at runtime:
- sample multiple candidates;
- search/rerank;
- verifier-guided best-of-N;
- prefix/branch search when justified.

Then distill the verified best trajectories back into the single-call release model.

Goal: move expensive inference-time intelligence into weights.

## 6. Coding/agentic frontier lane

AQLEVON should import recipes, not benchmark answers, from strong open SWE work.

High-value recipe components:
- agentic trajectory SFT;
- execution-grounded RL;
- repository navigation;
- LSP/code-graph tools;
- failure recovery;
- test-time verification/ranking;
- summary-based context management.

Training data must be disjoint from protected release benchmarks.

## 7. Continual-learning / anti-forgetting lane

Catastrophic forgetting is a first-class failure.

Research methods to test:
- SLoRA-style subspace denoising;
- soft/strict orthogonal LoRA initialization;
- PASs-style pathway preservation;
- continual merge-before-forget;
- replay from small private capability anchors;
- frozen base + isolated specialist adapters before consolidation.

Every specialist training run must execute a global regression suite before promotion.

## 8. Specialist composition: three tiers

### Tier 1 — Simple merge baselines
- weighted delta average;
- task arithmetic;
- TIES;
- DARE/TIES.

### Tier 2 — Conflict-driven merge
Use naive-merge failures as hard negative preference pairs and optimize a tiny set of merge coefficients, CoMerge-style.

This is a major V2 priority because it learns directly from interference instead of guessing fixed merge weights.

### Tier 3 — Dynamic LoRA experts (research only first)
Explore:
- LoRA-Mixer;
- LD-MoLE;
- CoMoL;
- HotMoE/GROLE-style learned routing.

Potential use:
- Research Brain dynamically composes coding/research/Arabic/tool experts.
- Periodically distill/router-trace the best compositions into a unified Release Brain.

Do not add runtime expert complexity to the public model until it proves net benefit after latency and memory costs.

## 9. AQLEVON Evolution Loop

```
Frozen benchmark + private holdouts
        ↓
Defect miner clusters failures
        ↓
Curriculum designer chooses lane
        ↓
[Teacher Council | SVD | SPADE | EnvFactory | RLVR]
        ↓
Objective verifier bank
        ↓
Clean training shard + provenance
        ↓
Specialist LoRA / delta
        ↓
Target eval + global regressions
        ↓
Keep / reject
        ↓
Conflict-aware specialist composition
        ↓
Consolidation training
        ↓
Full common-harness evaluation
        ↓
New AQLEVON checkpoint OR rejection
        ↓
Harder failure mining
        ↺
```

The loop is allowed to automate experiment generation, data generation, verifier generation, hyperparameter proposals and merge search. It is never allowed to promote itself without the frozen gates.

## 10. Curriculum allocation

Training budget should follow measured defects, not equal proportions.

Each evaluation cycle outputs a defect vector:
- coding repair;
- tool correctness;
- research/citation;
- Arabic/Darija;
- math/reasoning;
- long-context grounding;
- factuality/calibration;
- long-horizon state;
- multimodal;
- efficiency.

Allocate the next training batch to the largest high-value verified gaps while protecting existing strengths.

## 11. Arabic / Darija strategy

Do not train Arabic as translation only.

Separate specialists/strata:
- MSA reasoning;
- Moroccan Darija Arabic script;
- Arabizi;
- French/Darija code-switch;
- technical/coding language;
- administration/business;
- tool calling;
- culturally natural dialogue.

Use native Moroccan review for private holdouts. Evaluate semantic correctness and naturalness separately.

For future MoE research, investigate cross-lingual routing alignment: middle-layer task experts that generalize in English may need explicit alignment to Arabic/Darija rather than language-isolated experts.

## 12. Multimodal lane

Because Qwen3.8-27B is multimodal, create separate multimodal specialists instead of freezing vision forever once text R0 is stable:
- screenshot/UI reasoning;
- document/table understanding;
- visual coding/debugging;
- charts/diagrams;
- image-grounded tool tasks.

Multimodal data must have objective/grounded verification where possible.

## 13. Data flywheel

Sources, in priority order:
1. objective public datasets passing license/provenance gate;
2. synthetic executable tasks generated from open source material;
3. Teacher Council verified corrections;
4. AQLEVON's own verified failures;
5. human/native-review shards for hard subjective domains;
6. public product failures only after privacy, consent, de-identification and policy gates.

Never ingest user conversations by default.

## 14. Verifier hierarchy

Strongest to weakest:
1. executable ground truth / unit tests / exact solver;
2. deterministic schema/constraint/source validation;
3. multiple independent grounded verifiers;
4. calibrated learned verifier;
5. teacher/self-judge consensus.

Lower tiers may propose; higher tiers decide whenever available.

## 15. Test-time intelligence as a training tool

AQLEVON can temporarily use expensive search during R&D even if production cannot.

Use test-time scaling to discover:
- better solutions;
- better plans;
- better tool sequences;
- corrections to first-pass errors.

Distill verified results so the release checkpoint needs less inference compute.

Benchmark both:
- single-call model quality;
- full system quality under fixed compute budgets.

## 16. Compute strategy

Do not start with full 27B full-parameter training.

Order:
1. one-step LoRA/QLoRA probe;
2. tiny specialist smoke;
3. 4B/8B surrogate experiments for recipe search where architecture behavior transfers;
4. 27B specialist confirmation;
5. merge/consolidation;
6. only then large-scale transfer.

SPADE/agentic RL at 27B may require multi-GPU. Validate orchestration first on smaller compatible Qwen models.

## 17. Frontier recipe search

Create an experiment controller that treats training recipes as a search space:
- dataset mixture;
- adapter target modules;
- rank/alpha;
- curriculum ordering;
- reward weights;
- KL strength;
- GRPO/GSPO/DHPO-style optimizer choice where supported;
- sampling temperature;
- verifier budget;
- number of self-play candidates;
- merge coefficients.

Use successive halving / early stopping. Kill experiments quickly when target metrics do not move or regressions appear.

## 18. Promotion metric

Primary metric should not be leaderboard average alone.

Use **Cost per Verified Success (CVS)**:

`CVS = total serving/training-adjusted compute cost / number of correctly verified completed tasks`

Track alongside:
- pass@1;
- latency/TTFT;
- output tokens;
- GPU seconds;
- failure severity;
- calibration;
- regression count.

Goal: be stronger per verified task and per dollar, not merely larger.

## 19. Model-size ladder

### R0 Lab
Qwen3.8-27B.

### Edge
Distill successful R0 behaviors into smaller AQLEVON Edge models.

### Max
Transfer only proven recipes to a larger sparse/open base when license/compute allow.

### Future native AQLEVON architecture
Architecture R&D may combine independently reimplemented ideas such as hybrid sparse/linear attention, efficient index sharing, stronger MTP/speculative heads, expert routing and long-context mechanisms. This is a separate architecture-training program, not direct tensor merging.

## 20. Immediate execution priorities

P0. Preserve current base/harness/decontamination gates.
P1. Add SVD generator/filter lane to Teacher Council.
P2. Add SPADE-inspired executable environment generator in a sandbox.
P3. Add process-reward interfaces to verifier framework.
P4. Add long-context grounding reward format.
P5. Produce first R0-A coding specialist checkpoint.
P6. Produce R0-B tools specialist.
P7. Produce R0-D Arabic/Darija specialist.
P8. Run pairwise interference matrix.
P9. Baseline Task Arithmetic/TIES/DARE.
P10. Add CoMerge-style conflict dataset + learned merge coefficient experiment.
P11. Short consolidation training.
P12. Quantize only after BF16/FP16 release-gate pass.

## 21. What would be genuinely novel for AQLEVON

The novel system is not one paper copied verbatim. It is the integration:
- multi-teacher legal capability harvest;
- self-verified distillation;
- adaptive executable self-play;
- dense verifiable process rewards;
- long-context grounding rewards;
- defect-driven curricula;
- anti-forgetting specialist bank;
- conflict-driven model merging;
- test-time search distilled back into weights;
- cost-per-verified-success optimization;
- Arabic/Darija native specialization;
- public product failure loop under privacy gates.

This creates an AI-development engine that can keep generating new verified training signal as the model improves instead of exhausting a static dataset.

## 22. Release claim gate

No model is marketed as superior to named closed competitors until:
- common dated versions are fixed;
- task/tool/context budgets are matched;
- external + private benchmarks are run;
- contamination audit passes;
- raw outputs and costs are retained;
- reliability/latency regressions are included.

Until then, report exact per-domain measurements only.