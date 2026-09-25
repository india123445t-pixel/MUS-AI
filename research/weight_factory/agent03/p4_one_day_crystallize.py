#!/usr/bin/env python3
"""AQLEVON one-day verified-trajectory crystallization.

Trains a small LoRA only on verifier-passed PUBLIC discovery trajectories from
the one-day pass@N probe. The PUBLIC shadow split is never used for gradient
updates; it is evaluated before and after training with identical seeds.
Worker05 sealed/private evaluation is forbidden.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import re
from pathlib import Path
from typing import Any

MODEL_REPO = "Qwen/Qwen3.5-4B-Base"
MODEL_REV = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
PACK_SHA = "35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
RECOVERY_KIND = "AQLEVON_ONE_DAY_PUBLIC_PASSN_PROBE_RECOVERED_DECISION_V1"
AUTH05_LOG_SHA = "047c1a06bb68ba7c8799eff3d569dd6639ed96d16deae1700c279ecb1449875d"
AUTH05_ARTIFACT_SHA = "7aa1949505d9e10c8e332f0a5cca288e16f975e93d6bff12b20531316f8454bd"
SEED = 1701
MAX_TRAIN_EXAMPLES = 24
LR = 1e-5
CAP = 2048
LAYERS = (3, 7, 11, 15, 19, 23, 27, 31)
TARGET_SUFFIXES = {f"layers.{i}.self_attn.{p}" for i in LAYERS for p in ("q_proj", "v_proj")}
WEIGHT_NAME = re.compile(r"(?:^|\.)layers\.(\d+)\.self_attn\.(q_proj|v_proj)\.lora_([AB])(?:\.default)?\.weight$")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def canonical_sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def sealed(obj: dict, field: str) -> dict:
    obj = dict(obj)
    obj[field] = canonical_sha(obj)
    return obj


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def load_w02(path: Path):
    spec = importlib.util.spec_from_file_location("aqlevon_w02_crystallize", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot_load_w02")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def strict_json_program(text: str) -> Any | None:
    s = text.strip()
    if s.startswith("```") and s.endswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"}:
            s = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(s)
    except Exception:
        return None
    return value if isinstance(value, list) and value else None


def task_index(task: dict[str, Any]) -> int:
    m = re.search(r"-(\d{2})-hardened$", task["task_id"])
    if not m:
        raise ValueError(task["task_id"])
    return int(m.group(1))


def build_core(w02, task: dict[str, Any]) -> dict[str, Any]:
    return w02._core(task["family"], task_index(task))


def verify_text(w02, task: dict[str, Any], text: str) -> tuple[bool, str]:
    program = strict_json_program(text)
    if program is None:
        return False, "invalid_json_program"
    result = w02.verify(task, build_core(w02, task), program)
    return bool(result.get("passed")), str(result.get("reason"))


def tensor_layout(weights: dict) -> dict:
    modules: dict[tuple[int, str], dict[str, tuple[int, ...]]] = {}
    if len(weights) != 32:
        raise RuntimeError(f"expected_32_adapter_tensors:{len(weights)}")
    for name, value in weights.items():
        hit = WEIGHT_NAME.search(name)
        if not hit:
            raise RuntimeError(f"unexpected_adapter_key:{name}")
        layer, projection, part = int(hit[1]), hit[2], hit[3]
        modules.setdefault((layer, projection), {})[part] = tuple(value.shape)
    expected = {(i, p) for i in LAYERS for p in ("q_proj", "v_proj")}
    if set(modules) != expected:
        raise RuntimeError("adapter_topology_mismatch")
    for (_, projection), parts in modules.items():
        if set(parts) != {"A", "B"}:
            raise RuntimeError("adapter_AB_mismatch")
        if parts["A"] != (4, 2560):
            raise RuntimeError("adapter_A_shape_mismatch")
        expected_b = (8192, 4) if projection == "q_proj" else (1024, 4)
        if parts["B"] != expected_b:
            raise RuntimeError("adapter_B_shape_mismatch")
    return {f"{layer}:{proj}": {k: list(v) for k, v in parts.items()}
            for (layer, proj), parts in sorted(modules.items())}


def state_hash(weights: dict) -> str:
    h = hashlib.sha256()
    for name in sorted(weights):
        value = weights[name].detach().cpu().contiguous().float()
        h.update(name.encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.numpy().tobytes(order="C"))
    return h.hexdigest()


def load_inputs(args):
    if os.environ.get("AQLEVON_SEALED_EVAL_PATH") or os.environ.get("AQLEVON_EVAL_SECRET"):
        raise RuntimeError("sealed_eval_environment_forbidden")
    probe = json.loads(args.probe_result.read_text())
    recovery_mode = probe.get("kind") == RECOVERY_KIND
    if recovery_mode:
        if probe.get("recovered_decision") != "MATERIAL_LATENT_CAPABILITY":
            raise RuntimeError("recovery_not_material")
        if probe.get("probe_log_sha256") != AUTH05_LOG_SHA or probe.get("artifact_zip_sha256") != AUTH05_ARTIFACT_SHA:
            raise RuntimeError("auth05_recovery_evidence_identity_mismatch")
    else:
        if probe.get("result_kind") != "AQLEVON_ONE_DAY_PUBLIC_VERIFIED_TRAJECTORY_PROBE_V1":
            raise RuntimeError("wrong_probe_kind")
        if probe.get("decision") != "MATERIAL_LATENT_CAPABILITY":
            raise RuntimeError(f"probe_not_material:{probe.get('decision')}")
    if probe.get("sealed_eval_consumed") is not False or probe.get("worker05_used_for_tuning") is not False:
        raise RuntimeError("protected_eval_contamination")
    if probe.get("model_repo") != MODEL_REPO or probe.get("model_revision") != MODEL_REV:
        raise RuntimeError("model_identity_mismatch")
    if probe.get("training_pack_sha256") != PACK_SHA:
        raise RuntimeError("pack_identity_mismatch")

    pack = json.loads(args.training_pack.read_text())
    if pack.get("pack_sha256") != PACK_SHA or pack.get("pack_kind") != "AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1":
        raise RuntimeError("public_pack_mismatch")
    tasks = {t["task_id"]: t for t in pack["tasks"]
             if t.get("verifier_mode") == "hardened" and t.get("training_eligible") is True}
    if len(tasks) != 56:
        raise RuntimeError(f"expected_56_public_tasks:{len(tasks)}")

    if recovery_mode:
        statuses = probe.get("task_status") or []
        if len(statuses) != 56 or len({x["task_id"] for x in statuses}) != 56:
            raise RuntimeError("recovery_status_count_or_uniqueness_error")
        if set(tasks) != {x["task_id"] for x in statuses}:
            raise RuntimeError("recovery_task_identity_mismatch")
        discovery = [x for x in statuses if x.get("public_split") == "discovery"]
        shadow_status = [x for x in statuses if x.get("public_split") == "shadow"]
        d1 = sum(bool(x["pass_at_1"]) for x in discovery)
        d8 = sum(bool(x["pass_at_8"]) for x in discovery)
        s1 = sum(bool(x["pass_at_1"]) for x in shadow_status)
        s8 = sum(bool(x["pass_at_8"]) for x in shadow_status)
        a1 = sum(bool(x["pass_at_1"]) for x in statuses)
        a8 = sum(bool(x["pass_at_8"]) for x in statuses)
        if not (len(discovery) == 28 and len(shadow_status) == 28
                and (d8-d1)/28 >= 0.10 and (s8-s1)/28 >= 0.10 and (a8-a1) >= 6):
            raise RuntimeError("recovered_material_rule_recompute_failed")
        records = []
        for status in statuses:
            tid = status["task_id"]
            task = tasks[tid]
            split = status["public_split"]
            candidates = []
            if split == "discovery":
                oracle = json.dumps(task["oracle_program"], ensure_ascii=False, separators=(",", ":"))
                if status["pass_at_8"]:
                    if status["pass_at_1"]:
                        candidates = [{"passed": True, "reason": "recovery_public_oracle_anchor", "text": oracle}]
                    else:
                        candidates = [
                            {"passed": False, "reason": "auth05_pass1_failed", "text": "[]"},
                            {"passed": True, "reason": "recovery_public_oracle_rescued_core", "text": oracle},
                        ]
                else:
                    candidates = [{"passed": False, "reason": "auth05_pass8_failed", "text": "[]"}]
            records.append({
                "task_id": tid,
                "semantic_core_id": task["semantic_core_id"],
                "family": task["family"],
                "public_split": split,
                "candidates": candidates,
                "repair": None,
            })
    else:
        records = probe.get("records") or []
    if len(records) != 56:
        raise RuntimeError(f"expected_56_probe_records:{len(records)}")
    train = []
    shadow = []
    for rec in records:
        tid = rec["task_id"]
        task = tasks[tid]
        if rec["public_split"] == "discovery":
            candidates = rec.get("candidates") or []
            chosen = None
            chosen_kind = None
            priority = None
            # Highest-value signal: pass@1 failed but a later sampled trajectory passed.
            for idx, cand in enumerate(candidates[1:], start=2):
                if candidates and not candidates[0].get("passed") and cand.get("passed"):
                    chosen, chosen_kind, priority = cand["text"], f"rescued_sample_{idx}", 0
                    break
            # Next: deterministic verifier feedback repaired a task after all 8 samples failed.
            if chosen is None and (rec.get("repair") or {}).get("passed"):
                chosen, chosen_kind, priority = rec["repair"]["text"], "repair_after_8_failures", 1
            # Filler/stability only: a task already solved at pass@1.
            if chosen is None and candidates and candidates[0].get("passed"):
                chosen, chosen_kind, priority = candidates[0]["text"], "pass1_verified_filler", 2
            # Last fallback: any verified later sample (should normally already be rescue).
            if chosen is None:
                for idx, cand in enumerate(candidates[1:], start=2):
                    if cand.get("passed"):
                        chosen, chosen_kind, priority = cand["text"], f"later_verified_sample_{idx}", 3
                        break
            if chosen is not None:
                program = strict_json_program(chosen)
                if program is None:
                    raise RuntimeError(f"verified_candidate_not_json:{tid}")
                canonical = json.dumps(program, ensure_ascii=False, separators=(",", ":"))
                source_label = rec.get("recovered_source") if probe.get("recovered_materialization") else chosen_kind
                if not source_label:
                    source_label = chosen_kind
                train.append({"task_id": tid, "prompt": task["prompt"], "target": canonical,
                              "source": source_label, "priority": priority, "family": task["family"]})
        elif rec["public_split"] == "shadow":
            shadow.append(task)
        else:
            raise RuntimeError(f"unexpected_split:{rec['public_split']}")
    if len(shadow) != 28:
        raise RuntimeError(f"expected_28_shadow:{len(shadow)}")
    if len(train) < 6:
        raise RuntimeError(f"too_few_verified_discovery_trajectories:{len(train)}")
    # Preserve information efficiency: rescue/repaired blind spots first, then stable fillers.
    rng = random.Random(SEED)
    for item in train:
        item["_tie"] = rng.random()
    train.sort(key=lambda x: (x["priority"], x["_tie"], x["task_id"]))
    train = train[:MAX_TRAIN_EXAMPLES]
    for item in train:
        item.pop("_tie", None)
    return probe, train, sorted(shadow, key=lambda x: x["task_id"])


def evaluate_shadow(model, tokenizer, w02, shadow, generation):
    import torch
    model.eval()
    passed = 0
    rows = []
    for task in shadow:
        seed = SEED + int(hashlib.sha256(task["task_id"].encode()).hexdigest()[:8], 16)
        random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        chat = tokenizer.apply_chat_template([{"role": "user", "content": task["prompt"]}],
                                              tokenize=False, add_generation_prompt=True,
                                              enable_thinking=False)
        enc = tokenizer(chat, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            out = model.generate(**enc, do_sample=True, temperature=generation["temperature"],
                                 top_p=generation["top_p"], top_k=generation["top_k"],
                                 max_new_tokens=generation["max_new_tokens"], num_return_sequences=1,
                                 use_cache=True, pad_token_id=tokenizer.eos_token_id)[0]
        text = tokenizer.decode(out[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        ok, reason = verify_text(w02, task, text)
        passed += int(ok)
        rows.append({"task_id": task["task_id"], "passed": ok, "reason": reason, "text": text})
        del enc, out
    return {"successes": passed, "tasks": len(shadow), "pass_at_1": passed / len(shadow), "records": rows}


def run(args):
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, get_peft_model_state_dict
    from peft.tuners.lora.layer import LoraLayer
    from safetensors.torch import load_file
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("bf16_cuda_required")
    probe, train_rows, shadow = load_inputs(args)
    w02 = load_w02(args.w02_module)
    generation = dict(probe["generation"])

    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True, trust_remote_code=False)
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0},
        low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False)
    full_layers = [i for i, kind in enumerate(base.config.text_config.layer_types) if kind == "full_attention"]
    if full_layers != list(LAYERS):
        raise RuntimeError(f"full_attention_layers_changed:{full_layers}")

    pre = evaluate_shadow(base, tokenizer, w02, shadow, generation)
    print("AQLEVON_CRYSTALLIZE_SHADOW_PRE", json.dumps({k:v for k,v in pre.items() if k!="records"}, sort_keys=True), flush=True)

    base.config.use_cache = False
    base.gradient_checkpointing_enable()
    lora = LoraConfig(r=4, lora_alpha=4, target_modules=["q_proj", "v_proj"],
                      lora_dropout=0, bias="none", task_type=TaskType.CAUSAL_LM, init_lora_weights=True)
    model = get_peft_model(base, lora)
    model.enable_input_require_grads()
    targets = sorted(name for name, mod in model.named_modules()
                     if isinstance(mod, LoraLayer) and name.endswith((".q_proj", ".v_proj")))
    observed = {next((s for s in TARGET_SUFFIXES if name.endswith(s)), "") for name in targets}
    if observed != TARGET_SUFFIXES or len(targets) != 16:
        raise RuntimeError("lora_target_topology_mismatch")
    params = [p for p in model.parameters() if p.requires_grad]
    if sum(p.numel() for p in params) != 458752:
        raise RuntimeError("trainable_parameter_count_mismatch")
    optimizer = torch.optim.AdamW(params, lr=LR, weight_decay=0.05)
    model.train()
    losses=[]; grad_norms=[]; used=[]
    eos = tokenizer.eos_token or "<|im_end|>"
    steps = len(train_rows)
    for step, row in enumerate(train_rows):
        optimizer.zero_grad(set_to_none=True)
        prompt = tokenizer.apply_chat_template([{"role":"user","content":row["prompt"]}],
                                               tokenize=False, add_generation_prompt=True,
                                               enable_thinking=False)
        prefix = tokenizer(prompt, add_special_tokens=False).input_ids
        target = tokenizer(row["target"] + eos, add_special_tokens=False).input_ids
        if not target or len(prefix)+len(target) > CAP:
            raise RuntimeError(f"sequence_cap_violation:{row['task_id']}")
        ids = torch.tensor([prefix+target], device="cuda", dtype=torch.long)
        labels = torch.tensor([[-100]*len(prefix)+target], device="cuda", dtype=torch.long)
        logits = model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False).logits
        loss = F.cross_entropy(logits[:, :-1, :].float().reshape(-1, logits.shape[-1]),
                               labels[:, 1:].reshape(-1), ignore_index=-100)
        if not bool(torch.isfinite(loss).item()) or loss.item() <= 0:
            raise RuntimeError(f"invalid_loss:{step+1}")
        loss.backward()
        grad = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
        if not math.isfinite(grad) or grad <= 0:
            raise RuntimeError(f"invalid_gradient:{step+1}")
        # short cosine decay; no warmup because each verified trajectory is used once.
        frac = step / max(1, steps-1)
        lr = 1e-6 + (LR-1e-6) * (1 + math.cos(math.pi*frac)) / 2
        for group in optimizer.param_groups:
            group["lr"] = lr
        optimizer.step()
        losses.append(float(loss.detach()))
        grad_norms.append(grad)
        used.append(row)
        print(f"AQLEVON_CRYSTALLIZE_UPDATE={step+1}/{steps} loss={losses[-1]:.6f} grad_norm={grad:.6f} lr={lr:.9g}", flush=True)
        del ids, labels, logits, loss
    torch.cuda.synchronize()

    outdir=args.output_dir
    if outdir.exists():
        raise RuntimeError("refuse_overwrite_output")
    artifact=outdir/"candidate_artifact"
    artifact.mkdir(parents=True)
    model.save_pretrained(str(artifact), safe_serialization=True)
    saved=load_file(str(artifact/"adapter_model.safetensors"), device="cpu")
    layout=tensor_layout(saved)
    changed=sum(int(torch.count_nonzero(v).item()) for n,v in saved.items() if ".lora_B." in n)
    if changed <= 0:
        raise RuntimeError("no_lora_B_change")
    saved_hash=state_hash(saved)

    # Prove that the exact saved artifact reloads to the identical LoRA state,
    # then evaluate the reloaded artifact rather than the in-memory trainer.
    del saved, model, base, optimizer
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    reloaded_base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0},
        low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False)
    reloaded = PeftModel.from_pretrained(reloaded_base, str(artifact), is_trainable=False)
    reloaded_state = get_peft_model_state_dict(reloaded)
    if tensor_layout(reloaded_state) != layout:
        raise RuntimeError("save_reload_layout_mismatch")
    reloaded_hash = state_hash(reloaded_state)
    if reloaded_hash != saved_hash:
        raise RuntimeError("save_reload_hash_mismatch")
    reloaded.config.use_cache = True
    post=evaluate_shadow(reloaded, tokenizer, w02, shadow, generation)
    improvement=post["pass_at_1"]-pre["pass_at_1"]
    gain_tasks=post["successes"]-pre["successes"]
    public_gate=bool(improvement >= 0.10 and gain_tasks >= 3)
    print("AQLEVON_CRYSTALLIZE_SHADOW_POST", json.dumps({k:v for k,v in post.items() if k!="records"}, sort_keys=True), flush=True)
    print(f"AQLEVON_CRYSTALLIZE_PUBLIC_GATE={'PASS' if public_gate else 'FAIL'} improvement={improvement:.6f} gain_tasks={gain_tasks}", flush=True)

    probe_sha=sha_file(args.probe_result)
    train_path=outdir/"verified_discovery_trajectories.json"
    write_json(train_path, used)
    receipt=sealed({
        "receipt_kind":"AQLEVON_ONE_DAY_VERIFIED_TRAJECTORY_CRYSTALLIZATION_RECEIPT_V1",
        "base_repo":MODEL_REPO,"base_revision":MODEL_REV,"probe_result_sha256":probe_sha,
        "public_pack_sha256":PACK_SHA,"seed":SEED,"train_examples":len(used),
        "train_task_ids":[x["task_id"] for x in used],
        "train_sources":[{"task_id":x["task_id"],"source":x["source"],"priority":x["priority"]} for x in used],
        "optimizer_updates":len(used),
        "losses":losses,"gradient_norms":grad_norms,"adapter_tensors":32,"target_modules":16,
        "changed_lora_B_elements":changed,"adapter_state_sha256":saved_hash,
        "reloaded_adapter_state_sha256":reloaded_hash,"save_reload_hash_match":True,
        "shadow_pre_successes":pre["successes"],"shadow_pre_pass_at_1":pre["pass_at_1"],
        "shadow_post_successes":post["successes"],"shadow_post_pass_at_1":post["pass_at_1"],
        "shadow_gain_tasks":gain_tasks,"shadow_improvement":improvement,"public_shadow_gate_pass":public_gate,
        "recovered_materialization":bool(probe.get("recovered_materialization", False)),
        "target_provenance":probe.get("target_provenance"),
        "recovered_decision_sha256":probe.get("recovered_decision_sha256"),
        "auth05_probe_log_sha256":probe.get("auth05_probe_log_sha256"),
        "sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False
    },"receipt_sha256")
    write_json(outdir/"training_run_receipt.json",receipt)
    write_json(outdir/"shadow_pre_eval.json",pre)
    write_json(outdir/"shadow_post_eval.json",post)

    del reloaded_state
    manifest=sealed({
        "manifest_kind":"AQLEVON_ONE_DAY_CRYSTALLIZED_CANDIDATE_MANIFEST_V1",
        "candidate_status":"READY_FOR_WORKER05_EVALUATION" if public_gate else "PUBLIC_SHADOW_GATE_FAILED",
        "artifact_type":"adapter","base_repo":MODEL_REPO,"base_revision":MODEL_REV,
        "probe_result_sha256":probe_sha,"verified_trajectory_file_sha256":sha_file(train_path),
        "training_receipt_sha256":sha_file(outdir/"training_run_receipt.json"),
        "adapter_config_sha256":sha_file(artifact/"adapter_config.json"),
        "adapter_model_sha256":sha_file(artifact/"adapter_model.safetensors"),
        "adapter_state_sha256":saved_hash,"reloaded_adapter_state_sha256":reloaded_hash,
        "save_reload_hash_match":True,"tensor_layout":layout,
        "public_shadow_gate_pass":public_gate,
        "recovered_materialization":bool(probe.get("recovered_materialization", False)),
        "target_provenance":probe.get("target_provenance"),
        "recovered_decision_sha256":probe.get("recovered_decision_sha256"),
        "auth05_probe_log_sha256":probe.get("auth05_probe_log_sha256"),
        "sealed_eval_consumed":False,
        "worker05_used_for_tuning":False,"capability_gain_claim":False
    },"manifest_sha256")
    write_json(outdir/"candidate_artifact_manifest.json",manifest)
    handoff=sealed({
        "handoff_kind":"AQLEVON_ONE_DAY_CRYSTALLIZED_WORKER05_HANDOFF_V1",
        "candidate_status":manifest["candidate_status"],
        "candidate_manifest_sha256":manifest["manifest_sha256"],
        "probe_result_sha256":probe_sha,
        "public_shadow_gate_pass":public_gate,
        "sealed_eval_consumed":False,"capability_gain_claim":False
    },"handoff_sha256")
    write_json(outdir/"worker05_handoff_index.json",handoff)
    print(f"AQLEVON_CRYSTALLIZE_PACKAGE_PASS status={manifest['candidate_status']} tensors=32 modules=16 changed_B={changed}", flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--probe-result", type=Path, required=True)
    p.add_argument("--w02-module", type=Path, required=True)
    p.add_argument("--training-pack", type=Path, required=True)
    p.add_argument("--model-dir", type=Path)
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--preflight-only", action="store_true")
    args=p.parse_args()
    probe, train, shadow=load_inputs(args)
    print(f"AQLEVON_CRYSTALLIZE_PUBLIC_PREFLIGHT_PASS train_verified={len(train)} shadow={len(shadow)} probe_decision={probe['decision']}", flush=True)
    if args.preflight_only:
        return
    if not args.model_dir or not args.output_dir:
        p.error("--model-dir and --output-dir required unless --preflight-only")
    run(args)

if __name__=="__main__":
    main()
