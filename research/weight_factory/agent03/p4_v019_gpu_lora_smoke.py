#!/usr/bin/env python3
"""AQLEVON P4 A1 GPU infrastructure smoke for native Qwen3.5 + vLLM 0.19.1.

This performs ZERO optimizer/reward/training steps. It creates an ephemeral,
random non-zero PEFT LoRA adapter only to prove that the frozen q_proj/v_proj
target set is discovered and is functionally active in vLLM rollout.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
from pathlib import Path

MODEL_REPO = "Qwen/Qwen3.5-4B-Base"
MODEL_REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
SEED = 1701
EXPECTED_FULL_ATTN_LAYERS = [3, 7, 11, 15, 19, 23, 27, 31]
EXPECTED_TARGET_MODULES = 16
SMOKE_PROMPT = "AQLEVON infrastructure smoke. Return one short token."


def _logprob_map(request_output):
    choice = request_output[0].outputs[0]
    if not choice.logprobs:
        raise RuntimeError("AQLEVON_SMOKE_LOGPROBS_MISSING")
    step = choice.logprobs[0]
    out = {}
    for token_id, item in step.items():
        value = getattr(item, "logprob", None)
        if value is None:
            continue
        out[int(token_id)] = float(value)
    if not out:
        raise RuntimeError("AQLEVON_SMOKE_LOGPROBS_EMPTY")
    return out


def build_ephemeral_adapter(model_path: Path, adapter_dir: Path) -> tuple[list[str], list[int]]:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from peft.tuners.lora.layer import LoraLayer
    from transformers import Qwen3_5ForConditionalGeneration

    torch.manual_seed(SEED)
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(model_path),
        dtype=torch.bfloat16,
        device_map={"": "cpu"},
        low_cpu_mem_usage=True,
    )
    layer_types = list(base.config.text_config.layer_types)
    full_layers = [i for i, kind in enumerate(layer_types) if kind == "full_attention"]
    if full_layers != EXPECTED_FULL_ATTN_LAYERS:
        raise RuntimeError(
            f"AQLEVON_SMOKE_FULL_ATTN_LAYOUT:{full_layers}:expected_{EXPECTED_FULL_ATTN_LAYERS}"
        )

    cfg = LoraConfig(
        r=4,
        lora_alpha=4,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.0,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        init_lora_weights=False,  # PEFT documents False as non-noop debug init.
    )
    peft_model = get_peft_model(base, cfg)
    targets = sorted(
        name
        for name, module in peft_model.named_modules()
        if isinstance(module, LoraLayer)
        and (name.endswith(".q_proj") or name.endswith(".v_proj"))
    )
    if len(targets) != EXPECTED_TARGET_MODULES:
        raise RuntimeError(
            f"AQLEVON_SMOKE_PEFT_TARGET_COUNT:{len(targets)}:expected_{EXPECTED_TARGET_MODULES}"
        )

    expected_suffixes = {
        f"layers.{idx}.self_attn.{proj}"
        for idx in EXPECTED_FULL_ATTN_LAYERS
        for proj in ("q_proj", "v_proj")
    }
    observed_suffixes = {
        next(
            (
                suffix
                for suffix in expected_suffixes
                if name.endswith(suffix)
            ),
            "",
        )
        for name in targets
    }
    observed_suffixes.discard("")
    missing = sorted(expected_suffixes - observed_suffixes)
    if missing:
        raise RuntimeError("AQLEVON_SMOKE_PEFT_TARGET_MISSING:" + ",".join(missing))

    shutil.rmtree(adapter_dir, ignore_errors=True)
    peft_model.save_pretrained(str(adapter_dir), safe_serialization=True)
    adapter_cfg = json.loads((adapter_dir / "adapter_config.json").read_text())
    target_cfg = set(adapter_cfg.get("target_modules") or [])
    if target_cfg != {"q_proj", "v_proj"}:
        raise RuntimeError(f"AQLEVON_SMOKE_ADAPTER_TARGET_CONFIG:{sorted(target_cfg)}")

    del peft_model, base
    gc.collect()
    return targets, full_layers


def run_vllm_smoke(model_path: Path, adapter_dir: Path) -> dict:
    import torch
    import vllm
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest

    if vllm.__version__.split("+")[0] != "0.19.1":
        raise RuntimeError(f"AQLEVON_SMOKE_VLLM_VERSION:{vllm.__version__}")
    if not torch.cuda.is_available():
        raise RuntimeError("AQLEVON_SMOKE_CUDA_UNAVAILABLE")

    llm = LLM(
        model=str(model_path),
        tokenizer=str(model_path),
        dtype="bfloat16",
        tensor_parallel_size=1,
        max_model_len=4096,
        max_num_batched_tokens=4096,
        gpu_memory_utilization=0.25,
        enable_lora=True,
        max_loras=1,
        # vLLM 0.19.1 accepts discrete capacity ceilings; rank-4 adapters use ceiling 8.
        # This does NOT change the frozen PEFT adapter rank (r=4).
        max_lora_rank=8,
        # Native Qwen3.5 packs HF q/k/v into the actual vLLM module qkv_proj.
        # Keep PEFT adapter targets q_proj/v_proj; restrict only vLLM's deployment
        # wrapper to the packed container so the 8 full-attention qkv_proj layers
        # can ingest the 16 q/v adapter shards through packed_modules_mapping.
        lora_target_modules=["qkv_proj"],
        language_model_only=True,
        trust_remote_code=False,
        seed=SEED,
    )
    request = LoRARequest("aqlevon-smoke", 1, str(adapter_dir))

    deterministic = SamplingParams(
        temperature=0.0,
        max_tokens=1,
        logprobs=20,
        seed=SEED,
    )
    base_out = llm.generate([SMOKE_PROMPT], deterministic)
    lora_out = llm.generate([SMOKE_PROMPT], deterministic, lora_request=request)
    base_lp = _logprob_map(base_out)
    lora_lp = _logprob_map(lora_out)
    common = sorted(set(base_lp) & set(lora_lp))
    if common:
        max_delta = max(abs(base_lp[t] - lora_lp[t]) for t in common)
        if max_delta <= 1e-7:
            raise RuntimeError(
                f"AQLEVON_LORA_FUNCTIONALLY_INERT:max_logprob_delta={max_delta}"
            )
    else:
        max_delta = None  # disjoint top-logprob sets already prove a functional change.

    frozen_sampling = SamplingParams(
        temperature=0.7,
        top_p=0.8,
        top_k=20,
        max_tokens=8,
        seed=SEED,
    )
    rollout = llm.generate([SMOKE_PROMPT], frozen_sampling, lora_request=request)
    token_ids = list(rollout[0].outputs[0].token_ids)
    if not token_ids:
        raise RuntimeError("AQLEVON_SMOKE_TINY_ROLLOUT_EMPTY")

    return {
        "vllm": vllm.__version__,
        "cuda_device": torch.cuda.get_device_name(0),
        "language_model_only": True,
        "max_model_len": 4096,
        "peft_lora_target_modules": ["q_proj", "v_proj"],
        "vllm_lora_target_modules": ["qkv_proj"],
        "peft_lora_rank": 4,
        "vllm_max_lora_rank_capacity": 8,
        "base_lora_common_logprob_tokens": len(common),
        "max_common_logprob_delta": max_delta,
        "tiny_rollout_token_ids": token_ids,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-path", required=True)
    p.add_argument("--evidence", required=True)
    args = p.parse_args()

    model_path = Path(args.model_path)
    evidence_path = Path(args.evidence)
    adapter_dir = Path("/tmp/aqlevon-v019-smoke-adapter")
    if not (model_path / "config.json").is_file():
        raise SystemExit("AQLEVON_SMOKE_MODEL_CONFIG_MISSING")

    config = json.loads((model_path / "config.json").read_text())
    if config.get("_name_or_path") not in (None, "", MODEL_REPO):
        # Local snapshots may preserve the repo name; do not require it.
        pass
    layer_types = list((config.get("text_config") or {}).get("layer_types") or [])
    full_layers = [i for i, kind in enumerate(layer_types) if kind == "full_attention"]
    if full_layers != EXPECTED_FULL_ATTN_LAYERS:
        raise SystemExit(
            f"AQLEVON_SMOKE_CONFIG_FULL_ATTN_LAYOUT:{full_layers}:expected_{EXPECTED_FULL_ATTN_LAYERS}"
        )

    targets, peft_full_layers = build_ephemeral_adapter(model_path, adapter_dir)
    result = run_vllm_smoke(model_path, adapter_dir)
    result.update(
        {
            "smoke_kind": "AQLEVON_P4_A1_V019_NATIVE_LORA_FUNCTIONAL_SMOKE_V1",
            "model_repo": MODEL_REPO,
            "model_revision": MODEL_REVISION,
            "seed": SEED,
            "optimizer_steps": 0,
            "reward_calls": 0,
            "candidate_checkpoint_written": False,
            "full_attention_layers": peft_full_layers,
            "required_target_module_count": EXPECTED_TARGET_MODULES,
            "peft_target_modules": targets,
            "status": "PASS",
        }
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("AQLEVON_V019_NATIVE_LORA_FUNCTIONAL_SMOKE_PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
