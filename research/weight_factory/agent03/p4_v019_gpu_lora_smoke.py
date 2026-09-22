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
EXPECTED_TRAINABLE_PARAMS = 458_752
EXPECTED_HIDDEN_SIZE = 2560
EXPECTED_NUM_HEADS = 16
EXPECTED_NUM_KV_HEADS = 4
EXPECTED_HEAD_DIM = 256
EXPECTED_Q_OUT = 8192
EXPECTED_V_OUT = 1024
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
    text_cfg = base.config.text_config
    layer_types = list(text_cfg.layer_types)
    if int(text_cfg.num_hidden_layers) != 32:
        raise RuntimeError(f"AQLEVON_SMOKE_LAYER_COUNT:{text_cfg.num_hidden_layers}:expected_32")
    if not bool(getattr(text_cfg, "attn_output_gate", False)):
        raise RuntimeError("AQLEVON_SMOKE_ATTN_OUTPUT_GATE_DISABLED")
    geometry = {
        "hidden_size": int(text_cfg.hidden_size),
        "num_attention_heads": int(text_cfg.num_attention_heads),
        "num_key_value_heads": int(text_cfg.num_key_value_heads),
        "head_dim": int(text_cfg.head_dim),
    }
    expected_geometry = {
        "hidden_size": EXPECTED_HIDDEN_SIZE,
        "num_attention_heads": EXPECTED_NUM_HEADS,
        "num_key_value_heads": EXPECTED_NUM_KV_HEADS,
        "head_dim": EXPECTED_HEAD_DIM,
    }
    if geometry != expected_geometry:
        raise RuntimeError(f"AQLEVON_SMOKE_GEOMETRY:{geometry}:expected_{expected_geometry}")
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
    trainable_params, _ = peft_model.get_nb_trainable_parameters()
    if int(trainable_params) != EXPECTED_TRAINABLE_PARAMS:
        raise RuntimeError(
            f"AQLEVON_SMOKE_TRAINABLE_PARAM_COUNT:{trainable_params}:expected_{EXPECTED_TRAINABLE_PARAMS}"
        )
    named_modules = dict(peft_model.named_modules())
    for name in targets:
        module = named_modules[name]
        base_layer = getattr(module, "base_layer", None)
        if base_layer is None:
            raise RuntimeError("AQLEVON_SMOKE_LORA_BASE_LAYER_MISSING:" + name)
        dims = (int(base_layer.in_features), int(base_layer.out_features))
        expected_dims = (
            (EXPECTED_HIDDEN_SIZE, EXPECTED_Q_OUT)
            if name.endswith(".q_proj")
            else (EXPECTED_HIDDEN_SIZE, EXPECTED_V_OUT)
        )
        if dims != expected_dims:
            raise RuntimeError(
                f"AQLEVON_SMOKE_TARGET_SHAPE:{name}:{dims}:expected_{expected_dims}"
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
    from safetensors.torch import load_file
    adapter_state = load_file(str(adapter_dir / "adapter_model.safetensors"))
    lora_keys = sorted(k for k in adapter_state if ".lora_A." in k or ".lora_B." in k)
    if len(lora_keys) != EXPECTED_TARGET_MODULES * 2:
        raise RuntimeError(
            f"AQLEVON_SMOKE_ADAPTER_TENSOR_COUNT:{len(lora_keys)}:expected_{EXPECTED_TARGET_MODULES * 2}"
        )
    forbidden = [k for k in lora_keys if ".linear_attn." in k or ".mtp." in k or ".visual." in k]
    if forbidden:
        raise RuntimeError("AQLEVON_SMOKE_FORBIDDEN_ADAPTER_KEYS:" + ",".join(forbidden))
    if not any(float(adapter_state[k].abs().max()) > 0 for k in lora_keys if ".lora_B." in k):
        raise RuntimeError("AQLEVON_SMOKE_DEBUG_ADAPTER_B_ALL_ZERO")

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
    base_repeat_out = llm.generate([SMOKE_PROMPT], deterministic)
    lora_out = llm.generate([SMOKE_PROMPT], deterministic, lora_request=request)
    base_lp = _logprob_map(base_out)
    base_repeat_lp = _logprob_map(base_repeat_out)
    lora_lp = _logprob_map(lora_out)
    base_common = sorted(set(base_lp) & set(base_repeat_lp))
    base_noise = (
        max(abs(base_lp[t] - base_repeat_lp[t]) for t in base_common)
        if base_common else float("inf")
    )
    if base_noise > 1e-5:
        raise RuntimeError(f"AQLEVON_SMOKE_BASE_NONDETERMINISTIC:max_logprob_delta={base_noise}")
    common = sorted(set(base_lp) & set(lora_lp))
    if common:
        max_delta = max(abs(base_lp[t] - lora_lp[t]) for t in common)
        required_delta = max(1e-6, base_noise * 10.0)
        if max_delta <= required_delta:
            raise RuntimeError(
                "AQLEVON_LORA_FUNCTIONALLY_INERT:"
                f"max_logprob_delta={max_delta}:required_gt_{required_delta}:noise={base_noise}"
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
        "base_repeat_common_logprob_tokens": len(base_common),
        "base_repeat_max_logprob_delta": base_noise,
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
