# AQLEVON Worker 03 — P1 Repair Wave / G1 Harness Repair V2

**Task:** `P1-R03-G1-HARNESS-REPAIR`  
**Worker:** `03`  
**Date:** 2026-09-19  
**Repository:** `india123445t-pixel/MUS-AI`  
**Existing branch/PR:** `agent/03-g1-efficient-training` / PR #15  
**Canonical base:** `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`  
**Physical G1 status:** still NOT RUN — no owner-authorized compatible GPU exists in this worker environment.

## Repair decision

Manager review was correct: the original PR silently promoted QLoRA to the primary G1 lane even though canonical AQLEVON policy says:

- preferred: `bf16_lora`
- experimental: `qlora_4bit`
- experimental promotion requires: `quantization_regression_pass`

V2 therefore restores **BF16 LoRA as the CLI/default/canonical G1 lane**. QLoRA remains available only as an explicitly acknowledged experimental cost challenger and cannot produce canonical-G1-ready evidence without a frozen quantization regression plus Manager approval.

No canonical policy file was modified.

## Blocking correction 1 — canonical policy truth boundary

### Before
`--mode` defaulted to `qlora`, and the report recommended QLoRA as the first G1 route.

### After
- default mode: `bf16`
- canonical report state: `PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL`
- QLoRA mode: `qlora-experimental`
- actual QLoRA execution additionally requires `--ack-experimental-qlora`
- experimental success state: `PASS_EXPERIMENTAL_QLORA_DELTA_SMOKE_NOT_CANONICAL_G1`
- QLoRA promotion remains blocked on `quantization_regression_pass + Manager approval`

The rank-4 q/v-only target profile remains a G1 *smoke-layout choice*, not a canonical statement about the optimal later R0-A capability-training target set.

## Blocking correction 2 — Gated DeltaNet / linear_attn quantization preflight

The original harness quantized the full hybrid model on-the-fly. That exceeded the evidence from Unsloth issue #10010.

The repaired experimental QLoRA lane now reproduces the **validated workaround boundary**:
- use the exact official checkpoint, not the Unsloth pre-quantized mirror;
- on-the-fly NF4 + double quantization;
- explicitly skip `model.language_model.layers.{0..63}.linear_attn`;
- keep skipped linear-attention projections BF16;
- no automatic fallback to/from BF16.

Before PEFT, optimizer creation, forward or backward, the harness enumerates the Gated DeltaNet projections:
- expected DeltaNet layers: 48;
- suffixes: `in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a`, `out_proj`;
- expected total projection modules: **240**.

Every one must satisfy:
1. dtype is BF16;
2. weight is 2-D;
3. when `in_features` / `out_features` exist, shape equals `(out_features, in_features)`;
4. `quant_state` is absent;
5. module class is not `Linear4bit` / `Linear8bit`.

Any violation raises `FAIL-CLOSED` before training.

For the experimental QLoRA q/v targets themselves, the opposite integrity rule applies: every selected quantized target must have a non-null `quant_state`; otherwise execution stops before LoRA attachment/training.

The full linear-attention preflight is also rerun after base reload, before adapter reload evidence is accepted.

### Evidence boundary
This does **not** prove the skip mechanism works in AQLEVON's environment yet. It proves the harness will reject a load where the skip is not actually honored. Physical proof still requires a GPU run.

## Blocking correction 3 — first-run compatibility profile pinned

The old harness only recorded package versions after execution. V2 pins the first-run profile before model download:

- `transformers==5.17.0`
- `peft==0.21.0`
- `bitsandbytes==0.50.2`
- `accelerate==1.15.0`

These were the current PyPI releases observed on 2026-09-19:
- Transformers 5.17.0 — released 2026-09-09;
- PEFT 0.21.0 — released 2026-09-15;
- bitsandbytes 0.50.2 — released 2026-08-27;
- Accelerate 1.15.0 — released 2026-09-09.

The harness performs exact-match fail-closed validation:
- BF16 requires exact Transformers + PEFT + Accelerate;
- QLoRA additionally requires exact bitsandbytes.

**Truth boundary:** this is a pinned first-run profile, not a claim that those versions have already passed Qwen3.8-27B GPU training in AQLEVON. If the first authorized run shows incompatibility, the profile must be reviewed and changed explicitly rather than silently drifting packages.

The Unsloth issue's successful workaround used an older reported environment (`Unsloth 2026.8.22`, Transformers 5.5.0, PyTorch 2.11.0+cu130). That evidence justifies the skip-linear-attn design, not a claim that AQLEVON's newer pinned profile is already validated.

## Blocking correction 4 — deterministic claim

The original code used:

`torch.use_deterministic_algorithms(True, warn_only=True)`

while describing the harness as deterministic.

V2 uses strict:

`torch.use_deterministic_algorithms(True)`

and keeps TF32 disabled plus deterministic cuDNN settings. If a used kernel cannot satisfy PyTorch deterministic mode, execution fails instead of silently warning and continuing.

The manifest wording is deliberately precise: deterministic algorithms are **requested/enforced fail-closed by PyTorch**; no claim is made that unexecuted hardware has already reproduced identical artifact hashes.

## Blocking correction 5 — regression tests

The repaired contract suite is **18/18 PASS**.

It now proves:
1. exact model/revision hard pin;
2. BF16 is canonical/default;
3. QLoRA is experimental and needs explicit acknowledgement;
4. manifest preserves the canonical truth boundary;
5. exact package pins are present;
6. package mismatch fails closed;
7. deterministic mode is strict (`warn_only=True` absent);
8. all 64 linear-attention skip prefixes are explicitly configured;
9. a valid 240-projection BF16 linear-attention topology passes;
10. wrong `linear_attn` dtype fails closed;
11. malformed/1-D `linear_attn` shape fails closed;
12. unexpected `quant_state` on skipped `linear_attn` fails closed;
13. unexpected 4-bit `linear_attn` class fails closed;
14. missing one of the 240 projections fails closed;
15. experimental QLoRA target without `quant_state` fails closed;
16. delta/save/reload/hash evidence remains required;
17. default `--print-plan` is BF16;
18. QLoRA can be described for planning without authorizing execution.

Additional checks:
- `python -m py_compile`: PASS
- manifest `python -m json.tool`: PASS
- default `--print-plan`: PASS and parseable JSON

No GPU/paid compute was used.

## Why QLoRA remains useful but not canonical

The cost hypothesis remains valuable: QLoRA may eventually reduce the VRAM needed for iterative specialist work. But the canonical project already established that Qwen3_5-family quantization may have unusual regression/safety behavior, and the hybrid DeltaNet bug shows why a cheap memory path must not be promoted before measured quality parity.

Therefore the repaired ordering is:

1. **Canonical G1:** BF16 LoRA, one step, non-zero delta, save/reload/hash.
2. Frozen Worker 05 target + regression evaluation.
3. **Experimental challenger:** QLoRA with linear-attn kept BF16 and all preflights green.
4. Same evaluation conditions plus explicit `quantization_regression_pass`.
5. Only Manager may decide whether the cost challenger changes canonical policy.

## OOM behavior

No mode switches precision automatically.

If canonical BF16 OOMs:
- record OOM and stop;
- use a larger authorized GPU or a separately manager-reviewed distributed BF16 plan;
- do not silently fall back to QLoRA.

If experimental QLoRA OOMs:
- record OOM and stop;
- do not silently alter skip policy, model, revision, rank, or precision lane.

This is intentionally stricter than the original seq-length fallback because Manager's repair assignment prioritizes policy/quantization truth over squeezing a pass from unknown hardware.

## External evidence reviewed for repair

1. AQLEVON canonical `merge_safety_policy_v2/v3`: BF16 LoRA preferred; QLoRA experimental pending quantization regression.
2. AQLEVON Frontier Weight Strategy V3: G1 explicitly says BF16 LoRA preferred.
3. Unsloth issue #10010, opened 2026-08-30 and still open at review: successful workaround uses official checkpoint on-the-fly and explicitly skips `linear_attn`, keeping it BF16. The report shows a proper BF16 2-D tensor after the workaround and a successful training step.
4. Hugging Face `BitsAndBytesConfig` current docs: 4-bit is enabled by replacing Linear layers with bitsandbytes modules; the API includes `llm_int8_skip_modules`. The Qwen3.8 issue supplies the architecture-specific empirical evidence that this skip field is honored for its on-the-fly workaround.
5. Current PyPI releases as of 2026-09-19: Transformers 5.17.0, PEFT 0.21.0, bitsandbytes 0.50.2, Accelerate 1.15.0.

## Files repaired in the same PR

- `research/weight_factory/agent03/aqlevon_g1_delta_probe.py`
- `research/weight_factory/agent03/g1_run_manifest.template.json`
- `research/weight_factory/agent03/test_agent03_g1_contract.py`
- `research/weight_factory/agent03/AQLEVON_AGENT03_EFFICIENT_TRAINING_REPORT_V1.md`

No new branch or replacement PR was created.

## Remaining risks / unresolved physical evidence

- No CUDA execution has occurred.
- Exact pinned package profile has not yet been GPU-validated.
- BF16 VRAM peak is not measured by AQLEVON yet.
- QLoRA skip-module behavior is guarded but not yet physically observed by AQLEVON.
- No non-zero 27B adapter delta exists yet.
- No Worker 05 frozen evaluation exists for this future artifact.
- No `quantization_regression_pass` exists.
- Therefore no model-quality, quantization-parity, promotion, or new-checkpoint claim is allowed.

## Deliberately not changed

- `main`;
- PR #12 or another worker branch;
- canonical Frontier/Genome/merge-safety policies;
- base model/revision;
- product/runtime code;
- training datasets;
- paid GPU state;
- model capability claims.

## Manager decision requested

Re-review PR #15 as a **policy-aligned G1 harness** only. If accepted, the next irreversible action remains owner/Manager authorization of compatible GPU compute for canonical BF16 G1. QLoRA should remain a later matched-evaluation cost challenger until it earns `quantization_regression_pass`.