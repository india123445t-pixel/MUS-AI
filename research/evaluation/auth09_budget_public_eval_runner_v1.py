#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, platform, random, time
from pathlib import Path
from typing import Any

ADAPTER_SHA="5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74"
ADAPTER_STATE_SHA="1e3ff8a0fbc88686a2d96f93d4f04fdd66db2034ffdfafc2cc91e532ed0bf80f"
CANDIDATE_MANIFEST_SHA="e020c6b140ffba104d1fe4485333fb225afd29c52dc03bf9a62d0f8c614e01c5"
BASE_REPO="Qwen/Qwen3.8-27B"
BASE_REV="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
TOTAL=144

class EvalError(RuntimeError): pass

def canonical(v:Any)->bytes:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def sha_obj(v:Any)->str:
    return hashlib.sha256(canonical(v)).hexdigest()

def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def load(p:Path)->Any: return json.loads(p.read_text())

def write(p:Path,v:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(canonical(v)+b"\n")

def status(p:Path|None,**kw:Any)->None:
    if p is None: return
    q={"kind":"AQLEVON_AUTH09_BUDGET_PUBLIC_STATUS_V1",**kw,"updated_at":time.time()}
    t=p.with_suffix(".tmp"); write(t,q); os.replace(t,p)

def validate(args):
    af=args.adapter_dir/"adapter_model.safetensors"
    if not af.is_file() or sha_file(af)!=ADAPTER_SHA: raise EvalError("adapter_sha_mismatch")
    cm=load(args.candidate_manifest)
    if cm.get("manifest_sha256")!=CANDIDATE_MANIFEST_SHA or cm.get("adapter_sha256")!=ADAPTER_SHA or cm.get("adapter_state_sha256")!=ADAPTER_STATE_SHA:
        raise EvalError("candidate_manifest_mismatch")
    if cm.get("base_repo")!=BASE_REPO or cm.get("base_revision")!=BASE_REV: raise EvalError("base_identity_mismatch")
    plan=load(args.plan); ph=plan.pop("plan_sha256",None)
    if ph!=sha_obj(plan): raise EvalError("plan_self_hash")
    plan["plan_sha256"]=ph
    if plan.get("kind")!="AQLEVON_AUTH09_BUDGET_PUBLIC_EVAL_PLAN_V1": raise EvalError("plan_kind")
    rows=plan.get("rows") or []
    if len(rows)!=TOTAL or plan.get("attempt_counts",{}).get("total_model_dispatches")!=TOTAL: raise EvalError("plan_count")
    if plan.get("source_policy",{}).get("sealed_eval_consumed") is not False or plan.get("source_policy",{}).get("historical_w05_used") is not False:
        raise EvalError("forbidden_source")
    return plan

def generation_kwargs(cfg,tok):
    return {"do_sample":bool(cfg["do_sample"]),"temperature":float(cfg["temperature"]),"top_p":float(cfg["top_p"]),
            "top_k":int(cfg["top_k"]),"max_new_tokens":int(cfg["max_new_tokens"]),"num_return_sequences":1,
            "use_cache":bool(cfg["use_cache"]),"pad_token_id":tok.eos_token_id}

def main()->int:
    ap=argparse.ArgumentParser()
    for n in ("model_dir","adapter_dir","candidate_manifest","plan","output_dir"):
        ap.add_argument("--"+n.replace("_","-"),type=Path,required=True)
    ap.add_argument("--status-path",type=Path)
    a=ap.parse_args()

    import torch,transformers,peft
    from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
    from peft import PeftModel
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(): raise EvalError("bf16_cuda_required")

    plan=validate(a); rows=plan["rows"]; a.output_dir.mkdir(parents=True,exist_ok=False)
    status(a.status_path,stage="LOAD_BASE",completed=0,total=TOTAL)
    tok=AutoTokenizer.from_pretrained(str(a.model_dir),local_files_only=True,trust_remote_code=False)
    max_memory={0:"45GiB","cpu":"60GiB"}
    base=Qwen3_5ForConditionalGeneration.from_pretrained(
        str(a.model_dir),dtype=torch.bfloat16,device_map="auto",max_memory=max_memory,
        low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    base.eval()
    device_map={str(k):str(v) for k,v in getattr(base,"hf_device_map",{}).items()}
    vals=[str(v) for v in device_map.values()]
    if not device_map or "cpu" not in vals or not any(v=="0" or v.startswith("cuda") for v in vals):
        raise EvalError("expected_gpu_cpu_offload_map_missing")
    input_device=torch.device("cuda:0")
    out=[]; t0=time.time(); done=0

    def run_system(model,system):
        nonlocal done
        selected=[r for r in rows if r["system"]==system]
        for i,row in enumerate(selected,1):
            seed=int(row["seed"]); random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
            chat=tok.apply_chat_template([{"role":"user","content":row["prompt"]}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            enc=tok(chat,return_tensors="pt",add_special_tokens=False).to(input_device)
            with torch.inference_mode():
                gen=model.generate(**enc,**generation_kwargs(row["generation"],tok))[0]
            txt=tok.decode(gen[enc["input_ids"].shape[1]:],skip_special_tokens=True).strip()
            out.append({"section":row["section"],"system":system,"split":row["split"],"task_id":row["task_id"],"seed":seed,"output":txt})
            done+=1
            if i==1 or i%8==0 or i==len(selected):
                status(a.status_path,stage="INFERENCE",system=system,completed=done,total=TOTAL)
            del enc,gen

    run_system(base,"canonical_base")
    run_system(base,"base")
    status(a.status_path,stage="LOAD_ADAPTER",completed=done,total=TOTAL)
    candidate=PeftModel.from_pretrained(base,str(a.adapter_dir),is_trainable=False); candidate.eval()
    run_system(candidate,"candidate_adapter_on_same_base")
    run_system(candidate,"candidate")
    if done!=TOTAL: raise EvalError(f"attempt_count:{done}")

    write(a.output_dir/"auth09-results.json",out)
    receipt={
      "kind":"AQLEVON_AUTH09_BUDGET_PUBLIC_RUNTIME_RECEIPT_V1","base_repo":BASE_REPO,"base_revision":BASE_REV,
      "adapter_sha256":ADAPTER_SHA,"candidate_manifest_sha256":CANDIDATE_MANIFEST_SHA,"plan_sha256":plan["plan_sha256"],
      "total_model_dispatches":TOTAL,"no_retry_after_dispatch":True,"dtype":"bfloat16","quantization":None,
      "device_map":device_map,"max_memory":max_memory,"elapsed_seconds":round(time.time()-t0,3),
      "python":platform.python_version(),"torch":torch.__version__,"transformers":transformers.__version__,
      "peft":peft.__version__,"gpu_name":torch.cuda.get_device_name(0),"sealed_eval_consumed":False}
    receipt["receipt_sha256"]=sha_obj(receipt)
    write(a.output_dir/"runtime-receipt.json",receipt)
    status(a.status_path,stage="DONE",completed=TOTAL,total=TOTAL,receipt_sha256=receipt["receipt_sha256"])
    print("AQLEVON_AUTH09_EVAL_DONE",json.dumps(receipt,sort_keys=True),flush=True)
    return 0

if __name__=="__main__": raise SystemExit(main())
