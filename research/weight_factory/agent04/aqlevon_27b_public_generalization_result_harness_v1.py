#!/usr/bin/env python3
"""AQLEVON Agent 04 Wave2 frozen public-generalization result harness.

CPU-only: prepares the frozen 128-row result matrix and deterministically
validates/scores completed base-vs-candidate outputs. It never runs inference.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import pathlib
import re
from fractions import Fraction
from typing import Any

HERE=pathlib.Path(__file__).resolve().parent
CHALLENGE_PATH=HERE/"aqlevon_27b_public_generalization_challenge_v1.py"
FREEZE_PATH=HERE/"aqlevon_27b_public_generalization_freeze_v1.json"

TEMPLATE_KIND="AQLEVON_27B_PUBLIC_GENERALIZATION_EXECUTION_TEMPLATE_V1"
MANIFEST_KIND="AQLEVON_27B_PUBLIC_GENERALIZATION_EXECUTION_MANIFEST_V1"
ATTEMPT_KIND="AQLEVON_27B_PUBLIC_GENERALIZATION_ATTEMPT_V1"
SCORE_KIND="AQLEVON_27B_PUBLIC_GENERALIZATION_SCORE_V1"

FROZEN_GIT_COMMIT="061ef205664aa7af27708c2ee27741a6cf246667"
FROZEN_GENERATOR_SHA256="06bb54774830918bc1f9b3254186f139b442b334e7e7ac328100db437e39ad83"
FROZEN_PACK_SHA256="10e049fa86fb034023bfa7e93a9dc0cfa58b3cff35718ef32b26533a18ff2b3b"
FROZEN_FREEZE_SHA256="5d1e848c5609874d0f1e184f285f4202538fab4a0456828e008f77ba9914c7fd"
BASE_REPO="Qwen/Qwen3.8-27B"
BASE_REVISION="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
SYSTEMS=("canonical_base","candidate_adapter_on_same_base")
SEEDS=(27092026,27092027,27092028,27092029)
_SHA256=re.compile(r"^[0-9a-f]{64}$")
ROW_KEYS={
    "kind","system","task_id","seed","manifest_sha256",
    "challenge_pack_sha256","freeze_manifest_sha256",
    "model_identity_sha256","raw_output",
}

class HarnessError(ValueError):
    pass

def canonical_bytes(v:Any)->bytes:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def sha256_obj(v:Any)->str:
    return hashlib.sha256(canonical_bytes(v)).hexdigest()

def sha256_file(p:pathlib.Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def require_sha(v:Any,field:str)->str:
    if not isinstance(v,str) or not _SHA256.fullmatch(v):
        raise HarnessError(f"invalid_sha256:{field}")
    return v

def load_challenge():
    spec=importlib.util.spec_from_file_location("agent04_frozen_challenge",CHALLENGE_PATH)
    if spec is None or spec.loader is None: raise HarnessError("challenge_module_unloadable")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def load_frozen_state()->tuple[Any,dict[str,Any],dict[str,Any]]:
    if not CHALLENGE_PATH.is_file() or not FREEZE_PATH.is_file():
        raise HarnessError("frozen_files_missing")
    if sha256_file(CHALLENGE_PATH)!=FROZEN_GENERATOR_SHA256:
        raise HarnessError("frozen_generator_file_hash_mismatch")
    freeze=json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if freeze.get("freeze_manifest_sha256")!=FROZEN_FREEZE_SHA256:
        raise HarnessError("freeze_manifest_identity_mismatch")
    body={k:v for k,v in freeze.items() if k!="freeze_manifest_sha256"}
    if sha256_obj(body)!=FROZEN_FREEZE_SHA256:
        raise HarnessError("freeze_manifest_self_hash_mismatch")
    challenge=freeze.get("challenge") or {}
    if challenge.get("generator_file_sha256")!=FROZEN_GENERATOR_SHA256:
        raise HarnessError("freeze_generator_binding_mismatch")
    if challenge.get("logical_pack_sha256")!=FROZEN_PACK_SHA256:
        raise HarnessError("freeze_pack_binding_mismatch")
    if freeze.get("protected_or_sealed_material_used") is not False:
        raise HarnessError("private_material_flag_invalid")
    gxc=load_challenge()
    pack=gxc.build_pack()
    claimed=pack.get("pack_sha256")
    pack_body={k:v for k,v in pack.items() if k!="pack_sha256"}
    if claimed!=FROZEN_PACK_SHA256 or gxc.sha256_obj(pack_body)!=FROZEN_PACK_SHA256:
        raise HarnessError("regenerated_pack_hash_mismatch")
    return gxc,freeze,pack

def immutable_template()->dict[str,Any]:
    _gxc,freeze,pack=load_frozen_state()
    task_ids=sorted(t["task_id"] for t in pack["tasks"])
    return {
        "schema_version":1,
        "kind":TEMPLATE_KIND,
        "authoritative_freeze_git_commit":FROZEN_GIT_COMMIT,
        "challenge_generator_sha256":FROZEN_GENERATOR_SHA256,
        "challenge_pack_sha256":FROZEN_PACK_SHA256,
        "freeze_manifest_sha256":FROZEN_FREEZE_SHA256,
        "base_identity":{"repo":BASE_REPO,"revision":BASE_REVISION},
        "candidate_identity":{
            "base_repo":BASE_REPO,"base_revision":BASE_REVISION,
            "adapter_sha256":"<REQUIRED_64_HEX>",
            "adapter_state_sha256":"<REQUIRED_64_HEX>",
            "candidate_manifest_sha256":"<REQUIRED_64_HEX>",
        },
        "generation":freeze["frozen_inference_protocol"],
        "scoring":freeze["frozen_scoring_protocol"],
        "task_ids":task_ids,
        "expected_result_rows":len(task_ids)*len(SEEDS)*len(SYSTEMS),
    }

def validate_template(t:dict[str,Any])->None:
    expected=immutable_template()
    for k in (
        "schema_version","kind","authoritative_freeze_git_commit",
        "challenge_generator_sha256","challenge_pack_sha256","freeze_manifest_sha256",
        "base_identity","generation","scoring","task_ids","expected_result_rows",
    ):
        if t.get(k)!=expected[k]: raise HarnessError(f"template_frozen_field_mismatch:{k}")
    c=t.get("candidate_identity")
    if not isinstance(c,dict): raise HarnessError("template_candidate_identity_missing")
    if c.get("base_repo")!=BASE_REPO or c.get("base_revision")!=BASE_REVISION:
        raise HarnessError("template_candidate_base_mismatch")

def finalize_manifest(
    template:dict[str,Any],*,adapter_sha256:str,
    adapter_state_sha256:str,candidate_manifest_sha256:str
)->dict[str,Any]:
    validate_template(template)
    m=json.loads(json.dumps(template))
    m["kind"]=MANIFEST_KIND
    c=m["candidate_identity"]
    c["adapter_sha256"]=require_sha(adapter_sha256,"adapter_sha256")
    c["adapter_state_sha256"]=require_sha(adapter_state_sha256,"adapter_state_sha256")
    c["candidate_manifest_sha256"]=require_sha(candidate_manifest_sha256,"candidate_manifest_sha256")
    m["manifest_sha256"]=sha256_obj(m)
    validate_manifest(m)
    return m

def validate_manifest(m:dict[str,Any])->None:
    if not isinstance(m,dict) or m.get("schema_version")!=1 or m.get("kind")!=MANIFEST_KIND:
        raise HarnessError("manifest_kind_or_schema_mismatch")
    t=immutable_template()
    for k in (
        "authoritative_freeze_git_commit","challenge_generator_sha256",
        "challenge_pack_sha256","freeze_manifest_sha256","base_identity",
        "generation","scoring","task_ids","expected_result_rows",
    ):
        if m.get(k)!=t[k]: raise HarnessError(f"manifest_frozen_field_mismatch:{k}")
    c=m.get("candidate_identity")
    if not isinstance(c,dict): raise HarnessError("manifest_candidate_identity_missing")
    if c.get("base_repo")!=BASE_REPO or c.get("base_revision")!=BASE_REVISION:
        raise HarnessError("manifest_candidate_base_mismatch")
    for k in ("adapter_sha256","adapter_state_sha256","candidate_manifest_sha256"):
        require_sha(c.get(k),k)
    claimed=require_sha(m.get("manifest_sha256"),"manifest_sha256")
    body={k:v for k,v in m.items() if k!="manifest_sha256"}
    if sha256_obj(body)!=claimed: raise HarnessError("manifest_self_hash_mismatch")

def model_identity(m:dict[str,Any],system:str)->dict[str,Any]:
    if system=="canonical_base":
        return {
            "system":system,"base_repo":BASE_REPO,"base_revision":BASE_REVISION,
            "adapter_sha256":None,"adapter_state_sha256":None,"candidate_manifest_sha256":None,
        }
    if system=="candidate_adapter_on_same_base":
        c=m["candidate_identity"]
        return {
            "system":system,"base_repo":c["base_repo"],"base_revision":c["base_revision"],
            "adapter_sha256":c["adapter_sha256"],
            "adapter_state_sha256":c["adapter_state_sha256"],
            "candidate_manifest_sha256":c["candidate_manifest_sha256"],
        }
    raise HarnessError("unknown_system")

def model_identity_sha256(m:dict[str,Any],system:str)->str:
    return sha256_obj(model_identity(m,system))

def build_result_skeleton(m:dict[str,Any])->list[dict[str,Any]]:
    validate_manifest(m)
    out=[]
    for system in SYSTEMS:
        identity=model_identity_sha256(m,system)
        for task_id in m["task_ids"]:
            for seed in SEEDS:
                out.append({
                    "kind":ATTEMPT_KIND,"system":system,"task_id":task_id,"seed":seed,
                    "manifest_sha256":m["manifest_sha256"],
                    "challenge_pack_sha256":FROZEN_PACK_SHA256,
                    "freeze_manifest_sha256":FROZEN_FREEZE_SHA256,
                    "model_identity_sha256":identity,"raw_output":"",
                })
    if len(out)!=128: raise HarnessError("internal_result_skeleton_count")
    return out

def validate_rows(m:dict[str,Any],rows:Any)->tuple[Any,dict[tuple[str,str,int],dict[str,Any]]]:
    validate_manifest(m)
    gxc,_freeze,_pack=load_frozen_state()
    if not isinstance(rows,list): raise HarnessError("results_not_list")
    expected={(s,t,z) for s in SYSTEMS for t in m["task_ids"] for z in SEEDS}
    seen={}
    for i,row in enumerate(rows):
        if not isinstance(row,dict): raise HarnessError(f"result_row_not_object:{i}")
        if set(row)!=ROW_KEYS: raise HarnessError(f"result_row_schema_mismatch:{i}")
        if row.get("kind")!=ATTEMPT_KIND: raise HarnessError(f"result_row_kind_mismatch:{i}")
        pair=(row.get("system"),row.get("task_id"),row.get("seed"))
        if pair not in expected: raise HarnessError(f"extra_pair:{pair}")
        if pair in seen: raise HarnessError(f"duplicate_pair:{pair}")
        s,t,z=pair
        if row.get("manifest_sha256")!=m["manifest_sha256"]:
            raise HarnessError(f"manifest_binding_mismatch:{s}:{t}:{z}")
        if row.get("challenge_pack_sha256")!=FROZEN_PACK_SHA256:
            raise HarnessError(f"challenge_hash_mismatch:{s}:{t}:{z}")
        if row.get("freeze_manifest_sha256")!=FROZEN_FREEZE_SHA256:
            raise HarnessError(f"freeze_hash_mismatch:{s}:{t}:{z}")
        if row.get("model_identity_sha256")!=model_identity_sha256(m,s):
            raise HarnessError(f"model_identity_mismatch:{s}:{t}:{z}")
        if not isinstance(row.get("raw_output"),str):
            raise HarnessError(f"malformed_output_type:{s}:{t}:{z}")
        seen[pair]=row
    missing=expected-set(seen)
    if missing:
        s,t,z=sorted(missing,key=lambda x:(x[0],x[1],x[2]))[0]
        raise HarnessError(f"missing_pair:{s}:{t}:{z}")
    if len(seen)!=m["expected_result_rows"]: raise HarnessError("result_count_mismatch")
    return gxc,seen

def score_attempt(gxc:Any,task_id:str,raw_output:str)->dict[str,Any]:
    try: program=json.loads(raw_output.strip())
    except Exception:
        return {"passed":False,"reason":"malformed_output_invalid_json"}
    if not isinstance(program,list) or not program:
        return {"passed":False,"reason":"malformed_output_program_shape"}
    v=gxc.verify_program(task_id,program)
    return {"passed":bool(v.get("passed")),"reason":str(v.get("reason"))}

def exact_one_sided_sign_p(candidate_wins:int,base_wins:int)->Fraction:
    if candidate_wins<0 or base_wins<0: raise HarnessError("negative_discordant_count")
    n=candidate_wins+base_wins
    if n==0: return Fraction(1,1)
    return Fraction(sum(math.comb(n,k) for k in range(candidate_wins,n+1)),2**n)

def score_results(m:dict[str,Any],rows:Any)->dict[str,Any]:
    gxc,seen=validate_rows(m,rows)
    task_ids=m["task_ids"]
    per={}
    successes={s:0 for s in SYSTEMS}
    malformed={s:0 for s in SYSTEMS}
    task_successes={s:{t:0 for t in task_ids} for s in SYSTEMS}
    reasons={s:{} for s in SYSTEMS}
    for pair in sorted(seen,key=lambda x:(x[1],x[2],x[0])):
        s,t,_z=pair
        r=score_attempt(gxc,t,seen[pair]["raw_output"])
        per[pair]=r
        successes[s]+=int(r["passed"])
        task_successes[s][t]+=int(r["passed"])
        reasons[s][r["reason"]]=reasons[s].get(r["reason"],0)+1
        if r["reason"].startswith("malformed_output_"): malformed[s]+=1
    cw=bw=0; paired=[]
    for t in task_ids:
        for z in SEEDS:
            b=per[("canonical_base",t,z)]["passed"]
            c=per[("candidate_adapter_on_same_base",t,z)]["passed"]
            if c and not b: cw+=1
            elif b and not c: bw+=1
            paired.append({"task_id":t,"seed":z,"base_passed":b,"candidate_passed":c})
    p=exact_one_sided_sign_p(cw,bw)
    robust={
        s:sorted(t for t,n in task_successes[s].items() if n>=3)
        for s in SYSTEMS
    }
    delta=successes["candidate_adapter_on_same_base"]-successes["canonical_base"]
    report={
        "schema_version":1,"kind":SCORE_KIND,
        "manifest_sha256":m["manifest_sha256"],
        "authoritative_freeze_git_commit":FROZEN_GIT_COMMIT,
        "challenge_pack_sha256":FROZEN_PACK_SHA256,
        "freeze_manifest_sha256":FROZEN_FREEZE_SHA256,
        "attempts_per_system":64,
        "successes":successes,
        "malformed_outputs_scored_failed_no_retry":malformed,
        "failure_reason_counts":reasons,
        "primary_delta_candidate_minus_base":delta,
        "discordant_pairs":{"candidate_wins":cw,"base_wins":bw,"total":cw+bw},
        "paired_one_sided_exact_sign_binomial_p":{
            "numerator":p.numerator,"denominator":p.denominator,
            "fraction":f"{p.numerator}/{p.denominator}",
            "decimal":format(float(p),".17g"),
        },
        "robust_tasks":{
            s:{"count":len(robust[s]),"task_ids":robust[s],
               "criterion":"at_least_3_successes_of_4_frozen_seeds"}
            for s in SYSTEMS
        },
        "frozen_support_threshold":{
            "delta_must_be_positive":True,
            "one_sided_exact_p_max_fraction":"1/20",
        },
        "support_observed":delta>0 and p<=Fraction(1,20),
        "interpretation_boundary":
            "Additional public structural-generalization evidence only; not W05 sealed evaluation and not final promotion authority.",
        "paired_attempts":paired,
    }
    report["score_report_sha256"]=sha256_obj(report)
    return report

def read_json(p:pathlib.Path)->Any:
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p:pathlib.Path,v:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(canonical_bytes(v)+b"\n")

def cmd_prepare(a:argparse.Namespace)->int:
    m=finalize_manifest(
        read_json(a.template),
        adapter_sha256=a.adapter_sha256,
        adapter_state_sha256=a.adapter_state_sha256,
        candidate_manifest_sha256=a.candidate_manifest_sha256,
    )
    write_json(a.manifest_out,m); write_json(a.results_out,build_result_skeleton(m))
    print(json.dumps({"manifest_sha256":m["manifest_sha256"],"rows":128,"inference_executed":False},sort_keys=True))
    return 0

def cmd_score(a:argparse.Namespace)->int:
    report=score_results(read_json(a.manifest),read_json(a.results))
    write_json(a.out,report)
    print(json.dumps({
        "score_report_sha256":report["score_report_sha256"],
        "delta":report["primary_delta_candidate_minus_base"],
        "p":report["paired_one_sided_exact_sign_binomial_p"]["fraction"],
        "support_observed":report["support_observed"],
    },sort_keys=True))
    return 0

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    p=sub.add_parser("prepare")
    p.add_argument("--template",type=pathlib.Path,required=True)
    p.add_argument("--adapter-sha256",required=True)
    p.add_argument("--adapter-state-sha256",required=True)
    p.add_argument("--candidate-manifest-sha256",required=True)
    p.add_argument("--manifest-out",type=pathlib.Path,required=True)
    p.add_argument("--results-out",type=pathlib.Path,required=True)
    p.set_defaults(func=cmd_prepare)
    p=sub.add_parser("score")
    p.add_argument("--manifest",type=pathlib.Path,required=True)
    p.add_argument("--results",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    p.set_defaults(func=cmd_score)
    a=ap.parse_args()
    return int(a.func(a))

if __name__=="__main__":
    raise SystemExit(main())
