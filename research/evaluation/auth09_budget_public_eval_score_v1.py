#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve()
REPO=HERE.parents[2]
AGENT03=REPO/"research/weight_factory/agent03/aqlevon_27b_rerun_contract_v1.py"
GXC=REPO/"research/weight_factory/agent04/aqlevon_27b_public_generalization_challenge_v1.py"

class ScoreError(RuntimeError): pass

def canonical(v:Any)->bytes:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def sha(v:Any)->str: return hashlib.sha256(canonical(v)).hexdigest()

def load_module(n,p):
    s=importlib.util.spec_from_file_location(n,p)
    if s is None or s.loader is None: raise ScoreError(f"unloadable:{p}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def strict(text):
    try:
        v=json.loads(text.strip())
        return v if isinstance(v,list) and v else None
    except Exception:
        return None

def pval(cw,bw):
    n=cw+bw
    if n==0: return Fraction(1,1)
    return Fraction(sum(math.comb(n,k) for k in range(cw,n+1)),2**n)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",type=Path,required=True)
    ap.add_argument("--results",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    plan=json.loads(a.plan.read_text())
    ph=plan.pop("plan_sha256",None)
    if ph!=sha(plan): raise ScoreError("plan_self_hash")
    plan["plan_sha256"]=ph

    rows=json.loads(a.results.read_text())
    expected={(r["section"],r["system"],r["task_id"],int(r["seed"])) for r in plan["rows"]}
    seen={}
    for r in rows:
        k=(r["section"],r["system"],r["task_id"],int(r["seed"]))
        if k not in expected or k in seen: raise ScoreError(f"bad_result_key:{k}")
        seen[k]=r
    if set(seen)!=expected: raise ScoreError("incomplete_results")

    a03=load_module("auth09_a03",AGENT03)
    gxc=load_module("auth09_gxc",GXC)
    contract=a03.load_contract()
    taskrecs=a03.build_task_records(contract)
    taskmap={r["task_id"]:r for r in taskrecs}
    w02=a03.load_w02(contract)
    scores={}
    for k,r in seen.items():
        sec,sys,tid,seed=k
        prog=strict(r["output"])
        if sec=="generalization":
            verdict=gxc.verify_program(tid,prog) if prog is not None else {"passed":False,"reason":"invalid_json"}
        else:
            rec=taskmap[tid]
            verdict=w02.verify(rec["_task"],rec["_core"],prog) if prog is not None else {"passed":False,"reason":"invalid_json"}
        scores[k]={"passed":bool(verdict.get("passed")),"reason":str(verdict.get("reason"))}

    def section_report(section,base,cand):
        tasks=sorted({k[2] for k in scores if k[0]==section})
        pairs=[]; cw=bw=0; bs=cs=0; by_split={}
        for tid in tasks:
            kb=next(k for k in scores if k[0]==section and k[1]==base and k[2]==tid)
            kc=next(k for k in scores if k[0]==section and k[1]==cand and k[2]==tid)
            b=scores[kb]["passed"]; c=scores[kc]["passed"]; bs+=int(b); cs+=int(c)
            split=seen[kb]["split"]; d=by_split.setdefault(split,{"base":0,"candidate":0})
            d["base"]+=int(b); d["candidate"]+=int(c)
            if c and not b: cw+=1
            elif b and not c: bw+=1
            pairs.append({"task_id":tid,"split":split,"base_passed":b,"candidate_passed":c})
        p=pval(cw,bw); delta=cs-bs
        for d in by_split.values(): d["delta"]=d["candidate"]-d["base"]
        return {"attempts_per_system":len(tasks),"base_successes":bs,"candidate_successes":cs,"delta":delta,
                "discordant":{"candidate_wins":cw,"base_wins":bw},"p_fraction":f"{p.numerator}/{p.denominator}",
                "p_decimal":float(p),"by_split":by_split,"pairs":pairs}

    gen=section_report("generalization","canonical_base","candidate_adapter_on_same_base")
    pair=section_report("paired_public","base","candidate")
    gen_pass=gen["delta"]>0 and gen["p_decimal"]<=0.05
    pair_pass=pair["delta"]>0 and pair["p_decimal"]<=0.05 and all(x["delta"]>=0 for x in pair["by_split"].values())
    report={
      "kind":"AQLEVON_AUTH09_BUDGET_PUBLIC_SCORE_V1","plan_sha256":ph,"complete":True,
      "generalization":gen,"paired_public":pair,"generalization_pass":gen_pass,"paired_public_pass":pair_pass,
      "combined_public_support":gen_pass and pair_pass,"sealed_eval_consumed":False,
      "truth_boundary":"New public evidence only; not historical W05 and not final promotion authority."}
    report["score_sha256"]=sha(report)
    a.out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({k:report[k] for k in ["generalization_pass","paired_public_pass","combined_public_support","score_sha256"]},sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
