#!/usr/bin/env python3
"""AQLEVON Worker-04 P2.1 merge receipt consumer/gate.

Consumes Worker-03 Candidate Artifact Manifest V1 and Worker-05 Evaluation Decision
Receipt V1. Owns only merge admission/construction and post-evaluation promotion.
Evaluation thresholds/correctness and final release remain upstream/Manager authority.
"""
from __future__ import annotations
import argparse, hashlib, json, numbers, re, unicodedata
from pathlib import Path
from typing import Any

HASH_PROFILE="AQLEVON_CANONICAL_JSON_SHA256_V1"
CANDIDATE_KIND="AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1"
EVAL_KIND="AQLEVON_EVALUATION_DECISION_RECEIPT_V1"
ADMISSION_KIND="AQLEVON_MERGE_SOURCE_ADMISSION_RECEIPT_V1"
PROMOTION_KIND="AQLEVON_MERGE_PROMOTION_DECISION_RECEIPT_V1"
SHA_RE=re.compile(r"^[0-9a-f]{64}$")
ID_RE=re.compile(r"^aqlevon-candidate-artifact-v1:sha256:[0-9a-f]{64}$")
ARTIFACT_TYPES={"adapter","full_checkpoint","merge","quantized_serving_artifact"}
ARTIFACT_STAGES={"probe_only","reproducible_gene","promotion_candidate","merge_candidate","release_candidate"}
TOPOLOGIES={"FULL_HYBRID_TEXT","ATTENTION_MLP_PARTIAL","MLP_ONLY","CUSTOM_EXPERIMENTAL"}
EVAL_STATUS={"INVALID","REJECTED","PROMOTION_ELIGIBLE"}

# Public interoperability names retained for P2.1 consumers/tests.
CANDIDATE_MANIFEST_KIND=CANDIDATE_KIND
EVALUATION_RECEIPT_KIND=EVAL_KIND
SOURCE_ADMISSION_RECEIPT_KIND=ADMISSION_KIND
PROMOTION_RECEIPT_KIND=PROMOTION_KIND

CANDIDATE_REQUIRED={
 "schema_version","manifest_kind","manifest_id","hash_profile","artifact_type","artifact_stage","base",
 "tokenizer_sha256","config_sha256","training_shard_manifest_sha256","training_run_receipt_sha256",
 "merge_recipe_sha256","parameter_layout_sha256","topology_class","artifact_files","artifact_file_tree_sha256",
 "adapter_state_sha256","checkpoint_state_sha256","parent_candidate_artifact_manifest_sha256",
 "environment_toolchain_manifest_sha256","manifest_sha256"}
EVAL_REQUIRED={
 "schema_version","receipt_kind","hash_profile","candidate_artifact_manifest_sha256","experiment_manifest_sha256",
 "preregistration_anchor","evaluation_policy_sha256","evaluation_code_sha256","harness_manifest_sha256",
 "provenance_receipt_sha256","contamination_scan_receipt_sha256","red_team_evidence_root_sha256","base_run",
 "candidate_run","domain_metric_summary","efficiency_scope","efficiency_metric_summary","runtime_attempt_authority",
 "final_status","invalid_reason_codes","invalid_reason_set_sha256","failure_reason_codes","failure_reason_set_sha256",
 "truth_boundary","receipt_sha256"}


def is_sha(v:Any)->bool: return isinstance(v,str) and SHA_RE.fullmatch(v) is not None
def norm(s:str)->str: return unicodedata.normalize("NFKC",s).replace("\r\n","\n").replace("\r","\n")

def _canon(v:Any)->Any:
    if isinstance(v,str): return norm(v)
    if v is None or type(v) is bool or type(v) is int: return v
    if isinstance(v,numbers.Number): raise ValueError("direct non-integral numeric forbidden in P2 hash payload")
    if isinstance(v,list): return [_canon(x) for x in v]
    if isinstance(v,dict):
        if any(not isinstance(k,str) or not k or any(ord(c)>=128 for c in k) for k in v):
            raise ValueError("P2 hash object keys must be non-empty ASCII")
        return {k:_canon(v[k]) for k in sorted(v,key=lambda x:x.encode("ascii"))}
    raise ValueError(f"unsupported P2 hash payload type: {type(v).__name__}")

def canonical_bytes(v:Any)->bytes:
    return json.dumps(_canon(v),ensure_ascii=False,sort_keys=False,separators=(",",":"),allow_nan=False).encode()
def canonical_sha(v:Any)->str: return hashlib.sha256(canonical_bytes(v)).hexdigest()
canonical_p2_sha256=canonical_sha
def sha256_file(path:str|Path)->str: return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def self_digest_ok(v:Any,field:str)->bool:
    if not isinstance(v,dict) or v.get("hash_profile")!=HASH_PROFILE or not is_sha(v.get(field)): return False
    try: return canonical_sha({k:x for k,x in v.items() if k!=field})==v[field]
    except ValueError: return False

def _missing(obj:dict, required:set[str], name:str, errors:list[str]):
    miss=sorted(required-set(obj))
    if miss: errors.append(f"{name} missing fields: "+",".join(miss))
def _sha_fields(obj:dict, fields:tuple[str,...], prefix:str, errors:list[str]):
    for f in fields:
        if not is_sha(obj.get(f)): errors.append(f"{prefix}.{f} invalid")

def validate_candidate(m:Any)->list[str]:
    e=[]
    if not isinstance(m,dict): return ["candidate manifest must be an object"]
    _missing(m,CANDIDATE_REQUIRED,"candidate manifest",e)
    if m.get("schema_version")!=1: e.append("candidate manifest schema mismatch")
    if m.get("manifest_kind")!=CANDIDATE_KIND: e.append("candidate manifest kind mismatch")
    if not isinstance(m.get("manifest_id"),str) or not ID_RE.fullmatch(m.get("manifest_id","")): e.append("candidate manifest manifest_id invalid")
    if m.get("hash_profile")!=HASH_PROFILE: e.append("candidate manifest hash_profile mismatch")
    if not self_digest_ok(m,"manifest_sha256"): e.append("candidate manifest self-digest mismatch")
    if m.get("artifact_type") not in ARTIFACT_TYPES: e.append("candidate manifest artifact_type invalid")
    if m.get("artifact_stage") not in ARTIFACT_STAGES: e.append("candidate manifest artifact_stage invalid")
    if m.get("topology_class") not in TOPOLOGIES: e.append("candidate manifest topology_class invalid")
    b=m.get("base")
    if not isinstance(b,dict): e.append("candidate manifest base missing")
    else:
        if not b.get("repo") or not isinstance(b.get("repo"),str): e.append("candidate manifest base.repo invalid")
        if not b.get("revision") or not isinstance(b.get("revision"),str): e.append("candidate manifest base.revision invalid")
        if not is_sha(b.get("base_manifest_sha256")): e.append("candidate manifest base_manifest_sha256 invalid")
    _sha_fields(m,("tokenizer_sha256","config_sha256","parameter_layout_sha256","artifact_file_tree_sha256","environment_toolchain_manifest_sha256"),"candidate manifest",e)
    for f in ("training_shard_manifest_sha256","training_run_receipt_sha256","merge_recipe_sha256","adapter_state_sha256","checkpoint_state_sha256"):
        if m.get(f) is not None and not is_sha(m.get(f)): e.append(f"candidate manifest.{f} invalid")
    parents=m.get("parent_candidate_artifact_manifest_sha256")
    if not isinstance(parents,list) or any(not is_sha(x) for x in parents) or len(set(parents))!=len(parents): e.append("candidate manifest parent identities invalid")
    files=m.get("artifact_files")
    if not isinstance(files,list) or not files: e.append("candidate manifest artifact_files missing")
    else:
        for i,x in enumerate(files):
            if not isinstance(x,dict) or not isinstance(x.get("path"),str) or not x.get("path") or type(x.get("size")) is not int or x.get("size")<0 or not is_sha(x.get("sha256")):
                e.append(f"candidate manifest artifact_files[{i}] invalid")
    return e

def validate_eval(r:Any)->list[str]:
    e=[]
    if not isinstance(r,dict): return ["evaluation receipt must be an object"]
    _missing(r,EVAL_REQUIRED,"evaluation receipt",e)
    if r.get("schema_version")!=1: e.append("evaluation receipt schema mismatch")
    if r.get("receipt_kind")!=EVAL_KIND: e.append("evaluation receipt kind mismatch")
    if r.get("hash_profile")!=HASH_PROFILE: e.append("evaluation receipt hash_profile mismatch")
    if not self_digest_ok(r,"receipt_sha256"): e.append("evaluation receipt self-digest mismatch")
    if r.get("final_status") not in EVAL_STATUS: e.append("evaluation receipt final_status invalid")
    _sha_fields(r,("candidate_artifact_manifest_sha256","experiment_manifest_sha256","evaluation_policy_sha256","evaluation_code_sha256","harness_manifest_sha256","provenance_receipt_sha256","contamination_scan_receipt_sha256","red_team_evidence_root_sha256","invalid_reason_set_sha256","failure_reason_set_sha256"),"evaluation receipt",e)
    for run_name in ("base_run","candidate_run"):
        run=r.get(run_name)
        if not isinstance(run,dict): e.append(f"evaluation receipt {run_name} missing")
        else: _sha_fields(run,("raw_outputs_sha256","run_trace_sha256"),f"evaluation receipt {run_name}",e)
    a=r.get("preregistration_anchor")
    if not isinstance(a,dict): e.append("evaluation receipt preregistration_anchor missing")
    else:
        _sha_fields(a,("anchor_request_sha256","external_evidence_sha256","manager_attestation_sha256","verification_record_sha256"),"evaluation receipt preregistration_anchor",e)
        for f in ("anchor_kind","immutable_reference","manager_authority_id","anchored_at_utc"):
            if not isinstance(a.get(f),str) or not a.get(f): e.append(f"evaluation receipt preregistration_anchor.{f} invalid")
    if not isinstance(r.get("domain_metric_summary"),dict) or not r.get("domain_metric_summary"): e.append("evaluation receipt domain_metric_summary missing")
    if not isinstance(r.get("efficiency_scope"),dict): e.append("evaluation receipt efficiency_scope missing")
    if not isinstance(r.get("efficiency_metric_summary"),dict) or not r.get("efficiency_metric_summary"): e.append("evaluation receipt efficiency_metric_summary missing")
    ra=r.get("runtime_attempt_authority")
    if not isinstance(ra,dict): e.append("evaluation receipt runtime_attempt_authority missing")
    elif ra.get("authoritative_for_arbitrary_runtime_attempts") is not False: e.append("evaluation receipt cannot authorize arbitrary runtime attempts")
    if r.get("truth_boundary")!="PROMOTION_ELIGIBLE_REQUIRES_MANAGER_REVIEW_AND_INDEPENDENT_RERUN": e.append("evaluation receipt truth_boundary mismatch")
    return e

def _policy_errors(p:Any,sha:str)->list[str]:
    e=[]
    if not isinstance(p,dict): return ["merge policy must be an object"]
    if not is_sha(sha): e.append("merge_policy_sha256 invalid")
    b=p.get("base")
    if not isinstance(b,dict) or not isinstance(b.get("repo"),str) or not isinstance(b.get("revision"),str): e.append("merge policy base invalid")
    return e

def _lineage(m:dict)->dict:
    return {"base_repo":m["base"]["repo"],"base_revision":m["base"]["revision"],"base_manifest_sha256":m["base"]["base_manifest_sha256"],"parameter_layout_sha256":m["parameter_layout_sha256"],"topology_class":m["topology_class"]}

def pre_merge_source_admission(*,source_manifests:list[dict],source_evaluation_receipts:list[dict],merge_policy:dict,merge_policy_sha256:str,legacy_p1_evidence:dict|None=None)->dict:
    e=_policy_errors(merge_policy,merge_policy_sha256)
    if not isinstance(source_manifests,list) or len(source_manifests)<2: e.append("pre-merge admission requires at least two source candidate manifests")
    if not isinstance(source_evaluation_receipts,list) or len(source_evaluation_receipts)!=len(source_manifests): e.append("pre-merge admission requires one evaluation receipt per source candidate")
    if e: raise ValueError("; ".join(e))
    pb=merge_policy["base"]; lineage=None; bindings=[]
    for i,(m,r) in enumerate(zip(source_manifests,source_evaluation_receipts)):
        local=validate_candidate(m)+validate_eval(r)
        if local: raise ValueError(f"source[{i}] invalid: "+"; ".join(local))
        if m["artifact_stage"]=="probe_only": raise ValueError(f"source[{i}] probe_only is not merge-admissible")
        if m["base"]["repo"]!=pb["repo"] or m["base"]["revision"]!=pb["revision"]: raise ValueError(f"source[{i}] base lineage does not match merge policy")
        if r["candidate_artifact_manifest_sha256"]!=m["manifest_sha256"]: raise ValueError(f"source[{i}] evaluation receipt candidate binding mismatch")
        if r["final_status"]!="PROMOTION_ELIGIBLE": raise ValueError(f"source[{i}] evaluation status is not PROMOTION_ELIGIBLE")
        cur=_lineage(m)
        if lineage is None: lineage=cur
        elif cur!=lineage: raise ValueError(f"source[{i}] lineage/layout/topology mismatch")
        bindings.append({"candidate_artifact_manifest_sha256":m["manifest_sha256"],"evaluation_decision_receipt_sha256":r["receipt_sha256"]})
    out={"schema_version":1,"receipt_kind":ADMISSION_KIND,"hash_profile":HASH_PROFILE,"merge_policy_sha256":merge_policy_sha256,"source_bindings":bindings,"compatible_lineage":lineage,"decision":"ADMIT_FOR_MERGE_CONSTRUCTION","legacy_p1_booleans_authoritative":False,"truth_boundary":"PRE_MERGE_CONSTRUCTION_ONLY_NOT_PROMOTION_AUTHORITY"}
    out["receipt_sha256"]=canonical_sha(out); return out

def validate_admission(r:Any)->list[str]:
    e=[]
    if not isinstance(r,dict): return ["source admission receipt must be an object"]
    if r.get("schema_version")!=1 or r.get("receipt_kind")!=ADMISSION_KIND: e.append("source admission receipt identity/schema mismatch")
    if r.get("hash_profile")!=HASH_PROFILE: e.append("source admission receipt hash_profile mismatch")
    if not self_digest_ok(r,"receipt_sha256"): e.append("source admission receipt self-digest mismatch")
    if not is_sha(r.get("merge_policy_sha256")): e.append("source admission receipt merge_policy_sha256 invalid")
    b=r.get("source_bindings")
    if not isinstance(b,list) or len(b)<2: e.append("source admission receipt source_bindings invalid")
    elif any(not isinstance(x,dict) or not is_sha(x.get("candidate_artifact_manifest_sha256")) or not is_sha(x.get("evaluation_decision_receipt_sha256")) for x in b): e.append("source admission receipt binding invalid")
    l=r.get("compatible_lineage")
    if not isinstance(l,dict) or any(not isinstance(l.get(f),str) or not l.get(f) for f in ("base_repo","base_revision","topology_class")) or any(not is_sha(l.get(f)) for f in ("base_manifest_sha256","parameter_layout_sha256")): e.append("source admission receipt compatible_lineage invalid")
    if r.get("decision")!="ADMIT_FOR_MERGE_CONSTRUCTION": e.append("source admission receipt decision invalid")
    if r.get("legacy_p1_booleans_authoritative") is not False: e.append("source admission receipt legacy boolean authority violation")
    if r.get("truth_boundary")!="PRE_MERGE_CONSTRUCTION_ONLY_NOT_PROMOTION_AUTHORITY": e.append("source admission receipt truth_boundary mismatch")
    return e

def post_evaluation_merge_promotion(*,source_admission_receipt:dict,source_manifests:list[dict],source_evaluation_receipts:list[dict],merged_candidate_manifest:dict,merged_evaluation_receipt:dict,merge_policy:dict,merge_policy_sha256:str,interference_report_sha256:str,merge_roundtrip_receipt_sha256:str,request_quantized_release:bool=False,quantized_candidate_manifest:dict|None=None,quantized_evaluation_receipt:dict|None=None,legacy_p1_evidence:dict|None=None)->dict:
    e=validate_admission(source_admission_receipt)
    if e: raise ValueError("invalid source admission receipt: "+"; ".join(e))
    expected=pre_merge_source_admission(source_manifests=source_manifests,source_evaluation_receipts=source_evaluation_receipts,merge_policy=merge_policy,merge_policy_sha256=merge_policy_sha256,legacy_p1_evidence=legacy_p1_evidence)
    if expected!=source_admission_receipt: raise ValueError("source admission receipt does not match current source manifests/receipts")
    local=validate_candidate(merged_candidate_manifest)+validate_eval(merged_evaluation_receipt)
    if local: raise ValueError("merged candidate/evaluation invalid: "+"; ".join(local))
    if merged_candidate_manifest["artifact_type"]!="merge": raise ValueError("merged candidate artifact_type must be merge")
    if merged_candidate_manifest["artifact_stage"]=="probe_only": raise ValueError("merged candidate probe_only cannot be promoted")
    if merged_evaluation_receipt["candidate_artifact_manifest_sha256"]!=merged_candidate_manifest["manifest_sha256"]: raise ValueError("merged evaluation receipt candidate binding mismatch")
    if merged_evaluation_receipt["final_status"]!="PROMOTION_ELIGIBLE": raise ValueError("merged candidate evaluation status is not PROMOTION_ELIGIBLE")
    if merged_candidate_manifest.get("merge_recipe_sha256") is None: raise ValueError("merged candidate merge_recipe_sha256 is required")
    ids=[x["candidate_artifact_manifest_sha256"] for x in source_admission_receipt["source_bindings"]]
    if merged_candidate_manifest["parent_candidate_artifact_manifest_sha256"]!=ids: raise ValueError("merged candidate parent manifest list must exactly match admitted source order")
    if _lineage(merged_candidate_manifest)!=source_admission_receipt["compatible_lineage"]: raise ValueError("merged candidate lineage/layout/topology differs from admitted sources")
    if not is_sha(interference_report_sha256): raise ValueError("interference_report_sha256 invalid")
    if not is_sha(merge_roundtrip_receipt_sha256): raise ValueError("merge_roundtrip_receipt_sha256 invalid")
    qbind=None; decision="MERGE_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW"
    if request_quantized_release:
        if quantized_candidate_manifest is None or quantized_evaluation_receipt is None: raise ValueError("quantized release promotion requires quantized candidate manifest and evaluation receipt")
        local=validate_candidate(quantized_candidate_manifest)+validate_eval(quantized_evaluation_receipt)
        if local: raise ValueError("quantized candidate/evaluation invalid: "+"; ".join(local))
        if quantized_candidate_manifest["artifact_type"]!="quantized_serving_artifact": raise ValueError("quantized candidate artifact_type must be quantized_serving_artifact")
        if quantized_candidate_manifest["parent_candidate_artifact_manifest_sha256"]!=[merged_candidate_manifest["manifest_sha256"]]: raise ValueError("quantized candidate must identify the merged candidate as its sole parent")
        if quantized_evaluation_receipt["candidate_artifact_manifest_sha256"]!=quantized_candidate_manifest["manifest_sha256"]: raise ValueError("quantized evaluation receipt candidate binding mismatch")
        if quantized_evaluation_receipt["final_status"]!="PROMOTION_ELIGIBLE": raise ValueError("quantized survival evaluation is not PROMOTION_ELIGIBLE")
        qbind={"candidate_artifact_manifest_sha256":quantized_candidate_manifest["manifest_sha256"],"evaluation_decision_receipt_sha256":quantized_evaluation_receipt["receipt_sha256"]}
        decision="MERGE_AND_QUANTIZED_SURVIVAL_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW"
    out={"schema_version":1,"receipt_kind":PROMOTION_KIND,"hash_profile":HASH_PROFILE,"merge_policy_sha256":merge_policy_sha256,"source_admission_receipt_sha256":source_admission_receipt["receipt_sha256"],"merged_candidate_artifact_manifest_sha256":merged_candidate_manifest["manifest_sha256"],"merged_evaluation_decision_receipt_sha256":merged_evaluation_receipt["receipt_sha256"],"merge_recipe_sha256":merged_candidate_manifest["merge_recipe_sha256"],"interference_report_sha256":interference_report_sha256,"merge_roundtrip_receipt_sha256":merge_roundtrip_receipt_sha256,"quantized_survival_binding":qbind,"decision":decision,"legacy_p1_booleans_authoritative":False,"release_authority":"MANAGER_ONLY","truth_boundary":"P2_MERGE_PROMOTION_IS_NOT_FINAL_RELEASE_APPROVAL"}
    out["receipt_sha256"]=canonical_sha(out); return out

def validate_promotion(r:Any)->list[str]:
    e=[]
    if not isinstance(r,dict): return ["promotion receipt must be an object"]
    if r.get("schema_version")!=1 or r.get("receipt_kind")!=PROMOTION_KIND: e.append("promotion receipt identity/schema mismatch")
    if r.get("hash_profile")!=HASH_PROFILE: e.append("promotion receipt hash_profile mismatch")
    if not self_digest_ok(r,"receipt_sha256"): e.append("promotion receipt self-digest mismatch")
    _sha_fields(r,("merge_policy_sha256","source_admission_receipt_sha256","merged_candidate_artifact_manifest_sha256","merged_evaluation_decision_receipt_sha256","merge_recipe_sha256","interference_report_sha256","merge_roundtrip_receipt_sha256"),"promotion receipt",e)
    q=r.get("quantized_survival_binding")
    if q is not None and (not isinstance(q,dict) or not is_sha(q.get("candidate_artifact_manifest_sha256")) or not is_sha(q.get("evaluation_decision_receipt_sha256"))): e.append("promotion receipt quantized_survival_binding invalid")
    if r.get("decision") not in {"MERGE_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW","MERGE_AND_QUANTIZED_SURVIVAL_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW"}: e.append("promotion receipt decision invalid")
    if r.get("legacy_p1_booleans_authoritative") is not False: e.append("promotion receipt legacy boolean authority violation")
    if r.get("release_authority")!="MANAGER_ONLY": e.append("promotion receipt release authority violation")
    if r.get("truth_boundary")!="P2_MERGE_PROMOTION_IS_NOT_FINAL_RELEASE_APPROVAL": e.append("promotion receipt truth_boundary mismatch")
    return e

# Stable public validator names used by P2.1 integration tests and callers.
validate_candidate_manifest_shared=validate_candidate
validate_evaluation_receipt_shared=validate_eval
validate_source_admission_receipt=validate_admission
validate_promotion_receipt=validate_promotion

def load_json_with_file_sha256(path:str|Path)->tuple[dict,str]:
    path=Path(path); v=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(v,dict): raise ValueError(f"{path}: expected JSON object")
    return v,sha256_file(path)
def _load(path:str|Path)->dict:
    v=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(v,dict): raise ValueError(f"{path}: expected JSON object")
    return v

def main()->None:
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest="cmd",required=True)
    for cmd,arg in (("validate-candidate","manifest"),("validate-evaluation","receipt"),("validate-source-admission","receipt"),("validate-promotion","receipt")):
        q=s.add_parser(cmd); q.add_argument(arg)
    a=p.parse_args(); v=_load(getattr(a,"manifest",None) or a.receipt)
    e={"validate-candidate":validate_candidate,"validate-evaluation":validate_eval,"validate-source-admission":validate_admission,"validate-promotion":validate_promotion}[a.cmd](v)
    if e: raise SystemExit("P2_MERGE_GATE_FAIL\n"+"\n".join(e))
    print("P2_MERGE_GATE_PASS")
if __name__=="__main__": main()
