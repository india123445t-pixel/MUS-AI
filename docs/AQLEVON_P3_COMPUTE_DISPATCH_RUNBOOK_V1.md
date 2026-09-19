# AQLEVON P3 Compute Dispatch Runbook V1

Task: `P3-A06-COMPUTE-DISPATCH`  
Status: implementation/runbook only; no GPU run or capability claim is implied.

## Safety law
The dispatcher is dry-run by default. Real GPU execution requires **both**:
- `AQLEVON_GPU_EXECUTION_AUTHORIZED=1`; and
- `AQLEVON_COMPUTE_ORIGIN` equal to `owned`, `donated`, or `free`.

Any other origin, including paid/spot cloud, fails closed. The dispatcher never activates or purchases compute.

Every real run also requires a pre-frozen lowercase SHA-256 `run_manifest_sha256`, explicit GPU indices, and a payload telemetry file. Receipt/log output stores only a hash of payload argv, never the raw argv or environment secrets.

## Payload telemetry contract
The payload writes this JSON atomically to the path passed via `--telemetry-json`:

```json
{
  "schema": "aqlevon-p3-payload-telemetry-v1",
  "peak_vram_bytes": 123456789,
  "tokens_processed": 512,
  "tokens_generated": 0
}
```

`peak_vram_bytes` must come from the payload's framework/CUDA peak allocator counter, not an estimate. Token counters must be exact integers. The dispatcher separately samples `nvidia-smi` device memory as diagnostic evidence but does not pretend that polling is the authoritative peak.

A successful child process without the telemetry contract is recorded as a **failed/incomplete telemetry attempt**, never as complete physical evidence.

## Profiles

| Profile | Hardware shape | Use |
|---|---|---|
| `g1-1x80-bf16-lora` | 1 GPU, >=78,000 MiB visible | primary G1 BF16 LoRA |
| `g1-2x48-fsdp2` | 2 GPUs, >=45,000 MiB each | Worker-03 FSDP2 fallback |
| `g1-4x24-fsdp2` | 4 GPUs, >=22,000 MiB each | Worker-03 FSDP2 fallback |
| `b07-e0-1x8to12` | 1 GPU, >=7,800 MiB; <=13,000 MiB is planning target | Worker-07 B07-E0 |
| `rl-qwen38-1x80-ms-swift-colocate` | 1 GPU, >=78,000 MiB | later online-RL systems smoke only |

The B07 profile accepts a larger owned/free GPU but emits a planning-class advisory; it does not waste time merely because a larger device is available.

## One-command dry-run templates
Replace `<RUN_MANIFEST_SHA>` and payload paths only after the owning worker has frozen them.

### 1x80GB G1
```bash
node scripts/p3-compute-dispatch.mjs --profile g1-1x80-bf16-lora --run-manifest-sha <RUN_MANIFEST_SHA> --gpu-indices 0 --telemetry-json artifacts/g1/payload-telemetry.json --receipt-dir artifacts/g1/compute --dry-run -- python <WORKER03_G1_SCRIPT> <ARGS>
```

### 2x48GB G1 FSDP2
```bash
node scripts/p3-compute-dispatch.mjs --profile g1-2x48-fsdp2 --run-manifest-sha <RUN_MANIFEST_SHA> --gpu-indices 0,1 --telemetry-json artifacts/g1/payload-telemetry.json --receipt-dir artifacts/g1/compute --dry-run -- torchrun --standalone --nproc_per_node=2 <WORKER03_G1_FSDP2_SCRIPT> <ARGS>
```

### 4x24GB G1 FSDP2
```bash
node scripts/p3-compute-dispatch.mjs --profile g1-4x24-fsdp2 --run-manifest-sha <RUN_MANIFEST_SHA> --gpu-indices 0,1,2,3 --telemetry-json artifacts/g1/payload-telemetry.json --receipt-dir artifacts/g1/compute --dry-run -- torchrun --standalone --nproc_per_node=4 <WORKER03_G1_FSDP2_SCRIPT> <ARGS>
```

### B07-E0 <=12GB planning class
```bash
node scripts/p3-compute-dispatch.mjs --profile b07-e0-1x8to12 --run-manifest-sha <RUN_MANIFEST_SHA> --gpu-indices 0 --telemetry-json artifacts/b07-e0/payload-telemetry.json --receipt-dir artifacts/b07-e0/compute --dry-run -- python <WORKER07_B07_E0_RUNNER> <ARGS>
```

## Later ms-swift + vLLM colocate / LoRA-only-sync smoke
This is a **systems smoke path**, not a method winner and not authorized for execution merely by existing in this file. The builder is pinned to `Qwen/Qwen3.8-27B`, BF16 LoRA semantics, vLLM colocate, and `vllm_enable_lora=true`; it rejects QLoRA/4-bit/quantization flags.

```bash
node scripts/p3-compute-dispatch.mjs \
  --profile rl-qwen38-1x80-ms-swift-colocate \
  --run-manifest-sha <RUN_MANIFEST_SHA> \
  --gpu-indices 0 \
  --telemetry-json artifacts/rl-smoke/payload-telemetry.json \
  --receipt-dir artifacts/rl-smoke/compute \
  --ms-swift-dataset <OWNED_OR_ADMITTED_DATASET_PATH> \
  --ms-swift-plugin <WORKER02_05_APPROVED_REWARD_PLUGIN_PATH> \
  --ms-swift-reward-func <OBJECTIVE_REWARD_FUNCTION> \
  --ms-swift-lora-rank 8 \
  --dry-run
```

The generated command uses the current ms-swift GRPO flags: `--use_vllm true`, `--vllm_mode colocate`, `--vllm_enable_lora true`, matching `--vllm_max_lora_rank`, `--sleep_level 1`, `--offload_optimizer true`, and `--offload_model true`.

## Authorized free/owned execution form
Only after the Manager identifies an actually available zero-cash compatible GPU:

```bash
AQLEVON_GPU_EXECUTION_AUTHORIZED=1 AQLEVON_COMPUTE_ORIGIN=owned \
node scripts/p3-compute-dispatch.mjs <SAME_ARGS_AS_DRY_RUN> --execute -- <PAYLOAD...>
```

For donated/free hardware use `AQLEVON_COMPUTE_ORIGIN=donated` or `free`. Do not use `paid`, `spot`, or any unrecognized origin.

## Retry law
Default retries are zero. A retry requires both `--max-retries N` (max 3) and `--retry-safe`. This prevents an optimizer step from being repeated automatically when the payload is not idempotent. Each retry is a separate self-hashed Compute Attempt Receipt with its own GPU-seconds, peak VRAM, tokens, outcome, and retry index.

## Receipt semantics
`AQLEVON_COMPUTE_ATTEMPT_RECEIPT_V1` uses `AQLEVON_CANONICAL_JSON_SHA256_V1` and binds:
- P3 task/profile;
- frozen run-manifest SHA-256;
- hash-only payload identity;
- zero-cash compute origin;
- exact selected hardware identity;
- monotonic elapsed time and allocated GPU-seconds;
- authoritative payload peak-VRAM/token counters when present;
- diagnostic sampled device-memory peak;
- retry index and failure outcome;
- self digest.

It is intentionally separate from `AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1`: the latter represents runtime/inference attempts bound to candidate artifact manifests. This P3 receipt represents training/experiment compute and does not claim correctness or capability gain.

## Zero-cash availability truth at P3 start
- No compatible zero-cash 27B G1 GPU is verified as attached to this worker now.
- AQLEVON Commons can accept donated/owned workers, but availability must be rechecked before scheduling; transport existence is not GPU availability.
- HF ZeroGPU/Kaggle-style quotas are micro-preflight/B07 possibilities only until exact model fit and quota are verified; they are not counted as a G1 80GB allocation.
- Grant applications/credits are not “available” until actually granted.
- Paid/spot providers are excluded from this wave.

Therefore this lane prepares dispatch and evidence capture without silently converting a planning lead into an available GPU claim.
