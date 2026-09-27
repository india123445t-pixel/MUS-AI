#!/usr/bin/env python3
from __future__ import annotations
import argparse, gc, hashlib, importlib.util, json, math, random, time
from pathlib import Path
from typing import Any

MODEL_REPO="Qwen/Qwen3.8-27B"
MODEL_REV="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
SEED=1701
LR=1e-5
MIN_LR=1e-6
CAP=1024
MAX_UPDATES=672
CHECK_EVERY=112
SYNTH_START=4
SYNTH_STOP=20
PROMPT_PERTURBATIONS=3
EXPECTED_TARGET_MODULES=32
EXPECTED_TRAINABLE_PARAMS=1507328

def sha_file(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def state_hash(weights: dict[str,Any]) -> str:
    h=hashlib.sha256()
    for name in sorted(weights):
        t=weights[name].detach().cpu().contiguous().float()
        h.update(name.encode()); h.update(str(tuple(t.shape)).encode()); h.update(t.numpy().tobytes(order="C"))
    return h.hexdigest()

def load_w02(path: Path):
    spec=importlib.util.spec_from_file_location("aqlevon_w02_27b",str(path))
    if spec is None or spec.loader is None: raise RuntimeError("cannot_load_w02")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def strict_program(text: str):
    try: v=json.loads(text.strip())
    except Exception: return None
    return v if isinstance(v,list) and v else None

def build_eval(w02, indices):
    out=[]
    for fam in w02.FAMILIES:
        for idx in indices:
            core=w02._core(fam,idx)
            task=w02._task(core,"hardened",training_visible=True)
            out.append((task,core))
    return sorted(out,key=lambda x:x[0]["task_id"])

def build_train(w02):
    rows=[]
    for fam in w02.FAMILIES:
        for idx in range(SYNTH_START,SYNTH_STOP):
            core=w02._core(fam,idx)
            task=w02._task(core,"hardened",training_visible=True)
            chk=w02.verify(task,core,core["oracle_program"])
            if not chk.get("passed"): raise RuntimeError(f"oracle_failed:{fam}:{idx}")
            target=json.dumps(core["oracle_program"],ensure_ascii=False,separators=(",",":"))
            for perturb in range(PROMPT_PERTURBATIONS):
                rows.append({"id":f"{fam}-{idx:02d}-p{perturb}","prompt":w02._render_prompt(core,perturb),"target":target,"family":fam})
    rows=sorted(rows,key=lambda x:x["id"])
    if len(rows)!=672: raise RuntimeError(f"expected_672_rows:{len(rows)}")
    return rows

def eval_tasks(model,tokenizer,w02,pairs,label):
    import torch
    model.eval(); passed=0; records=[]
    for task,core in pairs:
        seed=SEED+int(hashlib.sha256((label+":"+task["task_id"]).encode()).hexdigest()[:8],16)
        random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        chat=tokenizer.apply_chat_template([{"role":"user","content":task["prompt"]}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        enc=tokenizer(chat,return_tensors="pt",add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            out=model.generate(**enc,do_sample=True,temperature=0.7,top_p=0.8,top_k=20,max_new_tokens=256,num_return_sequences=1,use_cache=True,pad_token_id=tokenizer.eos_token_id)[0]
        txt=tokenizer.decode(out[enc["input_ids"].shape[1]:],skip_special_tokens=True).strip()
        prog=strict_program(txt)
        result=w02.verify(task,core,prog) if prog is not None else {"passed":False,"reason":"invalid_json"}
        ok=bool(result.get("passed")); passed+=int(ok)
        records.append({"task_id":task["task_id"],"passed":ok,"reason":str(result.get("reason"))})
        del enc,out
    res={"label":label,"successes":passed,"tasks":len(pairs),"pass_at_1":passed/len(pairs),"records":records}
    print("AQLEVON_27B_EVAL",json.dumps({k:v for k,v in res.items() if k!="records"},sort_keys=True),flush=True)
    return res

def discover_targets(base):
    targets=[]
    for name,_ in base.named_modules():
        if name.startswith("model.language_model.layers.") and ".self_attn." in name and name.rsplit(".",1)[-1] in {"q_proj","v_proj"}:
            targets.append(name)
    targets=sorted(set(targets))
    if len(targets)!=EXPECTED_TARGET_MODULES: raise RuntimeError(f"target_count:{len(targets)}")
    return targets

def run(args):
    import torch
    from peft import LoraConfig,PeftModel,get_peft_model,get_peft_model_state_dict
    from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(): raise RuntimeError("bf16_cuda_required")
    w02=load_w02(args.w02_module)
    train_rows=build_train(w02); dev=build_eval(w02,(0,1)); shadow=build_eval(w02,(2,3))
    random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    tok=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    base=Qwen3_5ForConditionalGeneration.from_pretrained(str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    targets=discover_targets(base)
    baseline_dev=eval_tasks(base,tok,w02,dev,"baseline_dev")
    baseline_shadow=eval_tasks(base,tok,w02,shadow,"baseline_shadow")
    for p in base.parameters(): p.requires_grad_(False)
    base.config.use_cache=False
    base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant":False})
    cfg=LoraConfig(r=4,lora_alpha=8,lora_dropout=0.0,bias="none",target_modules=targets,task_type="CAUSAL_LM")
    model=get_peft_model(base,cfg); model.enable_input_require_grads()
    params=[p for p in model.parameters() if p.requires_grad]
    trainable=sum(p.numel() for p in params)
    if trainable!=EXPECTED_TRAINABLE_PARAMS: raise RuntimeError(f"trainable_count:{trainable}")
    opt=torch.optim.AdamW(params,lr=LR,weight_decay=0.05)
    order=list(train_rows); random.Random(SEED).shuffle(order)
    losses=[]; global_step=0; checkpoints=[]
    eos=tok.eos_token or "<|im_end|>"; t0=time.time()
    for row in order:
        opt.zero_grad(set_to_none=True)
        prompt=tok.apply_chat_template([{"role":"user","content":row["prompt"]}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        prefix=tok(prompt,add_special_tokens=False).input_ids
        target=tok(row["target"]+eos,add_special_tokens=False).input_ids
        if not target or len(prefix)+len(target)>CAP: raise RuntimeError(f"sequence_cap:{row['id']}")
        ids=torch.tensor([prefix+target],device="cuda",dtype=torch.long)
        labels=torch.tensor([[-100]*len(prefix)+target],device="cuda",dtype=torch.long)
        out=model(input_ids=ids,attention_mask=torch.ones_like(ids),labels=labels,use_cache=False)
        loss=out.loss
        if loss is None or not bool(torch.isfinite(loss).item()): raise RuntimeError(f"nonfinite_loss:{global_step+1}")
        loss.backward()
        grad=float(torch.nn.utils.clip_grad_norm_(params,1.0))
        if not math.isfinite(grad) or grad<=0: raise RuntimeError(f"bad_grad:{global_step+1}")
        frac=global_step/max(1,MAX_UPDATES-1)
        lr=MIN_LR+(LR-MIN_LR)*(1+math.cos(math.pi*frac))/2
        for g in opt.param_groups: g["lr"]=lr
        opt.step(); global_step+=1; losses.append(float(loss.detach()))
        if global_step==1 or global_step%28==0:
            print(f"AQLEVON_27B_UPDATE={global_step}/{MAX_UPDATES} loss={losses[-1]:.6f} grad={grad:.6f} lr={lr:.9g}",flush=True)
        del ids,labels,out,loss
        if global_step%CHECK_EVERY==0:
            torch.cuda.empty_cache()
            chk=eval_tasks(model,tok,w02,dev,f"dev_after_{global_step}")
            checkpoints.append({"step":global_step,"successes":chk["successes"]})
            if chk["successes"]==len(dev) and chk["successes"]>=baseline_dev["successes"]:
                print(f"AQLEVON_27B_EARLY_STOP step={global_step}",flush=True)
                break
    torch.cuda.synchronize()
    if global_step<=0: raise RuntimeError("no_updates")
    outdir=args.output_dir
    if outdir.exists(): raise RuntimeError("refuse_overwrite")
    adapter=outdir/"adapter"; adapter.mkdir(parents=True)
    model.save_pretrained(str(adapter),safe_serialization=True); tok.save_pretrained(str(adapter))
    saved_state=get_peft_model_state_dict(model); saved_hash=state_hash(saved_state)
    adapter_file=adapter/"adapter_model.safetensors"; adapter_sha=sha_file(adapter_file)
    del saved_state,model,base,opt; gc.collect(); torch.cuda.empty_cache()
    reload_base=Qwen3_5ForConditionalGeneration.from_pretrained(str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    reloaded=PeftModel.from_pretrained(reload_base,str(adapter),is_trainable=False)
    reload_hash=state_hash(get_peft_model_state_dict(reloaded))
    if reload_hash!=saved_hash: raise RuntimeError("reload_hash_mismatch")
    final_dev=eval_tasks(reloaded,tok,w02,dev,"final_dev")
    final_shadow=eval_tasks(reloaded,tok,w02,shadow,"final_shadow")
    dev_nonreg=final_dev["successes"]>=baseline_dev["successes"]; shadow_nonreg=final_shadow["successes"]>=baseline_shadow["successes"]
    any_gain=(final_dev["successes"]>baseline_dev["successes"] or final_shadow["successes"]>baseline_shadow["successes"])
    status="AQLEVON_27B_R0_PUBLIC_PASS" if dev_nonreg and shadow_nonreg else "AQLEVON_27B_R0_PUBLIC_FAIL"
    manifest={"kind":"AQLEVON_27B_R0_CANDIDATE_MANIFEST_V1","status":status,"model_name":"AQLEVON-27B-R0","base_repo":MODEL_REPO,"base_revision":MODEL_REV,"adapter_sha256":adapter_sha,"adapter_state_sha256":saved_hash,"trainable_parameters":trainable,"optimizer_updates":global_step,"max_optimizer_updates":MAX_UPDATES,"early_stop_check_every":CHECK_EVERY,"baseline_dev_successes":baseline_dev["successes"],"final_dev_successes":final_dev["successes"],"baseline_shadow_successes":baseline_shadow["successes"],"final_shadow_successes":final_shadow["successes"],"dev_nonregression":dev_nonreg,"shadow_nonregression":shadow_nonreg,"public_gain_observed":any_gain,"sealed_eval_consumed":False,"worker05_used_for_tuning":False,"elapsed_seconds":round(time.time()-t0,3),"checkpoints":checkpoints,"truth_boundary":"Real parameter-changing 27B LoRA artifact with save/reload hash and public held-out checks. No sealed/private W05 claim."}
    manifest["manifest_sha256"]=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    (outdir/"candidate_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    receipt={"kind":"AQLEVON_27B_R0_TRAINING_RECEIPT_V1","model_name":"AQLEVON-27B-R0","base_repo":MODEL_REPO,"base_revision":MODEL_REV,"optimizer_updates":global_step,"loss_first":losses[0],"loss_last":losses[-1],"adapter_sha256":adapter_sha,"adapter_state_sha256":saved_hash,"reload_hash_match":True,"public_dev":{"before":baseline_dev["successes"],"after":final_dev["successes"],"tasks":len(dev)},"public_shadow":{"before":baseline_shadow["successes"],"after":final_shadow["successes"],"tasks":len(shadow)},"sealed_eval_consumed":False,"worker05_used_for_tuning":False}
    (outdir/"training_receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print("AQLEVON_27B_FINAL",json.dumps(manifest,sort_keys=True),flush=True)
    return 0 if status=="AQLEVON_27B_R0_PUBLIC_PASS" else 3

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--w02-module",type=Path,required=True); ap.add_argument("--model-dir",type=Path,required=True); ap.add_argument("--output-dir",type=Path,required=True)
    raise SystemExit(run(ap.parse_args()))
if __name__=="__main__": main()
