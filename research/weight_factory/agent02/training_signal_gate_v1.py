#!/usr/bin/env python3
"""AQLEVON Worker 02 — fail-closed instance-level training signal admission gate."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Iterable

ADMIT="ADMIT"; QUARANTINE="QUARANTINE"; DENY="DENY"
_SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
_ROW_DOMAIN="AQLEVON_TRAINING_ROW_CONTENT_V1"

@dataclass
class Decision:
    decision: str
    reasons: list[str]
    metrics: dict[str, Any]

def sha256_text(text:str)->str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _is_int(v:Any)->bool: return type(v) is int
def _is_number(v:Any)->bool: return type(v) in (int,float)
def _valid_sha256(v:Any)->bool: return isinstance(v,str) and _SHA256_RE.fullmatch(v) is not None
def _str_list(v:Any, nonempty:bool=False)->bool:
    return isinstance(v,list) and (bool(v) or not nonempty) and all(isinstance(x,str) and x for x in v) and len(v)==len(set(v))

def _canon(v:Any)->Any:
    if isinstance(v,str):
        return unicodedata.normalize("NFKC",v).replace("\r\n","\n").replace("\r","\n")
    if v is None or type(v) in (bool,int,float): return v
    if isinstance(v,list): return [_canon(x) for x in v]
    if isinstance(v,dict):
        if not all(isinstance(k,str) for k in v): raise TypeError("non_string_key")
        return {k:_canon(v[k]) for k in sorted(v)}
    raise TypeError(f"unsupported:{type(v).__name__}")

def canonical_json_bytes(v:Any)->bytes:
    return json.dumps(_canon(v),ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def record_content_payload(record:dict[str,Any])->dict[str,Any]:
    if not isinstance(record,dict): raise TypeError("record")
    if not isinstance(record.get("record_id"),str) or not record["record_id"]: raise ValueError("record_id")
    if not isinstance(record.get("prompt"),str): raise ValueError("prompt")
    if "answer" in record: answer=record["answer"]
    elif "response" in record: answer=record["response"]
    else: raise KeyError("answer_or_response")
    return {"domain":_ROW_DOMAIN,"record_id":record["record_id"],"prompt":record["prompt"],"answer":answer}

def record_content_sha256(record:dict[str,Any])->str:
    return hashlib.sha256(canonical_json_bytes(record_content_payload(record))).hexdigest()

def source_registry_sha256(registry:dict[str,Any])->str:
    return hashlib.sha256(canonical_json_bytes(registry)).hexdigest()

def _norm_overlap(text:str)->str:
    return " ".join(unicodedata.normalize("NFKC",text).casefold().split())

def content_text(record:dict[str,Any])->str:
    a=record.get("answer",record.get("response",""))
    if not isinstance(a,str): a=json.dumps(a,ensure_ascii=False,sort_keys=True,allow_nan=False)
    return f"{record.get('prompt','')}\n{a}".strip()

def ngram_hashes(text:str,n:int)->set[str]:
    if not _is_int(n) or n<=0: raise ValueError("ngram_size")
    toks=_norm_overlap(text).split()
    if len(toks)<n: return set()
    return {sha256_text(" ".join(toks[i:i+n])) for i in range(len(toks)-n+1)}

def build_protected_manifest(texts:Iterable[str],ngram_size:int,manifest_id:str)->dict[str,Any]:
    if not _is_int(ngram_size) or ngram_size<=0: raise ValueError("ngram_size")
    if not isinstance(manifest_id,str) or not manifest_id.strip(): raise ValueError("manifest_id")
    ng=set(); short=set(); count=0
    for text in texts:
        if not isinstance(text,str): raise TypeError("protected_text")
        norm=_norm_overlap(text)
        if not norm: continue
        count+=1; toks=norm.split()
        if len(toks)<ngram_size: short.add(sha256_text(norm))
        else: ng.update(ngram_hashes(norm,ngram_size))
    payload={"schema_version":1,"manifest_id":manifest_id,"ngram_size":ngram_size,"record_count":count,
             "ngram_hashes":sorted(ng),"short_hashes":sorted(short)}
    payload["manifest_sha256"]=hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return payload

def validate_manifest(m:Any)->tuple[bool,str]:
    if not isinstance(m,dict): return False,"protected_manifest_not_object"
    req={"schema_version","manifest_id","ngram_size","record_count","ngram_hashes","short_hashes","manifest_sha256"}
    miss=req-set(m)
    if miss: return False,"protected_manifest_missing:"+",".join(sorted(miss))
    if not _is_int(m["schema_version"]) or m["schema_version"]!=1: return False,"protected_manifest_invalid_schema_version"
    if not isinstance(m["manifest_id"],str) or not m["manifest_id"].strip(): return False,"protected_manifest_invalid_id"
    if not _is_int(m["ngram_size"]) or m["ngram_size"]<=0: return False,"protected_manifest_invalid_ngram_size"
    if not _is_int(m["record_count"]) or m["record_count"]<0: return False,"protected_manifest_invalid_record_count"
    for k in ("ngram_hashes","short_hashes"):
        vals=m[k]
        if not isinstance(vals,list): return False,f"protected_manifest_invalid_{k}_type"
        if not all(_valid_sha256(x) for x in vals): return False,f"protected_manifest_invalid_{k}_digest"
        if len(vals)!=len(set(vals)): return False,f"protected_manifest_duplicate_{k}"
    if not _valid_sha256(m["manifest_sha256"]): return False,"protected_manifest_invalid_manifest_sha256"
    try: expected=hashlib.sha256(canonical_json_bytes({k:m[k] for k in m if k!="manifest_sha256"})).hexdigest()
    except (TypeError,ValueError): return False,"protected_manifest_uncanonicalizable"
    if expected!=m["manifest_sha256"]: return False,"protected_manifest_digest_mismatch"
    return True,"ok"

def validate_registry(r:Any)->tuple[bool,str]:
    if not isinstance(r,dict): return False,"source_registry_not_object"
    if not _is_int(r.get("schema_version")) or r["schema_version"]<=0: return False,"source_registry_invalid_schema_version"
    if r.get("policy")!="default_deny": return False,"source_registry_not_default_deny"
    if not isinstance(r.get("sources"),list): return False,"source_registry_sources_not_list"
    ids=set()
    for i,e in enumerate(r["sources"]):
        if not isinstance(e,dict): return False,f"source_registry_entry_{i}_not_object"
        if not isinstance(e.get("id"),str) or not e["id"]: return False,f"source_registry_entry_{i}_invalid_id"
        if e["id"] in ids: return False,"source_registry_duplicate_id"
        ids.add(e["id"])
        if not isinstance(e.get("kind"),str) or not e["kind"]: return False,f"source_registry_entry_{i}_invalid_kind"
        if not isinstance(e.get("admission"),str) or not e["admission"]: return False,f"source_registry_entry_{i}_invalid_admission"
    try: source_registry_sha256(r)
    except (TypeError,ValueError): return False,"source_registry_uncanonicalizable"
    return True,"ok"

def validate_policy(p:Any)->tuple[bool,str]:
    if not isinstance(p,dict): return False,"policy_not_object"
    if not _is_int(p.get("schema_version")) or p["schema_version"]<=0: return False,"policy_invalid_schema_version"
    if p.get("default_decision")!=DENY: return False,"policy_must_default_deny"
    keys=("trainable_source_kinds","recipe_only_source_kinds","trainable_source_admissions",
          "allowed_license_statuses","allowed_provenance_statuses","hard_verifier_types")
    for k in keys:
        if not _str_list(p.get(k),True): return False,f"policy_invalid_{k}"
    if set(p["trainable_source_kinds"]) & set(p["recipe_only_source_kinds"]): return False,"policy_source_kind_overlap"
    if "recipe_allow" in p["trainable_source_admissions"]: return False,"policy_recipe_allow_cannot_train_rows"
    v=p.get("verifier")
    if not isinstance(v,dict) or not _is_int(v.get("min_hard_verifier_passes")) or v["min_hard_verifier_passes"]<=0:
        return False,"policy_invalid_verifier"
    c=p.get("contamination")
    if not isinstance(c,dict): return False,"policy_invalid_contamination"
    if not _is_int(c.get("protected_ngram_size")) or c["protected_ngram_size"]<=0: return False,"policy_invalid_protected_ngram_size"
    if not _is_number(c.get("max_semantic_duplicate_score")) or not 0<=float(c["max_semantic_duplicate_score"])<=1:
        return False,"policy_invalid_max_semantic_duplicate_score"
    l=p.get("learnability")
    if not isinstance(l,dict) or l.get("mode")!="research_heuristic": return False,"policy_invalid_learnability"
    if not _is_int(l.get("min_attempts")) or l["min_attempts"]<=0: return False,"policy_invalid_min_attempts"
    lo=l.get("min_student_success_rate"); hi=l.get("max_student_success_rate")
    if not _is_number(lo) or not _is_number(hi) or not 0<=float(lo)<=float(hi)<=1: return False,"policy_invalid_learning_band"
    q=p.get("language_quality")
    if not isinstance(q,dict) or not _str_list(q.get("lanes_requiring_audit")): return False,"policy_invalid_language_quality"
    return True,"ok"

def protected_overlap(text:str,m:dict[str,Any])->dict[str,Any]:
    ok,reason=validate_manifest(m)
    if not ok: raise ValueError(reason)
    n=m["ngram_size"]; norm=_norm_overlap(text); toks=norm.split()
    if not norm: return {"matched":False,"match_count":0,"candidate_unit_count":0}
    if len(toks)<n:
        hit=sha256_text(norm) in set(m["short_hashes"])
        return {"matched":hit,"match_count":int(hit),"candidate_unit_count":1}
    units=ngram_hashes(norm,n); hits=units & set(m["ngram_hashes"])
    return {"matched":bool(hits),"match_count":len(hits),"candidate_unit_count":len(units)}

def _missing(r:dict[str,Any],path:tuple[str,...])->bool:
    cur:Any=r
    for k in path:
        if not isinstance(cur,dict) or k not in cur: return True
        cur=cur[k]
    return cur is None or cur==""

def _deny(reason:str,metrics:dict[str,Any]|None=None)->Decision:
    return Decision(DENY,[reason],metrics or {})

def assess_record(record:Any, policy:Any, manifest:Any, registry:Any)->Decision:
    metrics={}
    ok,reason=validate_policy(policy)
    if not ok: return _deny(reason)
    ok,reason=validate_manifest(manifest)
    if not ok: return _deny(reason)
    ok,reason=validate_registry(registry)
    if not ok: return _deny(reason)
    if manifest["ngram_size"]!=policy["contamination"]["protected_ngram_size"]:
        return _deny("protected_manifest_policy_ngram_mismatch")
    if not isinstance(record,dict): return _deny("record_not_object")
    paths=[("record_id",),("prompt",),("record_content_sha256",),("source","id"),("source","revision"),
           ("source","immutable_revision"),("source","content_sha256"),("source","registry_sha256"),
           ("source","kind"),("source","admission"),("source","license_status"),("source","provenance_status"),
           ("dedup","is_canonical"),("dedup","semantic_duplicate_score"),("contamination","holdout_scan_completed"),
           ("contamination","protected_eval_hits"),("baseline","attempts"),("baseline","successes"),("verifiers",)]
    missing=[".".join(p) for p in paths if _missing(record,p)]
    if "answer" not in record and "response" not in record: missing.append("answer_or_response")
    if missing: return _deny("missing_required:"+",".join(missing))
    source=record.get("source"); dedup=record.get("dedup"); cont=record.get("contamination"); baseline=record.get("baseline")
    if not all(isinstance(x,dict) for x in (source,dedup,cont,baseline)): return _deny("record_schema_type_error")

    if not _valid_sha256(record.get("record_content_sha256")): return _deny("invalid_record_content_sha256")
    try: expected=record_content_sha256(record)
    except (TypeError,ValueError,KeyError): return _deny("record_content_uncanonicalizable")
    if record["record_content_sha256"]!=expected: return _deny("record_content_sha256_mismatch")
    metrics["record_content_sha256_verified"]=True

    if source.get("immutable_revision") is not True: return _deny("source_revision_not_immutable")
    if not _valid_sha256(source.get("content_sha256")): return _deny("invalid_source_content_sha256")
    if not _valid_sha256(source.get("registry_sha256")): return _deny("invalid_source_registry_sha256")
    try: reg_sha=source_registry_sha256(registry)
    except (TypeError,ValueError): return _deny("source_registry_uncanonicalizable")
    if source["registry_sha256"]!=reg_sha: return _deny("source_registry_sha256_mismatch")
    entries={e["id"]:e for e in registry["sources"]}; entry=entries.get(source.get("id"))
    if entry is None: return _deny("source_not_in_trusted_registry")
    if source.get("kind")!=entry.get("kind"): return _deny("source_kind_registry_mismatch")
    if source.get("admission")!=entry.get("admission"): return _deny("source_admission_registry_mismatch")
    kind=entry["kind"]; admission=entry["admission"]
    if kind in set(policy["recipe_only_source_kinds"]): return _deny("recipe_only_source_kind_not_trainable")
    if kind not in set(policy["trainable_source_kinds"]): return _deny("source_kind_not_trainable")
    if admission=="recipe_allow": return _deny("recipe_allow_not_trainable_data_admission")
    if admission not in set(policy["trainable_source_admissions"]): return _deny("source_admission_not_trainable")
    if source.get("license_status") not in set(policy["allowed_license_statuses"]): return _deny("license_not_cleared")
    if source.get("provenance_status") not in set(policy["allowed_provenance_statuses"]): return _deny("provenance_not_cleared")
    metrics["source_registry_sha256"]=reg_sha; metrics["source_kind"]=kind

    if record.get("protected_eval") is True: return _deny("protected_eval_record",metrics)
    if cont.get("holdout_scan_completed") is not True: return _deny("holdout_scan_not_completed",metrics)
    hits=cont.get("protected_eval_hits")
    if not _is_int(hits) or hits<0: return _deny("invalid_protected_eval_hits",metrics)
    if hits: return _deny("protected_eval_hit",metrics)
    try: overlap=protected_overlap(content_text(record),manifest)
    except (TypeError,ValueError): return _deny("protected_overlap_evaluation_error",metrics)
    metrics["protected_overlap"]=overlap
    if overlap["matched"]: return _deny("protected_manifest_overlap",metrics)

    if dedup.get("is_canonical") is not True: return Decision(QUARANTINE,["noncanonical_duplicate"],metrics)
    sem=dedup.get("semantic_duplicate_score")
    if not _is_number(sem) or not 0<=float(sem)<=1: return _deny("invalid_semantic_duplicate_score",metrics)
    metrics["semantic_duplicate_score"]=float(sem)
    if float(sem)>float(policy["contamination"]["max_semantic_duplicate_score"]):
        return Decision(QUARANTINE,["semantic_near_duplicate"],metrics)

    verifiers=record.get("verifiers")
    if not isinstance(verifiers,list) or not verifiers: return Decision(QUARANTINE,["missing_verifier_evidence"],metrics)
    hard=set(policy["hard_verifier_types"]); passes=0; vreasons=[]
    for i,v in enumerate(verifiers):
        if not isinstance(v,dict): vreasons.append(f"verifier_{i}_malformed"); continue
        typ=v.get("type")
        if not isinstance(typ,str): vreasons.append(f"verifier_{i}_invalid_type"); continue
        if v.get("passed") is False: vreasons.append(f"verifier_{i}_failed")
        elif v.get("passed") is not True: vreasons.append(f"verifier_{i}_invalid_passed")
        if typ in hard and v.get("passed") is True:
            if not _str_list(v.get("target_failure_modes"),True): vreasons.append(f"verifier_{i}_missing_failure_modes")
            elif v.get("fault_injection_passed") is not True: vreasons.append(f"verifier_{i}_not_fault_tested")
            elif v.get("independent_observation") is not True: vreasons.append(f"verifier_{i}_not_independent_observation")
            else: passes+=1
    metrics["hard_verifier_passes"]=passes
    if vreasons: return Decision(QUARANTINE,vreasons,metrics)
    if passes<policy["verifier"]["min_hard_verifier_passes"]: return Decision(QUARANTINE,["no_qualified_hard_verifier"],metrics)

    attempts=baseline.get("attempts"); successes=baseline.get("successes")
    if not _is_int(attempts) or not _is_int(successes): return _deny("invalid_baseline_count_types",metrics)
    if attempts<=0 or successes<0 or successes>attempts: return _deny("invalid_baseline_counts",metrics)
    if attempts<policy["learnability"]["min_attempts"]: return Decision(QUARANTINE,["insufficient_baseline_attempts"],metrics)
    rate=successes/attempts; metrics["student_success_rate"]=rate
    lo=float(policy["learnability"]["min_student_success_rate"]); hi=float(policy["learnability"]["max_student_success_rate"])
    if rate<lo: return Decision(QUARANTINE,["too_hard_or_unstable_for_current_stage"],metrics)
    if rate>hi: return Decision(QUARANTINE,["already_mastered_low_information_gain"],metrics)

    lane=record.get("language_lane","other")
    if not isinstance(lane,str): return _deny("invalid_language_lane",metrics)
    if record.get("synthetic") is True and lane in set(policy["language_quality"]["lanes_requiring_audit"]):
        audit=record.get("language_quality_audit")
        if not isinstance(audit,dict) or audit.get("passed") is not True or not isinstance(audit.get("auditor_class"),str) or not audit["auditor_class"]:
            return Decision(QUARANTINE,["language_quality_audit_required"],metrics)
    return Decision(ADMIT,["all_required_gates_passed"],metrics)

def _load_json(path:pathlib.Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def _load_jsonl(path:pathlib.Path)->list[dict[str,Any]]:
    rows=[]
    for i,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        value=json.loads(line)
        if not isinstance(value,dict): raise ValueError(f"JSONL line {i} must be object")
        rows.append(value)
    return rows
def _write_jsonl(path:pathlib.Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n")

def cmd_build_manifest(a:argparse.Namespace)->int:
    try:
        rows=_load_jsonl(a.input); texts=[]
        for r in rows:
            parts=[]
            for field in a.text_fields:
                v=r.get(field,"")
                if not isinstance(v,str): v=json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)
                parts.append(v)
            texts.append("\n".join(parts))
        m=build_protected_manifest(texts,a.ngram_size,a.manifest_id)
        a.output.write_text(json.dumps(m,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    except (OSError,json.JSONDecodeError,TypeError,ValueError) as e:
        print(json.dumps({"status":DENY,"reason":f"manifest_build_error:{type(e).__name__}"})); return 2
    print(json.dumps({"manifest_id":m["manifest_id"],"records":m["record_count"],"sha256":m["manifest_sha256"]})); return 0

def cmd_gate(a:argparse.Namespace)->int:
    try: rows=_load_jsonl(a.input)
    except (OSError,json.JSONDecodeError,TypeError,ValueError) as e:
        print(json.dumps({"status":DENY,"reason":f"input_parse_error:{type(e).__name__}"})); return 2
    try:
        policy=_load_json(a.policy); manifest=_load_json(a.protected_manifest); registry=_load_json(a.source_registry); config_error=None
    except (OSError,json.JSONDecodeError,TypeError,ValueError) as e:
        policy=manifest=registry={}; config_error=f"config_parse_error:{type(e).__name__}"
    buckets={ADMIT:[],QUARANTINE:[],DENY:[]}
    for r in rows:
        d=_deny(config_error) if config_error else assess_record(r,policy,manifest,registry)
        out=dict(r); out["training_signal_decision"]=asdict(d); buckets[d.decision].append(out)
    try:
        _write_jsonl(a.admitted,buckets[ADMIT]); _write_jsonl(a.quarantine,buckets[QUARANTINE]); _write_jsonl(a.denied,buckets[DENY])
    except (OSError,TypeError,ValueError) as e:
        print(json.dumps({"status":DENY,"reason":f"output_write_error:{type(e).__name__}"})); return 2
    print(json.dumps({"admit":len(buckets[ADMIT]),"quarantine":len(buckets[QUARANTINE]),"deny":len(buckets[DENY]),"configuration_error":config_error},sort_keys=True))
    return 2 if config_error else 0

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="command",required=True)
    m=sub.add_parser("build-protected-manifest"); m.add_argument("--input",type=pathlib.Path,required=True); m.add_argument("--output",type=pathlib.Path,required=True)
    m.add_argument("--manifest-id",required=True); m.add_argument("--ngram-size",type=int,default=8); m.add_argument("--text-fields",nargs="+",default=["prompt","answer"]); m.set_defaults(func=cmd_build_manifest)
    g=sub.add_parser("gate"); g.add_argument("--policy",type=pathlib.Path,required=True); g.add_argument("--protected-manifest",type=pathlib.Path,required=True)
    g.add_argument("--source-registry",type=pathlib.Path,required=True); g.add_argument("--input",type=pathlib.Path,required=True); g.add_argument("--admitted",type=pathlib.Path,required=True)
    g.add_argument("--quarantine",type=pathlib.Path,required=True); g.add_argument("--denied",type=pathlib.Path,required=True); g.set_defaults(func=cmd_gate)
    return p
def main()->int:
    a=build_parser().parse_args(); return int(a.func(a))
if __name__=="__main__": raise SystemExit(main())
