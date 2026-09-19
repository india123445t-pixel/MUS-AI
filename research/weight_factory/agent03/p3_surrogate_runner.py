#!/usr/bin/env python3
"""AQLEVON P3 same-architecture systems surrogate runner.

Pinned same-family hybrid model for cheap systems/method falsification.
This is not a 27B capability-gain path and emits no promotion truth.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any

MODEL_ID = "Qwen/Qwen3.5-4B-Base"
REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
SEED = 3407
LORA_R = 4
LORA_ALPHA = 8
LEARNING_RATE = 1e-4
TARGET_SUFFIXES = ("q_proj", "v_proj")
TRAIN_TEXT = (
    "Coding task: implement a pure function that returns the sum of even integers in a list. "
    "Preserve input order and do not mutate the list."
)
HOLDOUT_TEXT = (
    "Coding task: implement a pure function that counts negative integers without mutating its input."
)

def plan(max_length: int) -> dict[str, Any]:
    return {
        "task": "AQLEVON P3 same-architecture systems surrogate",
        "model": MODEL_ID,
        "revision": REVISION,
        "architecture_family": "qwen3_5_hybrid_gated_deltanet_full_attention",
        "precision": "bf16",
        "quantization": "none",
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "target_suffixes": list(TARGET_SUFFIXES),
        "optimizer_steps": 1,
        "max_length": max_length,
        "seed": SEED,
        "authority_boundary": "SURROGATE_SYSTEMS_EVIDENCE_ONLY_NOT_27B_CAPABILITY_GAIN",
    }

def _hash_state(state: dict[str, Any]) -> str:
    h = hashlib.sha256()
    for name in sorted(state):
        t = state[name].detach().cpu().contiguous().float()
        h.update(name.encode("utf-8"))
        h.update(str(tuple(t.shape)).encode("ascii"))
        h.update(t.numpy().tobytes(order="C"))
    return h.hexdigest()

def _encode(tokenizer: Any, text: str, max_length: int, device: Any) -> dict[str, Any]:
    enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length, padding="max_length")
    ids = enc["input_ids"].to(device)
    mask = enc["attention_mask"].to(device)
    labels = ids.clone()
    labels[mask == 0] = -100
    return {"input_ids": ids, "attention_mask": mask, "labels": labels}

def _discover_targets(model: Any) -> list[str]:
    selected = []
    for name, _ in model.named_modules():
        if ".self_attn." in name and name.rsplit(".", 1)[-1] in TARGET_SUFFIXES:
            selected.append(name)
    selected = sorted(set(selected))
    if not selected:
        raise RuntimeError("FAIL-CLOSED: no q/v self-attention targets discovered")
    if any(".linear_attn." in name or ".visual." in name for name in selected):
        raise RuntimeError("FAIL-CLOSED: forbidden non-self-attention target selected")
    return selected

def _layout(model: Any) -> dict[str, Any]:
    config = model.config
    text = getattr(config, "text_config", config)
    layer_types = list(getattr(text, "layer_types", []) or [])
    full = sum(x == "full_attention" for x in layer_types)
    linear = sum(x == "linear_attention" for x in layer_types)
    if not layer_types or full <= 0 or linear <= 0:
        raise RuntimeError("FAIL-CLOSED: surrogate must expose hybrid full/linear layer_types")
    return {
        "layer_count": len(layer_types),
        "full_attention_layers": full,
        "linear_attention_layers": linear,
        "hidden_size": int(getattr(text, "hidden_size")),
    }

def run(max_length: int, output_dir: Path) -> dict[str, Any]:
    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("FAIL-CLOSED: BF16-capable CUDA GPU required for physical surrogate execution")
    from peft import LoraConfig, PeftModel, get_peft_model, get_peft_model_state_dict
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID,
        revision=REVISION,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        device_map={"": torch.cuda.current_device()},
        low_cpu_mem_usage=True,
    )
    layout = _layout(model)
    for p in model.parameters():
        p.requires_grad_(False)
    if hasattr(model.config, "use_cache"):
        model.config.use_cache = False
    if hasattr(model.config, "text_config") and hasattr(model.config.text_config, "use_cache"):
        model.config.text_config.use_cache = False

    targets = _discover_targets(model)
    model = get_peft_model(model, LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.0,
        bias="none",
        target_modules=targets,
        task_type="CAUSAL_LM",
    ))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if trainable <= 0:
        raise RuntimeError("FAIL-CLOSED: surrogate has zero trainable parameters")
    device = next(p for p in model.parameters() if p.device.type == "cuda").device
    train = _encode(tokenizer, TRAIN_TEXT, max_length, device)
    holdout = _encode(tokenizer, HOLDOUT_TEXT, max_length, device)

    pre = {k: v.detach().cpu().clone() for k, v in get_peft_model_state_dict(model).items()}
    pre_hash = _hash_state(pre)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=LEARNING_RATE, weight_decay=0.0)
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    optimizer.zero_grad(set_to_none=True)
    out = model(**train, use_cache=False)
    if out.loss is None or not torch.isfinite(out.loss):
        raise RuntimeError("FAIL-CLOSED: non-finite surrogate loss")
    out.loss.backward()
    grad_sq = sum(float(p.grad.detach().float().pow(2).sum().cpu()) for p in model.parameters() if p.requires_grad and p.grad is not None)
    if grad_sq <= 0:
        raise RuntimeError("FAIL-CLOSED: zero surrogate gradient")
    optimizer.step()
    torch.cuda.synchronize()
    seconds = time.perf_counter() - t0
    peak = int(torch.cuda.max_memory_allocated())
    post = {k: v.detach().cpu().clone() for k, v in get_peft_model_state_dict(model).items()}
    post_hash = _hash_state(post)
    changed = 0
    delta_sq = 0.0
    for name in pre:
        d = post[name].float() - pre[name].float()
        changed += int((d != 0).sum().item())
        delta_sq += float(d.pow(2).sum().item())
    if changed <= 0 or delta_sq <= 0 or pre_hash == post_hash:
        raise RuntimeError("FAIL-CLOSED: surrogate optimizer step produced no adapter delta")

    output_dir.mkdir(parents=True, exist_ok=True)
    adapter = output_dir / "adapter"
    model.save_pretrained(adapter, safe_serialization=True)
    tokenizer.save_pretrained(adapter)
    saved_hash = post_hash
    del optimizer, model, pre, post
    gc.collect()
    torch.cuda.empty_cache()

    reload_base = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID, revision=REVISION, trust_remote_code=False, dtype=torch.bfloat16,
        device_map={"": torch.cuda.current_device()}, low_cpu_mem_usage=True,
    )
    reload_model = PeftModel.from_pretrained(reload_base, adapter, is_trainable=False)
    reload_hash = _hash_state(get_peft_model_state_dict(reload_model))
    if reload_hash != saved_hash:
        raise RuntimeError("FAIL-CLOSED: surrogate save/reload state hash mismatch")
    reload_device = next(p for p in reload_model.parameters() if p.device.type == "cuda").device
    hb = _encode(tokenizer, HOLDOUT_TEXT, max_length, reload_device)
    with torch.no_grad():
        h = reload_model(**hb, use_cache=False).loss
    if h is None or not torch.isfinite(h):
        raise RuntimeError("FAIL-CLOSED: non-finite surrogate reload holdout loss")

    report = {
        "status": "PASS_SURROGATE_ONE_STEP_DELTA_INTEGRITY_ONLY",
        "plan": plan(max_length),
        "layout": layout,
        "target_modules": targets,
        "trainable_parameter_count": trainable,
        "parameter_delta": {
            "pre_state_sha256": pre_hash,
            "post_state_sha256": post_hash,
            "changed_elements": changed,
            "delta_l2": math.sqrt(delta_sq),
            "gradient_l2": math.sqrt(grad_sq),
        },
        "artifact": {
            "directory": str(adapter),
            "saved_adapter_state_sha256": saved_hash,
            "reloaded_adapter_state_sha256": reload_hash,
            "reload_hash_match": True,
        },
        "telemetry": {
            "optimizer_step_seconds": seconds,
            "peak_vram_allocated_bytes": peak,
        },
        "reload_holdout_loss_not_quality_claim": float(h.detach().cpu()),
        "authority_boundary": "SURROGATE_SYSTEMS_INTEGRITY_ONLY_NOT_27B_CAPABILITY_GAIN",
    }
    (output_dir / "surrogate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--output-dir", default="aqlevon_p3_surrogate_output")
    ap.add_argument("--print-plan", action="store_true")
    args = ap.parse_args()
    if args.max_length < 64 or args.max_length > 512:
        raise SystemExit("FAIL-CLOSED: max_length must stay in [64,512]")
    if args.print_plan:
        print(json.dumps(plan(args.max_length), ensure_ascii=False, indent=2))
        return
    try:
        print(json.dumps(run(args.max_length, Path(args.output_dir)), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
