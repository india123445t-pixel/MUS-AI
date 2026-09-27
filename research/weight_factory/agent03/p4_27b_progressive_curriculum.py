#!/usr/bin/env python3
"""AQLEVON 27B Gene #1 progressive curriculum transfer.

Transfers the publicly verified Auth16 AQLEVON-owned synthetic curriculum recipe
onto the canonical Qwen3.8-27B research base. Protected Worker05 material is
forbidden. PUBLIC discovery tasks (indices 00..01) may select an early stop;
PUBLIC shadow tasks (02..03) are evaluated exactly once after the checkpoint is
frozen. Training uses only newly generated synthetic indices 04..19.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import shutil
import time
from pathlib import Path
from typing import Any

MODEL_REPO = "Qwen/Qwen3.8-27B"
MODEL_REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
PACK_SHA = "35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
SEED = 1701
PHASES = ((4, 8), (8, 12), (12, 16), (16, 20))
PERTURBATIONS = 3
LR = 1e-5
MIN_LR = 1e-6
CAP = 2048
LORA_R = 8
LORA_ALPHA = 16
EXPECTED_TEXT_LAYERS = 64
EXPECTED_FULL_ATTN_LAYERS = 16
GENERATION = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_new_tokens": 96}
PROJECTIONS = ("q_proj", "k_proj", "v_proj", "o_proj")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def sealed(obj: dict[str, Any], field: str) -> dict[str, Any]:
    out = dict(obj)
    out[field] = canonical_sha(out)
    return out


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_w02(path: Path):
    spec = importlib.util.spec_from_file_location("aqlevon_w02_gene1", str(path))
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
        raise RuntimeError(f"bad_task_id:{task['task_id']}")
    return int(m.group(1))


def build_core(w02, task: dict[str, Any]) -> dict[str, Any]:
    return w02._core(task["family"], task_index(task))


def verify_text(w02, task: dict[str, Any], text: str) -> tuple[bool, str]:
    program = strict_json_program(text)
    if program is None:
        return False, "invalid_json_program"
    result = w02.verify(task, build_core(w02, task), program)
    return bool(result.get("passed")), str(result.get("reason"))


def load_public_inputs(pack_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if os.environ.get("AQLEVON_SEALED_EVAL_PATH") or os.environ.get("AQLEVON_EVAL_SECRET"):
        raise RuntimeError("sealed_eval_environment_forbidden")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    if pack.get("pack_kind") != "AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1" or pack.get("pack_sha256") != PACK_SHA:
        raise RuntimeError("public_pack_identity_mismatch")
    tasks = [t for t in pack.get("tasks", []) if t.get("verifier_mode") == "hardened" and t.get("training_eligible") is True]
    if len(tasks) != 56:
        raise RuntimeError(f"expected_56_public_tasks:{len(tasks)}")
    dev, shadow = [], []
    for task in tasks:
        idx = task_index(task)
        if idx in (0, 1):
            dev.append(task)
        elif idx in (2, 3):
            shadow.append(task)
        else:
            raise RuntimeError(f"unexpected_public_index:{idx}")
    dev.sort(key=lambda x: x["task_id"])
    shadow.sort(key=lambda x: x["task_id"])
    if len(dev) != 28 or len(shadow) != 28:
        raise RuntimeError("public_split_count_mismatch")
    return dev, shadow


def build_rows(w02, start: int, stop: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in w02.FAMILIES:
        for idx in range(start, stop):
            core = w02._core(family, idx)
            task = w02._task(core, "hardened", training_visible=True)
            check = w02.verify(task, core, core["oracle_program"])
            if not check.get("passed"):
                raise RuntimeError(f"synthetic_oracle_verify_failed:{family}:{idx}:{check}")
            target = json.dumps(core["oracle_program"], ensure_ascii=False, separators=(",", ":"))
            for perturb in range(PERTURBATIONS):
                rows.append({
                    "task_id": f"synthetic-{family}-{idx:02d}-p{perturb}",
                    "prompt": w02._render_prompt(core, perturb),
                    "target": target,
                    "family": family,
                    "synthetic_index": idx,
                    "perturbation": perturb,
                })
    rows.sort(key=lambda x: (x["family"], x["synthetic_index"], x["perturbation"]))
    expected = len(w02.FAMILIES) * (stop - start) * PERTURBATIONS
    if len(rows) != expected:
        raise RuntimeError(f"synthetic_row_count_mismatch:{len(rows)}:{expected}")
    return rows


def state_hash(weights: dict[str, Any]) -> str:
    h = hashlib.sha256()
    for name in sorted(weights):
        value = weights[name].detach().cpu().contiguous().float()
        h.update(name.encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.numpy().tobytes(order="C"))
    return h.hexdigest()


def evaluate_tasks(model, tokenizer, w02, tasks: list[dict[str, Any]], label: str) -> dict[str, Any]:
    import torch
    model.eval()
    passed = 0
    rows = []
    for i, task in enumerate(tasks):
        seed = SEED + int(hashlib.sha256((label + ":" + task["task_id"]).encode()).hexdigest()[:8], 16)
        random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        chat = tokenizer.apply_chat_template([{"role": "user", "content": task["prompt"]}], tokenize=False,
                                              add_generation_prompt=True, enable_thinking=False)
        enc = tokenizer(chat, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            out = model.generate(**enc, do_sample=True, temperature=GENERATION["temperature"],
                                 top_p=GENERATION["top_p"], top_k=GENERATION["top_k"],
                                 max_new_tokens=GENERATION["max_new_tokens"], num_return_sequences=1,
                                 use_cache=True, pad_token_id=tokenizer.eos_token_id)[0]
        text_out = tokenizer.decode(out[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        ok, reason = verify_text(w02, task, text_out)
        passed += int(ok)
        rows.append({"task_id": task["task_id"], "passed": ok, "reason": reason, "text": text_out})
        del enc, out
        if (i + 1) % 7 == 0:
            print(f"AQLEVON_27B_EVAL label={label} progress={i+1}/{len(tasks)} pass={passed}", flush=True)
    return {"successes": passed, "tasks": len(tasks), "pass_at_1": passed / len(tasks), "records": rows}


def regression_ids(pre: dict[str, Any], post: dict[str, Any]) -> list[str]:
    a = {r["task_id"]: bool(r["passed"]) for r in pre["records"]}
    b = {r["task_id"]: bool(r["passed"]) for r in post["records"]}
    return sorted(k for k, v in a.items() if v and not b.get(k, False))


def discover_exact_targets(base) -> tuple[list[int], list[str]]:
    layer_types = list(base.config.text_config.layer_types)
    if len(layer_types) != EXPECTED_TEXT_LAYERS:
        raise RuntimeError(f"text_layer_count_changed:{len(layer_types)}")
    full_layers = [i for i, kind in enumerate(layer_types) if kind == "full_attention"]
    if len(full_layers) != EXPECTED_FULL_ATTN_LAYERS:
        raise RuntimeError(f"full_attention_layer_count_changed:{full_layers}")
    selected = []
    prefix = "model.language_model.layers."
    for name, _module in base.named_modules():
        if not name.startswith(prefix) or ".self_attn." not in name:
            continue
        suffix = name.rsplit(".", 1)[-1]
        if suffix not in PROJECTIONS:
            continue
        try:
            layer = int(name[len(prefix):].split(".", 1)[0])
        except Exception:
            continue
        if layer in full_layers:
            selected.append(name)
    selected = sorted(set(selected))
    if len(selected) != EXPECTED_FULL_ATTN_LAYERS * len(PROJECTIONS):
        raise RuntimeError(f"target_module_count_changed:{len(selected)}")
    if any("visual" in n.lower() or "linear_attn" in n.lower() for n in selected):
        raise RuntimeError("forbidden_target_module")
    return full_layers, selected


def save_adapter(model, tokenizer, path: Path) -> dict[str, Any]:
    from peft import get_peft_model_state_dict
    path.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(path, safe_serialization=True)
    tokenizer.save_pretrained(path)
    state = get_peft_model_state_dict(model)
    h = state_hash(state)
    files = {str(p.relative_to(path)): sha_file(p) for p in sorted(path.rglob("*")) if p.is_file()}
    return {"state_sha256": h, "files": files}


def run(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, get_peft_model_state_dict
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("bf16_cuda_required")
    if args.output_dir.exists():
        raise RuntimeError("refuse_overwrite_output")
    args.output_dir.mkdir(parents=True)
    w02 = load_w02(args.w02_module)
    dev, shadow = load_public_inputs(args.training_pack)

    random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True, trust_remote_code=False)
    torch.cuda.reset_peak_memory_stats()
    load_t0 = time.time()
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0}, low_cpu_mem_usage=True,
        local_files_only=True, trust_remote_code=False)
    load_seconds = time.time() - load_t0
    full_layers, selected = discover_exact_targets(base)
    print("AQLEVON_27B_TOPOLOGY", json.dumps({"full_layers": full_layers, "targets": len(selected)}), flush=True)

    base.config.use_cache = True
    dev_pre = evaluate_tasks(base, tokenizer, w02, dev, "dev-pre")
    print("AQLEVON_27B_DEV_PRE", json.dumps({k:v for k,v in dev_pre.items() if k != "records"}, sort_keys=True), flush=True)

    for p in base.parameters():
        p.requires_grad_(False)
    base.config.use_cache = False
    base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    lora = LoraConfig(r=LORA_R, lora_alpha=LORA_ALPHA, target_modules=selected, lora_dropout=0,
                      bias="none", task_type=TaskType.CAUSAL_LM, init_lora_weights=True)
    model = get_peft_model(base, lora)
    model.enable_input_require_grads()
    trainable_names = [n for n,p in model.named_parameters() if p.requires_grad]
    if not trainable_names or any("visual" in n.lower() or "linear_attn" in n.lower() for n in trainable_names):
        raise RuntimeError("invalid_trainable_topology")
    params = [p for p in model.parameters() if p.requires_grad]
    trainable_count = sum(p.numel() for p in params)
    optimizer = torch.optim.AdamW(params, lr=LR, weight_decay=0.05)
    max_updates = sum(len(build_rows(w02, a, b)) for a,b in PHASES)
    if max_updates != 672:
        raise RuntimeError(f"max_update_count_changed:{max_updates}")

    history=[]; global_step=0; best_success=-1; best_phase=None; best_dir=None; best_meta=None
    eos = tokenizer.eos_token or "<|im_end|>"
    for phase_idx, (start, stop) in enumerate(PHASES, 1):
        rows = build_rows(w02, start, stop)
        random.Random(SEED + phase_idx).shuffle(rows)
        model.train(); model.config.use_cache=False
        losses=[]; phase_t0=time.time()
        for row in rows:
            optimizer.zero_grad(set_to_none=True)
            prompt = tokenizer.apply_chat_template([{"role":"user","content":row["prompt"]}], tokenize=False,
                                                   add_generation_prompt=True, enable_thinking=False)
            prefix = tokenizer(prompt, add_special_tokens=False).input_ids
            target = tokenizer(row["target"] + eos, add_special_tokens=False).input_ids
            if not target or len(prefix)+len(target)>CAP:
                raise RuntimeError(f"sequence_cap_violation:{row['task_id']}")
            ids=torch.tensor([prefix+target], device="cuda", dtype=torch.long)
            labels=torch.tensor([[-100]*len(prefix)+target], device="cuda", dtype=torch.long)
            logits=model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False).logits
            loss=F.cross_entropy(logits[:,:-1,:].float().reshape(-1,logits.shape[-1]), labels[:,1:].reshape(-1), ignore_index=-100)
            if not bool(torch.isfinite(loss).item()) or loss.item()<=0:
                raise RuntimeError(f"invalid_loss:{global_step+1}")
            loss.backward()
            grad=float(torch.nn.utils.clip_grad_norm_(params,1.0))
            if not math.isfinite(grad) or grad<=0:
                raise RuntimeError(f"invalid_gradient:{global_step+1}")
            frac=global_step/max(1,max_updates-1)
            lr=MIN_LR+(LR-MIN_LR)*(1+math.cos(math.pi*frac))/2
            for group in optimizer.param_groups: group["lr"]=lr
            optimizer.step(); global_step+=1; losses.append(float(loss.detach()))
            if global_step==1 or global_step%42==0:
                print(f"AQLEVON_27B_UPDATE={global_step}/{max_updates} phase={phase_idx} loss={losses[-1]:.6f} grad={grad:.6f} lr={lr:.9g}", flush=True)
            del ids,labels,logits,loss
        torch.cuda.synchronize()
        model.config.use_cache=True
        dev_post=evaluate_tasks(model,tokenizer,w02,dev,f"dev-phase-{phase_idx}")
        regs=regression_ids(dev_pre,dev_post)
        phase_dir=args.output_dir/f"phase_{phase_idx}_adapter"
        meta=save_adapter(model,tokenizer,phase_dir)
        row={"phase":phase_idx,"synthetic_index_start":start,"synthetic_index_stop_exclusive":stop,
             "cumulative_updates":global_step,"phase_seconds":time.time()-phase_t0,
             "loss_first":losses[0],"loss_last":losses[-1],"dev_successes":dev_post["successes"],
             "dev_gain":dev_post["successes"]-dev_pre["successes"],"dev_regressions":regs,
             "adapter_state_sha256":meta["state_sha256"]}
        history.append(row); print("AQLEVON_27B_PHASE",json.dumps(row,sort_keys=True),flush=True)
        if not regs and dev_post["successes"]>best_success:
            best_success=dev_post["successes"]; best_phase=phase_idx; best_dir=phase_dir; best_meta=meta
        if not regs and dev_post["successes"]==len(dev):
            print(f"AQLEVON_27B_EARLY_STOP phase={phase_idx} reason=perfect_dev",flush=True)
            break
        model.config.use_cache=False

    if best_dir is None:
        raise RuntimeError("no_nonregressing_dev_checkpoint")
    selected_updates=next(x["cumulative_updates"] for x in history if x["phase"]==best_phase)
    selected_dev=next(x for x in history if x["phase"]==best_phase)
    del optimizer, model, base, params
    gc.collect(); torch.cuda.empty_cache()

    final_dir=args.output_dir/"candidate_artifact"
    shutil.copytree(best_dir,final_dir)
    selected_manifest={"selected_phase":best_phase,"selected_updates":selected_updates,
                       "dev_successes":selected_dev["dev_successes"],"dev_gain":selected_dev["dev_gain"],
                       "dev_regressions":selected_dev["dev_regressions"],
                       "adapter_state_sha256":best_meta["state_sha256"]}
    write_json(args.output_dir/"selected_checkpoint_before_shadow.json",selected_manifest)

    reload_base=Qwen3_5ForConditionalGeneration.from_pretrained(str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},
                                                                 low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    reloaded=PeftModel.from_pretrained(reload_base,str(final_dir),is_trainable=False)
    reloaded.config.use_cache=True
    reload_state=get_peft_model_state_dict(reloaded)
    reload_hash=state_hash(reload_state)
    if reload_hash != best_meta["state_sha256"]:
        raise RuntimeError("save_reload_state_hash_mismatch")
    shadow_post=evaluate_tasks(reloaded,tokenizer,w02,shadow,"shadow-post-frozen")
    del reload_state,reloaded,reload_base
    gc.collect(); torch.cuda.empty_cache()

    fresh=Qwen3_5ForConditionalGeneration.from_pretrained(str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},
                                                           low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    fresh.config.use_cache=True
    shadow_pre=evaluate_tasks(fresh,tokenizer,w02,shadow,"shadow-pre-frozen")
    del fresh
    gc.collect(); torch.cuda.empty_cache()

    shadow_regs=regression_ids(shadow_pre,shadow_post)
    dev_gain=selected_dev["dev_successes"]-dev_pre["successes"]
    shadow_gain=shadow_post["successes"]-shadow_pre["successes"]
    dev_gate=bool(dev_gain>=3 and not selected_dev["dev_regressions"])
    shadow_gate=bool(shadow_gain>=3 and not shadow_regs)
    public_gate=bool(dev_gate and shadow_gate)
    adapter_file=final_dir/"adapter_model.safetensors"
    result={
      "kind":"AQLEVON_27B_R0A_PROGRESSIVE_RECIPE_TRANSFER_RECEIPT_V1",
      "model_repo":MODEL_REPO,"model_revision":MODEL_REV,"training_pack_sha256":PACK_SHA,
      "seed":SEED,"precision":"bf16","quantization":"none","lora_r":LORA_R,"lora_alpha":LORA_ALPHA,
      "full_attention_layers":full_layers,"target_module_count":len(selected),"trainable_parameter_count":trainable_count,
      "max_optimizer_updates":max_updates,"selected_optimizer_updates":selected_updates,"selected_phase":best_phase,
      "phase_history":history,"dev_pre_successes":dev_pre["successes"],"dev_post_successes":selected_dev["dev_successes"],
      "dev_gain_tasks":dev_gain,"dev_regressions":selected_dev["dev_regressions"],"discovery_dev_gate_pass":dev_gate,
      "shadow_pre_successes":shadow_pre["successes"],"shadow_post_successes":shadow_post["successes"],
      "shadow_gain_tasks":shadow_gain,"shadow_regressions":shadow_regs,"public_shadow_gate_pass":shadow_gate,
      "public_gate_pass":public_gate,"adapter_state_sha256":reload_hash,
      "adapter_model_sha256":sha_file(adapter_file) if adapter_file.exists() else None,
      "load_seconds":load_seconds,"peak_vram_allocated_bytes":int(torch.cuda.max_memory_allocated()),
      "sealed_eval_consumed":False,"worker05_used_for_tuning":False,
      "candidate_status":"READY_FOR_INDEPENDENT_PRIVATE_EVAL" if public_gate else "PUBLIC_GATE_NOT_PASSED",
      "capability_gain_claim":False,
      "truth_boundary":"Real 27B AQLEVON LoRA artifact if training completed; public evidence only. Original Worker05 sealed secret is unavailable and was not regenerated."
    }
    result=sealed(result,"receipt_sha256")
    write_json(args.output_dir/"training_run_receipt.json",result)
    print("AQLEVON_27B_RESULT",json.dumps({k:v for k,v in result.items() if k not in {"phase_history","full_attention_layers"}},sort_keys=True),flush=True)
    return result


def preflight(args: argparse.Namespace) -> None:
    w02=load_w02(args.w02_module)
    dev,shadow=load_public_inputs(args.training_pack)
    phase_counts=[len(build_rows(w02,a,b)) for a,b in PHASES]
    assert phase_counts==[168,168,168,168],phase_counts
    print(f"AQLEVON_27B_PUBLIC_PREFLIGHT_PASS phases={phase_counts} max_updates={sum(phase_counts)} dev={len(dev)} shadow={len(shadow)} families={len(w02.FAMILIES)} sealed_eval=forbidden")


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--w02-module",type=Path,required=True)
    ap.add_argument("--training-pack",type=Path,required=True)
    ap.add_argument("--model-dir",type=Path)
    ap.add_argument("--output-dir",type=Path,default=Path("aqlevon_27b_r0a_output"))
    ap.add_argument("--preflight-only",action="store_true")
    args=ap.parse_args()
    if args.preflight_only:
        preflight(args); return 0
    if args.model_dir is None:
        raise SystemExit("--model-dir required")
    run(args); return 0

if __name__=="__main__":
    raise SystemExit(main())
