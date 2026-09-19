#!/usr/bin/env python3
"""P4 A0 SFT LoRA surrogate control on exact Worker-02 training shard."""
from __future__ import annotations
import argparse, gc, hashlib, importlib.metadata as md, json, math, random, sys, time
from pathlib import Path
from typing import Any
import p4_gene1_trainer as c

PINNED={"transformers":"5.17.0","peft":"0.21.0","accelerate":"1.15.0"}
ARM_ID="P4_A0_SFT_LORA_CONTROL"
TARGET_SUFFIXES=("q_proj","v_proj")

def _hash_state(state:dict[str,Any])->str:
    h=hashlib.sha256()
    for name in sorted(state):
        t=state[name].detach().cpu().contiguous().float(); h.update(name.encode()); h.update(str(tuple(t.shape)).encode()); h.update(t.numpy().tobytes(order="C"))
    return h.hexdigest()

def _arm(plan:dict[str,Any])->dict[str,Any]:
    if not c.verify_self_digest(plan,"plan_sha256") or plan.get("plan_kind")!=c.FROZEN_PLAN_KIND: raise RuntimeError("invalid_frozen_plan")
    x=[a for a in plan["arms"] if a.get("arm_id")==ARM_ID]
    if len(x)!=1: raise RuntimeError("A0_missing")
    a=x[0]
    if a.get("training_mode")!="supervised_next_token_cross_entropy" or a.get("lr")!="0.00001" or a.get("weight_decay")!="0.10" or a.get("scheduler")!="cosine" or a.get("min_lr")!="0.000001" or a.get("warmup_fraction")!="0.10": raise RuntimeError("A0_contract_mismatch")
    return a

def plan_summary(plan:dict[str,Any],seed:int)->dict[str,Any]:
    _arm(plan)
    if seed not in plan["training_seeds"]: raise RuntimeError("seed_not_frozen")
    b=plan["screen_budget"]
    if seed==1701 and b.get("max_optimizer_updates")!=12: raise RuntimeError("screen_budget_mismatch")
    return {"arm_id":ARM_ID,"seed":seed,"model":c.SURROGATE_MODEL,"revision":c.SURROGATE_REVISION,"precision":"bf16","quantization":"none","optimizer_updates":12,"examples_per_update":4,"max_example_exposures":48,"lora_r":4,"lora_alpha":4,"target_scope":"language_model_full_attention_qv_only","training_plan_sha256":plan["plan_sha256"],"capability_claim":False}

def _discover(model:Any)->list[str]:
    names=[]
    for name,module in model.named_modules():
        suffix=name.rsplit(".",1)[-1]
        if ".self_attn." in name and suffix in TARGET_SUFFIXES and ".visual." not in name and ".vision." not in name:
            names.append(name)
    names=sorted(set(names))
    if not names or any(".linear_attn." in n for n in names): raise RuntimeError("invalid_full_attention_qv_target_set")
    if not all(n.endswith((".q_proj",".v_proj")) for n in names): raise RuntimeError("unexpected_target_suffix")
    return names

def _rows(path:Path)->list[dict[str,Any]]:
    rows=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(rows)!=56 or any(r.get("row_kind")!=c.W02_ROW_KIND for r in rows): raise RuntimeError("invalid_training_shard_rows")
    return rows

def _text(row): return row["prompt"].rstrip()+"\n\nAnswer:\n"+json.dumps(row["answer"],ensure_ascii=False,separators=(",",":"))

def run(plan_path:Path,manifest_path:Path,shard_path:Path,seed:int,outdir:Path)->dict[str,Any]:
    plan=json.loads(plan_path.read_text()); summary=plan_summary(plan,seed); manifest=json.loads(manifest_path.read_text()); shard=shard_path.read_bytes()
    if manifest.get("manifest_sha256")!=plan["w02_training_manifest_sha256"] or hashlib.sha256(shard).hexdigest()!=plan["w02_training_shard_sha256"]: raise RuntimeError("plan_shard_binding_mismatch")
    got={k:md.version(k) for k in PINNED}
    if got!=PINNED: raise RuntimeError("package_profile_mismatch:"+json.dumps(got,sort_keys=True))
    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(): raise RuntimeError("bf16_cuda_required")
    from peft import LoraConfig,PeftModel,get_peft_model,get_peft_model_state_dict
    from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
    random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); torch.use_deterministic_algorithms(True); torch.backends.cuda.matmul.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(c.SURROGATE_MODEL,revision=c.SURROGATE_REVISION,trust_remote_code=False)
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=Qwen3_5ForConditionalGeneration.from_pretrained(c.SURROGATE_MODEL,revision=c.SURROGATE_REVISION,trust_remote_code=False,dtype=torch.bfloat16,device_map={"":torch.cuda.current_device()},low_cpu_mem_usage=True)
    for p in model.parameters(): p.requires_grad_(False)
    if hasattr(model.config,"use_cache"): model.config.use_cache=False
    if hasattr(model.config,"text_config") and hasattr(model.config.text_config,"use_cache"): model.config.text_config.use_cache=False
    targets=_discover(model)
    model=get_peft_model(model,LoraConfig(r=4,lora_alpha=4,lora_dropout=0.0,bias="none",target_modules=targets,task_type="CAUSAL_LM"))
    trainable=[n for n,p in model.named_parameters() if p.requires_grad]
    if not trainable or any("linear_attn" in n or "visual" in n or "lm_head" in n or "embed" in n for n in trainable): raise RuntimeError("forbidden_trainable_parameter")
    device=next(p for p in model.parameters() if p.device.type=="cuda").device; rows=_rows(shard_path)
    initial={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}; prehash=_hash_state(initial)
    opt=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=1e-5,weight_decay=0.10)
    total=12; warmup=max(1,round(total*0.10)); min_ratio=0.1
    def lr_lambda(step):
        if step < warmup: return max((step+1)/warmup,min_ratio)
        progress=(step-warmup)/max(1,total-warmup); return min_ratio+(1-min_ratio)*0.5*(1+math.cos(math.pi*progress))
    sch=torch.optim.lr_scheduler.LambdaLR(opt,lr_lambda); rng=random.Random(seed); order=list(range(len(rows))); cursor=0; losses=[]; exposures=0
    torch.cuda.reset_peak_memory_stats(); t0=time.perf_counter()
    for step in range(total):
        if cursor+4>len(order): rng.shuffle(order); cursor=0
        idx=order[cursor:cursor+4]; cursor+=4; texts=[_text(rows[i]) for i in idx]
        enc=tok(texts,return_tensors="pt",padding=True,truncation=True,max_length=2048); enc={k:v.to(device) for k,v in enc.items()}; labels=enc["input_ids"].clone(); labels[enc["attention_mask"]==0]=-100
        model.train(); opt.zero_grad(set_to_none=True); o=model(**enc,labels=labels,use_cache=False)
        if o.loss is None or not torch.isfinite(o.loss): raise RuntimeError("nonfinite_loss")
        o.loss.backward(); g2=sum(float(p.grad.detach().float().pow(2).sum().cpu()) for p in model.parameters() if p.requires_grad and p.grad is not None)
        if g2<=0: raise RuntimeError("zero_gradient")
        opt.step(); sch.step(); losses.append(float(o.loss.detach().cpu())); exposures+=4
    torch.cuda.synchronize(); elapsed=time.perf_counter()-t0; peak=int(torch.cuda.max_memory_allocated())
    post={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}; posthash=_hash_state(post); changed=0; d2=0.0
    for k in initial:
        d=post[k].float()-initial[k].float(); changed+=int((d!=0).sum()); d2+=float(d.pow(2).sum())
    if changed<=0 or d2<=0 or prehash==posthash: raise RuntimeError("zero_adapter_delta")
    outdir.mkdir(parents=True,exist_ok=True); adapter=outdir/"adapter"; model.save_pretrained(adapter,safe_serialization=True); tok.save_pretrained(adapter)
    del opt,sch,model,initial,post; gc.collect(); torch.cuda.empty_cache()
    base=Qwen3_5ForConditionalGeneration.from_pretrained(c.SURROGATE_MODEL,revision=c.SURROGATE_REVISION,trust_remote_code=False,dtype=torch.bfloat16,device_map={"":torch.cuda.current_device()},low_cpu_mem_usage=True); reload=PeftModel.from_pretrained(base,adapter,is_trainable=False); rh=_hash_state(get_peft_model_state_dict(reload))
    if rh!=posthash: raise RuntimeError("reload_state_hash_mismatch")
    report={"schema_version":1,"report_kind":"AQLEVON_P4_SURROGATE_TRAINING_REPORT_V1","status":"COMPLETED_ARTIFACT_PENDING_WORKER05_EVALUATION","plan":summary,"target_modules":targets,"trainable_parameter_names":trainable,"parameter_delta":{"pre_state_sha256":prehash,"post_state_sha256":posthash,"changed_elements":changed,"delta_l2":format(math.sqrt(d2),".12g")},"training":{"optimizer_updates":12,"example_exposures":exposures,"losses_not_quality_evidence":[format(x,".12g") for x in losses]},"artifact":{"directory":str(adapter),"saved_adapter_state_sha256":posthash,"reloaded_adapter_state_sha256":rh,"reload_hash_match":True},"telemetry":{"gpu_seconds_decimal":format(elapsed,".12g"),"peak_vram_allocated_bytes":peak},"environment":{"packages":got},"capability_gain_claim":False,"authority_boundary":"SURROGATE_ARTIFACT_ONLY_WORKER05_EVALUATION_REQUIRED"}
    (outdir/"training_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n"); return report

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--training-plan",type=Path,required=True); ap.add_argument("--training-shard-manifest",type=Path,required=True); ap.add_argument("--training-shard",type=Path,required=True); ap.add_argument("--arm-id",required=True); ap.add_argument("--seed",type=int,required=True); ap.add_argument("--output-dir",type=Path,required=True); ap.add_argument("--print-plan",action="store_true"); a=ap.parse_args()
    try:
        if a.arm_id!=ARM_ID: raise RuntimeError("this_runner_only_executes_A0")
        plan=json.loads(a.training_plan.read_text()); s=plan_summary(plan,a.seed)
        if a.print_plan: print(json.dumps(s,indent=2,sort_keys=True)); return 0
        print(json.dumps(run(a.training_plan,a.training_shard_manifest,a.training_shard,a.seed,a.output_dir),ensure_ascii=False,indent=2)); return 0
    except Exception as exc: print(json.dumps({"status":"FAIL_CLOSED","error":f"{type(exc).__name__}: {exc}"}),file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
