#!/usr/bin/env python3
"""P4 A0 public-reference SFT control; independent of the failed A1 RLVR run."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import subprocess
from pathlib import Path

MODEL_REPO = "Qwen/Qwen3.5-4B-Base"
MODEL_REV = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
W02_HEAD = "abb94ef134e2e97036b6959dbc9db4278d3736b6"
W02_SHARD_SHA = "59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49"
W02_MANIFEST_SHA = "f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f"
PLAN_SHA = "3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095"
LAYERS = (3, 7, 11, 15, 19, 23, 27, 31)
TARGET_SUFFIXES = {f"layers.{i}.self_attn.{p}" for i in LAYERS for p in ("q_proj", "v_proj")}
WEIGHT_NAME = re.compile(r"(?:^|\.)layers\.(\d+)\.self_attn\.(q_proj|v_proj)\.lora_([AB])(?:\.default)?\.weight$")
SEED = 1701
UPDATES = 12
PER_UPDATE = 4
CAP = 2048


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def sealed(obj: dict, field: str) -> dict:
    obj = dict(obj)
    obj[field] = canonical_sha(obj)
    return obj


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def load_public_rows(shard_path: Path, manifest_path: Path, plan_path: Path) -> list[dict]:
    assert sha_file(shard_path) == W02_SHARD_SHA, "public training shard bytes changed"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads(plan_path.read_text())
    assert manifest["manifest_sha256"] == W02_MANIFEST_SHA
    assert canonical_sha({k: v for k, v in manifest.items() if k != "manifest_sha256"}) == W02_MANIFEST_SHA
    assert manifest["shard_file_sha256"] == W02_SHARD_SHA
    assert plan["plan_sha256"] == PLAN_SHA
    assert canonical_sha({k: v for k, v in plan.items() if k != "plan_sha256"}) == PLAN_SHA
    assert plan["surrogate_model"] == {"repo": MODEL_REPO, "revision": MODEL_REV,
                                        "precision": "bf16", "quantization": "none"}
    assert plan["screen_budget"]["max_optimizer_updates"] == UPDATES
    assert plan["screen_budget"]["examples_or_prompts_per_update"] == PER_UPDATE
    assert plan["screen_budget"]["sft_example_exposure_ceiling"] == UPDATES * PER_UPDATE
    a0 = next(x for x in plan["arms"] if x["arm_id"] == "P4_A0_SFT_LORA_CONTROL")
    assert a0["algorithm"].startswith("supervised next-token CE")
    assert a0["lr"] == "0.00001" and a0["min_lr"] == "0.000001"
    assert a0["optimizer"] == "AdamW" and a0["schedule"] == "cosine"
    assert a0["weight_decay"] == "0.10" and a0["warmup_fraction"] == "0.10"
    assert a0["teacher"] == "none" and a0["synthetic_targets"] is False
    rows = [json.loads(line) for line in shard_path.read_text().splitlines() if line.strip()]
    assert len(rows) == manifest["row_count"] == 56
    assert len({r["record_id"] for r in rows}) == 56
    for row in rows:
        assert row["row_kind"] == "AQLEVON_P3_SFT_CONTROL_RECORD_V1"
        assert isinstance(row["prompt"], str) and row["prompt"]
        assert isinstance(row["answer"], list) and row["answer"]
        assert "sealed" not in json.dumps(row).casefold(), "protected field in public training row"
    random.Random(SEED).shuffle(rows)
    chosen = rows[: UPDATES * PER_UPDATE]
    assert len({x["record_id"] for x in chosen}) == 48
    return chosen


def tensor_layout(weights: dict) -> dict:
    modules: dict[tuple[int, str], dict[str, tuple[int, ...]]] = {}
    assert len(weights) == 32, f"expected 32 A/B tensors, observed {len(weights)}"
    for name, value in weights.items():
        hit = WEIGHT_NAME.search(name)
        assert hit, f"unexpected adapter key: {name}"
        layer, projection, part = int(hit[1]), hit[2], hit[3]
        key = (layer, projection)
        assert part not in modules.setdefault(key, {}), f"duplicate LoRA part: {name}"
        modules[key][part] = tuple(value.shape)
    expected = {(i, p) for i in LAYERS for p in ("q_proj", "v_proj")}
    assert set(modules) == expected, f"adapter topology mismatch: {sorted(set(modules)^expected)}"
    for (layer, projection), parts in modules.items():
        assert set(parts) == {"A", "B"}
        assert parts["A"] == (4, 2560)
        assert parts["B"] == ((8192, 4) if projection == "q_proj" else (1024, 4))
    return {f"{layer}:{proj}": {k: list(v) for k, v in parts.items()}
            for (layer, proj), parts in sorted(modules.items())}


def state_hash(weights: dict) -> str:
    h = hashlib.sha256()
    for name in sorted(weights):
        value = weights[name].detach().cpu().contiguous().float()
        h.update(name.encode())
        h.update(str(tuple(value.shape)).encode("ascii"))
        h.update(value.numpy().tobytes(order="C"))
    return h.hexdigest()


def train(args: argparse.Namespace, rows: list[dict]) -> None:
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, get_peft_model_state_dict
    from peft.tuners.lora.layer import LoraLayer
    from safetensors.torch import load_file
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(), "BF16 GPU required"
    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True,
                                               trust_remote_code=False)
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0},
        low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False)
    full_layers = [i for i, kind in enumerate(base.config.text_config.layer_types)
                   if kind == "full_attention"]
    assert full_layers == list(LAYERS), full_layers
    base.config.use_cache = False
    base.gradient_checkpointing_enable()
    lora = LoraConfig(r=4, lora_alpha=4, target_modules=["q_proj", "v_proj"],
                      lora_dropout=0, bias="none", task_type=TaskType.CAUSAL_LM,
                      init_lora_weights=True)
    model = get_peft_model(base, lora)
    model.enable_input_require_grads()
    targets = sorted(name for name, mod in model.named_modules()
                     if isinstance(mod, LoraLayer) and name.endswith((".q_proj", ".v_proj")))
    observed = {next((s for s in TARGET_SUFFIXES if name.endswith(s)), "") for name in targets}
    assert observed == TARGET_SUFFIXES and len(targets) == 16, targets
    params = [p for p in model.parameters() if p.requires_grad]
    assert sum(p.numel() for p in params) == 458752
    model.train()
    optimizer = torch.optim.AdamW(params, lr=1e-5, weight_decay=0.1)
    record_ids, losses, grad_norms, lrs = [], [], [], []
    eos = tokenizer.eos_token or "<|im_end|>"
    for step in range(UPDATES):
        optimizer.zero_grad(set_to_none=True)
        total_loss = 0.0
        for row in rows[step * PER_UPDATE:(step + 1) * PER_UPDATE]:
            text = tokenizer.apply_chat_template([{"role": "user", "content": row["prompt"]}],
                                                  tokenize=False, add_generation_prompt=True,
                                                  enable_thinking=False)
            prefix = tokenizer(text, add_special_tokens=False).input_ids
            target = tokenizer(json.dumps(row["answer"], ensure_ascii=False,
                                          separators=(",", ":")) + eos,
                               add_special_tokens=False).input_ids
            assert 0 < len(target) and len(prefix) + len(target) <= CAP
            ids = prefix + target
            labels = [-100] * len(prefix) + target
            inputs = torch.tensor([ids], device="cuda", dtype=torch.long)
            supervision = torch.tensor([labels], device="cuda", dtype=torch.long)
            logits = model(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                           use_cache=False).logits
            loss = F.cross_entropy(logits[:, :-1, :].float().reshape(-1, logits.shape[-1]),
                                   supervision[:, 1:].reshape(-1), ignore_index=-100)
            assert bool(torch.isfinite(loss).item()) and loss.item() > 0
            (loss / PER_UPDATE).backward()
            total_loss += float(loss.detach()) / PER_UPDATE
            record_ids.append(row["record_id"])
            del logits, inputs, supervision, loss
        grad_norm = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
        assert math.isfinite(grad_norm) and grad_norm > 0, f"zero/invalid gradient at {step+1}"
        # One optimizer update follows exactly four unique public reference examples.
        warm = max(1, round(UPDATES * 0.10))
        if step < warm:
            lr = 1e-5 * (step + 1) / warm
        else:
            fraction = (step - warm) / max(1, UPDATES - warm - 1)
            lr = 1e-6 + (1e-5 - 1e-6) * (1 + math.cos(math.pi * fraction)) / 2
        for group in optimizer.param_groups: group["lr"] = lr
        optimizer.step()
        torch.cuda.synchronize()
        losses.append(total_loss)
        grad_norms.append(grad_norm)
        lrs.append(lr)
        print(f"AQLEVON_A0_OPTIMIZER_UPDATE={step+1}/{UPDATES} loss={total_loss:.6f} grad_norm={grad_norm:.6f} lr={lr:.9g}", flush=True)
    assert len(record_ids) == len(set(record_ids)) == 48

    output = args.output_dir
    assert not output.exists(), "refuse to overwrite Candidate"
    artifact = output / "candidate_artifact"
    artifact.mkdir(parents=True)
    model.save_pretrained(str(artifact), safe_serialization=True)
    saved = load_file(str(artifact / "adapter_model.safetensors"), device="cpu")
    layout = tensor_layout(saved)
    changed = sum(int(torch.count_nonzero(value).item()) for name, value in saved.items()
                  if ".lora_B." in name)
    assert changed > 0, "no trained LoRA-B parameter change"
    before_hash = state_hash(saved)
    cfg = json.loads((artifact / "adapter_config.json").read_text())
    assert cfg["r"] == cfg["lora_alpha"] == 4
    assert set(cfg["target_modules"]) == {"q_proj", "v_proj"}
    del saved, model, base
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    second = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0},
        low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False)
    restored = PeftModel.from_pretrained(second, str(artifact), is_trainable=False)
    reloaded = get_peft_model_state_dict(restored)
    assert tensor_layout(reloaded) == layout
    after_hash = state_hash(reloaded)
    assert before_hash == after_hash, "save/reload hash mismatch"

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo_dir, text=True).strip()
    assert head == os.environ["AQLEVON_EXPECTED_A0_HEAD"]
    digest = os.environ["AQLEVON_EXPECTED_IMAGE_DIGEST"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    receipt = sealed({
        "receipt_kind": "AQLEVON_P4_A0_SFT_TRAINING_RECEIPT_V1", "arm_id": "P4_A0_SFT_LORA_CONTROL",
        "seed": SEED, "optimizer_updates": UPDATES, "examples_per_update": PER_UPDATE,
        "unique_training_examples": len(record_ids), "training_record_ids": record_ids,
        "losses": losses, "gradient_norms": grad_norms, "learning_rates": lrs,
        "changed_lora_B_elements": changed, "adapter_tensors": 32,
        "target_modules": 16, "saved_adapter_state_sha256": before_hash,
        "reloaded_adapter_state_sha256": after_hash, "save_reload_hash_match": True,
        "public_training_shard_sha256": W02_SHARD_SHA, "public_training_manifest_sha256": W02_MANIFEST_SHA,
        "frozen_plan_sha256": PLAN_SHA, "w03_a0_execution_head": head,
        "runtime_appliance_digest": digest, "base_repo": MODEL_REPO, "base_revision": MODEL_REV,
        "sealed_eval_consumed": False, "capability_gain_claim": False,
    }, "receipt_sha256")
    write_json(output / "training_run_receipt.json", receipt)
    manifest = sealed({
        "manifest_kind": "AQLEVON_P4_A0_SFT_CANDIDATE_ARTIFACT_MANIFEST_V1",
        "artifact_type": "adapter", "candidate_stage": "ready_for_worker05_evaluation",
        "arm_id": "P4_A0_SFT_LORA_CONTROL", "base_repo": MODEL_REPO,
        "base_revision": MODEL_REV, "seed": SEED, "optimizer_updates": UPDATES,
        "training_plan_sha256": PLAN_SHA, "training_shard_sha256": W02_SHARD_SHA,
        "training_run_receipt_sha256": sha_file(output / "training_run_receipt.json"),
        "adapter_config_sha256": sha_file(artifact / "adapter_config.json"),
        "adapter_model_sha256": sha_file(artifact / "adapter_model.safetensors"),
        "adapter_state_sha256": before_hash, "tensor_layout": layout,
        "w03_a0_execution_head": head, "runtime_appliance_digest": digest,
        "capability_gain_claim": False,
    }, "manifest_sha256")
    write_json(output / "candidate_artifact_manifest.json", manifest)
    index = sealed({
        "handoff_kind": "AQLEVON_P4_A0_WORKER05_CANDIDATE_HANDOFF_V1",
        "candidate_status": "ARTIFACT_READY_FOR_WORKER05_EVALUATION",
        "arm_id": "P4_A0_SFT_LORA_CONTROL", "seed": SEED,
        "optimizer_updates": UPDATES, "candidate_manifest_sha256": manifest["manifest_sha256"],
        "training_receipt_sha256": sha_file(output / "training_run_receipt.json"),
        "w03_a0_execution_head": head, "runtime_appliance_digest": digest,
        "sealed_eval_consumed": False, "capability_gain_claim": False,
    }, "handoff_sha256")
    write_json(output / "worker05_handoff_index.json", index)
    assert sha_file(args.shard_path) == W02_SHARD_SHA
    print(f"AQLEVON_A0_CANDIDATE_PACKAGE_PASS updates=12 tensors=32 modules=16 changed_B={changed} hash={before_hash}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-path", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--plan-path", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--repo-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    rows = load_public_rows(args.shard_path, args.manifest_path, args.plan_path)
    print(f"AQLEVON_A0_PUBLIC_ONLY_PREFLIGHT_PASS rows={len(rows)} unique=48", flush=True)
    if args.preflight_only:
        return
    assert args.model_dir and args.repo_dir and args.output_dir
    train(args, rows)


if __name__ == "__main__":
    main()
