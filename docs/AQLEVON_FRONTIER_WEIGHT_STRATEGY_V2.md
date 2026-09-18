# AQLEVON Frontier Weight Strategy V2 — Capability Genome & Evolutionary Weight Foundry

**Status:** ACTIVE RESEARCH + EXECUTION STRATEGY  
**Date:** 2026-09-18  
**Supersedes/extends:** `AQLEVON_FRONTIER_WEIGHT_STRATEGY_V1.md`  
**Objective:** produce genuinely new AQLEVON checkpoints by combining verified capabilities—not incompatible tensors—using a repeatable evolutionary training/merging loop.

## 1. Non-negotiable truth boundary

AQLEVON may target frontier competitiveness, but it must not claim to be stronger than ChatGPT, Claude, Kimi, DeepSeek, GLM, Qwen-Max, or any other frontier system until it wins a predeclared broad common-harness evaluation with acceptable reliability, latency, cost, and contamination evidence.

A new AQLEVON checkpoint exists only after parameters actually change, an artifact is saved, SHA256 is recorded, lineage/data/licenses are documented, and the checkpoint is evaluated against the untouched base.

## 2. What "collecting the strongest weights" actually means

Directly splicing weights from unrelated architectures is rejected. DeepSeek V4, GLM-5.2, Kimi K3, gpt-oss-120b and Qwen3.8 differ in architecture, dimensions, expert layout, tokenization and training conventions.

AQLEVON instead collects **capability genes** through:
1. AQLEVON-owned same-base LoRA/full-delta specialists.
2. Legally usable local open-weight teachers and verified behavioral distillation.
3. Executable RL/RLVR with objective rewards.
4. Self-play curriculum generation with hard verifiers.
5. Same-base task vectors and LoRA/delta merging.
6. Conflict-aware/evolutionary merge optimization.
7. Architecture/training-recipe transfer from incompatible models without copying their tensors.
8. Continued pretraining or world-model warmup when evidence shows a weight-level deficit cannot be solved by adapters alone.

## 3. Canonical laboratory base

Base remains:
`Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

Reason:
- Apache-2.0 commercial-friendly base.
- 27B scale is large enough to expose real capability while still allowing iterative LoRA/QLoRA research.
- Existing AQLEVON topology lock and one-step probe target this exact family.
- Native hybrid architecture includes 48 Gated DeltaNet layers and 16 full-attention layers; adapter targeting must cover both.

Do not silently switch base, precision, tokenizer, template or revision after an OOM. An OOM is a result.

## 4. Capability Genome abstraction

Every accepted specialist becomes a **gene** with immutable metadata:
- gene ID/version;
- exact ancestral base + revision;
- domain and objective;
- trainable modules;
- dataset shards + hashes + licenses;
- teacher/model provenance if used;
- verifier type and version;
- training code commit;
- seed/hardware/hyperparameters;
- standalone target-domain gain;
- global regression vector;
- contamination scan result;
- artifact SHA256;
- merge eligibility.

A gene is `PROMOTION_ELIGIBLE` only if it improves its target capability and does not exceed predeclared regression limits.

## 5. Teacher-specific branches — no teacher soup

New evidence from Merge-of-Thought Distillation shows that the best teacher depends on the student and dataset, and naive multi-teacher unions are not reliably optimal. AQLEVON therefore creates teacher-specific same-base branches instead of mixing all teacher outputs into one SFT corpus.

For a domain such as coding:
- branch DS: verified examples from local DeepSeek V4 teacher;
- branch GLM: verified examples from local GLM-5.2 teacher;
- branch OSS: verified examples from local gpt-oss-120b teacher;
- branch SELF: AQLEVON self-play + executable corrections;
- branch KIMI only when license/use conditions are satisfied.

Each branch is evaluated separately. Only winning branches enter the merge tournament. After a winning merge, run short consolidation training.

Research extension: test the 2026 soft-prompt privileged-context multi-teacher method once Qwen3.8 soft-prompt support is topology-verified. It is not the default until reproduced on the AQLEVON base.

## 6. R0 specialist genes

- **R0-A Coding/Agentic:** repo navigation, inspect-plan-edit-test-recover, minimal diffs, terminal recovery, multi-round coding.
- **R0-B Tools/Function Calling:** schema choice, no-call/call, parallel calls, multi-step, malformed/error recovery, exact arguments.
- **R0-C Research/Evidence:** long-horizon browsing, evidence ledger, claim-source entailment, calibrated abstention.
- **R0-D Arabic/Darija:** MSA, Moroccan Darija Arabic script, Arabizi, French/English code-switch, technical/tool language.
- **R0-E Adaptive Reasoning:** direct/fast/deep/max; accuracy-vs-token efficiency.
- **R0-F Factuality/Calibration:** supported/unsupported/abstain/tool-required pairs and calibration.
- **R0-G Long-Horizon State:** goal ledger, constraints, completed/failed/pending, recovery.
- **R0-H Minimal Intervention:** smallest verified diff, protected files, scope discipline.
- **R0-I Multi-Teacher/Adversarial:** verified failure harvesting across all domains.
- **R0-J Long-Context Evidence:** evidence extraction and reasoning over long contexts, trained with dense evidence rewards when possible.
- **R0-K Environment World Model:** predict environment next state/action consequence from allowed trajectories before policy RL.

## 7. Coding/agentic priority — executable environments over static demos

Terminal-Universe (2026) shows a high-leverage recipe: reconstruct reusable executable environments from public agent trajectories, then generate new tasks across breadth and multi-round depth. Its paper reports that SFT on reconstructed environments improved Qwen3.5-27B substantially on terminal/coding benchmarks. This is unusually transferable to AQLEVON-27B because the scale/family is close.

AQLEVON action:
1. audit Terminal-Universe code/data licenses and contamination boundaries;
2. reconstruct environments only from approved sources;
3. generate new repository tasks on those environments;
4. execute tests/builds to verify each task and answer;
5. keep release benchmarks isolated;
6. train R0-A first because executable verification provides the cleanest reward.

TerminalTraj-like executable trajectory corpora are candidate sources after the same license/decontamination gate.

## 8. Self-evolving curriculum — AQLEVON Curriculum Forge

Absolute Zero demonstrated a self-play paradigm where the model proposes code/reasoning tasks and a code executor validates both task and solution.

AQLEVON Curriculum Forge should:
- generate tasks just beyond current measured capability;
- require an objective verifier before admission;
- maintain difficulty bands;
- enforce task-style diversity;
- reject duplicates and benchmark-near-duplicates;
- track which gene/checkpoint failed each task;
- regenerate adversarial variants from real failures;
- use curriculum gain, not raw task count, as the objective.

Self-play augments curated/public data; it does not replace independent benchmarks or human/native review.

## 9. RL stack — choose algorithm by failure mode

AQLEVON should not declare one RL algorithm universally best.

### Dense 27B reasoning/code baseline
- DAPO/GRPO-class objective as a reproducible baseline with executable rewards.
- DAPO is attractive because it publishes a full large-scale recipe and dynamic sampling/clip strategy.

### Stable sequence-level RL
- Test GSPO. Sequence-level importance ratios and clipping are particularly relevant for future MoE AQLEVON, and GSPO was reported to stabilize MoE RL.

### Agentic multi-turn
- Test sub-sequence/Think-Action optimization ideas such as Workflow-R1 GSsPO, where the optimization unit matches semantic action cycles rather than an entire trajectory.

### Long-context evidence
- R0-J should evaluate EAPO-style evidence rewards: reward evidence extraction quality separately from final-answer correctness so lucky guesses do not receive full credit.

RL promotion rule: no algorithm graduates because a paper reports a higher score. It must beat the AQLEVON baseline under the same model/data/compute budget.

## 10. World-model warmup before long-horizon agent RL

Qwen-AgentWorld provides a useful recipe: CPT -> SFT -> GSPO RL on environment next-state prediction across MCP/Search/Terminal/SWE/Android/Web/OS, with the model card explicitly stating no external API outputs were used in its training pipeline.

AQLEVON should evaluate a separate R0-K branch:
1. collect allowed environment transition trajectories;
2. train prediction of the next observable environment state conditioned on state/history/action;
3. evaluate OOD next-state fidelity;
4. use the accepted world-model checkpoint or adapter to initialize agent policy post-training;
5. compare against policy-RL-from-base to determine whether warmup improves sample efficiency and long-horizon stability.

Do not merge AgentWorld tensors into Qwen3.8-27B; transfer the recipe/task structure only unless exact compatibility is proven.

## 11. Deep research gene

OpenResearcher releases a 96K long-horizon research-trajectory pipeline generated with local gpt-oss-120b plus a self-built retrieval corpus; QUEST already provides synthetic deep-research SFT/RL recipes in the AQLEVON registry.

R0-C/R0-J plan:
- audit OpenResearcher dataset/retriever/source licenses and benchmark contamination;
- quarantine until audit passes;
- use evidence-ledger labels: claim -> source -> support span -> status;
- reward citation entailment and evidence retrieval, not verbose browsing;
- build a local retrieval corpus so training does not depend on paid search APIs;
- preserve BrowseComp/GAIA-style release evaluation separation.

Reported benchmark claims from project authors are treated as claims until AQLEVON reproduces them.

## 12. Arabic and Moroccan Darija as a frontier differentiator

AQLEVON should aim to be unusually strong in MSA + Moroccan Darija while preserving general capability.

Data policy:
- native-quality Darija > translated English;
- include Arabic script, Arabizi, French/English code-switch, technical/coding/tool vocabulary;
- build Arabic function-calling and agent trajectories, not just chat;
- create a private Moroccan-native holdout not exposed to training generation;
- keep DialectalArabicMMLU-style data benchmark-only by default;
- any dataset generated through a hosted model with terms restricting competitive-model development is quarantined until downstream rights are clearly established.

AryWiki-Instruct is high-value as a research reference because it contains 46,590 Darija QA pairs, but its generation used Gemini-2.5-Flash; therefore it is not auto-admitted into AQLEVON training. Legal/provenance review is required.

## 13. Merge Tournament — 2026 generation

Baseline tournament:
1. simple weighted interpolation;
2. Task Arithmetic;
3. TIES;
4. DARE/TIES;
5. isotropic/common+task-specific-subspace merging;
6. WUDI/FroM-style data-free candidates where implementation is available and validated;
7. TSPA for multi-LoRA alignment;
8. ENMP to prune negative LoRA modules before merge;
9. EvoGM evolutionary coefficient search;
10. CoMerge conflict-driven coefficient optimization using naive-merge failures as hard negatives.

Important new law: **a merge method is not selected globally in advance.** The winner is chosen per gene set by private-development evidence.

Private dev data may tune merge coefficients/module masks. Public/release benchmarks may never tune them.

## 14. Layer/module interference atlas

Before expensive merge search, construct an interference atlas:
- adapter A alone score vector;
- adapter B alone score vector;
- A+B simple merge score vector;
- module/layer contribution ablation;
- cosine/sign conflict statistics for deltas;
- negative-module candidates;
- targeted regression examples.

This atlas guides TSPA/ENMP/EvoGM/CoMerge search and prevents wasting GPU on obviously destructive combinations.

## 15. Qwen3.8 hybrid-architecture adapter rule

Qwen3.8-27B has 64 language layers: 48 Gated DeltaNet and 16 full attention. Community evidence confirms that ordinary `q_proj/k_proj/v_proj/o_proj` targeting touches only the full-attention layers.

AQLEVON candidate targets remain:
`q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj,in_proj_qkv,in_proj_z,in_proj_b,in_proj_a,out_proj`

Default exclusions remain vision tower, embeddings/lm_head, MTP, norms and bias unless a dedicated experiment explicitly enables them.

Any external LoRA that does not cover the intended topology must be scored accordingly; “Apache-2.0” alone is not enough to make it a useful donor.

## 16. Community Qwen3.8 weights policy

The current Qwen3.8-27B tree contains many adapters/fine-tunes/merges, but AQLEVON will not consume them blindly.

Classify every community artifact:
- `DIRECT_CANDIDATE`: exact base/revision, clean license/data provenance, compatible targets, contamination checked.
- `RECIPE_ONLY`: useful technique/training configuration, but weights/data provenance insufficient.
- `QUARANTINE`: incomplete source/license/teacher provenance.
- `REJECT`: proprietary-hosted-model distill with unclear/forbidden rights, benchmark leakage, incompatible base, or unverifiable artifact.

Observed examples:
- community code LoRAs can be useful recipe references but may target only standard attention + MLP and miss Gated DeltaNet projections;
- some coding-distilled releases explicitly have incomplete license/data placeholders -> quarantine;
- small full-topology LoRA examples confirm correct hybrid targets but also show factual confabulation under aggressive tiny-data SFT -> useful topology example, not a knowledge donor;
- random community merge soups are never source-of-truth for AQLEVON lineage.

## 17. Strong teachers and commercial gates

Current teacher/reference policy:
- DeepSeek-V4-Pro: MIT -> strong local teacher/reference candidate.
- GLM-5.2: MIT -> strong local teacher/reference candidate.
- gpt-oss-120b: Apache-2.0 -> strong local teacher, reasoning-control/tool reference.
- Kimi-K3: custom license -> allowed only with recorded conditions; MaaS revenue threshold and display conditions require ongoing compliance review.
- Qwen3.8-Flash-Next: research/architecture reference only for AQLEVON commercial product unless a separate Qwen commercial license is obtained, because its current license explicitly requires a separate license for commercial MaaS or AI Work Assistant use.
- Closed hosted GPT/Claude/Gemini: evaluation/reference only where permitted; no competitive training harvest.

## 18. Future AQLEVON architecture research

If AQLEVON eventually trains a new architecture rather than only post-training Qwen3.8, investigate independently implemented ideas from current sparse frontier systems:
- low active-parameter MoE;
- sparse/indexed attention for 1M context;
- Gated DeltaNet + sparse attention hybrids;
- gated residual pathways;
- MTP/speculative decoding;
- environment/world-model auxiliary objectives;
- adaptive reasoning effort.

Architecture transfer does not mean copying restricted weights.

## 19. Evolutionary Weight Foundry loop

```
Frozen Base B0
  -> capability defect map
  -> generate/audit training candidates
  -> teacher-specific branches
  -> objective verification
  -> train specialist genes
  -> standalone eval + regression
  -> reject or promote gene
  -> interference atlas
  -> merge tournament
  -> consolidation SFT/RL
  -> broad eval + contamination scan
  -> retain winner
  -> Curriculum Forge generates harder verified failures
  -> repeat
```

The process should be automated enough that AI proposes experiments, data and merge candidates, while deterministic gates control admission and promotion.

## 20. Novelty hypothesis — not a claim

The combination of:
- defect-first gene creation;
- teacher-specific branch distillation;
- objective-verifier admission;
- self-evolving curriculum;
- world-model warmup;
- layer/module interference atlas;
- evolutionary merge tournament;
- evidence-aware RL;
- private-development decontamination gates;
- economics-aware deployment/Edge/Commons routing

is a strong systems-level research direction for AQLEVON. Do not call it scientifically novel until a broader literature review and prior-art search confirms that an equivalent end-to-end pipeline does not already exist.

## 21. Execution order from today

### G0 — Genome infrastructure (can be done without GPU)
- executable source/weight admission registry;
- capability-gene schema;
- merge-tournament manifest;
- provenance/license/contamination gates;
- frozen eval vector schema.

### G1 — Real training proof
- run the existing one-step Qwen3.8-27B probe on real GPU;
- prove parameter delta + reload + artifact hash;
- no long run before this passes.

### G2 — R0-A coding gene
- prioritize executable environment curriculum;
- SFT first, then verifier-driven RL if compute permits;
- create separate teacher-specific branches.

### G3 — Merge science
- after at least two independently accepted same-base genes exist, build interference atlas and run baseline merge tournament;
- only then test TSPA/ENMP/EvoGM/CoMerge.

### G4 — Research + Arabic/Darija + long-context genes
- build R0-C/R0-D/R0-J with provenance/native-quality gates.

### G5 — Curriculum Forge + world-model experiment
- introduce self-play and environment-state prediction only after the base training/evaluation loop is proven reproducible.

### G6 — AQLEVON-27B-R0 candidate
- controlled consolidation;
- full BF16 eval;
- contamination audit;
- artifact SHA/license/data manifest;
- quantize and independently re-evaluate.

## 22. Release rule

No checkpoint becomes `AQLEVON-27B-R0` until:
1. real parameters changed;
2. checkpoint reloads;
3. artifact SHA256 recorded;
4. lineage/data/license manifest complete;
5. target-domain improvements reproduced;
6. global regressions within frozen limits;
7. protected benchmark contamination absent;
8. merge coefficients were never tuned on release test sets;
9. BF16/FP16 winner was frozen before quantization;
10. quantized serving artifact separately passes required evals.

## 23. Current truth

As of 2026-09-18, the Evolutionary Weight Foundry strategy and supporting research exist, but **no real AQLEVON-27B trained checkpoint has yet been produced**. The existing one-step training probe has not yet executed on a real 27B GPU. This boundary must remain explicit until the first checkpoint artifact exists.

## 24. Primary research sources used for V2

- Merge-of-Thought Distillation — arXiv:2509.08814
- One Student, Many Teachers — arXiv:2607.18293
- DAPO — arXiv:2503.14476
- GSPO — arXiv:2507.18071
- Absolute Zero — arXiv:2505.03335
- Workflow-R1 / GSsPO — arXiv:2602.01202
- EAPO (long-context evidence) — ACL 2026 / arXiv:2601.10306
- Terminal-Universe — arXiv:2609.04148
- Qwen-AgentWorld-35B-A3B — Qwen model card / arXiv:2606.24597
- OpenResearcher — open repository and dataset
- No Task Left Behind / Isotropic Merge — arXiv:2502.04959
- WUDI-Merging — arXiv:2503.08099
- MergeBench — arXiv:2505.10833
- EvoGM — arXiv:2605.29295
- ENMP — arXiv:2604.17753
- TSPA — ACL Findings 2026
- CoMerge — arXiv:2609.02273
- Qwen3.8-27B official model repository/tree
- Qwen3.8-Flash-Next current Qwen Community License 1.0
- DeepSeek-V4-Pro MIT license
- GLM-5.2 MIT license
- gpt-oss-120b Apache-2.0 license
- Kimi-K3 current custom license