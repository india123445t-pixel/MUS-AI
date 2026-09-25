#!/usr/bin/env python3
"""Materialize a training-safe probe record from the Auth05 recovered decision.

No model inference is repeated. Only PUBLIC discovery task IDs proven pass@8 in
Auth05 are paired with their PUBLIC Worker02 oracle_program targets. PUBLIC
shadow tasks carry no training target. Worker05 is never read.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

MODEL_REPO="Qwen/Qwen3.5-4B-Base"
MODEL_REV="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
PACK_SHA="35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
W02_HEAD="abb94ef134e2e97036b6959dbc9db4278d3736b6"

def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--recovered-decision",type=Path,required=True)
    ap.add_argument("--training-pack",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.recovered_decision.read_text())
    p=json.loads(a.training_pack.read_text())
    assert d["kind"]=="AQLEVON_ONE_DAY_PUBLIC_PASSN_PROBE_RECOVERED_DECISION_V1"
    assert d["recovered_decision"]=="MATERIAL_LATENT_CAPABILITY"
    assert d["source_head"]=="c7b859f0a5459c1a79ea6fa96ca4adafe17599b6"
    assert d["w02_head"]==W02_HEAD
    assert d["model_repo"]==MODEL_REPO and d["model_revision"]==MODEL_REV
    assert d["training_pack_sha256"]==PACK_SHA
    assert d["sealed_eval_consumed"] is False and d["worker05_used_for_tuning"] is False
    assert d["full_task_execution_observed"] is True
    assert p["pack_sha256"]==PACK_SHA and p["pack_kind"]=="AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1"
    tasks={t["task_id"]:t for t in p["tasks"] if t.get("verifier_mode")=="hardened" and t.get("training_eligible") is True}
    assert len(tasks)==56
    status={x["task_id"]:x for x in d["task_status"]}
    assert set(status)==set(tasks)
    pass8=set(d["discovery_pass8_task_ids"])
    rescued=set(d["discovery_rescued_task_ids"])
    pass1=set(d["discovery_pass1_success_task_ids"])
    assert pass8==rescued|pass1 and not (rescued&pass1) and len(pass8)==6
    records=[]
    train_targets=0
    for tid in sorted(tasks):
        t=tasks[tid]; s=status[tid]
        rec={"task_id":tid,"semantic_core_id":t["semantic_core_id"],"family":t["family"],
             "public_split":s["public_split"],"candidates":[],"repair":None}
        if s["public_split"]=="discovery" and tid in pass8:
            target=json.dumps(t["oracle_program"],ensure_ascii=False,separators=(",",":"))
            if tid in rescued:
                rec["candidates"]=[
                    {"passed":False,"reason":"auth05_pass1_failed_text_not_recovered","text":"[]"},
                    {"passed":True,"reason":"public_oracle_for_auth05_pass8_rescue","text":target}
                ]
                rec["recovered_source"]="auth05_rescued_task_public_oracle"
            else:
                rec["candidates"]=[{"passed":True,"reason":"public_oracle_for_auth05_pass1_success","text":target}]
                rec["recovered_source"]="auth05_pass1_task_public_oracle"
            train_targets+=1
        records.append(rec)
    assert train_targets==6
    assert all(not r["candidates"] for r in records if r["public_split"]=="shadow")
    out={
      "result_kind":"AQLEVON_ONE_DAY_PUBLIC_VERIFIED_TRAJECTORY_PROBE_V1",
      "model_repo":MODEL_REPO,"model_revision":MODEL_REV,
      "training_pack_sha256":PACK_SHA,
      "sealed_eval_consumed":False,"worker05_used_for_tuning":False,
      "decision":"MATERIAL_LATENT_CAPABILITY",
      "generation":{"temperature":0.7,"top_p":0.8,"top_k":20,"max_new_tokens":96},
      "records":records,
      "recovered_materialization":True,
      "recovered_decision_kind":d["kind"],
      "recovered_decision_sha256":sha_file(a.recovered_decision),
      "auth05_probe_log_sha256":d["probe_log_sha256"],
      "target_provenance":"PUBLIC Worker02 oracle_program only for Auth05 pass@8 discovery task IDs; no shadow target; no model rerun"
    }
    a.output.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(f"AQLEVON_RECOVERED_MATERIALIZATION_PASS train_targets={train_targets} shadow_targets=0")

if __name__=="__main__":
    main()
