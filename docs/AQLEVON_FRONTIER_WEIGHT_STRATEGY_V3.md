# AQLEVON Frontier Weight Strategy V3 — Stable Core + Capability Genome + Expert Mesh

**Status:** ACTIVE RESEARCH / EXECUTION STRATEGY  
**Date:** 2026-09-18  
**Extends:** `AQLEVON_FRONTIER_WEIGHT_STRATEGY_V2.md`

## 1. Objective

Build genuinely new AQLEVON-owned checkpoints and adapters that become progressively stronger across coding, reasoning, tools, research, Arabic/Darija, long-context work, factuality, and long-horizon agents.

No claim of superiority over frontier systems is valid until AQLEVON wins a frozen common-harness evaluation with acceptable reliability, latency, cost, provenance, and contamination evidence.

## 2. New architectural decision: do not force every capability into one checkpoint too early

AQLEVON will use four cooperating weight layers under one product identity:

1. **Stable Core** — the current generalist AQLEVON checkpoint.
2. **Capability Genome** — independently trained same-base specialist adapters/genes.
3. **Expert Mesh** — request-level selection/composition of accepted genes when dynamic specialization is superior to static consolidation.
4. **Edge Student** — smaller distilled AQLEVON for low-cost local tasks.

Users see only `AQLEVON`. Weight routing is internal.

Periodically, genes that are repeatedly Pareto-positive are consolidated into a new Stable Core. This avoids destroying general capability merely to make every specialization permanent on day one.

## 3. Canonical laboratory base remains frozen

`Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

License: Apache-2.0.

The model is Qwen3_5-family hybrid text architecture inside a multimodal wrapper: 64 language layers, 48 Gated DeltaNet/linear-attention layers and 16 full-attention layers. Adapter design must explicitly account for both paths.

## 4. Training toolchain lock

### SFT / LoRA
Primary: **Unsloth BF16 LoRA** for the first real 27B gene proof.

Reason: current Unsloth documentation explicitly supports Qwen3.5 27B and reports ~56GB VRAM for BF16 LoRA. It also warns against default QLoRA on Qwen3.5 because quantization differences are unusually high. Qwen3.8 uses the same `qwen3_5` architecture family, so AQLEVON treats QLoRA as experimental until its own quality delta is measured.

Secondary: **ms-swift** for distributed scaling and RL because it supports LoRA/full training plus GRPO/DAPO-class methods.

`verl` is not a critical-path dependency until Qwen3_5 support is independently verified; recent issues show support gaps.

### Merge backend
Primary baseline: **PEFT-native LoRA composition**.

Supported candidate families include SVD, concat, linear, TIES, DARE-TIES, DARE-linear, and magnitude pruning.

`mergekit` is **not** the primary Qwen3.8 merge engine yet. Current mergekit issues show incomplete Qwen3_5 architecture support. It may be reintroduced only after exact Qwen3.8 round-trip validation.

## 5. Merge Safety Gate V2

Every adapter/merge candidate must pass:

- exact base repository + revision check;
- explicit topology coverage declaration;
- target-module allowlist;
- forbidden-scope scan;
- training precision declaration;
- teacher/data/license provenance;
- benchmark contamination pass;
- non-zero delta proof;
- expected LoRA delta identity check on sampled modules;
- save/reload round trip;
- merged-vs-base output divergence sanity check;
- target-domain gain;
- global regression vector.

### PEFT rank-pattern rule

A September 2026 PEFT issue demonstrates that `add_weighted_adapter()` with `rank_pattern` can produce adapters that cannot reload for linear/TIES/DARE/magnitude-prune families. Therefore:

- TIES/DARE/linear/magnitude-prune are forbidden when `rank_pattern` is non-empty unless a patched implementation is explicitly pinned and round-trip tested.
- SVD/cat may be tested separately, but still require reload and delta-integrity gates.
- AQLEVON specialists intended for the same merge tournament should prefer a uniform rank/target layout unless evidence justifies otherwise.

## 6. Topology coverage classes

Every gene declares one of:

- `FULL_HYBRID_TEXT`: full-attention + Gated DeltaNet + MLP target coverage.
- `ATTENTION_MLP_PARTIAL`: standard full-attention + MLP only; DeltaNet untouched.
- `MLP_ONLY`.
- `CUSTOM_EXPERIMENTAL`.

A partial adapter may still be useful, but it cannot silently claim full-hybrid coverage.

Candidate suffixes remain:
`q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj,in_proj_qkv,in_proj_z,in_proj_b,in_proj_a,out_proj`.

Default frozen exclusions: vision tower, embeddings/lm_head, MTP, norms and bias unless a dedicated experiment explicitly opens them.

## 7. Community-weight rule strengthened

Community Qwen3.8 adapters are **evidence and recipe sources first**, not automatic donors.

Observed examples reinforce this policy:

- Some tool-calling adapters improve a headline BFCL aggregate while collapsing refusal detection, proving that one-domain gain can hide a severe regression.
- Some releases target only the 16 full-attention layers plus MLP, leaving 48 Gated DeltaNet layers untouched.
- Some community reports document `merge_and_unload()` producing a checkpoint effectively identical to the base, proving that a successful command is not proof of a successful merge.
- Some reasoning distills depend on proprietary hosted-model traces; these remain quarantined unless downstream training rights are unambiguous.

AQLEVON therefore copies **methods that survive audit**, not random public adapters.

## 8. Strongest practical capability transfer mechanism

For each domain, create teacher-specific same-base branches:

`B0 -> Gene_DS`, `B0 -> Gene_GLM`, `B0 -> Gene_OSS`, `B0 -> Gene_SELF`, optional other legally clean teachers.

Do not mix all teacher outputs into one corpus by default. Evaluate each branch independently. Promote only the best verified branches into the merge tournament.

This follows evidence from multi-teacher distillation showing that the best teacher depends on student and task, and that teacher-specific branches plus merging can outperform naive teacher unions.

## 9. Expert Mesh: capability without premature permanent interference

When at least three specialist genes are promotion-eligible, evaluate a runtime Expert Mesh.

Candidate research directions:

- **LoGo**: instance-level training-free LoRA selection/merging.
- **CoMoL**: dynamic core-space LoRA expert composition.
- static selection from a small trusted adapter pool as the production baseline.

Serving can use vLLM LoRA support. Dynamic adapter-management endpoints must never be exposed to untrusted users; vLLM documentation explicitly warns that runtime LoRA loading is a privileged operation.

The product router may choose an adapter internally, but only an administrator/control plane may load or unload weight artifacts.

## 10. Static consolidation tournament

Only after at least two genes pass standalone promotion:

Stage 0:
- SVD/cat sanity baselines;
- weighted interpolation/task arithmetic where valid.

Stage 1:
- TIES;
- DARE-TIES;
- magnitude prune.

Stage 2:
- isotropic/common+task-specific subspace merging;
- WUDI.

Stage 3:
- TSPA;
- TaDA/TARA-style per-layer/subspace candidates;
- ENMP negative-module pruning.

Stage 4:
- EvoGM evolutionary coefficient search;
- CoMerge conflict-driven preference optimization.

No method is crowned globally. The winner is chosen for the current gene set using private development data only.

## 11. The interference atlas becomes mandatory

Before expensive evolutionary search, compute per gene and per merge pair:

- standalone score vector;
- delta norms by module/layer;
- cosine similarity of deltas;
- sign conflict rate;
- singular-value spectrum;
- topology coverage;
- target-domain gain;
- general regressions;
- negative modules;
- failure examples unique to the naive merge.

This turns merge search from blind coefficient guessing into measured conflict resolution.

## 12. RL and self-evolution

The strongest general recipe is not “more SFT.”

AQLEVON should use:

- executable RLVR for code/tools/math;
- evidence rewards for long-context/research;
- agent/environment state rewards for long-horizon work;
- self-play curriculum only when tasks have objective verifiers;
- world-model warmup experiments before expensive long-horizon policy RL.

Candidate algorithms remain DAPO/GRPO-class baselines, GSPO-style sequence objectives, and action/subsequence objectives for multi-turn agents. Promotion is empirical, not paper-driven.

## 13. Data moat

The long-term advantage is the **verified failure corpus**, not merely a clever merge algorithm.

AQLEVON should continuously collect:

- failures of the current Stable Core;
- failures unique to each specialist;
- failures introduced by merges;
- successful recovery trajectories;
- tool execution evidence;
- source/claim evidence;
- Arabic/Darija native corrections;
- minimal-diff coding corrections;
- hard negatives produced by naive merges.

Every accepted example must carry provenance, license, contamination and verifier metadata.

The private failure corpus becomes the compounding asset that competitors cannot copy by downloading our public base.

## 14. Frontier teachers

Current strong local/open-weight teachers and references include:

- DeepSeek-V4-Pro — MIT, different architecture; teacher/recipe/reference only.
- GLM-5.2 — MIT, 1M-context long-horizon reference; different architecture.
- gpt-oss-120b — Apache-2.0; strong local reasoning/tool teacher candidate.
- Kimi-K3 — custom license; conditional teacher/reference only after exact commercial-use review.

No direct tensor splicing across these architectures.

Closed hosted GPT/Claude/Gemini output is not harvested for competitive training when service terms prohibit or restrict it.

## 15. Edge student

AQLEVON should eventually distill a smaller `AQLEVON-Edge` from the accepted Stable Core + verified task corpus.

Edge handles cheap/local work; 27B handles hard tasks. This is both a product-economics strategy and a way to reserve the largest model's capacity for tasks where it creates measurable value.

## 16. Promotion hierarchy

Artifact states:

1. `EXPERIMENTAL_GENE`
2. `REPRODUCIBLE_GENE`
3. `PROMOTION_ELIGIBLE_GENE`
4. `MERGE_CANDIDATE`
5. `CONSOLIDATED_CANDIDATE`
6. `AQLEVON-27B-Rx`
7. separately evaluated quantized serving artifact

No artifact may skip stages.

## 17. Immediate execution order

### G0.1 — Merge Safety hardening (now)
- add machine-readable merge-safety policy;
- add adapter manifest validator;
- add tests for base mismatch, unsafe rank patterns, partial topology, and required delta/reload proof;
- add Expert Mesh research manifest.

### G1 — First real parameter-change proof
- use exact frozen base;
- BF16 LoRA preferred;
- tiny R0-A coding batch;
- one optimizer step first;
- save adapter;
- reload;
- verify nonzero parameter delta + expected LoRA identity;
- hash artifact.

### G2 — R0-A coding gene
- executable environments first;
- teacher-specific branches;
- SFT -> RLVR;
- private coding regressions + protected SWE-style evals.

### G3 — First merge science experiment
- only after >=2 promotion-eligible same-base genes;
- interference atlas;
- PEFT SVD/cat/TIES/DARE baselines under safety gate;
- no mergekit dependency.

### G4 — Expert Mesh prototype
- static trusted adapter selection first;
- then LoGo/CoMoL-style dynamic research if it beats static selection under latency and regression constraints.

### G5 — Consolidated AQLEVON release candidate
- consolidation SFT/RL;
- broad untouched eval;
- contamination audit;
- BF16/FP16 freeze;
- quantize afterward and re-evaluate.

## 18. Research sources added in V3

- Unsloth Qwen3.5 fine-tuning guide — current Qwen3_5 BF16 LoRA/QLoRA guidance.
- Hugging Face PEFT model merging docs — TIES/DARE/SVD/cat.
- PEFT issue #3737 (2026-09-14) — rank-pattern round-trip failure in several weighted merge methods.
- mergekit issue #669 — Qwen3_5 architecture support gap.
- vLLM LoRA documentation and security guidance.
- Two-Stage Parameter Alignment for Multi-LoRA Merging (ACL Findings 2026).
- ENMP (ACL 2026).
- LoRA on the Go (ACL 2026).
- CoMoL (ACL Findings 2026).
- CoMerge (arXiv:2609.02273).
- EvoGM (arXiv:2605.29295).
- WUDI-Merging (arXiv:2503.08099).
- Merge-of-Thought Distillation (arXiv:2509.08814).
- Terminal-Universe (arXiv:2609.04148).
- Qwen-AgentWorld (arXiv:2606.24597).
- OpenResearcher (arXiv:2603.20278).

## 19. Current truth

V3 strengthens the foundry architecture and merge safety, but it still does **not** mean AQLEVON has a new trained checkpoint. The first real checkpoint is created only after G1 changes model parameters, reloads the saved artifact, verifies the delta, hashes it, and passes evaluation.