# AQLEVON Frontier Weight Strategy V4 — Two-Scale Evolutionary Foundry

**Status:** ACTIVE RESEARCH / EXECUTION STRATEGY  
**Date:** 2026-09-18  
**Extends:** V3 Stable Core + Capability Genome + Expert Mesh

## 1. Mission

AQLEVON will not be built by randomly combining unrelated frontier tensors. The objective is to accumulate verified capabilities into AQLEVON-owned checkpoints through a repeatable foundry:

**measure defect -> generate/audit data -> train same-base gene -> hard verification -> regression gate -> merge/route -> consolidate -> retest -> scale only proven recipes.**

A claim that AQLEVON is stronger than any frontier product is forbidden until it wins a frozen common-harness evaluation with acceptable reliability, latency, cost, provenance and contamination evidence.

## 2. New V4 decision: Two-Scale Weight Foundry

AQLEVON now has two explicit weight scales.

### Scale A — AQLEVON-27B Lab/Core

Canonical laboratory base:
`Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

Role:
- rapid capability experiments;
- BF16 LoRA / specialist-gene training;
- low-cost inference product path;
- merge science;
- self-evolution experiments;
- reproducible ablations.

The 27B line is not treated as the final ceiling of AQLEVON.

### Scale B — AQLEVON-Max Frontier Target

Frontier transfer target:
`Qwen/Qwen3.8-2.4T-A95B`

Official model card currently reports:
- 2.4T total parameters;
- 95B activated parameters;
- 92 layers;
- 23 repeated hybrid blocks;
- 512 experts;
- 10 routed + 1 shared expert activated;
- 262,144 native context;
- extensibility to roughly 1,010,000 tokens.

This model uses the `qwen3_5_moe_text` family and is not tensor-shape compatible with the dense 27B laboratory model. Therefore **27B LoRA/adapters never transfer directly to A95B**.

What transfers upward:
- verified training data;
- curriculum;
- reward design;
- teacher branch selection;
- verifier stack;
- failure corpus;
- hyperparameter/optimization lessons;
- evaluation gates.

A95B training is attempted only after the recipe is Pareto-positive on 27B and the compute budget is explicitly approved.

## 3. Commercial license watch for frontier target

The current Qwen3.8-Max license permits use, modification, derivatives, deployment and hosting, subject to conditions. It adds UI-attribution requirements at very large scale and a separate-license requirement for commercial MaaS/AI Work Assistant use after the stated aggregate revenue threshold.

AQLEVON therefore treats A95B as **commercially usable with an ongoing compliance watch**, not as Apache-2.0. License terms must be snapshotted again before every commercial release derived from it.

## 4. Capability Genome V4

Genes remain independently trained and evaluated before consolidation:
- R0-A coding/agentic
- R0-B tool use
- R0-C research/citations
- R0-D Arabic/Darija
- R0-E adaptive reasoning effort
- R0-F factuality/calibration
- R0-G long-horizon state
- R0-H minimal intervention
- R0-I multi-teacher/adversarial
- R0-J long-context evidence
- R0-K environment world model
- **R0-L self-evolving curriculum**

R0-L is new as a first-class gene instead of being hidden inside multi-teacher training.

## 5. Self-Evolution Arena

AQLEVON will combine the strongest transferable lessons from current self-evolution research without blindly copying code or data.

### Agent0
Apache-2.0 project. Use as a recipe reference for tool-integrated challenger/executor co-evolution.

### R-Zero
Strong challenger/solver zero-data result. Current repository audit did not surface a clear license; therefore use the paper/idea as research reference only until licensing is confirmed.

### Dr. Zero
Useful search-agent self-evolution / HRPO reference, but the repository explicitly states a non-commercial license. AQLEVON may study the idea; code is not admitted into the commercial stack without separate permission.

### R0-L hard law
Self-generated data is not automatically trusted.

Every task admitted from self-evolution requires:
- objective/external verifier;
- novelty/dedup scan;
- benchmark-distance scan;
- reproducible environment where relevant;
- provenance + hash;
- difficulty-band metadata;
- regression holdout.

LLM self-judgment alone can never make an example training-eligible.

## 6. Frontier teachers are capability sources, not tensor donors

Current high-value local/open-weight teachers:
- DeepSeek-V4-Pro — MIT; strong coding/reasoning teacher/reference.
- GLM-5.2 — MIT; long-context/long-horizon reference with 1M-context emphasis.
- gpt-oss-120b — Apache-2.0; reasoning-control/tool teacher candidate.
- Kimi-K3 — conditional custom license; long-horizon/multimodal teacher/reference after compliance review.

The teacher branch law remains:
`B0 -> Gene_teacher_A`, `B0 -> Gene_teacher_B`, `B0 -> Gene_SELF`.

Do not create one undifferentiated teacher soup. Evaluate branches independently, then merge only winners.

## 7. Community checkpoints remain evidence-first

A community Qwen3.8 coding-distilled checkpoint currently advertises large-scale coding distillation, but its own model card says exact license inheritance, dataset composition/sourcing, training details and hardware still need verification. AQLEVON classifies it as **QUARANTINE / recipe reference only** until that chain is complete.

No community weight enters the foundry merely because it has a high benchmark claim.

## 8. Merge science V4

The merge tournament remains gene-set specific.

Baseline families:
- interpolation / task arithmetic;
- TIES;
- DARE-TIES;
- DELLA / magnitude-aware methods where validated;
- Breadcrumbs / SCE / Model Stock where topology support is proven;
- subspace alignment;
- TSPA / negative-module pruning;
- evolutionary coefficient search.

EvoGM is now explicitly tracked as an MIT-licensed research implementation of learnable evolutionary coefficient search. It is only relevant after AQLEVON owns at least two compatible promotion-eligible genes.

`mergekit-evolve` is useful as a research baseline for evaluation-driven merge search, but mergekit remains blocked as the production Qwen3.8 merge backend until exact qwen3_5 round-trip support is independently proven.

## 9. Interference Atlas before evolutionary search

For every pair/set of genes record:
- standalone evaluation vector;
- per-layer/module delta norm;
- cosine similarity;
- sign conflict rate;
- singular-value spectrum;
- topology coverage;
- target-domain gain;
- global regressions;
- negative modules;
- naive-merge failure examples.

Evolutionary search is then constrained to measured conflict regions instead of blindly exploring coefficients.

## 10. Capability Acquisition Matrix

Each capability has its own teacher/recipe/verifier stack. The machine-readable source of truth is:
`research/weight_factory/genome/capability_acquisition_matrix_v2.json`.

Core rule: **we collect capabilities, not foreign weights.**

## 11. Scaling law for AQLEVON research

The project must not spend frontier-scale compute merely because a larger model exists.

A recipe may move from 27B to A95B only after:
1. 27B gene is reproducible;
2. target gain is statistically/operationally meaningful;
3. global regression vector passes;
4. ablation shows the gain comes from the recipe, not accidental data leakage;
5. A95B topology is separately validated;
6. license/commercial compliance passes;
7. compute budget is explicitly approved;
8. fresh untouched A95B baseline is recorded first.

This creates **cheap discovery, expensive confirmation**, not expensive guessing.

## 12. Data moat

The most defensible asset remains AQLEVON's verified private failure corpus:
- failures of Stable Core;
- specialist-only failures;
- merge-induced failures;
- successful recovery trajectories;
- source/claim evidence;
- tool execution evidence;
- native Arabic/Darija corrections;
- minimal-diff coding corrections;
- self-evolution frontier tasks that pass benchmark-distance checks.

This corpus compounds even if public base models improve.

## 13. Release hierarchy

Artifacts advance only through:
`EXPERIMENTAL_GENE -> REPRODUCIBLE_GENE -> PROMOTION_ELIGIBLE_GENE -> MERGE_CANDIDATE -> CONSOLIDATED_CANDIDATE -> AQLEVON-27B-Rx`.

Frontier-scale artifacts use a separate lineage:
`FRONTIER_RECIPE_CANDIDATE -> A95B_REPRODUCTION -> A95B_PROMOTION_ELIGIBLE -> AQLEVON-Max-Rx`.

No 27B artifact is renamed into a Max artifact, and no 27B adapter tensor is reused directly on the MoE A95B target.

## 14. Immediate execution order

### G0.2 — now
- source registry v3;
- genome manifest v2 with 27B/A95B split;
- self-evolution policy v1;
- capability acquisition matrix v2;
- fail-closed tests for non-commercial/unknown/incomplete sources.

### G1 — unchanged, highest priority once GPU exists
- exact 27B base;
- BF16 LoRA preferred;
- one optimizer step;
- save/reload;
- non-zero delta proof;
- artifact hash;
- target-module identity proof.

### G2
Build R0-A coding gene first because executable verification is strongest.

### G3
Add R0-L self-evolution only after the base training loop is reproducible; generate frontier tasks around real AQLEVON failures.

### G4
After >=2 accepted genes, build Interference Atlas and merge tournament.

### G5
Only successful recipes become A95B frontier-transfer candidates.

## 15. Current truth

V4 increases AQLEVON's ceiling by separating **cheap experimental scale** from **frontier confirmation scale** and by making self-evolution a first-class, hard-verified capability source.

It does not create a new trained checkpoint by itself. The first real AQLEVON weight artifact still requires an actual parameter-changing training run and saved/reloaded checkpoint.
