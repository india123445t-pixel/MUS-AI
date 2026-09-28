#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
AGENT03 = REPO / "research/weight_factory/agent03/aqlevon_27b_rerun_contract_v1.py"
GXC = REPO / "research/weight_factory/agent04/aqlevon_27b_public_generalization_challenge_v1.py"

ADAPTER_SHA = "5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74"
ADAPTER_STATE_SHA = "1e3ff8a0fbc88686a2d96f93d4f04fdd66db2034ffdfafc2cc91e532ed0bf80f"
CANDIDATE_MANIFEST_SHA = "e020c6b140ffba104d1fe4485333fb225afd29c52dc03bf9a62d0f8c614e01c5"
BASE_REPO = "Qwen/Qwen3.8-27B"
BASE_REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
GEN_SEED = 280920261
PAIR_SEED = 280920262
AUTH08_FORBIDDEN_SEEDS = {27092026,27092027,27092028,27092029,1701,271828}
GENCFG = {
    "do_sample": True, "temperature": 0.7, "top_p": 0.8, "top_k": 20,
    "max_new_tokens": 256, "num_return_sequences": 1, "use_cache": True,
    "enable_thinking": False,
}

class PrepError(RuntimeError): pass

def canonical(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(v: Any) -> str:
    return hashlib.sha256(canonical(v)).hexdigest()

def load_module(name: str, path: Path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise PrepError(f"unloadable:{path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    if GEN_SEED in AUTH08_FORBIDDEN_SEEDS or PAIR_SEED in AUTH08_FORBIDDEN_SEEDS: raise PrepError("seed_collision")
    a03=load_module("aq_auth09_a03",AGENT03)
    gxc=load_module("aq_auth09_gxc",GXC)
    verified=a03.verify_contract()
    if verified.get("status")!="PASS": raise PrepError("agent03_contract_not_verified")
    task_records=a03.build_task_records(a03.load_contract())
    if len(task_records)!=56: raise PrepError(f"paired_task_count:{len(task_records)}")
    pack=gxc.build_pack(); tasks=pack["tasks"]
    if len(tasks)!=16: raise PrepError(f"gxc_task_count:{len(tasks)}")

    rows=[]
    for system in ("canonical_base","candidate_adapter_on_same_base"):
        for t in sorted(tasks,key=lambda x:x["task_id"]):
            rows.append({"section":"generalization","system":system,"task_id":t["task_id"],"split":"public_structural",
                         "seed":GEN_SEED,"prompt":t["prompt"],"prompt_sha256":hashlib.sha256(t["prompt"].encode()).hexdigest(),
                         "task_sha256":t["task_sha256"],"generation":GENCFG})
    for system in ("base","candidate"):
        for r in sorted(task_records,key=lambda x:(x["split"],x["task_id"])):
            rows.append({"section":"paired_public","system":system,"task_id":r["task_id"],"split":r["split"],
                         "seed":PAIR_SEED,"prompt":r["prompt"],"prompt_sha256":r["prompt_sha256"],
                         "task_sha256":r["task_sha256"],"generation":GENCFG})
    if len(rows)!=144: raise PrepError(f"row_count:{len(rows)}")
    keys={(x["section"],x["system"],x["task_id"],x["seed"]) for x in rows}
    if len(keys)!=144: raise PrepError("duplicate_rows")
    plan={
      "kind":"AQLEVON_AUTH09_BUDGET_PUBLIC_EVAL_PLAN_V1","schema_version":1,
      "candidate_identity":{"adapter_sha256":ADAPTER_SHA,"adapter_state_sha256":ADAPTER_STATE_SHA,
                            "candidate_manifest_sha256":CANDIDATE_MANIFEST_SHA,"base_repo":BASE_REPO,"base_revision":BASE_REV},
      "source_policy":{"sealed_eval_consumed":False,"historical_w05_used":False,"auth02_outputs_used":False,
                       "public_sources_only":True},
      "chronology":{"prepared_before_auth09_model_dispatch":True,"auth02_forbidden_seeds":sorted(AUTH08_FORBIDDEN_SEEDS),
                    "auth09_generalization_seed":GEN_SEED,"auth09_paired_seed":PAIR_SEED},
      "generation":GENCFG,
      "attempt_counts":{"generalization_per_system":16,"paired_public_per_system":56,"per_system_total":72,"total_model_dispatches":144},
      "retry_policy":{"retry_after_model_dispatch":False,"retry_malformed_output":False,"unknown_dispatch_state_action":"abort_fail_closed"},
      "scoring":{
        "pairing":"same task and same seed base-vs-candidate",
        "generalization_pass":"candidate_minus_base_successes > 0 AND one-sided exact sign p <= 0.05",
        "paired_public_pass":"candidate_minus_base_successes > 0 AND dev_delta >= 0 AND shadow_delta >= 0 AND one-sided exact sign p <= 0.05",
        "combined_public_support":"generalization_pass AND paired_public_pass",
        "truth_boundary":"New public evidence only; not historical W05 and not final promotion authority."},
      "challenge_pack_sha256":pack["pack_sha256"],
      "paired_public_task_catalog_sha256":verified["task_catalog_sha256"],
      "rows":rows,
    }
    plan["plan_sha256"]=sha(plan)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_bytes(canonical(plan)+b"\n")
    print(json.dumps({"status":"PASS","rows":len(rows),"plan_sha256":plan["plan_sha256"],"gen_seed":GEN_SEED,"pair_seed":PAIR_SEED},sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
