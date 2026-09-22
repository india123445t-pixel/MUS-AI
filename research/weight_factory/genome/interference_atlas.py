#!/usr/bin/env python3
"""AQLEVON Interference Atlas V1.

Compare two same-lineage task-delta safetensors without loading an entire model.
This is a diagnostic gate, not a merge algorithm.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import torch
from safetensors import safe_open


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    a=a.float().reshape(-1); b=b.float().reshape(-1)
    na=torch.linalg.vector_norm(a); nb=torch.linalg.vector_norm(b)
    if na.item()==0 or nb.item()==0: return 0.0
    return float(torch.dot(a,b)/(na*nb))


def tensor_metrics(a: torch.Tensor,b: torch.Tensor,eps: float)->dict:
    if a.shape!=b.shape: raise ValueError(f"shape mismatch {tuple(a.shape)} != {tuple(b.shape)}")
    af=a.float().reshape(-1); bf=b.float().reshape(-1)
    am=af.abs()>eps; bm=bf.abs()>eps; both=am & bm
    union=am | bm
    overlap=float(both.sum().item()/max(1,union.sum().item()))
    sign_conflict=float(((af[both]*bf[both])<0).sum().item()/max(1,both.sum().item())) if both.any() else 0.0
    na=float(torch.linalg.vector_norm(af)); nb=float(torch.linalg.vector_norm(bf))
    c=cosine(af,bf)
    # Diagnostic only: high when directions oppose and when both touch same coordinates.
    directional_risk=max(0.0,-c)*overlap
    return {
        "numel":af.numel(),"cosine":c,"support_overlap":overlap,
        "sign_conflict":sign_conflict,"left_norm":na,"right_norm":nb,
        "norm_ratio": (max(na,nb)/max(1e-30,min(na,nb))) if na and nb else None,
        "directional_risk":directional_risk,
    }


def group_name(key:str)->str:
    parts=key.split('.')
    for i,p in enumerate(parts):
        if p.isdigit(): return '.'.join(parts[:i+1])
    return '.'.join(parts[:-1]) if len(parts)>1 else key


def analyze(left:Path,right:Path,eps:float)->dict:
    rows=[]; missing=[]
    with safe_open(str(left),framework="pt",device="cpu") as lf, safe_open(str(right),framework="pt",device="cpu") as rf:
        lk=set(lf.keys()); rk=set(rf.keys())
        for k in sorted(lk^rk): missing.append(k)
        for k in sorted(lk&rk):
            m=tensor_metrics(lf.get_tensor(k),rf.get_tensor(k),eps)
            m["tensor"]=k; m["group"]=group_name(k); rows.append(m)
    total=sum(r["numel"] for r in rows) or 1
    weighted=lambda field: sum(r[field]*r["numel"] for r in rows)/total
    groups={}
    for r in rows:
        g=groups.setdefault(r["group"],{"numel":0,"cosine_num":0.0,"overlap_num":0.0,"sign_num":0.0,"risk_num":0.0})
        n=r["numel"]; g["numel"]+=n; g["cosine_num"]+=r["cosine"]*n; g["overlap_num"]+=r["support_overlap"]*n; g["sign_num"]+=r["sign_conflict"]*n; g["risk_num"]+=r["directional_risk"]*n
    group_rows=[]
    for name,g in groups.items():
        n=max(1,g["numel"])
        group_rows.append({"group":name,"numel":g["numel"],"cosine":g["cosine_num"]/n,"support_overlap":g["overlap_num"]/n,"sign_conflict":g["sign_num"]/n,"directional_risk":g["risk_num"]/n})
    group_rows.sort(key=lambda x:x["directional_risk"],reverse=True)
    return {
        "schema_version":1,"left":str(left),"right":str(right),"epsilon":eps,
        "compatible_keyset":not missing,"missing_or_extra_keys":missing,
        "summary":{"tensor_count":len(rows),"numel":total,"weighted_cosine":weighted("cosine"),"weighted_support_overlap":weighted("support_overlap"),"weighted_sign_conflict":weighted("sign_conflict"),"weighted_directional_risk":weighted("directional_risk")},
        "highest_risk_groups":group_rows[:50],"tensors":rows,
        "interpretation":"Diagnostic only. Negative orientation with overlapping support is a merge-risk signal; behavioral evaluation remains mandatory."
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("left",type=Path); ap.add_argument("right",type=Path)
    ap.add_argument("--epsilon",type=float,default=1e-8); ap.add_argument("--output",type=Path)
    args=ap.parse_args(); report=analyze(args.left,args.right,args.epsilon)
    text=json.dumps(report,indent=2,sort_keys=True)
    if args.output: args.output.write_text(text+"\n",encoding="utf-8")
    else: print(text)
    if not report["compatible_keyset"]: raise SystemExit(2)

if __name__=="__main__": main()