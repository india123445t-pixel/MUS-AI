#!/usr/bin/env python3
"""AQLEVON Candidate D — verifier-guided pairwise preference crystallization.

Scientific firewall:
- PUBLIC discovery (idx 00-01) only for mining, pair construction, and gradients.
- PUBLIC shadow (idx 02-03) is evaluation-only.
- Worker05 sealed/private evaluation is forbidden.
- Base/model/data identities remain pinned.

Core change vs Candidate C:
Instead of SFT-only imitation, train pairwise preferences:
chosen = verifier-passing model-native discovery output when available, else PUBLIC oracle.
rejected = model-native hard negative from the same discovery prompt.
Objective = pairwise logistic preference loss + small chosen NLL anchor.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, os, random, re
from pathlib import Path
from typing import Any

MODEL_REPO="Qwen/Qwen3.5-4B-Base"
MODEL_REV="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
PACK_SHA="35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
SEED=1701
EPOCHS=3
MINING_N=8
LR=7e-6
BETA=2.0
MARGIN=0.05
CHOSEN_NLL_WEIGHT=0.25
CAP=2048
LAYERS=(3,7,11,15,19,23,27,31)
TARGET_SUFFIXES={f"layers.{i}.self_attn.{p}" for i in LAYERS for p in ("q_proj","v_proj")}
WEIGHT_NAME=re.compile(r"(?:^|\.)layers\.(\d+)\.self_attn\.(q_proj|v_proj)\.lora_([AB])(?:\.default)?\.weight$")

def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(1<<20),b""): h.update(part)
    return h.hexdigest()

def canonical_sha(obj:Any)->str:
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def sealed(obj:dict,field:str)->dict:
    out=dict(obj); out[field]=canonical_sha(out); return out

def write_json(path:Path,obj:Any)->None:
    path.write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+"\n")

def load_w02(path:Path):
    spec=importlib.util.spec_from_file_location("aqlevon_w02_pref",str(path))
    if spec is None or spec.loader is None: raise RuntimeError("cannot_load_w02")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def strict_json_program(text:str)->Any|None:
    s=text.strip()
    if s.startswith("```") and s.endswith("```"):
        lines=s.splitlines()
        if len(lines)>=3 and lines[0].strip().lower() in {"```","```json"}:
            s="\n".join(lines[1:-1]).strip()
    try: value=json.loads(s)
    except Exception: return None
    return value if isinstance(value,list) and value else None

def task_index(task:dict[str,Any])->int:
    m=re.search(r"-(\d{2})-hardened$",task["task_id"])
    if not m: raise ValueError(task["task_id"])
    return int(m.group(1))

def build_core(w02,task): return w02._core(task["family"],task_index(task))

def verify_text(w02,task,text:str)->tuple[bool,str]:
    p=strict_json_program(text)
    if p is None: return False,"invalid_json_program"
    r=w02.verify(task,build_core(w02,task),p)
    return bool(r.get("passed")),str(r.get("reason"))

def load_inputs(args):
    if os.environ.get("AQLEVON_SEALED_EVAL_PATH") or os.environ.get("AQLEVON_EVAL_SECRET"):
        raise RuntimeError("sealed_eval_environment_forbidden")
    probe=json.loads(args.probe_result.read_text())
    if probe.get("decision")!="MATERIAL_LATENT_CAPABILITY": raise RuntimeError("probe_not_material")
    if probe.get("sealed_eval_consumed") is not False or probe.get("worker05_used_for_tuning") is not False:
        raise RuntimeError("protected_eval_contamination")
    if probe.get("model_repo")!=MODEL_REPO or probe.get("model_revision")!=MODEL_REV: raise RuntimeError("model_identity_mismatch")
    if probe.get("training_pack_sha256")!=PACK_SHA: raise RuntimeError("pack_identity_mismatch")
    pack=json.loads(args.training_pack.read_text())
    if pack.get("pack_sha256")!=PACK_SHA: raise RuntimeError("public_pack_mismatch")
    tasks=[t for t in pack["tasks"] if t.get("verifier_mode")=="hardened" and t.get("training_eligible") is True]
    if len(tasks)!=56: raise RuntimeError(f"expected_56_public_tasks:{len(tasks)}")
    discovery=[]; shadow=[]
    for t in tasks:
        i=task_index(t)
        if i in (0,1): discovery.append(t)
        elif i in (2,3): shadow.append(t)
        else: raise RuntimeError(f"unexpected_index:{i}")
    discovery=sorted(discovery,key=lambda x:(x["family"],x["task_id"]))
    shadow=sorted(shadow,key=lambda x:x["task_id"])
    if len(discovery)!=28 or len({t["family"] for t in discovery})!=14: raise RuntimeError("bad_discovery_coverage")
    if len(shadow)!=28: raise RuntimeError("bad_shadow_count")
    return probe,discovery,shadow

def render_prompt(tokenizer,prompt:str)->str:
    return tokenizer.apply_chat_template([{"role":"user","content":prompt}],tokenize=False,add_generation_prompt=True,enable_thinking=False)

def evaluate_shadow(model,tokenizer,w02,shadow,generation):
    import torch
    model.eval(); rows=[]; passed=0
    for t in shadow:
        seed=SEED+int(hashlib.sha256(t["task_id"].encode()).hexdigest()[:8],16)
        random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        chat=render_prompt(tokenizer,t["prompt"])
        enc=tokenizer(chat,return_tensors="pt",add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            out=model.generate(**enc,do_sample=True,temperature=generation["temperature"],top_p=generation["top_p"],top_k=generation["top_k"],max_new_tokens=generation["max_new_tokens"],num_return_sequences=1,use_cache=True,pad_token_id=tokenizer.eos_token_id)[0]
        text=tokenizer.decode(out[enc["input_ids"].shape[1]:],skip_special_tokens=True).strip()
        ok,reason=verify_text(w02,t,text); passed+=int(ok)
        rows.append({"task_id":t["task_id"],"passed":ok,"reason":reason,"text":text})
        del enc,out
    return {"successes":passed,"tasks":len(shadow),"pass_at_1":passed/len(shadow),"records":rows}

def mine_pairs(model,tokenizer,w02,discovery,generation):
    import torch
    model.eval(); pairs=[]; mining=[]
    for ti,t in enumerate(discovery):
        seed=SEED+int(hashlib.sha256(("pref:"+t["task_id"]).encode()).hexdigest()[:8],16)
        random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        chat=render_prompt(tokenizer,t["prompt"])
        enc=tokenizer(chat,return_tensors="pt",add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            outs=model.generate(**enc,do_sample=True,temperature=generation["temperature"],top_p=generation["top_p"],top_k=generation["top_k"],max_new_tokens=generation["max_new_tokens"],num_return_sequences=MINING_N,use_cache=True,pad_token_id=tokenizer.eos_token_id)
        prefix_len=enc["input_ids"].shape[1]
        positives=[]; parsed_neg=[]; invalid_neg=[]
        for out in outs:
            text=tokenizer.decode(out[prefix_len:],skip_special_tokens=True).strip()
            ok,reason=verify_text(w02,t,text)
            if ok:
                c=json.dumps(strict_json_program(text),ensure_ascii=False,separators=(",",":"))
                if c not in positives: positives.append(c)
            elif strict_json_program(text) is not None:
                parsed_neg.append((text,reason))
            else:
                invalid_neg.append((text,reason))
        oracle=t.get("oracle_program")
        if not isinstance(oracle,list) or not oracle: raise RuntimeError(f"missing_oracle:{t['task_id']}")
        chosen=positives[0] if positives else json.dumps(oracle,ensure_ascii=False,separators=(",",":"))
        neg_pool=parsed_neg or invalid_neg
        if not neg_pool: raise RuntimeError(f"no_rejected_candidate:{t['task_id']}")
        rejected,reason=neg_pool[0]
        if chosen.strip()==rejected.strip(): raise RuntimeError("degenerate_pair")
        pairs.append({"task_id":t["task_id"],"family":t["family"],"prompt":t["prompt"],"chosen":chosen,"rejected":rejected,"chosen_source":"model_verified" if positives else "public_oracle","rejected_reason":reason})
        mining.append({"task_id":t["task_id"],"verified_positives":len(positives),"parsed_negatives":len(parsed_neg),"invalid_negatives":len(invalid_neg),"chosen_source":"model_verified" if positives else "public_oracle","rejected_reason":reason})
        print(f"AQLEVON_PREF_MINE={ti+1}/{len(discovery)} id={t['task_id']} pos={len(positives)} parsed_neg={len(parsed_neg)} invalid_neg={len(invalid_neg)}",flush=True)
        del enc,outs; torch.cuda.empty_cache()
    if len(pairs)!=28: raise RuntimeError(f"bad_pair_count:{len(pairs)}")
    return pairs,mining

def seq_mean_logp(model,tokenizer,prompt:str,completion:str):
    import torch
    chat=render_prompt(tokenizer,prompt)
    prefix=tokenizer(chat,add_special_tokens=False).input_ids
    target=tokenizer(completion+(tokenizer.eos_token or "<|im_end|>"),add_special_tokens=False).input_ids
    if not target or len(prefix)+len(target)>CAP: raise RuntimeError("sequence_cap_violation")
    ids=torch.tensor([prefix+target],device="cuda",dtype=torch.long)
    labels=torch.tensor([[-100]*len(prefix)+target],device="cuda",dtype=torch.long)
    logits=model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False).logits[:,:-1,:].float()
    labs=labels[:,1:]
    mask=labs.ne(-100)
    safe=labs.masked_fill(~mask,0)
    lp=torch.log_softmax(logits,dim=-1).gather(-1,safe.unsqueeze(-1)).squeeze(-1)
    val=(lp*mask).sum()/mask.sum().clamp_min(1)
    return val

def tensor_layout(weights):
    modules={}
    if len(weights)!=32: raise RuntimeError(f"expected_32_adapter_tensors:{len(weights)}")
    for name,value in weights.items():
        hit=WEIGHT_NAME.search(name)
        if not hit: raise RuntimeError(f"unexpected_adapter_key:{name}")
        layer,proj,part=int(hit[1]),hit[2],hit[3]
        modules.setdefault((layer,proj),{})[part]=tuple(value.shape)
    expected={(i,p) for i in LAYERS for p in ("q_proj","v_proj")}
    if set(modules)!=expected: raise RuntimeError("adapter_topology_mismatch")
    return {f"{l}:{p}":{k:list(v) for k,v in parts.items()} for (l,p),parts in sorted(modules.items())}

def state_hash(weights):
    h=hashlib.sha256()
    for name in sorted(weights):
        v=weights[name].detach().cpu().contiguous().float()
        h.update(name.encode()); h.update(str(tuple(v.shape)).encode()); h.update(v.numpy().tobytes(order="C"))
    return h.hexdigest()

def run(args):
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig,PeftModel,TaskType,get_peft_model,get_peft_model_state_dict
    from peft.tuners.lora.layer import LoraLayer
    from safetensors.torch import load_file
    from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(): raise RuntimeError("bf16_cuda_required")
    probe,discovery,shadow=load_inputs(args); w02=load_w02(args.w02_module); generation=dict(probe["generation"])
    random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    base=Qwen3_5ForConditionalGeneration.from_pretrained(str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    full=[i for i,k in enumerate(base.config.text_config.layer_types) if k=="full_attention"]
    if full!=list(LAYERS): raise RuntimeError(f"full_attention_layers_changed:{full}")
    pre=evaluate_shadow(base,tokenizer,w02,shadow,generation)
    print("AQLEVON_PREF_SHADOW_PRE",json.dumps({k:v for k,v in pre.items() if k!="records"},sort_keys=True),flush=True)
    pairs,mining=mine_pairs(base,tokenizer,w02,discovery,generation)
    model=get_peft_model(base,LoraConfig(r=4,lora_alpha=4,target_modules=["q_proj","v_proj"],lora_dropout=0,bias="none",task_type=TaskType.CAUSAL_LM,init_lora_weights=True))
    base.config.use_cache=False; model.enable_input_require_grads(); model.gradient_checkpointing_enable()
    targets=sorted(n for n,m in model.named_modules() if isinstance(m,LoraLayer) and n.endswith((".q_proj",".v_proj")))
    observed={next((s for s in TARGET_SUFFIXES if n.endswith(s)),"") for n in targets}
    if observed!=TARGET_SUFFIXES or len(targets)!=16: raise RuntimeError("lora_target_topology_mismatch")
    params=[p for p in model.parameters() if p.requires_grad]
    if sum(p.numel() for p in params)!=458752: raise RuntimeError("trainable_parameter_count_mismatch")
    opt=torch.optim.AdamW(params,lr=LR,weight_decay=0.05)
    total=len(pairs)*EPOCHS; step=0; losses=[]; grads=[]; prefs=[]
    model.train()
    for epoch in range(EPOCHS):
        rows=list(pairs); random.Random(SEED+epoch).shuffle(rows)
        for row in rows:
            opt.zero_grad(set_to_none=True)
            chosen_lp=seq_mean_logp(model,tokenizer,row["prompt"],row["chosen"])
            rejected_lp=seq_mean_logp(model,tokenizer,row["prompt"],row["rejected"])
            gap=chosen_lp-rejected_lp
            pref_loss=-F.logsigmoid(BETA*(gap-MARGIN))
            loss=pref_loss+CHOSEN_NLL_WEIGHT*(-chosen_lp)
            if not bool(torch.isfinite(loss).item()): raise RuntimeError("nonfinite_loss")
            loss.backward()
            grad=float(torch.nn.utils.clip_grad_norm_(params,1.0))
            if not math.isfinite(grad) or grad<=0: raise RuntimeError(f"invalid_gradient:{step+1}")
            frac=step/max(1,total-1); lr=1e-6+(LR-1e-6)*(1+math.cos(math.pi*frac))/2
            for g in opt.param_groups: g["lr"]=lr
            opt.step(); step+=1
            losses.append(float(loss.detach())); grads.append(grad); prefs.append(float(gap.detach()))
            print(f"AQLEVON_PREF_UPDATE={step}/{total} epoch={epoch+1}/{EPOCHS} loss={losses[-1]:.6f} gap={prefs[-1]:.6f} grad={grad:.6f} lr={lr:.9g}",flush=True)
    if step!=84: raise RuntimeError(f"optimizer_update_accounting_mismatch:{step}:84")
    outdir=args.output_dir
    if outdir.exists(): raise RuntimeError("refuse_overwrite_output")
    artifact=outdir/"candidate_artifact"; artifact.mkdir(parents=True)
    model.save_pretrained(str(artifact),safe_serialization=True)
    saved=load_file(str(artifact/"adapter_model.safetensors"),device="cpu")
    layout=tensor_layout(saved); changed=sum(int(torch.count_nonzero(v).item()) for n,v in saved.items() if ".lora_B." in n)
    if changed<=0: raise RuntimeError("no_lora_B_change")
    sh=state_hash(saved)
    del saved,model,base,opt
    import gc; gc.collect(); torch.cuda.empty_cache()
    rb=Qwen3_5ForConditionalGeneration.from_pretrained(str(args.model_dir),dtype=torch.bfloat16,device_map={"":0},low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    reloaded=PeftModel.from_pretrained(rb,str(artifact),is_trainable=False)
    rs=get_peft_model_state_dict(reloaded)
    if state_hash(rs)!=sh: raise RuntimeError("save_reload_hash_mismatch")
    reloaded.config.use_cache=True
    post=evaluate_shadow(reloaded,tokenizer,w02,shadow,generation)
    improvement=post["pass_at_1"]-pre["pass_at_1"]; gain=post["successes"]-pre["successes"]
    pre_by={r["task_id"]:bool(r["passed"]) for r in pre["records"]}; post_by={r["task_id"]:bool(r["passed"]) for r in post["records"]}
    regressions=sorted(t for t,v in pre_by.items() if v and not post_by.get(t,False))
    gate=bool(improvement>=0.10 and gain>=3 and not regressions)
    print("AQLEVON_PREF_SHADOW_POST",json.dumps({k:v for k,v in post.items() if k!="records"},sort_keys=True),flush=True)
    print(f"AQLEVON_PREF_PUBLIC_GATE={'PASS' if gate else 'FAIL'} improvement={improvement:.6f} gain_tasks={gain} regressions={len(regressions)}",flush=True)
    write_json(outdir/"preference_pairs.json",pairs); write_json(outdir/"shadow_pre_eval.json",pre); write_json(outdir/"shadow_post_eval.json",post)
    receipt=sealed({"receipt_kind":"AQLEVON_ONE_DAY_VERIFIER_PREFERENCE_CRYSTALLIZATION_RECEIPT_V1","base_repo":MODEL_REPO,"base_revision":MODEL_REV,"pair_count":len(pairs),"epochs":EPOCHS,"optimizer_updates":step,"mining_n":MINING_N,"mining_records":mining,"losses":losses,"gradient_norms":grads,"preference_gaps":prefs,"adapter_state_sha256":sh,"changed_lora_B_elements":changed,"shadow_pre_successes":pre["successes"],"shadow_post_successes":post["successes"],"shadow_gain_tasks":gain,"shadow_improvement":improvement,"shadow_regressions":regressions,"public_shadow_gate_pass":gate,"sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False},"receipt_sha256")
    write_json(outdir/"training_run_receipt.json",receipt)
    manifest=sealed({"manifest_kind":"AQLEVON_ONE_DAY_PREFERENCE_CANDIDATE_MANIFEST_V1","candidate_status":"READY_FOR_WORKER05_EVALUATION" if gate else "PUBLIC_SHADOW_GATE_FAILED","artifact_type":"adapter","base_repo":MODEL_REPO,"base_revision":MODEL_REV,"adapter_model_sha256":sha_file(artifact/"adapter_model.safetensors"),"adapter_config_sha256":sha_file(artifact/"adapter_config.json"),"adapter_state_sha256":sh,"tensor_layout":layout,"public_shadow_gate_pass":gate,"sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False},"manifest_sha256")
    write_json(outdir/"candidate_artifact_manifest.json",manifest)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--probe-result",type=Path,required=True); p.add_argument("--w02-module",type=Path,required=True); p.add_argument("--training-pack",type=Path,required=True)
    p.add_argument("--model-dir",type=Path); p.add_argument("--output-dir",type=Path); p.add_argument("--preflight-only",action="store_true")
    a=p.parse_args(); probe,d,s=load_inputs(a)
    print(f"AQLEVON_PREF_PUBLIC_PREFLIGHT_PASS discovery={len(d)} shadow={len(s)} families={len({x['family'] for x in d})} epochs={EPOCHS} updates={len(d)*EPOCHS} mining_n={MINING_N} probe_decision={probe['decision']}",flush=True)
    if a.preflight_only:return
    if not a.model_dir or not a.output_dir:p.error("--model-dir and --output-dir required unless --preflight-only")
    run(a)
if __name__=="__main__": main()
