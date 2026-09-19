#!/usr/bin/env python3
"""AQLEVON P4 Gene #1 SFT/LoRA surrogate control runner.

Consumes a frozen P4 training plan and Worker-02 training shard.  It never reads
sealed evaluation assets.  This is a surrogate candidate producer, not a
capability/evaluation authority.
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

import p4_gene1_trainer as contract

MODEL_ID = contract.SURROGATE_MODEL
REVISION = contract.SURROGATE_REVISION
PINNED = {"transformers":"5.17.0","peft":"0.21.0","accelerate":"1.15.0"}
LORA_R = 4
LORA_ALPHA = 8
TARGET_SUFFIXES = ("q_proj","v_proj")

class RunnerError(RuntimeError): pass

def _pkg(name: str) -> str | None:
    import importlib.metadata as m
    try: return m.version(name)
    except m.PackageNotFoundError: return None

def _assert_versions() -> dict[str,str|None]:
    got={k:_pkg(k) for k in PINNED}
    bad=[f"{k}={got[k]!r} expected {v}" for k,v in PINNED.items() if got[k]!=v]
    if bad: raise RunnerError("FAIL-CLOSED: incompatible package profile: "+"; ".join(bad))
    return got

def _hash_state(state: dict[str,Any]) -> str:
    h=hashlib.sha256()
    for name in sorted(state):
        t=state[name].detach().cpu().contiguous().float()
        h.update(name.encode()); h.update(str(tuple(t.shape)).encode("ascii")); h.update(t.numpy().tobytes(order="C"))
    return h.hexdigest()

def _load_rows(path: Path) -> list[dict[str,Any]]:
    rows=[]
    for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        row=json.loads(line)
        if not isinstance(row,dict) or row.get("row_kind")!="AQLEVON_TRAINING_SHARD_ROW_V1":
            raise RunnerError(f"FAIL-CLOSED: invalid training row {n}")
        if contract._forbidden_eval_reference(row):
            raise RunnerError(f"FAIL-CLOSED: forbidden eval reference in training row {n}")
        if not isinstance(row.get("prompt"),str) or not isinstance(row.get("answer"),(str,list,dict,int,bool)):
            raise RunnerError(f"FAIL-CLOSED: row {n} missing prompt/answer")
        rows.append(row)
    if not rows: raise RunnerError("FAIL-CLOSED: empty training shard")
    return rows

def _arm(plan: dict[str,Any], arm_id: str) -> dict[str,Any]:
    if not contract.verify_self_digest(plan,"plan_sha256") or plan.get("plan_kind")!=contract.FROZEN_PLAN_KIND:
        raise RunnerError("FAIL-CLOSED: invalid frozen training plan")
    matches=[a for a in plan.get("arms",[]) if a.get("arm_id")==arm_id]
    if len(matches)!=1: raise RunnerError("FAIL-CLOSED: arm_id not uniquely present in frozen plan")
    arm=matches[0]
    if arm.get("method")!="SFT_LORA_CONTROL":
        raise RunnerError("FAIL-CLOSED: p4_sft_surrogate only executes SFT_LORA_CONTROL")
    return arm

def plan_summary(plan: dict[str,Any], arm_id: str, seed: int) -> dict[str,Any]:
    arm=_arm(plan,arm_id)
    seeds=(arm.get("seed_policy") or {}).get("seeds")
    if not isinstance(seeds,list) or seed not in seeds:
        raise RunnerError("FAIL-CLOSED: seed is not frozen for this arm")
    updates=(arm.get("budget") or {}).get("optimizer_updates")
    if type(updates) is not int or updates<1 or updates>128:
        raise RunnerError("FAIL-CLOSED: invalid optimizer update ceiling")
    return {
        "task_id":contract.TASK_ID,"arm_id":arm_id,"method":"SFT_LORA_CONTROL","seed":seed,
        "model":MODEL_ID,"revision":REVISION,"precision":"bf16","quantization":"none",
        "optimizer_updates":updates,"lora_r":LORA_R,"lora_alpha":LORA_ALPHA,
        "target_suffixes":list(TARGET_SUFFIXES),"training_plan_sha256":plan["plan_sha256"],
        "capability_claim":False,"authority_boundary":"SURROGATE_TRAINING_ARTIFACT_PENDING_WORKER05_EVALUATION",
    }

def _discover(model: Any) -> list[str]:
    out=[]
    for name,_ in model.named_modules():
        if ".self_attn." in name and name.rsplit(".",1)[-1] in TARGET_SUFFIXES: out.append(name)
    out=sorted(set(out))
    if not out or any(".linear_attn." in n or ".visual." in n for n in out):
        raise RunnerError("FAIL-CLOSED: invalid q/v target discovery")
    return out

def _answer_text(value: Any) -> str:
    if isinstance(value,str): return value
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def _batch(tokenizer: Any, row: dict[str,Any], max_length: int, device: Any) -> dict[str,Any]:
    text=row["prompt"].rstrip()+"\n\nAnswer:\n"+_answer_text(row["answer"])
    enc=tokenizer(text,return_tensors="pt",truncation=True,max_length=max_length)
    ids=enc["input_ids"].to(device); mask=enc["attention_mask"].to(device); labels=ids.clone()
    return {"input_ids":ids,"attention_mask":mask,"labels":labels}

def run(plan_path: Path, shard_manifest_path: Path, shard_path: Path, arm_id: str, seed: int, output_dir: Path, max_length: int) -> dict[str,Any]:
    plan=json.loads(plan_path.read_text())
    arm=_arm(plan,arm_id); summary=plan_summary(plan,arm_id,seed)
    manifest=json.loads(shard_manifest_path.read_text()); shard_bytes=shard_path.read_bytes()
    errors=contract.validate_training_shard(manifest,shard_bytes)
    if errors: raise RunnerError("FAIL-CLOSED: training shard invalid: "+";".join(errors))
    if plan.get("training_shard_manifest_sha256")!=manifest.get("manifest_sha256") or plan.get("training_shard_file_sha256")!=manifest.get("shard_file_sha256"):
        raise RunnerError("FAIL-CLOSED: frozen plan/training shard binding mismatch")
    rows=_load_rows(shard_path)
    stack=_assert_versions()
    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(): raise RunnerError("FAIL-CLOSED: BF16-capable CUDA required")
    from peft import LoraConfig,PeftModel,get_peft_model,get_peft_model_state_dict
    from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
    random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=REVISION,trust_remote_code=False)
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=Qwen3_5ForConditionalGeneration.from_pretrained(MODEL_ID,revision=REVISION,trust_remote_code=False,dtype=torch.bfloat16,device_map={"":torch.cuda.current_device()},low_cpu_mem_usage=True)
    for p in model.parameters(): p.requires_grad_(False)
    if hasattr(model.config,"use_cache"): model.config.use_cache=False
    if hasattr(model.config,"text_config") and hasattr(model.config.text_config,"use_cache"): model.config.text_config.use_cache=False
    targets=_discover(model)
    rp=arm.get("runner_parameters") or {}
    rank=rp.get("lora_rank",LORA_R)
    if type(rank) is not int or rank<1 or rank>64: raise RunnerError("FAIL-CLOSED: invalid frozen lora_rank")
    model=get_peft_model(model,LoraConfig(r=rank,lora_alpha=2*rank,lora_dropout=0.0,bias="none",target_modules=targets,task_type="CAUSAL_LM"))
    device=next(p for p in model.parameters() if p.device.type=="cuda").device
    state0={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}; pre_hash=_hash_state(state0)
    opt_cfg=arm.get("optimizer") or {}; lr_raw=opt_cfg.get("lr_decimal")
    try: lr=float(lr_raw)
    except Exception as exc: raise RunnerError("FAIL-CLOSED: invalid optimizer lr_decimal") from exc
    if not math.isfinite(lr) or lr<=0: raise RunnerError("FAIL-CLOSED: invalid optimizer learning rate")
    optimizer=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=lr,weight_decay=0.0)
    updates=summary["optimizer_updates"]; order=list(range(len(rows))); rng=random.Random(seed); exposures=0; losses=[]
    torch.cuda.reset_peak_memory_stats(); t0=time.perf_counter()
    for step in range(updates):
        if step % len(order)==0: rng.shuffle(order)
        row=rows[order[step % len(order)]]; batch=_batch(tok,row,max_length,device)
        model.train(); optimizer.zero_grad(set_to_none=True); out=model(**batch,use_cache=False)
        if out.loss is None or not torch.isfinite(out.loss): raise RunnerError(f"FAIL-CLOSED: nonfinite loss step={step}")
        out.loss.backward(); g2=sum(float(p.grad.detach().float().pow(2).sum().cpu()) for p in model.parameters() if p.requires_grad and p.grad is not None)
        if g2<=0: raise RunnerError(f"FAIL-CLOSED: zero gradient step={step}")
        optimizer.step(); losses.append(float(out.loss.detach().cpu())); exposures+=1
    torch.cuda.synchronize(); elapsed=time.perf_counter()-t0; peak=int(torch.cuda.max_memory_allocated())
    state1={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}; post_hash=_hash_state(state1)
    changed=0; d2=0.0
    for k in state0:
        d=state1[k].float()-state0[k].float(); changed+=int((d!=0).sum().item()); d2+=float(d.pow(2).sum().item())
    if changed<=0 or d2<=0 or pre_hash==post_hash: raise RunnerError("FAIL-CLOSED: no nonzero adapter delta")
    output_dir.mkdir(parents=True,exist_ok=True); adapter=output_dir/"adapter"; model.save_pretrained(adapter,safe_serialization=True); tok.save_pretrained(adapter)
    del optimizer,model,state0,state1; gc.collect(); torch.cuda.empty_cache()
    base=Qwen3_5ForConditionalGeneration.from_pretrained(MODEL_ID,revision=REVISION,trust_remote_code=False,dtype=torch.bfloat16,device_map={"":torch.cuda.current_device()},low_cpu_mem_usage=True)
    reload=PeftModel.from_pretrained(base,adapter,is_trainable=False); reload_hash=_hash_state(get_peft_model_state_dict(reload))
    if reload_hash!=post_hash: raise RunnerError("FAIL-CLOSED: save/reload adapter hash mismatch")
    report={
        "schema_version":1,"report_kind":"AQLEVON_P4_SURROGATE_TRAINING_REPORT_V1","task_id":contract.TASK_ID,
        "status":"COMPLETED_ARTIFACT_PENDING_WORKER05_EVALUATION","plan":summary,"method_arm":arm,
        "training_shard_manifest_sha256":manifest["manifest_sha256"],"training_shard_file_sha256":manifest["shard_file_sha256"],
        "parameter_delta":{"pre_state_sha256":pre_hash,"post_state_sha256":post_hash,"changed_elements":changed,"delta_l2":math.sqrt(d2)},
        "training":{"optimizer_updates":updates,"examples_exposed":exposures,"losses_not_quality_evidence":[format(x,".12g") for x in losses]},
        "artifact":{"directory":str(adapter),"saved_adapter_state_sha256":post_hash,"reloaded_adapter_state_sha256":reload_hash,"reload_hash_match":True},
        "telemetry":{"gpu_seconds_decimal":format(elapsed,".12g"),"peak_vram_allocated_bytes":peak},"environment":{"package_profile":stack},
        "capability_gain_claim":False,"authority_boundary":"SURROGATE_TRAINING_ARTIFACT_ONLY_WORKER05_EVALUATION_REQUIRED",
    }
    rp=output_dir/"training_report.json"; rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    return report

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--training-plan",type=Path,required=True); ap.add_argument("--training-shard-manifest",type=Path,required=True); ap.add_argument("--training-shard",type=Path,required=True); ap.add_argument("--arm-id",required=True); ap.add_argument("--seed",type=int,required=True); ap.add_argument("--max-length",type=int,default=512); ap.add_argument("--output-dir",type=Path,default=Path("aqlevon_p4_sft_surrogate")); ap.add_argument("--print-plan",action="store_true"); args=ap.parse_args()
    try:
        plan=json.loads(args.training_plan.read_text()); summary=plan_summary(plan,args.arm_id,args.seed)
        if args.print_plan: print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0
        print(json.dumps(run(args.training_plan,args.training_shard_manifest,args.training_shard,args.arm_id,args.seed,args.output_dir,args.max_length),ensure_ascii=False,indent=2)); return 0
    except Exception as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":f"{type(exc).__name__}: {exc}"},ensure_ascii=False),file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
