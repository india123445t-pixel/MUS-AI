#!/usr/bin/env python3
"""AQLEVON Worker 03 — prepared FSDP2 BF16 fallback for G1.

Hardware profiles: 2x48GB or 4x24GB only. This script is intentionally BF16-only.
It must be launched with one of the checked-in Accelerate FSDP2 configs. No QLoRA
fallback exists here.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from aqlevon_g1_delta_probe import (
    CANONICAL_PREFERRED_MODE,
    EXPECTED_TRAINABLE_PARAMS_R4,
    HOLDOUT_TEXT,
    LEARNING_RATE,
    LORA_ALPHA,
    LORA_R,
    MODEL_ID,
    REVISION,
    SEED,
    TARGET_SUFFIXES,
    TRAIN_TEXT,
    _assert_stack_versions,
    _discover_targets,
    _encode,
    _environment,
    _hash_adapter_state,
    _linear_attn_preflight,
    _micro_loss,
    _set_seed,
    _sha256_tree,
    plan,
)

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _local_clone(t: Any) -> Any:
    x = t.detach()
    if hasattr(x, "to_local"):
        x = x.to_local()
    return x.float().cpu().clone()

def _full_cpu_tensor(t: Any) -> Any:
    x = t.detach()
    if hasattr(x, "full_tensor"):
        x = x.full_tensor()
    return x.cpu().contiguous()

def _canonical_adapter_state(model: Any, get_peft_model_state_dict: Any) -> dict[str, Any]:
    state = get_peft_model_state_dict(model)
    return {name: _full_cpu_tensor(tensor) for name, tensor in state.items()}

def _hardware_record(torch: Any, accelerator: Any, expected_world_size: int) -> dict[str, Any]:
    if accelerator.num_processes != expected_world_size:
        raise RuntimeError(
            f"FAIL-CLOSED: expected world size {expected_world_size}, observed {accelerator.num_processes}"
        )
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("FAIL-CLOSED: FSDP2 G1 requires BF16-capable CUDA")
    props = torch.cuda.get_device_properties(torch.cuda.current_device())
    threshold = 46080 if expected_world_size == 2 else 22528
    total_mib = int(props.total_memory // (1024 * 1024))
    if total_mib < threshold:
        raise RuntimeError(
            f"FAIL-CLOSED: local GPU has {total_mib} MiB, profile requires >= {threshold} MiB"
        )
    return {
        "world_size": accelerator.num_processes,
        "rank": accelerator.process_index,
        "local_gpu_index": torch.cuda.current_device(),
        "local_gpu_name": props.name,
        "local_gpu_total_vram_mib": total_mib,
        "expected_world_size": expected_world_size,
        "profile": "2x48" if expected_world_size == 2 else "4x24",
    }

def run(expected_world_size: int, max_length: int, output_dir: Path) -> dict[str, Any] | None:
    if expected_world_size not in (2, 4):
        raise RuntimeError("FAIL-CLOSED: FSDP2 G1 supports expected world size 2 or 4 only")
    stack = _assert_stack_versions(CANONICAL_PREFERRED_MODE)

    import torch
    from accelerate import Accelerator
    from peft import LoraConfig, PeftModel, get_peft_model, get_peft_model_state_dict
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    accelerator = Accelerator(mixed_precision="bf16")
    if accelerator.distributed_type.name != "FSDP":
        raise RuntimeError("FAIL-CLOSED: launch must use Accelerate distributed_type=FSDP")
    fsdp_plugin = getattr(accelerator.state, "fsdp_plugin", None)
    if fsdp_plugin is None or int(getattr(fsdp_plugin, "fsdp_version", 0)) != 2:
        raise RuntimeError("FAIL-CLOSED: FSDP2 is required; FSDP1/DDP is not an allowed fallback")
    hw = _hardware_record(torch, accelerator, expected_world_size)
    _set_seed(torch)

    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = output_dir / "adapter"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_t0 = time.perf_counter()
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID,
        revision=REVISION,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )
    linear_preflight = _linear_attn_preflight(model, CANONICAL_PREFERRED_MODE)
    for p in model.parameters():
        p.requires_grad_(False)
    if hasattr(model.config, "use_cache"):
        model.config.use_cache = False
    if hasattr(model.config, "text_config") and hasattr(model.config.text_config, "use_cache"):
        model.config.text_config.use_cache = False

    selected = _discover_targets(model)
    lora_cfg = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.0,
        bias="none",
        target_modules=selected,
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    trainable_count = sum(p.numel() for _, p in trainable)
    if trainable_count != EXPECTED_TRAINABLE_PARAMS_R4:
        raise RuntimeError(
            f"FAIL-CLOSED: expected {EXPECTED_TRAINABLE_PARAMS_R4} trainable parameters, observed {trainable_count}"
        )
    optimizer = torch.optim.AdamW((p for _, p in trainable), lr=LEARNING_RATE, weight_decay=0.0)
    model, optimizer = accelerator.prepare(model, optimizer)
    load_seconds = time.perf_counter() - load_t0

    train_batch = _encode(tokenizer, TRAIN_TEXT, max_length, accelerator.device)
    holdout_batch = _encode(tokenizer, HOLDOUT_TEXT, max_length, accelerator.device)
    baseline_train_loss = _micro_loss(model, train_batch, torch)
    baseline_holdout_loss = _micro_loss(model, holdout_batch, torch)

    before = {n: _local_clone(p) for n, p in model.named_parameters() if p.requires_grad}
    optimizer.zero_grad(set_to_none=True)
    torch.cuda.reset_peak_memory_stats()
    step_t0 = time.perf_counter()
    out = model(**train_batch, use_cache=False)
    if out.loss is None or not torch.isfinite(out.loss):
        raise RuntimeError("FAIL-CLOSED: non-finite FSDP2 training loss")
    accelerator.backward(out.loss)
    local_grad_sq = torch.tensor(
        sum(float(p.grad.detach().float().pow(2).sum().item()) for p in model.parameters() if p.requires_grad and p.grad is not None),
        device=accelerator.device,
        dtype=torch.float64,
    )
    global_grad_sq = accelerator.reduce(local_grad_sq, reduction="sum")
    if float(global_grad_sq.item()) <= 0:
        raise RuntimeError("FAIL-CLOSED: zero global adapter gradient norm")
    optimizer.step()
    accelerator.wait_for_everyone()
    torch.cuda.synchronize()
    step_seconds = time.perf_counter() - step_t0
    step_peak = int(torch.cuda.max_memory_allocated())

    changed = 0
    delta_sq = 0.0
    delta_max = 0.0
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        after = _local_clone(p)
        delta = after - before[name]
        changed += int((delta != 0).sum().item())
        delta_sq += float(delta.pow(2).sum().item())
        if delta.numel():
            delta_max = max(delta_max, float(delta.abs().max().item()))
    stats = torch.tensor([float(changed), delta_sq, delta_max], device=accelerator.device, dtype=torch.float64)
    total_changed = accelerator.reduce(stats[0], reduction="sum")
    total_delta_sq = accelerator.reduce(stats[1], reduction="sum")
    global_delta_max = accelerator.reduce(stats[2], reduction="max")
    if float(total_changed.item()) <= 0 or float(total_delta_sq.item()) <= 0:
        raise RuntimeError("FAIL-CLOSED: FSDP2 optimizer step produced no global parameter delta")

    unwrapped = accelerator.unwrap_model(model)
    full_adapter_state = _canonical_adapter_state(unwrapped, get_peft_model_state_dict)
    saved_state_hash = _hash_adapter_state(full_adapter_state)
    if accelerator.is_main_process:
        unwrapped.save_pretrained(
            adapter_dir,
            state_dict=full_adapter_state,
            safe_serialization=True,
            is_main_process=True,
        )
        tokenizer.save_pretrained(adapter_dir)
    accelerator.wait_for_everyone()

    post_train_loss = _micro_loss(model, train_batch, torch)
    post_holdout_loss = _micro_loss(model, holdout_batch, torch)
    del optimizer, model, unwrapped, full_adapter_state, before
    gc.collect()
    torch.cuda.empty_cache()
    accelerator.wait_for_everyone()

    reload_base = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID,
        revision=REVISION,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )
    reload_linear_preflight = _linear_attn_preflight(reload_base, CANONICAL_PREFERRED_MODE)
    reload_model = PeftModel.from_pretrained(reload_base, adapter_dir, is_trainable=False)
    reload_model = accelerator.prepare(reload_model)
    reload_unwrapped = accelerator.unwrap_model(reload_model)
    reload_state = _canonical_adapter_state(reload_unwrapped, get_peft_model_state_dict)
    reload_state_hash = _hash_adapter_state(reload_state)
    if reload_state_hash != saved_state_hash:
        raise RuntimeError("FAIL-CLOSED: distributed save/reload adapter-state hash mismatch")
    reload_holdout_loss = _micro_loss(reload_model, holdout_batch, torch)

    accelerator.wait_for_everyone()
    if not accelerator.is_main_process:
        return None

    files = _sha256_tree(adapter_dir)
    report = {
        "status": "PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL",
        "canonical_policy": {
            "preferred": "bf16_lora",
            "qlora_4bit": "experimental",
            "qlora_promotion_requires": "quantization_regression_pass + Manager approval",
        },
        "truth_boundary": "FSDP2 one-step physical delta/save/reload/hash proof only; no capability claim.",
        "plan": plan(max_length, CANONICAL_PREFERRED_MODE),
        "execution_profile": hw,
        "preflight": {
            "linear_attn_before_training": linear_preflight,
            "linear_attn_after_reload": reload_linear_preflight,
            "fsdp_version": 2,
        },
        "selected_target_modules": selected,
        "trainable_parameter_count": trainable_count,
        "parameter_delta": {
            "pre_state_sha256": None,
            "post_state_sha256": saved_state_hash,
            "changed_elements": int(total_changed.item()),
            "delta_l2": math.sqrt(float(total_delta_sq.item())),
            "delta_max_abs": float(global_delta_max.item()),
            "gradient_l2": math.sqrt(float(global_grad_sq.item())),
        },
        "micro_diagnostics_not_quality_evidence": {
            "train_loss_before": baseline_train_loss,
            "train_loss_after": post_train_loss,
            "holdout_loss_before": baseline_holdout_loss,
            "holdout_loss_after": post_holdout_loss,
            "holdout_loss_after_reload": reload_holdout_loss,
        },
        "artifact": {
            "directory": str(adapter_dir),
            "file_sha256": files,
            "saved_adapter_state_sha256": saved_state_hash,
            "reloaded_adapter_state_sha256": reload_state_hash,
            "reload_hash_match": True,
        },
        "timing_seconds": {
            "base_load_and_prepare": load_seconds,
            "optimizer_step": step_seconds,
        },
        "peak_vram_allocated_bytes": {"optimizer_step_local_rank0": step_peak},
        "environment": {
            **_environment(torch, stack),
            "distributed_type": "FSDP",
            "fsdp_version": 2,
            "world_size": expected_world_size,
            "python": sys.version,
            "platform": platform.platform(),
        },
    }
    _write_json(output_dir / "g1_delta_report.json", report)
    return report

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-world-size", type=int, required=True, choices=(2, 4))
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    if args.max_length < 64 or args.max_length > 512:
        raise SystemExit("FAIL-CLOSED: max_length must stay in [64,512]")
    try:
        result = run(args.expected_world_size, args.max_length, Path(args.output_dir))
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
