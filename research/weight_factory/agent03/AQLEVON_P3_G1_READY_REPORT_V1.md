# AQLEVON Worker 03 — P3 G1 Ready

**Task:** `P3-A03-G1-READY`  
**Worker:** `03`  
**Mode:** implementation / execution preparation  
**Base:** accepted Worker-03 P2.1 head `ca2a39753b07acf6a7162866061a5c433f1f43ee`  
**Truth boundary:** no paid GPU, no physical 27B run, no capability claim.

## Goal

Make the exact pinned `Qwen/Qwen3.8-27B` canonical BF16 LoRA G1/R0-A path executable immediately when authorized compatible hardware exists, while preserving all existing P1/P2.1 truth boundaries.

## Added execution surfaces

### `p3_g1_ready.py`
One fail-closed orchestration entrypoint:
- hardware profile validation for `1x80`, `2x48`, `4x24`;
- exact visible-GPU count and minimum-VRAM enforcement;
- optional static official-config topology validation;
- command generation with `automatic_fallback=false`;
- physical G1 report validation;
- Candidate Artifact Manifest `probe_only` production through the accepted P2.1 producer;
- frozen CPU-side smoke integrity evaluation;
- final P3 evidence index.

Canonical run shape:

```text
python p3_g1_ready.py run \
  --profile 1x80 \
  --bindings <p2.1-bindings.json> \
  --model-config <exact-pinned-config.json> \
  --output-dir <g1-output>
```

The orchestrator invokes the already accepted `aqlevon_g1_delta_probe.py --mode bf16`. It never rewrites OOM/failure into QLoRA or another precision lane.

### Frozen hardware order

1. `1x80`: primary single-GPU BF16 path; exactly one visible GPU, >= 77824 MiB.
2. `2x48`: FSDP2 fallback; exactly two visible GPUs, >= 46080 MiB each.
3. `4x24`: FSDP2 fallback; exactly four visible GPUs, >= 22528 MiB each.

A mismatch fails. There is no automatic profile switching.

### `p3_g1_fsdp2_probe.py`
Prepared BF16-only FSDP2 fallback runner:
- requires Accelerate FSDP distributed mode + `fsdp_version=2`;
- exact world-size 2 or 4;
- exact pinned model/revision inherited from accepted G1 harness;
- no bitsandbytes / QLoRA path;
- Gated-DeltaNet preflight before training and after reload;
- q/v rank-4 LoRA target/trainable-count check;
- one optimizer step;
- nonzero global gradient and distributed parameter-delta proof;
- adapter-only canonical state gathering;
- safe serialization;
- distributed reload and adapter-state hash equality;
- output uses the same canonical G1 PASS status consumed by P2.1 Candidate Artifact Manifest.

This fallback is **prepared but not physically validated** because no compatible GPU is available in the current environment. It must fail closed if FSDP2 semantics, world size, dtype, target count, state gathering, or reload integrity differ at first execution.

### FSDP2 configs
- `accelerate_fsdp2_2x48.yaml`
- `accelerate_fsdp2_4x24.yaml`

Both freeze:
- `distributed_type: FSDP`
- `fsdp_version: 2`
- BF16 mixed precision
- CPU-RAM-efficient loading
- reshard-after-forward
- transformer-layer wrap
- sharded state dict
- exact process count.

Activation checkpointing is intentionally OFF for the first short G1 proof; it is a memory valve, not silently enabled acceleration.

### Same-architecture surrogate
`p3_surrogate_runner.py` pins:

- model: `Qwen/Qwen3.5-4B-Base`
- revision: `daa9c16f371249f9ad1c75a9ed6f956c08ea08f5`
- BF16 / no quantization
- q/v rank-4 LoRA
- one optimizer step
- strict nonzero delta
- save/reload hash equality
- hybrid-layer check.

Its report is explicitly systems/integrity evidence only and cannot be presented as Qwen3.8-27B capability gain.

## Static model-layout preflight

The P3 orchestrator can validate exact config bytes before launch. The pinned 27B topology must expose:

- `model_type=qwen3_5`
- `Qwen3_5ForConditionalGeneration`
- BF16 text dtype
- hidden size 5120
- 64 text layers
- exactly 48 `linear_attention`
- exactly 16 `full_attention`.

Dynamic module-level Gated-DeltaNet projection checks from the accepted P1 harness still run after actual model load.

## Candidate Artifact Manifest integration

After a physical canonical BF16 G1 PASS:
1. validate nonzero `changed_elements`, `delta_l2`, `gradient_l2`;
2. validate save/reload adapter-state hash equality;
3. consume externally supplied P2.1 bindings;
4. invoke `build_probe_only_manifest_from_g1`;
5. require `artifact_type=adapter`;
6. require `artifact_stage=probe_only`;
7. bind exact G1 report SHA as `training_run_receipt_sha256`;
8. revalidate exact artifact bytes through Candidate Manifest file-tree hashing.

No P3 code creates a `promotion_candidate`, `PROMOTION_ELIGIBLE`, or release declaration.

## Frozen smoke evaluation

`AQLEVON_G1_FROZEN_SMOKE_EVAL_V1` is an integrity-only post-run check:
- canonical BF16 G1 status;
- nonzero delta;
- save/reload state equality;
- valid P2.1 Candidate Manifest;
- exact artifact-byte match;
- `adapter + probe_only`;
- finite train/holdout diagnostics;
- reload holdout loss stable within the frozen numerical smoke tolerance.

Success status is exactly:

`PASS_INTEGRITY_ONLY_NO_CAPABILITY_CLAIM`

Authority boundary is explicit:

`SMOKE_INTEGRITY_ONLY_NOT_WORKER05_PROMOTION_NOT_CAPABILITY_GAIN`

Worker 05 remains the promotion/evaluation authority.

## CPU/mock evidence

Local P3 suite:
- **13/13 PASS**
- hardware parser/profile pass/fail cases;
- 1x80/2x48/4x24 exact-count/VRAM enforcement;
- no automatic fallback;
- official 64-layer / 48-linear / 16-full topology check;
- BF16 command generation;
- FSDP2 config/version/world-size checks;
- no QLoRA in FSDP2 runner;
- surrogate pin and truth boundary;
- frozen smoke PASS only as integrity;
- zero-delta rejection;
- non-`probe_only` rejection;
- reload-loss-drift rejection;
- CLI plan generation without ML/GPU stack.

Additional:
- `py_compile`: PASS for all new Python files;
- `p3_g1_profiles.json`: JSON parse PASS;
- command-plan generation: PASS for all three hardware profiles;
- surrogate `--print-plan`: PASS.

Current environment check:
- `nvidia-smi`: **not available**.
- Therefore physical 27B G1: **NOT RUN**.
- FSDP2 fallback: **NOT RUN**.
- surrogate GPU step: **NOT RUN**.
- paid compute: **NOT USED**.

## Current-source implementation notes

Accelerate stable documentation supports FSDP through config and FSDP2 selection with `fsdp_version=2`; FSDP2 uses DTensor/original-parameter semantics and sharded state dictionaries. Current documentation also requires distributed initialization before RAM-efficient pretrained loading. These requirements are encoded in the launcher/config and checked at runtime where possible.

FSDP2 remains a prepared fallback rather than the preferred first truth path because current public issue history shows that FSDP2 + meta/RAM-efficient loading and LoRA combinations have had implementation-sensitive failure modes. First physical use therefore records evidence rather than assuming success.

## Files added

1. `research/weight_factory/agent03/p3_g1_ready.py`
2. `research/weight_factory/agent03/p3_g1_fsdp2_probe.py`
3. `research/weight_factory/agent03/p3_surrogate_runner.py`
4. `research/weight_factory/agent03/p3_g1_profiles.json`
5. `research/weight_factory/agent03/accelerate_fsdp2_2x48.yaml`
6. `research/weight_factory/agent03/accelerate_fsdp2_4x24.yaml`
7. `research/weight_factory/agent03/test_p3_g1_ready.py`
8. `research/weight_factory/agent03/AQLEVON_P3_G1_READY_REPORT_V1.md`

## Deliberately not changed

- `main`;
- accepted P1 PR #15;
- accepted P2.1 PR #18 contents;
- any other worker branch/PR;
- production;
- training data;
- evaluation policy;
- runtime/dispatch policy;
- canonical Manager contracts;
- model weights;
- paid compute authorization.

## Execution truth

P3-A03 is **execution-ready preparation**, not a physical PASS.

The next irreversible step remains:
- Manager/owner provides explicitly authorized compatible free/donated hardware;
- run exactly one canonical BF16 G1 step;
- produce physical delta/save/reload/hash + Candidate Manifest `probe_only` + frozen smoke evidence;
- then Worker 05 reality/evaluation gates decide any capability statement.

Until then: **no new AQLEVON weights and no capability gain claim.**
