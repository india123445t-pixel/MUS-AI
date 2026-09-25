#!/usr/bin/env python3
"""AQLEVON-owned objective reward + sanitized feedback for P4 RLVR/SDPO.

Ground truth is training-visible only.  Feedback never includes expected state,
oracle operations, hidden tests, or sealed-evaluation material.
"""
from __future__ import annotations
import copy, json, re, unicodedata
from typing import Any

ALLOWED_REASONS={"objective_state_match","invalid_json","program_must_be_nonempty_list","invalid_program_step","unknown_op","execution_error","final_state_mismatch","side_effect_mismatch"}

def _execute(program:Any,initial:dict[str,Any])->tuple[dict[str,Any],list[str]]:
    if not isinstance(program,list) or not program: raise ValueError("program_must_be_nonempty_list")
    s=copy.deepcopy(initial); touched=[]
    def get(k):
        if k not in s: raise ValueError("execution_error")
        return s[k]
    for st in program:
        if not isinstance(st,dict) or not isinstance(st.get("op"),str): raise ValueError("invalid_program_step")
        op=st["op"]
        try:
            if op=="set": k=st["key"]; s[k]=copy.deepcopy(st.get("value")); touched.append(k)
            elif op=="delete": k=st["key"]; s.pop(k,None); touched.append(k)
            elif op=="increment": k=st["key"]; s[k]=get(k)+st["by"]; touched.append(k)
            elif op=="rename": src,dst=st["from"],st["to"]; s[dst]=get(src); del s[src]; touched.extend([src,dst])
            elif op=="append_unique": k=st["key"]; v=st["value"]; cur=get(k); cur.append(v) if v not in cur else None; touched.append(k)
            elif op=="sort_list": k=st["key"]; s[k]=sorted(get(k)); touched.append(k)
            elif op=="normalize_ws": k=st["key"]; s[k]=" ".join(get(k).split()); touched.append(k)
            elif op=="slugify": k=st["key"]; txt=unicodedata.normalize("NFKC",get(k)).strip().lower(); s[k]=re.sub(r"[^a-z0-9]+","-",txt).strip("-"); touched.append(k)
            elif op=="map_add": k=st["key"]; s[k]=[x+st["by"] for x in get(k)]; touched.append(k)
            elif op=="filter_ge": k=st["key"]; s[k]=[x for x in get(k) if x>=st["min"]]; touched.append(k)
            elif op=="toggle_bool": k=st["key"]; s[k]=not get(k); touched.append(k)
            elif op=="dedupe_list":
                k=st["key"]; seen=[]; s[k]=[x for x in get(k) if not (x in seen or seen.append(x))]; touched.append(k)
            elif op=="replace_text": k=st["key"]; s[k]=get(k).replace(st["old"],st["new"]); touched.append(k)
            elif op=="dict_put": k=st["key"]; sub=st["subkey"]; cur=get(k); cur[sub]=copy.deepcopy(st.get("value")); touched.append(f"{k}.{sub}")
            elif op=="move_item":
                src,dst,val=st["from"],st["to"],st["value"]; a=get(src); b=get(dst); a.remove(val); b.append(val); touched.extend([src,dst])
            else: raise ValueError("unknown_op")
        except (KeyError,TypeError,ValueError) as exc:
            if isinstance(exc,ValueError) and str(exc) in ALLOWED_REASONS: raise
            raise ValueError("execution_error") from exc
    return s,sorted(set(touched))

def _parse_solution(text:str)->Any:
    t=text.strip()
    if t.startswith("```"):
        t=re.sub(r"^```(?:json)?\s*","",t,flags=re.I); t=re.sub(r"\s*```$","",t)
    return json.loads(t)

def compute_score(data_source=None, solution_str=None, ground_truth=None, extra_info=None, **kwargs):
    solution_str = solution_str if solution_str is not None else kwargs.get("solution") or ""
    gt = ground_truth
    if isinstance(gt,str):
        try: gt=json.loads(gt)
        except json.JSONDecodeError: gt=None
    if not isinstance(gt,dict) or set(gt)!={"initial_state","oracle_program"}:
        return {"score":0.0,"acc":0.0,"pred":"","incorrect_format":1,"feedback":"execution_error"}
    try:
        expected,expected_touched=_execute(gt["oracle_program"],gt["initial_state"])
        try: program=_parse_solution(str(solution_str))
        except Exception: raise ValueError("invalid_json")
        actual,actual_touched=_execute(program,gt["initial_state"])
        if actual!=expected: reason="final_state_mismatch"; ok=False
        elif actual_touched!=expected_touched: reason="side_effect_mismatch"; ok=False
        else: reason="objective_state_match"; ok=True
    except ValueError as exc:
        reason=str(exc) if str(exc) in ALLOWED_REASONS else "execution_error"; ok=False
    return {"score":1.0 if ok else 0.0,"acc":1.0 if ok else 0.0,"pred":"VALID_DSL_PROGRAM" if ok else "INVALID_OR_INCORRECT_DSL_PROGRAM","incorrect_format":0 if reason not in {"invalid_json","program_must_be_nonempty_list","invalid_program_step"} else 1,"feedback":"" if ok else reason}
