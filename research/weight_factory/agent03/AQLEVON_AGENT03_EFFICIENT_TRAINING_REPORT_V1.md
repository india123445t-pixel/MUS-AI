# AQLEVON Worker 03 — Efficient Training / G1 Parameter-Delta Report V1

**Task:** `P1-A03-EFFICIENT-TRAINING`  
**Worker:** `03`  
**Date:** 2026-09-19  
**GitHub base before mutation:** `de2e576eec72581efb5f8e0910d2a8ea2e96b8c0`  
**Branch:** `agent/03-g1-efficient-training`  
**Status:** implementation-ready; GPU execution not performed in this worker environment because no CUDA device is attached and paid compute is not authorized.

## Decision

The cheapest defensible **G1 physical parameter-delta** recipe is a one-step **QLoRA NF4** smoke on the exact frozen base `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, quantized **on the fly from that exact checkpoint**, with BF16 compute, gradient checkpointing, batch 1, sequence length 128, rank-4 LoRA attached only to text `self_attn.q_proj` + `self_attn.v_proj`, standard AdamW, one optimizer step, then save → SHA256 → unload → reload → adapter-state-hash equality.

This is deliberately narrower than an R0-A capability recipe. It proves real trainable parameters changed reproducibly at minimum complexity; it does **not** prove coding gain.

## Assumption challenged

### Prior assumption: “more LoRA targets is automatically better for G1”

PEFT's generic QLoRA guidance recommends `all-linear`. That is a reasonable capability-training default on ordinary text transformers, but it is unsafe as a G1 default for this model because Qwen3.8-27B is a multimodal `Qwen3_5ForConditionalGeneration` with a vision tower plus 48 Gated DeltaNet layers and 16 full-attention layers. AQLEVON's own topology lock explicitly forbids accidentally training vision/MTP/auxiliary paths.

Using the frozen config and current Transformers layer definitions:
- 16 full-attention layers;
- `q_proj`: `5120 -> 12288` (query + gate);
- `v_proj`: `5120 -> 1024`;
- rank-4 `q+v` LoRA = **1,507,328 trainable parameters**;
- current 12-suffix language-trunk rank-8 probe profile = **58,363,904 trainable parameters**.

Thus G1 can cut adapter trainables by ~38.7x while still proving a real optimizer-created delta. This reduction is for the **smoke gate only**; broader R0-A training should run an ablation among q/v, attention-only, standard 7-module QLoRA, and full language-trunk targets.

### Prior assumption: “the pre-quantized Unsloth mirror is automatically the safest cheapest path”

Unsloth's current Qwen3.8 guide states QLoRA works on 24GB and recommends its pre-quantized mirror. However, as of this report, Unsloth issue #10010 remains open and documents missing `quant_state` on Qwen3.8 Gated DeltaNet projections in that mirror, with a shape-mismatch failure. The reported workaround is to load the official checkpoint exactly and quantize on the fly. G1 therefore does **not** depend on the mirror until a zero-step check proves the issue is fixed.

## Exact G1 recipe

1. Hard-pin model and revision; no CLI override.
2. Require CUDA + BF16 support.
3. Load official checkpoint with bitsandbytes NF4, double quantization, BF16 compute.
4. Freeze all base parameters.
5. Enable gradient checkpointing; disable KV cache.
6. Discover only `model.language_model.layers.*.self_attn.{q_proj,v_proj}`.
7. Require exactly 32 target modules and exactly 1,507,328 rank-4 trainables.
8. Reject any trainable path containing vision/visual/MTP/embedding/lm_head/linear-attention/MLP.
9. Fixed seed 3407, fixed local synthetic smoke strings, padded length 128, batch 1.
10. Record adapter state hash and micro losses before training.
11. Execute exactly one AdamW step at LR `1e-4`, weight decay 0.
12. Require finite loss, non-zero gradient, non-zero changed elements, non-zero L2 delta, and changed adapter-state hash.
13. Save adapter with safetensors and SHA256 every artifact file.
14. Delete model, clear CUDA cache, reload the exact base, reload adapter from disk.
15. Require reloaded adapter-state hash to equal the saved post-step hash.
16. Record load/step/reload time and peak allocated VRAM.
17. Emit `PASS_G1_DELTA_SMOKE_PENDING_FROZEN_EVAL`, never a capability/release claim.

## VRAM / compute / cost envelope

### QLoRA G1 — primary cheapest lane
- Official Unsloth guidance: Qwen3.8-27B QLoRA works with **24GB VRAM**.
- Because AQLEVON avoids the currently suspect pre-quantized mirror, **24GB is a test target, not a promise** for the raw Transformers+PEFT probe. The actual peak must be recorded by the script.
- A currently open Unsloth bug report measured ~22GB allocated at load and ~24.6GB peak for a workaround with batch 3 / seq 256 on an L40S while keeping linear-attention modules BF16. That makes a 24GB card marginal for that workaround and supports a 40/48GB safety lane when the 24GB raw probe OOMs.
- Adapter optimizer memory is negligible relative to the base/activations at 1.51M trainables, so standard AdamW is chosen instead of adding an 8-bit optimizer dependency merely to save a few MiB.

### BF16 LoRA confirmation lane
- Raw Qwen3.8-27B BF16 weights are ~55–56GB-class before training overhead; for raw Transformers, use an **80GB-class single GPU** or a validated sharded setup.
- Unsloth's optimized guide says LoRA needs **>36GB**, so a 48GB-class optimized lane is plausible, but must be measured rather than inferred from inference memory.
- BF16 confirmation remains valuable because it removes quantization as a confounder, but it is not the cheapest first physical-delta proof.

### Cost
- **Authorized paid cost: $0.** No paid GPU run was initiated.
- Unsloth currently documents free Kaggle notebooks with 30 hours of 2×T4 quota, but the open pre-quantized-mirror bug means the free notebook path must pass the same zero-step topology/quantization checks before use.
- Any rental cost must be computed only after a provider/rate is owner-authorized: `measured_gpu_seconds / 3600 * provider_hourly_rate`. Do not reserve hardware speculatively.

## OOM fallback ladder — fail closed

No automatic fallback is permitted.

1. `qlora`, seq 128, rank 4, q/v only — primary.
2. If OOM, explicitly retry **the same model/revision/mode/rank/targets** at seq 64 and record both failure reports.
3. If still OOM, move the exact recipe to a 40/48GB-class GPU; do not silently change base or revision.
4. If a single GPU is unavailable, validate FSDP-QLoRA on >=2 GPUs; ms-swift and Hugging Face provide FSDP-QLoRA patterns, but exact Qwen3.8 compatibility must pass zero-step and one-step tests first.
5. BF16 confirmation is a separate lane, not a silent OOM fallback.

## Small surrogate strategy

Use `Qwen/Qwen3.5-4B` only as a **framework/CI surrogate** because it uses the same `qwen3_5` hybrid architecture family and is much cheaper to load. It may test save/reload/hash plumbing and PEFT integration. It may **not** establish Qwen3.8-27B VRAM, quality, module counts, or G1 completion. G1 remains blocked until the exact 27B revision runs.

## Packing / checkpointing / optimizer findings

- Gradient checkpointing: keep on; it attacks activation memory, which matters more than adapter optimizer state here.
- Packing: not part of G1. The current Unsloth Qwen3.8 bug reproduction reports packing being ignored for the hybrid linear-attention model. Real R0-A throughput experiments should measure support rather than assume it.
- 8-bit/paged AdamW: useful when optimizer state is large or memory spikes occur, but G1's rank-4 q/v adapter is only 1.51M parameters. Standard AdamW gives fewer moving parts and clearer delta evidence.
- Sequence length: 128 for G1 proof only. Real R0-A coding training must use a separately measured context curriculum; no quality conclusion can be drawn from this micro length.

## RLVR / RPO / reward strategy

G1 should **not** begin with RL: rollout generation and reward/verifier plumbing add cost and confound the first physical-delta proof.

After a verified SFT adapter exists:
- R0-A coding: prefer verifier-grounded RLVR/VPR on executable repository tasks, with reward from tests/tool state rather than an LLM judge.
- R0-E adaptive reasoning: Root-token Policy Optimization (ACL 2026) is a high-leverage research candidate; the paper reports adaptive-thinking training at about **2% of the training compute of prior adaptive-reasoning methods** by optimizing the root decision. AQLEVON's source registry correctly keeps it research-only until implementation/code-license audit.
- Do not transfer RPO's paper result directly to Qwen3.8-27B; first run a small same-architecture surrogate, then a bounded 27B confirmatory experiment.

## Neighboring dependency checked

**Agent 05 / evaluation lane is mandatory.** The one-step script includes only fixed micro-loss diagnostics to detect gross reload/runtime corruption. They are explicitly not quality evidence. After the first GPU-created adapter exists, Agent 05 must run the frozen target + global regression harness under matched settings before the artifact can progress beyond diagnostic G1 evidence.

## External evidence reviewed (accessed 2026-09-19)

1. Qwen official Qwen3.8 README — finetuning frameworks include Unsloth, Swift, Llama-Factory: https://github.com/QwenLM/Qwen3.8/blob/main/README.md
2. Frozen Qwen3.8-27B config at exact AQLEVON revision: https://huggingface.co/Qwen/Qwen3.8-27B/raw/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/config.json
3. Unsloth Qwen3.8 fine-tuning guide — QLoRA 24GB, LoRA >36GB, free Kaggle notebooks, gradient-checkpointing/OOM guidance: https://unsloth.ai/docs/models/qwen3.8/train
4. Unsloth issue #10010 (open at review) — Qwen3.8 pre-quantized mirror `quant_state` failure and on-the-fly workaround: https://github.com/unslothai/unsloth/issues/10010
5. Hugging Face PEFT quantization guide — NF4 and QLoRA target guidance: https://huggingface.co/docs/peft/developer_guides/quantization
6. Hugging Face PEFT LoRA API — default q/v LoRA and `all-linear` QLoRA behavior: https://huggingface.co/docs/peft/main/package_reference/lora
7. QLoRA paper — NF4, double quantization and paged optimizers; 65B on 48GB result: https://arxiv.org/abs/2305.14314
8. Transformers Qwen3.5 implementation — exact self-attention and Gated DeltaNet projection definitions: https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3_5/modeling_qwen3_5.py
9. bitsandbytes AdamW docs — 8-bit and paged optimizer behavior: https://huggingface.co/docs/bitsandbytes/reference/optim/adamw
10. ms-swift FSDP-QLoRA example — multi-GPU fallback pattern (not Qwen3.8-specific): https://github.com/modelscope/ms-swift/blob/main/examples/train/multi-gpu/fsdp_qlora/train.sh
11. RPO paper, ACL 2026 — Root-token Policy Optimization: https://aclanthology.org/2026.acl-long.816/

## Provenance / license

- Base: Apache-2.0 as recorded by AQLEVON canonical source registry.
- Probe code/report/manifest in this branch: newly authored for AQLEVON Worker 03.
- Smoke data: two locally authored synthetic strings; no external dataset or protected benchmark instance.
- No hosted OpenAI/Anthropic/Gemini outputs used for training.
- No external recipe code copied into the implementation; external sources are cited as design evidence only.

## Tests possible without GPU

- Python compile of probe and contract test.
- JSON parse of manifest.
- `--print-plan` execution without ML dependencies or GPU.
- Static contract unit tests for canonical identity, target scope, NF4 settings, save/reload/hash proof, and no paid-compute/quality claim.

## Not changed

- `main` not touched.
- PR #12 not touched or merged.
- no runtime/application files.
- no canonical Frontier/Capability/Genome file replaced.
- no model revision changed.
- no paid GPU reservation.
- no claim that G1 has run or AQLEVON weights now exist.

## Manager decision requested

**Recommended:** approve this as the G1 execution harness and run it first on an owner-authorized compatible GPU. Treat 24GB QLoRA as the cheapest test target, with 40/48GB as the conservative fallback if the canonical on-the-fly path OOMs. Require Agent 05 frozen evaluation after the delta artifact exists. Keep BF16 LoRA as a separate confirmation lane rather than paying for it before the cheapest smoke proves the pipeline.
