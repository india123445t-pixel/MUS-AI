#!/usr/bin/env python3
"""AQLEVON 27B Auth16-recipe transfer candidate.

This independent 27B lane trains only on AQLEVON-owned PUBLIC synthetic
cores at indices 04..19. Public discovery indices 00..01 are held out as an
internal development gate. Public shadow indices 02..03 are not evaluated
unless the discovery-dev gate passes. Worker05 sealed/private evaluation is
forbidden and never used for training, model selection, or gating.
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

MODEL_REPO = "Qwen/Qwen3.8-27B"
MODEL_REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
PACK_SHA = "35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
RECOVERY_KIND = "AQLEVON_ONE_DAY_PUBLIC_PASSN_PROBE_RECOVERED_DECISION_V1"
AUTH05_LOG_SHA = "047c1a06bb68ba7c8799eff3d569dd6639ed96d16deae1700c279ecb1449875d"
AUTH05_ARTIFACT_SHA = "7aa1949505d9e10c8e332f0a5cca288e16f975e93d6bff12b20531316f8454bd"
SEED = 1701
SYNTH_START = 4
SYNTH_STOP = 20
PROMPT_PERTURBATIONS = 3
EPOCHS = 1
LR = 1e-5
MIN_LR = 1e-6
CAP = 2048
LAYERS = tuple(range(3, 64, 4))
TARGET_SUFFIXES = {f"layers.{i}.self_attn.{p}" for i in LAYERS for p in ("q_proj", "k_proj", "v_proj", "o_proj")}
WEIGHT_NAME = re.compile(r"(?:^|\.)layers\.(\d+)\.self_attn\.(q_proj|k_proj|v_proj|o_proj)\.lora_([AB])(?:\.default)?\.weight$")


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
    expected_tensors=len(LAYERS)*4*2
    if len(weights) != expected_tensors:
        raise RuntimeError(f"adapter_tensor_count_mismatch:{len(weights)} expected={expected_tensors}")
    for name, value in weights.items():
        hit = WEIGHT_NAME.search(name)
        if not hit:
            raise RuntimeError(f"unexpected_adapter_key:{name}")
        layer, projection, part = int(hit[1]), hit[2], hit[3]
        modules.setdefault((layer, projection), {})[part] = tuple(value.shape)
    expected = {(i, p) for i in LAYERS for p in ("q_proj", "k_proj", "v_proj", "o_proj")}
    if set(modules) != expected:
        raise RuntimeError("adapter_topology_mismatch")
    for (_, projection), parts in modules.items():
        if set(parts) != {"A", "B"}:
            raise RuntimeError("adapter_AB_mismatch")
        a_shape, b_shape = parts["A"], parts["B"]
        if len(a_shape) != 2 or len(b_shape) != 2:
            raise RuntimeError(f"adapter_rank_shape_invalid:{projection}:{a_shape}:{b_shape}")
        if a_shape[0] != 8 or b_shape[1] != 8:
            raise RuntimeError(f"adapter_lora_rank_mismatch:{projection}:{a_shape}:{b_shape}")
        if a_shape[1] <= 0 or b_shape[0] <= 0:
            raise RuntimeError(f"adapter_dimension_invalid:{projection}:{a_shape}:{b_shape}")
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
    tasks = [t for t in pack["tasks"] if t.get("verifier_mode") == "hardened" and t.get("training_eligible") is True]
    if len(tasks) != 56:
        raise RuntimeError(f"expected_56_public_tasks:{len(tasks)}")
    if len(probe.get("records") or []) != 56:
        raise RuntimeError("expected_56_probe_records")
    dev=[]; shadow=[]
    for task in tasks:
        idx=task_index(task)
        if idx in (0,1):
            dev.append(task)
        elif idx in (2,3):
            shadow.append(task)
        else:
            raise RuntimeError(f"unexpected_public_index:{idx}")
    dev=sorted(dev,key=lambda x:x["task_id"])
    shadow=sorted(shadow,key=lambda x:x["task_id"])
    if len(dev)!=28 or len(shadow)!=28 or len({x["family"] for x in dev})!=14:
        raise RuntimeError("bad_public_split")
    return probe, dev, shadow


def build_synthetic_rows(w02):
    rows=[]
    for family in w02.FAMILIES:
        for idx in range(SYNTH_START,SYNTH_STOP):
            core=w02._core(family,idx)
            task=w02._task(core,"hardened",training_visible=True)
            check=w02.verify(task,core,core["oracle_program"])
            if not check.get("passed"):
                raise RuntimeError(f"synthetic_oracle_verify_failed:{family}:{idx}:{check}")
            target=json.dumps(core["oracle_program"],ensure_ascii=False,separators=(",",":"))
            for perturb in range(PROMPT_PERTURBATIONS):
                rows.append({
                    "task_id":f"synthetic-{family}-{idx:02d}-p{perturb}",
                    "prompt":w02._render_prompt(core,perturb),
                    "target":target,
                    "source":"aqlevon_owned_synthetic_curriculum",
                    "priority":0,
                    "family":family,
                    "synthetic_index":idx,
                    "perturbation":perturb,
                })
    rows=sorted(rows,key=lambda x:(x["family"],x["synthetic_index"],x["perturbation"]))
    if len(rows)!=672 or len({x["family"] for x in rows})!=14:
        raise RuntimeError(f"bad_synthetic_curriculum:{len(rows)}")
    return rows

def evaluate_tasks(model, tokenizer, w02, shadow, generation):
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



def mine_discovery_on_policy(model, tokenizer, w02, train_rows, generation):
    """Mine verifier-passing base-model trajectories on PUBLIC discovery only."""
    import torch
    model.eval()
    mined = {}
    rows = []
    for ti, row in enumerate(train_rows):
        task = row["task"]
        seed = SEED + int(hashlib.sha256(("mine:" + task["task_id"]).encode()).hexdigest()[:8], 16)
        random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        chat = tokenizer.apply_chat_template(
            [{"role": "user", "content": task["prompt"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        enc = tokenizer(chat, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            outs = model.generate(
                **enc, do_sample=True, temperature=generation["temperature"],
                top_p=generation["top_p"], top_k=generation["top_k"],
                max_new_tokens=generation["max_new_tokens"],
                num_return_sequences=MINING_N, use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        prefix_len = enc["input_ids"].shape[1]
        accepted = []
        for out in outs:
            text = tokenizer.decode(out[prefix_len:], skip_special_tokens=True).strip()
            ok, reason = verify_text(w02, task, text)
            if ok:
                program = strict_json_program(text)
                if program is None:
                    raise RuntimeError("verifier_pass_without_parse")
                canonical = json.dumps(program, ensure_ascii=False, separators=(",", ":"))
                if canonical not in accepted:
                    accepted.append(canonical)
                if len(accepted) >= MAX_ON_POLICY_PER_TASK:
                    break
        if accepted:
            mined[task["task_id"]] = accepted
        rows.append({"task_id":task["task_id"],"accepted":len(accepted)})
        print(f"AQLEVON_RSFT_MINE={ti+1}/{len(train_rows)} id={task['task_id']} accepted={len(accepted)}", flush=True)
        del enc, outs
        torch.cuda.empty_cache()
    return mined, rows


def build_rsft_rows(train_rows, mined):
    """Keep balanced oracle coverage and add at most one verifier-passing on-policy positive."""
    out = []
    for row in train_rows:
        base = {k:v for k,v in row.items() if k != "task"}
        out.append(base)
        for text in mined.get(row["task_id"], [])[:MAX_ON_POLICY_PER_TASK]:
            # Keep the verified on-policy hit as a second weighted positive even
            # when its canonical program equals the oracle target.
            out.append({
                "task_id":row["task_id"], "prompt":row["prompt"], "target":text.strip(),
                "source":"public_discovery_on_policy_verifier_pass",
                "priority":-1, "family":row["family"],
            })
    return out


def run(args):
    import gc
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, get_peft_model_state_dict
    from peft.tuners.lora.layer import LoraLayer
    from safetensors.torch import load_file
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("bf16_cuda_required")
    probe, dev, shadow = load_inputs(args)
    w02 = load_w02(args.w02_module)
    train_rows = build_synthetic_rows(w02)
    generation = dict(probe["generation"])

    random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True, trust_remote_code=False)
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0},
        low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False)
    full_layers=[i for i,kind in enumerate(base.config.text_config.layer_types) if kind=="full_attention"]
    if full_layers != list(LAYERS):
        raise RuntimeError(f"full_attention_layers_changed:{full_layers}")

    dev_pre=evaluate_tasks(base,tokenizer,w02,dev,generation)
    print("AQLEVON_SYNTH_DEV_PRE",json.dumps({k:v for k,v in dev_pre.items() if k!="records"},sort_keys=True),flush=True)

    base.config.use_cache=False
    base.gradient_checkpointing_enable()
    lora=LoraConfig(r=8,lora_alpha=16,target_modules=["q_proj","k_proj","v_proj","o_proj"],
                    lora_dropout=0,bias="none",task_type=TaskType.CAUSAL_LM,init_lora_weights=True)
    model=get_peft_model(base,lora)
    model.enable_input_require_grads()
    targets=sorted(name for name,mod in model.named_modules()
                   if isinstance(mod,LoraLayer) and name.endswith((".q_proj",".k_proj",".v_proj",".o_proj")))
    observed={next((x for x in TARGET_SUFFIXES if name.endswith(x)),"") for name in targets}
    expected_modules=len(LAYERS)*4
    if observed != TARGET_SUFFIXES or len(targets)!=expected_modules:
        raise RuntimeError(f"lora_target_topology_mismatch:{len(targets)} expected={expected_modules}")
    params=[p for p in model.parameters() if p.requires_grad]
    trainable=sum(p.numel() for p in params)
    if trainable <= 0:
        raise RuntimeError(f"trainable_parameter_count_invalid:{trainable}")
    print(f"AQLEVON_27B_TRAINABLE_PARAMETERS={trainable}",flush=True)

    optimizer=torch.optim.AdamW(params,lr=LR,weight_decay=0.05)
    model.train()
    losses=[]; grad_norms=[]; used=[]
    eos=tokenizer.eos_token or "<|im_end|>"
    steps=len(train_rows)*EPOCHS
    global_step=0
    for epoch in range(EPOCHS):
        epoch_rows=list(train_rows)
        random.Random(SEED+epoch).shuffle(epoch_rows)
        for row in epoch_rows:
            optimizer.zero_grad(set_to_none=True)
            prompt=tokenizer.apply_chat_template([{"role":"user","content":row["prompt"]}],
                                                 tokenize=False,add_generation_prompt=True,
                                                 enable_thinking=False)
            prefix=tokenizer(prompt,add_special_tokens=False).input_ids
            target=tokenizer(row["target"]+eos,add_special_tokens=False).input_ids
            if not target or len(prefix)+len(target)>CAP:
                raise RuntimeError(f"sequence_cap_violation:{row['task_id']}")
            ids=torch.tensor([prefix+target],device="cuda",dtype=torch.long)
            labels=torch.tensor([[-100]*len(prefix)+target],device="cuda",dtype=torch.long)
            logits=model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False).logits
            loss=F.cross_entropy(logits[:,:-1,:].float().reshape(-1,logits.shape[-1]),
                                 labels[:,1:].reshape(-1),ignore_index=-100)
            if not bool(torch.isfinite(loss).item()) or loss.item()<=0:
                raise RuntimeError(f"invalid_loss:{global_step+1}")
            loss.backward()
            grad=float(torch.nn.utils.clip_grad_norm_(params,1.0))
            if not math.isfinite(grad) or grad<=0:
                raise RuntimeError(f"invalid_gradient:{global_step+1}")
            frac=global_step/max(1,steps-1)
            lr=MIN_LR+(LR-MIN_LR)*(1+math.cos(math.pi*frac))/2
            for group in optimizer.param_groups: group["lr"]=lr
            optimizer.step(); global_step+=1
            losses.append(float(loss.detach())); grad_norms.append(grad); used.append({**row,"epoch":epoch+1})
            if global_step==1 or global_step%50==0 or global_step==steps:
                print(f"AQLEVON_SYNTH_UPDATE={global_step}/{steps} loss={losses[-1]:.6f} grad_norm={grad:.6f} lr={lr:.9g}",flush=True)
            del ids,labels,logits,loss
    if global_step!=steps:
        raise RuntimeError("optimizer_update_accounting_mismatch")
    torch.cuda.synchronize()

    outdir=args.output_dir
    if outdir.exists(): raise RuntimeError("refuse_overwrite_output")
    artifact=outdir/"candidate_artifact"; artifact.mkdir(parents=True)
    model.save_pretrained(str(artifact),safe_serialization=True)
    saved=load_file(str(artifact/"adapter_model.safetensors"),device="cpu")
    layout=tensor_layout(saved)
    changed=sum(int(torch.count_nonzero(v).item()) for n,v in saved.items() if ".lora_B." in n)
    if changed<=0: raise RuntimeError("no_lora_B_change")
    saved_hash=state_hash(saved)

    del saved,model,base,optimizer
    gc.collect(); torch.cuda.empty_cache()
    reloaded_base=Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},
        low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    reloaded=PeftModel.from_pretrained(reloaded_base,str(artifact),is_trainable=False)
    reloaded_state=get_peft_model_state_dict(reloaded)
    if tensor_layout(reloaded_state)!=layout: raise RuntimeError("save_reload_layout_mismatch")
    reloaded_hash=state_hash(reloaded_state)
    if reloaded_hash!=saved_hash: raise RuntimeError("save_reload_hash_mismatch")
    reloaded.config.use_cache=True

    dev_post=evaluate_tasks(reloaded,tokenizer,w02,dev,generation)
    dev_improvement=dev_post["pass_at_1"]-dev_pre["pass_at_1"]
    dev_gain=dev_post["successes"]-dev_pre["successes"]
    dev_pre_by={r["task_id"]:bool(r["passed"]) for r in dev_pre["records"]}
    dev_post_by={r["task_id"]:bool(r["passed"]) for r in dev_post["records"]}
    dev_regressions=sorted(t for t,v in dev_pre_by.items() if v and not dev_post_by.get(t,False))
    dev_gate=bool(dev_improvement>=0.10 and dev_gain>=3 and not dev_regressions)
    print("AQLEVON_SYNTH_DEV_POST",json.dumps({k:v for k,v in dev_post.items() if k!="records"},sort_keys=True),flush=True)
    print(f"AQLEVON_SYNTH_DEV_GATE={'PASS' if dev_gate else 'FAIL'} improvement={dev_improvement:.6f} gain={dev_gain} regressions={len(dev_regressions)}",flush=True)

    shadow_pre={"not_run":True,"reason":"discovery_dev_gate_failed"}
    shadow_post={"not_run":True,"reason":"discovery_dev_gate_failed"}
    public_gate=False; shadow_improvement=None; shadow_gain=None; shadow_regressions=[]
    if dev_gate:
        shadow_post=evaluate_tasks(reloaded,tokenizer,w02,shadow,generation)
        del reloaded_state,reloaded,reloaded_base
        gc.collect(); torch.cuda.empty_cache()
        fresh_base=Qwen3_5ForConditionalGeneration.from_pretrained(
            str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},
            low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
        shadow_pre=evaluate_tasks(fresh_base,tokenizer,w02,shadow,generation)
        pre_by={r["task_id"]:bool(r["passed"]) for r in shadow_pre["records"]}
        post_by={r["task_id"]:bool(r["passed"]) for r in shadow_post["records"]}
        shadow_improvement=shadow_post["pass_at_1"]-shadow_pre["pass_at_1"]
        shadow_gain=shadow_post["successes"]-shadow_pre["successes"]
        shadow_regressions=sorted(t for t,v in pre_by.items() if v and not post_by.get(t,False))
        public_gate=bool(shadow_improvement>=0.10 and shadow_gain>=3 and not shadow_regressions)
        print("AQLEVON_SYNTH_SHADOW_PRE",json.dumps({k:v for k,v in shadow_pre.items() if k!="records"},sort_keys=True),flush=True)
        print("AQLEVON_SYNTH_SHADOW_POST",json.dumps({k:v for k,v in shadow_post.items() if k!="records"},sort_keys=True),flush=True)
        print(f"AQLEVON_SYNTH_PUBLIC_GATE={'PASS' if public_gate else 'FAIL'} improvement={shadow_improvement:.6f} gain={shadow_gain} regressions={len(shadow_regressions)}",flush=True)

    train_path=outdir/"synthetic_curriculum.json"
    write_json(train_path,used)
    receipt=sealed({
        "receipt_kind":"AQLEVON_27B_AUTH16_TRANSFER_RECEIPT_V1","lane":"AQLEVON_27B_AUTH16_TRANSFER_V1",
        "base_repo":MODEL_REPO,"base_revision":MODEL_REV,"public_pack_sha256":PACK_SHA,
        "seed":SEED,"synthetic_start":SYNTH_START,"synthetic_stop":SYNTH_STOP,
        "prompt_perturbations":PROMPT_PERTURBATIONS,"training_presentations":len(used),
        "optimizer_updates":global_step,"expected_optimizer_updates":steps,"epochs":EPOCHS,
        "lr":LR,"min_lr":MIN_LR,"trainable_parameters":trainable,
        "adapter_tensors":len(layout),"target_modules":len(targets),"losses":losses,"gradient_norms":grad_norms,
        "changed_lora_B_elements":changed,"adapter_state_sha256":saved_hash,
        "reloaded_adapter_state_sha256":reloaded_hash,"save_reload_hash_match":True,
        "dev_pre_successes":dev_pre["successes"],"dev_post_successes":dev_post["successes"],
        "dev_gain_tasks":dev_gain,"dev_improvement":dev_improvement,"dev_regressions":dev_regressions,
        "discovery_dev_gate_pass":dev_gate,"shadow_evaluated":dev_gate,
        "shadow_pre_successes":shadow_pre.get("successes"),"shadow_post_successes":shadow_post.get("successes"),
        "shadow_gain_tasks":shadow_gain,"shadow_improvement":shadow_improvement,
        "shadow_regressions":shadow_regressions,"public_shadow_gate_pass":public_gate,
        "sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False
    },"receipt_sha256")
    write_json(outdir/"training_run_receipt.json",receipt)
    write_json(outdir/"dev_pre_eval.json",dev_pre); write_json(outdir/"dev_post_eval.json",dev_post)
    write_json(outdir/"shadow_pre_eval.json",shadow_pre); write_json(outdir/"shadow_post_eval.json",shadow_post)

    status="PUBLICLY_VERIFIED_27B_CANDIDATE" if public_gate else ("PUBLIC_SHADOW_GATE_FAILED" if dev_gate else "DISCOVERY_DEV_GATE_FAILED")
    manifest=sealed({
        "manifest_kind":"AQLEVON_27B_AUTH16_TRANSFER_CANDIDATE_V1","lane":"AQLEVON_27B_AUTH16_TRANSFER_V1",
        "candidate_status":status,"artifact_type":"adapter",
        "base_repo":MODEL_REPO,"base_revision":MODEL_REV,
        "training_receipt_sha256":sha_file(outdir/"training_run_receipt.json"),
        "synthetic_curriculum_sha256":sha_file(train_path),
        "adapter_config_sha256":sha_file(artifact/"adapter_config.json"),
        "adapter_model_sha256":sha_file(artifact/"adapter_model.safetensors"),
        "adapter_state_sha256":saved_hash,"reloaded_adapter_state_sha256":reloaded_hash,
        "save_reload_hash_match":True,"tensor_layout":layout,
        "discovery_dev_gate_pass":dev_gate,"public_shadow_gate_pass":public_gate,
        "sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False
    },"manifest_sha256")
    write_json(outdir/"candidate_artifact_manifest.json",manifest)
    handoff=sealed({
        "handoff_kind":"AQLEVON_27B_PUBLIC_EVALUATION_INDEX_V1",
        "candidate_status":status,"candidate_manifest_sha256":manifest["manifest_sha256"],
        "discovery_dev_gate_pass":dev_gate,"public_shadow_gate_pass":public_gate,
        "sealed_eval_consumed":False,"capability_gain_claim":False
    },"handoff_sha256")
    write_json(outdir/"public_evaluation_index.json",handoff)
    print(f"AQLEVON_27B_PACKAGE_PASS status={status} tensors={len(layout)} modules={len(targets)} changed_B={changed}",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--probe-result",type=Path,required=True)
    p.add_argument("--w02-module",type=Path,required=True)
    p.add_argument("--training-pack",type=Path,required=True)
    p.add_argument("--model-dir",type=Path)
    p.add_argument("--output-dir",type=Path)
    p.add_argument("--preflight-only",action="store_true")
    args=p.parse_args()
    probe,dev,shadow=load_inputs(args)
    w02=load_w02(args.w02_module)
    synth=build_synthetic_rows(w02)
    if len(synth)!=672 or len(dev)!=28 or len(shadow)!=28:
        raise RuntimeError("bad_preflight_counts")
    if any(x.get("synthetic_index") in (0,1,2,3) for x in synth):
        raise RuntimeError("synthetic_index_firewall")
    print(f"AQLEVON_SYNTH_PUBLIC_PREFLIGHT_PASS synthetic={len(synth)} dev={len(dev)} shadow={len(shadow)} families={len(set(x['family'] for x in synth))} updates={len(synth)*EPOCHS} probe_decision={probe['decision']}",flush=True)
    if args.preflight_only: return
    if not args.model_dir or not args.output_dir:
        p.error("--model-dir and --output-dir required unless --preflight-only")
    run(args)

if __name__=="__main__":
    main()
