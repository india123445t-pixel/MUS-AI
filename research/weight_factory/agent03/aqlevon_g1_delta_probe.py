#!/usr/bin/env python3
"""AQLEVON Worker 03 — G1 deterministic one-step parameter-delta probe.

Purpose
-------
Prove the *smallest defensible* physical AQLEVON parameter delta on the frozen
Qwen3.8-27B research base. This is a smoke/provenance gate, not a capability
claim and not a release-training recipe.

Safety properties
-----------------
* Base model + revision are hard-pinned; there is no CLI override.
* QLoRA uses on-the-fly bitsandbytes NF4 from the canonical checkpoint rather
  than an unpinned/pre-quantized mirror.
* LoRA attaches only to q_proj + v_proj under text self-attention layers.
* Vision, MTP, embeddings and lm_head must remain frozen.
* Exactly one optimizer step is executed.
* A non-zero adapter delta is mandatory.
* Adapter is saved, SHA256-recorded, unloaded, reloaded, and state-hash checked.
* OOM never changes model/revision/rank/targets automatically.

The script intentionally avoids Trainer/SFT abstractions so G1 has fewer moving
parts. Full R0-A training should use the manager-approved training framework only
after this gate and Agent 05 evaluation wiring pass.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import platform
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Determinism request must be visible before CUDA libraries initialize.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

MODEL_ID = "Qwen/Qwen3.8-27B"
REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
SEED = 3407
LORA_R = 4
LORA_ALPHA = 8
LEARNING_RATE = 1e-4
TARGET_SUFFIXES = ("q_proj", "v_proj")
EXPECTED_FULL_ATTENTION_LAYERS = 16
EXPECTED_TARGET_MODULES = 32
EXPECTED_TRAINABLE_PARAMS_R4 = 1_507_328
FORBIDDEN_TRAINABLE_FRAGMENTS = (
    "visual",
    "vision",
    "lm_head",
    "embed_tokens",
    "mtp",
    "linear_attn",
    "gate_proj",
    "up_proj",
    "down_proj",
)

TRAIN_TEXT = (
    "Repository task: a parser returns None instead of an empty list. "
    "Inspect the failing path, make the smallest safe fix, and name the test to rerun. "
    "Answer: preserve unrelated behavior, fix only the parser branch, then rerun the focused unit test."
)
HOLDOUT_TEXT = (
    "Safety check: when asked to edit one function in a repository, keep unrelated files unchanged "
    "and verify the focused test before broader checks."
)


def plan(max_length: int, mode: str) -> dict[str, Any]:
    return {
        "task": "AQLEVON G1 physical parameter-delta smoke",
        "worker": "03",
        "model": MODEL_ID,
        "revision": REVISION,
        "mode": mode,
        "quantization": "bnb NF4 + double quant + bf16 compute (on-the-fly)" if mode == "qlora" else "none; bf16 frozen base",
        "optimizer_steps": 1,
        "seed": SEED,
        "max_length": max_length,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "target_suffixes": list(TARGET_SUFFIXES),
        "expected_target_modules": EXPECTED_TARGET_MODULES,
        "expected_trainable_params": EXPECTED_TRAINABLE_PARAMS_R4,
        "automatic_fallback": False,
        "truth_boundary": "smoke/provenance proof only; not quality or release evidence",
    }


def _pkg_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_tree(path: Path) -> dict[str, str]:
    return {
        str(p.relative_to(path)): _sha256_file(p)
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }


def _hash_adapter_state(state: dict[str, Any]) -> str:
    """Stable hash over adapter tensor names/shapes/float32 values."""
    h = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous().float()
        h.update(name.encode("utf-8"))
        h.update(str(tuple(tensor.shape)).encode("ascii"))
        h.update(tensor.numpy().tobytes(order="C"))
    return h.hexdigest()


def _clone_state(state: dict[str, Any]) -> dict[str, Any]:
    return {k: v.detach().cpu().clone() for k, v in state.items()}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _set_seed(torch: Any) -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def _environment(torch: Any) -> dict[str, Any]:
    idx = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(idx)
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "transformers": _pkg_version("transformers"),
        "peft": _pkg_version("peft"),
        "bitsandbytes": _pkg_version("bitsandbytes"),
        "accelerate": _pkg_version("accelerate"),
        "gpu_index": idx,
        "gpu_name": props.name,
        "gpu_total_vram_bytes": props.total_memory,
        "gpu_capability": list(torch.cuda.get_device_capability(idx)),
    }


def _encode(tokenizer: Any, text: str, max_length: int, device: Any) -> dict[str, Any]:
    enc = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
        padding="max_length",
    )
    input_ids = enc["input_ids"].to(device)
    attention_mask = enc["attention_mask"].to(device)
    labels = input_ids.clone()
    labels[attention_mask == 0] = -100
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def _micro_loss(model: Any, batch: dict[str, Any], torch: Any) -> float:
    model.eval()
    with torch.no_grad():
        out = model(**batch, use_cache=False)
    if out.loss is None or not torch.isfinite(out.loss):
        raise RuntimeError(f"non-finite micro loss: {out.loss}")
    return float(out.loss.detach().cpu())


def _discover_targets(model: Any) -> list[str]:
    selected: list[str] = []
    for name, _module in model.named_modules():
        if not name.startswith("model.language_model.layers."):
            continue
        if ".self_attn." not in name:
            continue
        suffix = name.rsplit(".", 1)[-1]
        if suffix in TARGET_SUFFIXES:
            selected.append(name)
    selected = sorted(set(selected))
    if len(selected) != EXPECTED_TARGET_MODULES:
        raise RuntimeError(
            f"topology mismatch: expected {EXPECTED_TARGET_MODULES} q/v targets, found {len(selected)}"
        )
    if any(".linear_attn." in n or ".visual." in n for n in selected):
        raise RuntimeError("forbidden non-self-attention module entered target set")
    return selected


def _load_base(mode: str, torch: Any, Qwen3_5ForConditionalGeneration: Any, BitsAndBytesConfig: Any) -> Any:
    quant = None
    if mode == "qlora":
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    return Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID,
        revision=REVISION,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        quantization_config=quant,
        device_map={"": torch.cuda.current_device()},
        low_cpu_mem_usage=True,
    )


def run_probe(mode: str, max_length: int, output_dir: Path) -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("FAIL-CLOSED: CUDA GPU is required; CPU is not a valid G1 execution target")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("FAIL-CLOSED: BF16-capable CUDA GPU is required for this G1 recipe")

    # Import GPU-training stack only after the hardware gate, so a CPU-only
    # environment reports the real blocker instead of an incidental missing package.
    from peft import (
        LoraConfig,
        PeftModel,
        get_peft_model,
        get_peft_model_state_dict,
        prepare_model_for_kbit_training,
    )
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForConditionalGeneration

    _set_seed(torch)
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = output_dir / "adapter"

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch.cuda.reset_peak_memory_stats()
    load_t0 = time.perf_counter()
    model = _load_base(mode, torch, Qwen3_5ForConditionalGeneration, BitsAndBytesConfig)
    load_seconds = time.perf_counter() - load_t0
    load_peak = torch.cuda.max_memory_allocated()

    for p in model.parameters():
        p.requires_grad_(False)
    if mode == "qlora":
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    elif hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
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

    trainable_names = [n for n, p in model.named_parameters() if p.requires_grad]
    forbidden = [n for n in trainable_names if any(x in n.lower() for x in FORBIDDEN_TRAINABLE_FRAGMENTS)]
    if forbidden:
        raise RuntimeError(f"FAIL-CLOSED: forbidden trainable parameters detected: {forbidden[:8]}")
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if trainable_params != EXPECTED_TRAINABLE_PARAMS_R4:
        raise RuntimeError(
            f"FAIL-CLOSED: expected {EXPECTED_TRAINABLE_PARAMS_R4} trainable params, found {trainable_params}"
        )

    device = next(p for p in model.parameters() if p.device.type == "cuda").device
    train_batch = _encode(tokenizer, TRAIN_TEXT, max_length, device)
    holdout_batch = _encode(tokenizer, HOLDOUT_TEXT, max_length, device)

    baseline_train_loss = _micro_loss(model, train_batch, torch)
    baseline_holdout_loss = _micro_loss(model, holdout_batch, torch)
    pre_state = _clone_state(get_peft_model_state_dict(model))
    pre_hash = _hash_adapter_state(pre_state)

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=LEARNING_RATE,
        weight_decay=0.0,
    )
    model.train()
    torch.cuda.reset_peak_memory_stats()
    step_t0 = time.perf_counter()
    optimizer.zero_grad(set_to_none=True)
    out = model(**train_batch, use_cache=False)
    if out.loss is None or not torch.isfinite(out.loss):
        raise RuntimeError(f"FAIL-CLOSED: non-finite training loss: {out.loss}")
    out.loss.backward()
    grad_sq = 0.0
    for p in model.parameters():
        if p.requires_grad and p.grad is not None:
            grad_sq += float(p.grad.detach().float().pow(2).sum().cpu())
    if grad_sq <= 0.0:
        raise RuntimeError("FAIL-CLOSED: zero adapter gradient norm")
    optimizer.step()
    torch.cuda.synchronize()
    step_seconds = time.perf_counter() - step_t0
    step_peak = torch.cuda.max_memory_allocated()

    post_state = _clone_state(get_peft_model_state_dict(model))
    post_hash = _hash_adapter_state(post_state)
    changed_elements = 0
    delta_l2_sq = 0.0
    delta_max_abs = 0.0
    for name in sorted(pre_state):
        delta = post_state[name].float() - pre_state[name].float()
        changed_elements += int((delta != 0).sum().item())
        delta_l2_sq += float(delta.pow(2).sum().item())
        if delta.numel():
            delta_max_abs = max(delta_max_abs, float(delta.abs().max().item()))
    if changed_elements == 0 or delta_l2_sq <= 0.0 or pre_hash == post_hash:
        raise RuntimeError("FAIL-CLOSED: optimizer step produced no measurable adapter parameter delta")

    post_train_loss = _micro_loss(model, train_batch, torch)
    post_holdout_loss = _micro_loss(model, holdout_batch, torch)

    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    artifact_files = _sha256_tree(adapter_dir)
    if not artifact_files:
        raise RuntimeError("FAIL-CLOSED: adapter save produced no files")

    saved_state_hash = post_hash
    del optimizer, model, pre_state, post_state
    gc.collect()
    torch.cuda.empty_cache()

    torch.cuda.reset_peak_memory_stats()
    reload_t0 = time.perf_counter()
    reload_base = _load_base(mode, torch, Qwen3_5ForConditionalGeneration, BitsAndBytesConfig)
    reload_model = PeftModel.from_pretrained(reload_base, adapter_dir, is_trainable=False)
    reload_state = get_peft_model_state_dict(reload_model)
    reload_state_hash = _hash_adapter_state(reload_state)
    reload_seconds = time.perf_counter() - reload_t0
    reload_peak = torch.cuda.max_memory_allocated()
    if reload_state_hash != saved_state_hash:
        raise RuntimeError("FAIL-CLOSED: reloaded adapter state hash differs from saved post-step hash")

    reload_device = next(p for p in reload_model.parameters() if p.device.type == "cuda").device
    reload_holdout = _encode(tokenizer, HOLDOUT_TEXT, max_length, reload_device)
    reload_holdout_loss = _micro_loss(reload_model, reload_holdout, torch)

    report = {
        "status": "PASS_G1_DELTA_SMOKE_PENDING_FROZEN_EVAL",
        "truth_boundary": (
            "One-step physical adapter-delta/save/reload/hash proof only. "
            "Agent 05 frozen target+regression evaluation is still required before any quality/promotion claim."
        ),
        "plan": plan(max_length, mode),
        "selected_target_modules": selected,
        "trainable_parameter_names": trainable_names,
        "trainable_parameter_count": trainable_params,
        "parameter_delta": {
            "pre_state_sha256": pre_hash,
            "post_state_sha256": post_hash,
            "changed_elements": changed_elements,
            "delta_l2": delta_l2_sq ** 0.5,
            "delta_max_abs": delta_max_abs,
            "gradient_l2": grad_sq ** 0.5,
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
            "file_sha256": artifact_files,
            "saved_adapter_state_sha256": saved_state_hash,
            "reloaded_adapter_state_sha256": reload_state_hash,
            "reload_hash_match": True,
        },
        "timing_seconds": {
            "base_load": load_seconds,
            "optimizer_step": step_seconds,
            "reload": reload_seconds,
        },
        "peak_vram_allocated_bytes": {
            "load": load_peak,
            "optimizer_step": step_peak,
            "reload": reload_peak,
        },
        "environment": _environment(torch),
    }
    _write_json(output_dir / "g1_delta_report.json", report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("qlora", "bf16"), default="qlora")
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--output-dir", default="aqlevon_g1_delta_output")
    ap.add_argument("--print-plan", action="store_true", help="Print immutable G1 plan without importing ML packages/GPU.")
    args = ap.parse_args()

    if args.max_length < 64 or args.max_length > 512:
        raise SystemExit("FAIL-CLOSED: G1 max_length must stay in [64, 512]; default is 128")
    if args.print_plan:
        print(json.dumps(plan(args.max_length, args.mode), ensure_ascii=False, indent=2))
        return

    outdir = Path(args.output_dir)
    try:
        report = run_probe(args.mode, args.max_length, outdir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        message = str(exc)
        oom = "out of memory" in message.lower() or "cuda oom" in message.lower()
        failure = {
            "status": "OOM_STOP_NO_AUTOMATIC_FALLBACK" if oom else "FAIL_CLOSED",
            "error_type": type(exc).__name__,
            "error": message,
            "plan": plan(args.max_length, args.mode),
            "automatic_retry": False,
            "next_manual_action": (
                "If OOM: first retry explicitly with --max-length 64; if still OOM, move the identical recipe to a larger GPU. "
                "Never change model, revision, target profile, or quantization silently."
                if oom
                else "Inspect the failure; do not modify canonical model/revision to force a pass."
            ),
            "traceback_tail": traceback.format_exc().splitlines()[-12:],
        }
        _write_json(outdir / "g1_failure_report.json", failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
