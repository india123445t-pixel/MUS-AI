#!/usr/bin/env python3
"""AQLEVON Agent 04 public generalization challenge V1.

Public, non-protected, deterministic CPU-only challenge generator/verifier.
It intentionally differs from the 27B training/eval template:
- every task requires 2-3 dependent tool operations (training/eval used one);
- prompts use a contract + state snapshot layout rather than W02's template;
- keys/scenarios are unrelated to trXX/eval core naming;
- verification is semantic and side-effect constrained;
- no sealed/private material is used.
"""
from __future__ import annotations
import copy, hashlib, json, re, unicodedata
from typing import Any

PACK_KIND = "AQLEVON_27B_PUBLIC_GENERALIZATION_CHALLENGE_V1"
HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
PUBLIC_SEED = 27092026
ALLOWED_OPS = (
    "increment","rename","append_unique","sort_list","delete","normalize_ws","slugify",
    "map_add","filter_ge","toggle_bool","dedupe_list","replace_text","dict_put","move_item",
)

class ChallengeError(ValueError):
    pass

def canonical_bytes(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def sha256_obj(v: Any) -> str:
    return hashlib.sha256(canonical_bytes(v)).hexdigest()

def _execute(program: Any, initial: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(program, list) or not program:
        raise ChallengeError("program_must_be_nonempty_list")
    state=copy.deepcopy(initial)
    touched=[]
    for step in program:
        if not isinstance(step, dict) or not isinstance(step.get("op"), str):
            raise ChallengeError("invalid_step")
        op=step["op"]
        if op not in ALLOWED_OPS:
            raise ChallengeError("op_not_allowed")
        key=step.get("key")
        if op not in {"rename","move_item"} and (not isinstance(key,str) or not key):
            raise ChallengeError(f"{op}_requires_key")
        if op=="increment":
            by=step.get("by")
            if type(by) is not int or type(state.get(key)) is not int: raise ChallengeError("increment_type_error")
            state[key]+=by; touched.append(key)
        elif op=="rename":
            src,dst=step.get("from"),step.get("to")
            if not isinstance(src,str) or not isinstance(dst,str) or not src or not dst or src==dst: raise ChallengeError("rename_invalid")
            if src not in state or dst in state: raise ChallengeError("rename_state_error")
            state[dst]=state.pop(src); touched += [src,dst]
        elif op=="append_unique":
            cur=state.get(key)
            if not isinstance(cur,list): raise ChallengeError("append_unique_type_error")
            val=copy.deepcopy(step.get("value"))
            if val not in cur: cur.append(val)
            touched.append(key)
        elif op=="sort_list":
            cur=state.get(key)
            if not isinstance(cur,list): raise ChallengeError("sort_list_type_error")
            state[key]=sorted(cur); touched.append(key)
        elif op=="delete":
            state.pop(key,None); touched.append(key)
        elif op=="normalize_ws":
            cur=state.get(key)
            if not isinstance(cur,str): raise ChallengeError("normalize_ws_type_error")
            state[key]=" ".join(cur.split()); touched.append(key)
        elif op=="slugify":
            cur=state.get(key)
            if not isinstance(cur,str): raise ChallengeError("slugify_type_error")
            s=unicodedata.normalize("NFKC",cur).strip().lower()
            state[key]=re.sub(r"[^a-z0-9]+","-",s).strip("-"); touched.append(key)
        elif op=="map_add":
            cur,by=state.get(key),step.get("by")
            if not isinstance(cur,list) or not all(type(x) is int for x in cur) or type(by) is not int: raise ChallengeError("map_add_type_error")
            state[key]=[x+by for x in cur]; touched.append(key)
        elif op=="filter_ge":
            cur,mn=state.get(key),step.get("min")
            if not isinstance(cur,list) or not all(type(x) is int for x in cur) or type(mn) is not int: raise ChallengeError("filter_ge_type_error")
            state[key]=[x for x in cur if x>=mn]; touched.append(key)
        elif op=="toggle_bool":
            cur=state.get(key)
            if type(cur) is not bool: raise ChallengeError("toggle_bool_type_error")
            state[key]=not cur; touched.append(key)
        elif op=="dedupe_list":
            cur=state.get(key)
            if not isinstance(cur,list): raise ChallengeError("dedupe_list_type_error")
            out=[]
            for x in cur:
                if x not in out: out.append(x)
            state[key]=out; touched.append(key)
        elif op=="replace_text":
            cur,old,new=state.get(key),step.get("old"),step.get("new")
            if not isinstance(cur,str) or not isinstance(old,str) or not isinstance(new,str): raise ChallengeError("replace_text_type_error")
            state[key]=cur.replace(old,new); touched.append(key)
        elif op=="dict_put":
            cur,sub=state.get(key),step.get("subkey")
            if not isinstance(cur,dict) or not isinstance(sub,str) or not sub: raise ChallengeError("dict_put_type_error")
            cur[sub]=copy.deepcopy(step.get("value")); touched.append(f"{key}.{sub}")
        elif op=="move_item":
            src,dst,val=step.get("from"),step.get("to"),step.get("value")
            if not isinstance(src,str) or not isinstance(dst,str) or src==dst: raise ChallengeError("move_item_invalid")
            a,b=state.get(src),state.get(dst)
            if not isinstance(a,list) or not isinstance(b,list) or val not in a: raise ChallengeError("move_item_state_error")
            a.remove(val); b.append(copy.deepcopy(val)); touched += [src,dst]
    return state, sorted(set(touched))

def _prompt(task_id: str, initial: dict[str,Any], goal_lines: list[str], exact_steps: int) -> str:
    catalog=", ".join(ALLOWED_OPS)
    goals="\n".join(f"- {x}" for x in goal_lines)
    return (
        f"Contract {task_id}\n"
        "STATE SNAPSHOT\n"
        + json.dumps(initial,ensure_ascii=False,sort_keys=True)
        + "\nACCEPTANCE CONDITIONS\n"
        + goals
        + f"\nACTION BUDGET: exactly {exact_steps} actions.\n"
        + "ACTION CATALOG\n"
        + catalog
        + "\nReturn one raw JSON array of action objects. No prose, markdown, or replacement-state shortcut."
    )

def _cases() -> list[dict[str,Any]]:
    cases=[]
    def add(kind, initial, program, goals):
        idx=len(cases)+1
        expected,touched=_execute(program,initial)
        tid=f"gxc-v1-{idx:02d}-{kind}"
        prompt=_prompt(tid,initial,goals,len(program))
        cases.append({
            "task_id":tid,"scenario":kind,"initial_state":initial,"oracle_program":program,
            "expected_state":expected,"required_touched_paths":touched,"exact_steps":len(program),"prompt":prompt,
        })

    # Two variants for each structural scenario. Each requires composition.
    for n in (3,7):
        add("rename_increment",
            {f"legacy_count_{n}":10+n,"audit":f"keep-{n}","flags":["stable"]},
            [{"op":"rename","from":f"legacy_count_{n}","to":f"active_count_{n}"},
             {"op":"increment","key":f"active_count_{n}","by":n}],
            [f"`legacy_count_{n}` must become `active_count_{n}` with its value increased by {n}.","Every unrelated field must be byte-for-byte equivalent as JSON."])
    for n in (4,8):
        add("dedupe_sort",
            {f"queue_{n}":[f"z{n}",f"a{n}",f"z{n}",f"m{n}",f"a{n}"],"guard":{"v":n}},
            [{"op":"dedupe_list","key":f"queue_{n}"},{"op":"sort_list","key":f"queue_{n}"}],
            [f"`queue_{n}` must contain each original item once, sorted ascending.","Do not alter `guard`."])
    for n in (5,9):
        old=f"old{n}"; new=f"new{n}"
        add("normalize_replace",
            {f"note_{n}":f"  ship   {old}  then\n archive {old}   ","counter":n},
            [{"op":"normalize_ws","key":f"note_{n}"},{"op":"replace_text","key":f"note_{n}","old":old,"new":new}],
            [f"Whitespace in `note_{n}` must be normalized to single spaces.",f"Every literal `{old}` in that normalized note must become `{new}`.","Do not alter `counter`."])
    for n in (6,10):
        add("map_filter",
            {f"scores_{n}":[1,n-1,n,n+2,2*n],"label":f"L{n}"},
            [{"op":"map_add","key":f"scores_{n}","by":2},{"op":"filter_ge","key":f"scores_{n}","min":n+2}],
            [f"Add 2 to each element of `scores_{n}`, then keep only values >= {n+2}.","Preserve the resulting order and leave `label` unchanged."])
    for n in (11,12):
        job=f"job-{n}"
        add("move_append",
            {f"inbox_{n}":[job,f"keep-{n}"],f"done_{n}":["existing"],"audit":n},
            [{"op":"move_item","from":f"inbox_{n}","to":f"done_{n}","value":job},
             {"op":"append_unique","key":f"done_{n}","value":f"tag-{n}"}],
            [f"Move `{job}` from `inbox_{n}` to the end of `done_{n}`.",f"Then ensure `tag-{n}` appears once at the end of `done_{n}`.","Leave `audit` unchanged."])
    for n in (13,14):
        old=f"Legacy {n}"
        add("replace_slugify",
            {f"title_{n}":f" {old}: Release Candidate! ","stable":True},
            [{"op":"replace_text","key":f"title_{n}","old":"Legacy","new":"AQLEVON"},{"op":"slugify","key":f"title_{n}"}],
            [f"In `title_{n}`, replace `Legacy` with `AQLEVON`, then slugify the whole field.","Leave `stable` unchanged."])
    for n in (15,16):
        add("dict_toggle_rename",
            {f"config_{n}":{"stable":True},f"enabled_{n}":bool(n%2),f"alias_{n}":f"value-{n}","guard":"keep"},
            [{"op":"dict_put","key":f"config_{n}","subkey":"limit","value":n+20},
             {"op":"toggle_bool","key":f"enabled_{n}"},
             {"op":"rename","from":f"alias_{n}","to":f"canonical_{n}"}],
            [f"Set `config_{n}.limit` to {n+20}.",f"Toggle `enabled_{n}` once.",f"Rename `alias_{n}` to `canonical_{n}` without changing its value.","Leave `guard` unchanged."])
    for n in (17,18):
        add("delete_move_sort",
            {f"obsolete_{n}":"remove",f"pending_{n}":[f"x{n}",f"a{n}"],f"done_{n}":[f"z{n}"],"guard":n},
            [{"op":"delete","key":f"obsolete_{n}"},
             {"op":"move_item","from":f"pending_{n}","to":f"done_{n}","value":f"x{n}"},
             {"op":"sort_list","key":f"done_{n}"}],
            [f"Delete `obsolete_{n}`.",f"Move `x{n}` from `pending_{n}` to `done_{n}`.",f"Sort `done_{n}` ascending after the move.","Leave `guard` unchanged."])
    return cases

def build_pack() -> dict[str,Any]:
    tasks=[]
    for c in _cases():
        t={
            "task_id":c["task_id"],"scenario":c["scenario"],"prompt":c["prompt"],
            "initial_state":c["initial_state"],
            "expected_state_sha256":sha256_obj(c["expected_state"]),
            "required_touched_paths":c["required_touched_paths"],
            "exact_steps":c["exact_steps"],
            "allowed_ops":list(ALLOWED_OPS),
        }
        t["task_sha256"]=sha256_obj(t)
        tasks.append(t)
    pack={
        "schema_version":1,
        "pack_kind":PACK_KIND,
        "hash_profile":HASH_PROFILE,
        "public":True,
        "protected_or_sealed_material_used":False,
        "public_seed":PUBLIC_SEED,
        "task_count":len(tasks),
        "structural_shift":{
            "training_reference":"W02 atomic one-operation synthetic families",
            "min_actions_per_task":2,
            "max_actions_per_task":3,
            "compositional_dependencies":True,
            "prompt_template_reused":False,
            "training_core_ids_reused":False,
            "oracle_in_pack":False,
        },
        "tasks":tasks,
    }
    pack["pack_sha256"]=sha256_obj(pack)
    return pack

def verify_program(task_id: str, program: Any) -> dict[str,Any]:
    cases={c["task_id"]:c for c in _cases()}
    if task_id not in cases:
        return {"passed":False,"reason":"unknown_task"}
    c=cases[task_id]
    if not isinstance(program,list) or len(program)!=c["exact_steps"]:
        return {"passed":False,"reason":"step_budget_mismatch"}
    try:
        state,touched=_execute(program,c["initial_state"])
    except ChallengeError as exc:
        return {"passed":False,"reason":str(exc)}
    if state!=c["expected_state"]:
        return {"passed":False,"reason":"final_state_mismatch"}
    if touched!=c["required_touched_paths"]:
        return {"passed":False,"reason":"side_effect_mismatch"}
    return {"passed":True,"reason":"objective_state_match"}

def reference_oracles() -> dict[str,Any]:
    return {c["task_id"]:copy.deepcopy(c["oracle_program"]) for c in _cases()}

if __name__=="__main__":
    print(json.dumps(build_pack(),ensure_ascii=False,sort_keys=True,separators=(",",":")))
