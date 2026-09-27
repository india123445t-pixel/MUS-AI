#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, tempfile
from pathlib import Path
from typing import Any

AUTH_KIND="AQLEVON_MANAGER_PUBLIC_EVAL_AUTHORIZATION_V1"
CONTROL_CONTRACT="AQLEVON_AUTH08_PUBLIC_EVAL_CONTROL_V1"
RES_KIND="AQLEVON_AUTH08_PUBLIC_EVAL_RESERVATION_V1"
CON_KIND="AQLEVON_AUTH08_PUBLIC_EVAL_CONSUMPTION_V1"
ADAPTER_SHA="5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74"
CANDIDATE_MANIFEST_SHA="e020c6b140ffba104d1fe4485333fb225afd29c52dc03bf9a62d0f8c614e01c5"
GEN_MANIFEST_SHA="25fa2777010255bd8d91431632ba65d72355340086250fe4bce8dffa64e33b0f"
PAIRED_BINDING_SHA="b5f26e20bcdd13cead301623cc5e3496e231b32418a98c895e31db5dfdf9a888"

def now()->str: return dt.datetime.now(dt.timezone.utc).isoformat()
def load(p:Path)->dict[str,Any]:
    d=json.loads(p.read_text())
    if not isinstance(d,dict): raise ValueError("json_not_object")
    return d
def rid(auth_id:str,run_id:str,attempt:str)->str:
    return hashlib.sha256(f"{auth_id}\0{run_id}\0{attempt}".encode()).hexdigest()
def validate_sha(s:str)->None:
    if not re.fullmatch(r"[0-9a-f]{40,64}",s): raise ValueError("invalid_source_sha")
def validate_auth(a:dict[str,Any],expected:str|None)->str:
    aid=str(a.get("authorization_id") or "")
    if not aid: raise ValueError("missing_authorization_id")
    if expected and aid!=expected: raise ValueError("authorization_id_mismatch")
    if a.get("kind")!=AUTH_KIND: raise ValueError("authorization_kind")
    if a.get("control_plane_contract")!=CONTROL_CONTRACT: raise ValueError("control_contract")
    if a.get("fresh_authorization") is not True: raise ValueError("not_fresh")
    if not str(a.get("issued_at_utc") or ""): raise ValueError("missing_issued_at")
    for k in ("single_use","evaluation_authorized","automatic_cleanup_required","artifact_preservation_required","no_main_merge","sealed_eval_forbidden"):
        if a.get(k) is not True: raise ValueError("flag_not_true:"+k)
    if float(a.get("max_total_cost_usd") or 999)>1.50: raise ValueError("per_run_cost_cap")
    if float(a.get("max_hourly_rate_usd") or 999)>1.60: raise ValueError("hourly_rate_cap")
    if int(a.get("max_billed_seconds") or 999999)>3300: raise ValueError("billed_seconds_cap")
    if a.get("adapter_sha256")!=ADAPTER_SHA: raise ValueError("adapter_sha")
    if a.get("candidate_manifest_sha256")!=CANDIDATE_MANIFEST_SHA: raise ValueError("candidate_manifest_sha")
    if a.get("generalization_manifest_sha256")!=GEN_MANIFEST_SHA: raise ValueError("generalization_manifest_sha")
    if a.get("paired_binding_sha256")!=PAIRED_BINDING_SHA: raise ValueError("paired_binding_sha")
    if a.get("sealed_eval_forbidden") is not True: raise ValueError("sealed_eval_must_be_forbidden")
    return aid
def write_exclusive(p:Path,d:dict[str,Any])->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(d,f,indent=2,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
def atomic(p:Path,d:dict[str,Any])->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=p.name+".",dir=str(p.parent))
    try:
        with os.fdopen(fd,"w") as f:
            json.dump(d,f,indent=2,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def reserve(args:argparse.Namespace)->None:
    validate_sha(args.source_sha)
    a=load(args.authorization); aid=validate_auth(a,args.expected_authorization_id)
    if args.reservation.exists() or args.consumed.exists(): raise ValueError("claim_exists")
    reservation_id=rid(aid,args.run_id,args.run_attempt); t=now()
    base={
        "authorization_id":aid,"reservation_id":reservation_id,
        "run_id":str(args.run_id),"run_attempt":str(args.run_attempt),
        "source_sha":args.source_sha,"reserved_at_utc":t,
        "adapter_sha256":ADAPTER_SHA,
        "candidate_manifest_sha256":CANDIDATE_MANIFEST_SHA,
        "generalization_manifest_sha256":GEN_MANIFEST_SHA,
        "paired_binding_sha256":PAIRED_BINDING_SHA,
        "provider_create_attempted":False,"pod_id":None,
    }
    r={**base,"kind":RES_KIND,"state":"RESERVED_BEFORE_PROVIDER_CREATE","single_use_claimed":True}
    c={**base,"kind":CON_KIND,"consumed_at_utc":t,"consumption_state":"CONSUMED_BY_PRECREATE_RESERVATION","single_use_consumed":True}
    write_exclusive(args.reservation,r)
    write_exclusive(args.consumed,c)
    print("AQLEVON_AUTH08_EVAL_PRECREATE_RESERVATION_LOCAL",reservation_id)

def verify(args:argparse.Namespace,require_created:bool=False)->dict[str,Any]:
    validate_sha(args.source_sha)
    a=load(args.authorization); aid=validate_auth(a,args.expected_authorization_id)
    r=load(args.reservation); c=load(args.consumed); expected_rid=rid(aid,args.run_id,args.run_attempt)
    for obj,kind in ((r,RES_KIND),(c,CON_KIND)):
        if obj.get("kind")!=kind: raise ValueError("claim_kind")
        if obj.get("authorization_id")!=aid or obj.get("reservation_id")!=expected_rid: raise ValueError("claim_identity")
        if str(obj.get("run_id"))!=str(args.run_id) or str(obj.get("run_attempt"))!=str(args.run_attempt): raise ValueError("run_identity")
        if obj.get("source_sha")!=args.source_sha: raise ValueError("source_sha")
    if require_created:
        if r.get("state")!="PROVIDER_CREATED" or c.get("consumption_state")!="PROVIDER_CREATED": raise ValueError("provider_not_created")
        if str(r.get("pod_id") or "")!=args.pod_id or str(c.get("pod_id") or "")!=args.pod_id: raise ValueError("pod_id")
    return {"authorization_id":aid,"reservation_id":expected_rid}

def mark_created(args:argparse.Namespace)->None:
    info=verify(args,False); r=load(args.reservation); c=load(args.consumed); t=now()
    for obj in (r,c):
        obj["provider_create_attempted"]=True; obj["provider_created_at_utc"]=t; obj["pod_id"]=args.pod_id
    r["state"]="PROVIDER_CREATED"; c["consumption_state"]="PROVIDER_CREATED"
    atomic(args.reservation,r); atomic(args.consumed,c)
    print("AQLEVON_AUTH08_EVAL_PROVIDER_CREATE_RECORDED",info["reservation_id"])

def common(p:argparse.ArgumentParser)->None:
    p.add_argument("--authorization",type=Path,required=True)
    p.add_argument("--reservation",type=Path,required=True)
    p.add_argument("--consumed",type=Path,required=True)
    p.add_argument("--run-id",required=True); p.add_argument("--run-attempt",required=True)
    p.add_argument("--source-sha",required=True); p.add_argument("--expected-authorization-id")
    p.add_argument("--pod-id",default="")

def main()->int:
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True)
    for name in ("reserve","verify","mark-created"):
        p=sp.add_parser(name); common(p)
    a=ap.parse_args()
    if a.cmd=="reserve": reserve(a)
    elif a.cmd=="verify":
        info=verify(a,bool(a.pod_id)); print("AQLEVON_AUTH08_EVAL_RESERVATION_VERIFIED",info["reservation_id"])
    else: mark_created(a)
    return 0
if __name__=="__main__": raise SystemExit(main())
