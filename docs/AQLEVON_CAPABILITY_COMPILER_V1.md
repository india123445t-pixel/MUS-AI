# AQLEVON Capability Compiler V1

**Status:** ACTIVE FRONTIER RESEARCH PROGRAM
**Date:** 2026-09-18
**Objective:** Turn verified capabilities from open models, data, tools, verifiers, and AQLEVON self-play into genuinely new AQLEVON weights with measurable gains and controlled regressions.

## 1. Core idea
AQLEVON should not try to literally splice incompatible frontier checkpoints. Instead it should operate a **Capability Compiler**:

`defect -> task/data synthesis -> strongest legal teacher(s) -> objective verifier -> specialist training -> RLVR/process rewards -> geometry analysis -> compatible merge/upcycle -> consolidation -> broad regression gate -> release`

The compiler ingests *capabilities*, not arbitrary tensors.

## 2. Why this is stronger than naive model merging
Modern open frontier models use different architectures, tokenizers, sparse-expert layouts, attention mechanisms and post-training recipes. DeepSeek-V4-Flash, GLM-5.2, Kimi-K3, gpt-oss-120b and Qwen3.8 cannot be treated as directly interchangeable weight tensors.

The correct transfer mechanisms are:
- behavior distillation from legally usable local open-weight teachers;
- same-base LoRA / delta specialists;
- RLVR and verifiable process rewards;
- conflict-aware same-base model merging;
- continued pretraining where justified;
- sparse/MoE upcycling when dense merging becomes the bottleneck;
- architecture transfer into a later AQLEVON generation.

## 3. Frontier teacher map — 2026-09-18

### DeepSeek-V4-Flash-0731
Use as high-value teacher/reference for:
- coding;
- tool use;
- agentic recovery;
- long context;
- reasoning.

Current official HF metadata reports MIT license. DeepSeek-V4 uses hybrid compressed/sparse attention and million-token-context engineering. Do not merge its tensors into Qwen; distill verified behavior and study architecture separately.

### GLM-5.2
Use for:
- long-horizon coding;
- 1M-context behaviors;
- research/planning;
- adaptive reasoning effort.

Official model card reports MIT license and IndexShare-based sparse attention improvements for long context.

### gpt-oss-120b
Use for:
- reasoning-control policies;
- tool/agent trajectories;
- low/medium/high reasoning-effort behavior;
- structured outputs.

Apache-2.0. 117B total / ~5.1B active according to official model card. Treat Harmony-format requirements carefully when harvesting local teacher outputs.

### Kimi-K3
Use for:
- long-horizon coding;
- multimodal agentic work;
- research/knowledge work;
- long-context task design;
- architecture inspiration.

Official model card: ~2.8T total, ~104B active, 1M context, KDA + Gated MLA + Stable LatentMoE. Custom Kimi K3 License must be rechecked before any commercial derivative dependency.

### Qwen3.8-27B
Canonical R0 laboratory base unless a later owner-approved base change passes the full base-swap gate.
- Apache-2.0.
- Same-base specialists are trained here first.
- All merge experiments require exact ancestry/revision match.

### Qwen3.8-2.4T-A95B
Later-stage frontier research target only. Custom Qwen3.8-Max license must be reviewed before commercial adoption.

## 4. Capability Compiler stages

### C0 — Frozen baseline
Evaluate untouched base on the exact common harness before any training.
Store raw outputs and hashes.

### C1 — Defect miner
Cluster failures by root cause, not by benchmark name:
- missing knowledge;
- reasoning failure;
- tool selection;
- bad argument formation;
- long-horizon state loss;
- coding/repository navigation;
- factuality/citation failure;
- Arabic/Darija weakness;
- verbosity/overthinking;
- premature stopping;
- multimodal grounding.

No training shard is created merely because a benchmark score is low.

### C2 — Evolutionary Verifiable Data Factory
Adopt the 2026 direction demonstrated by automated evolutionary verifiable-data synthesis:
1. start from small clean seeds;
2. generate harder/diverse tasks;
3. generate verification artifacts together with the task;
4. test verifier validity;
5. reject weak/trivial/non-discriminative checks;
6. retain only executable/checkable examples;
7. mutate successful examples to harder variants.

Use this first for coding, tools, math, agentic environments, structured research and planning constraints.

### C3 — Teacher tournament, not teacher averaging
For each admitted task:
- route to multiple *legally usable local open-weight* teachers only where useful;
- collect independent candidate answer/patch/action trajectories;
- do not choose by majority vote;
- choose by objective verifier/test/source support;
- store winning and failing attempts where licenses/provenance permit;
- turn the student-teacher gap into correction data.

A weaker teacher can still contribute a unique valid solution; a stronger teacher that fails the verifier contributes nothing to that example.

### C4 — Specialist Forge
Train same-base specialists independently:
- R0-A coding;
- R0-B tools;
- R0-C research;
- R0-D Arabic/Darija;
- R0-E reasoning-effort;
- R0-F factuality;
- R0-G long-horizon state;
- R0-H minimal intervention;
- R0-I adversarial multi-teacher recovery.

Every specialist must beat base on its target domain and stay inside global regression limits.

### C5 — RLVR + Verifiable Process Rewards
Do not rely only on SFT imitation.

Use outcome-level RLVR where final answers are objectively checkable.
Use **process-level verifiable rewards** where intermediate steps/actions can be checked, especially:
- repository edits;
- shell/tool actions;
- constraint planning;
- multi-step search;
- agent state transitions.

2026 research on Verifiable Process Rewards indicates dense verifier-grounded rewards can improve long-horizon credit assignment over outcome-only rewards when intermediate oracles are reliable.

For knowledge-intensive/research domains, follow the Knowledge-to-Verification direction: synthesize checkable claims/questions and verify reasoning/evidence instead of treating a subjective LLM judge as truth.

### C6 — Geometry Analyzer
Before any merge, measure specialist deltas relative to exact base:
- cosine similarity between task vectors;
- sign conflict rate;
- support overlap;
- layer-wise norm distribution;
- singular-vector/subspace overlap;
- gradient/eval interference on cross-domain holdouts.

The merge algorithm is chosen from measured geometry, not fashion.

### C7 — Merge Tournament
Run a predeclared tournament, at minimum:
1. weighted linear merge;
2. Task Arithmetic;
3. TIES;
4. DARE/TIES where validated;
5. CAT-style conflict trimming;
6. adaptive projective-gradient / shared-subspace approach;
7. SCORE-style subspace conflict resolution where applicable;
8. CT-Merging / LoRA-aware consensus-subspace approach for compatible adapters.

Important research finding: 2026 work shows some independently trained RL specialists can have near-orthogonal task vectors, in which case simple averaging can perform as well as sophisticated merging. Therefore complexity must be justified by measured interference.

### C8 — If merging fails: do not force it
If specialists strongly interfere, choose one of three branches:

**Branch A — Dynamic adapter composition**
Useful for research/product experiments, but not the preferred final one-checkpoint release.

**Branch B — MoE / Expert Upcycling**
Instead of compressing all expertise into one dense FFN, upcycle the base or specialist experts into a sparse MoE and continue pretraining/post-training. 2026 expert-upcycling work reports compute savings relative to training larger MoE systems from scratch.

**Branch C — Consolidation distillation**
Run the specialist ensemble/MoE as teacher and distill back into a deployable dense or smaller sparse student.

### C9 — Merge consolidation
Never release a raw merge immediately.
Perform a short post-merge consolidation stage using:
- replay from each capability domain;
- hard conflict examples found during merge evaluation;
- RLVR on objective tasks;
- anti-forgetting replay;
- calibration/factuality examples.

Then reevaluate from scratch.

### C10 — MoE-to-dense deployment research
2026 research demonstrates pruning/selecting MoE experts and distilling them into a dense architecture can outperform matched dense pruning in controlled studies. This gives AQLEVON a future path:

`large sparse research brain -> distilled dense/edge serving brain`

This is strategically valuable because frontier training and cheap serving need not use the same architecture.

## 5. Two-brain research architecture

AQLEVON should ultimately investigate two related weight families:

### AQLEVON Frontier
- sparse/MoE-capable;
- maximum coding/research/agentic quality;
- used for premium cloud / teacher generation / hard tasks.

### AQLEVON Edge
- dense or compact sparse student;
- distilled from Frontier + verified task corpus;
- local/browser/consumer-GPU tasks;
- routing, rewrite, summarization, translation, simple coding, memory compression.

Both remain AQLEVON product identity; internal router selects the cheapest sufficient brain.

## 6. The unprecedented part: Capability Flywheel

AQLEVON's strongest moat is not one training run. It is a continuously compounding verified-data system:

1. real users generate anonymized/consented failure *types* and evaluation signals;
2. defect miner clusters them;
3. AI generates new synthetic tasks without copying private content;
4. Teacher Council attacks those tasks;
5. verifiers select truth;
6. specialist gets trained;
7. RLVR/process rewards strengthen it;
8. geometry-aware merge/upcycle integrates the gain;
9. untouched holdouts verify improvement;
10. harder synthetic tasks are generated from remaining weaknesses.

The system should become better because it learns from *verified failure structure*, not because it stores users' raw conversations indiscriminately.

## 7. Data hierarchy

Priority order:
1. executable synthetic tasks generated under our control;
2. permissively licensed public training data after provenance/decontamination;
3. local open-weight teacher outputs allowed by license;
4. self-play/adversarial tasks;
5. human-native Arabic/Darija review for quality-critical slices.

Never admit:
- protected benchmark solutions;
- unknown-license corpora;
- hosted proprietary-model outputs prohibited for competitive training;
- private user data without an explicit policy/consent basis;
- unverifiable long CoT dumps merely because they look intelligent.

## 8. Arabic/Darija frontier strategy

Do not train Arabic by translation volume alone.
Build native competence across:
- MSA;
- Moroccan Darija in Arabic script;
- Arabizi;
- French/Arabic and English/Arabic code switching;
- coding/tool calls in Arabic;
- business/admin/support language;
- long-form reasoning;
- culturally natural dialogue.

The 2025 survey of Arabic post-training datasets identifies gaps in task diversity, documentation, annotation quality and robustness; AQLEVON should treat those gaps as an opportunity and maintain a private native-quality holdout.

## 9. Architecture ideas for AQLEVON v2+

Do not transplant tensors, but investigate independently:
- DeepSeek-V4 hybrid compressed/sparse attention, low-precision KV and long-context efficiency;
- GLM-5.2 IndexShare / sparse-attention compute reuse;
- Kimi-K3 KDA, Attention Residuals, Stable LatentMoE and 1M-context multimodal design;
- gpt-oss configurable reasoning effort and sparse activation;
- expert upcycling to expand capacity without starting from random initialization;
- MTP/speculative decoding co-design for serving efficiency.

Any architecture change belongs to AQLEVON v2 research, not R0 weight merging.

## 10. Promotion criteria

A candidate capability/merge is retained only when:
- target capability improves reproducibly;
- broad regressions remain inside predeclared limits;
- provenance and license are clean;
- contamination scan passes;
- gain survives at least one held-out dataset not used in recipe selection;
- cost/latency impact is measured;
- checkpoint is reproducible from manifest.

A method is not adopted because a paper reports SOTA on another architecture.

## 11. Immediate execution sequence

1. Finish frozen untouched-base benchmark on Qwen3.8-27B.
2. Execute the existing one-step training probe on a compatible GPU.
3. Build the Evolutionary Verifiable Data Factory MVP for coding/tools first.
4. Add VPR-capable trajectory schema to verifiers.
5. Produce R0-A coding specialist.
6. Produce R0-B tools specialist.
7. Record task-vector geometry between them.
8. Run merge tournament (linear / TIES / CAT / projective / subspace methods as implementable).
9. Short consolidation + RLVR.
10. Add R0-C research and R0-D Arabic/Darija.
11. If merge interference grows, begin MoE-upcycling experiment rather than forcing dense soup.
12. Build AQLEVON Edge distillation track only after Frontier specialist quality is real.

## 12. Research evidence snapshot

High-value 2025–2026 research incorporated into this program:
- Automated Evolutionary Verifiable Data Synthesis (ACL 2026): task-agnostic synthesis of problems, candidate solutions and executable verification artifacts; reported improvements on LiveCodeBench and AgentBench-OS.
- Knowledge-to-Verification (ACL 2026): extends RLVR toward knowledge-intensive domains with automated verifiable-data synthesis and reasoning verification.
- Verifiable Process Rewards for Agentic Reasoning (2026): dense objectively checkable process rewards for long-horizon credit assignment.
- ICLR 2026 RLVR analysis: evidence that RLVR can expand reasoning boundaries rather than merely reshuffle sampling probability.
- CAT Merging (ICML 2025): conflict-aware task-vector trimming.
- Adaptive Projective Gradient Descent merging (ICML 2025): shared-subspace constrained model merging.
- SCORE (CVPR 2026): subspace-conflict-resolution via shared orthogonal basis.
- CT-Merging (2026): consensus directions and task-level scaling for LoRA adapter merging.
- 2026 task-vector geometry work on AppWorld: merging can match joint RL when learned deltas are near-orthogonal; sophisticated merge rules are not automatically better.
- Expert Upcycling (2026): increase MoE expert capacity from a trained checkpoint while preserving active compute and reducing training cost relative to fixed-size alternatives in reported experiments.
- MoE-to-Dense Distillation (2026): diversity-aware expert selection + distillation as a deployment compression path.

## 13. Hard truth boundary

The goal is to compete with frontier closed systems. No claim of being stronger than ChatGPT, Claude, Kimi, DeepSeek or GLM is allowed until AQLEVON passes a dated, common, externally auditable harness with comparable tools/context/effort.

The fastest path to frontier quality is not pretending we already have it; it is building a compiler that makes every verified failure produce a better training signal than the previous generation.