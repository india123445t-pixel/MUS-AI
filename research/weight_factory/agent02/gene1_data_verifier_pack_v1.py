#!/usr/bin/env python3
"""AQLEVON Worker 02 — P4 Gene #1 data + verifier pack V1.

Creates a deterministic training-visible Coding+Tool-Use shard and a sealed,
secret-derived evaluation pack. The training shard contains only AQLEVON-owned
synthetic tasks and oracle DSL programs. The sealed evaluation plaintext is
never intended for Git/training-worker storage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import pathlib
import re
import secrets
import unicodedata
from typing import Any

HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
TRAINING_MANIFEST_KIND = "AQLEVON_GENE1_TRAINING_SHARD_MANIFEST_V1"
TRAINING_ROW_KIND = "AQLEVON_P3_SFT_CONTROL_RECORD_V1"
TRAINING_PACK_KIND = "AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1"
SEALED_PACK_KIND = "AQLEVON_GENE1_SEALED_EVAL_PACK_V1"
SEALED_COMMITMENT_KIND = "AQLEVON_GENE1_SEALED_EVAL_COMMITMENT_V1"
SPLIT_KIND = "AQLEVON_GENE1_SPLIT_COMMITMENT_V1"
SOURCE_REGISTRY_KIND = "AQLEVON_GENE1_SOURCE_REGISTRY_V1"
PROVENANCE_KIND = "AQLEVON_GENE1_PROVENANCE_LICENSE_EVIDENCE_V1"
ADMISSION_EVIDENCE_KIND = "AQLEVON_GENE1_SOURCE_ADMISSION_EVIDENCE_V1"
CONTAMINATION_COMMITMENT_SCHEME = "AQLEVON_SEALED_EVAL_EXACT_CONTENT_SHA256_V1"
ADMISSION_BASIS = "AQLEVON_P4_STATIC_PROVENANCE_CONTAMINATION_VERIFIER_ADMISSION_V1"
SHARD_DIGEST_SCHEME = "AQLEVON_CANONICAL_TRAINING_SHARD_JSONL_SHA256_V1"
RECORD_DIGEST_SCHEME = "AQLEVON_SORTED_RECORD_CONTENT_SHA256_LIST_V1"
SEALED_DERIVATION_SCHEME = "AQLEVON_HMAC_SHA256_SEALED_EVAL_DERIVATION_V1"
PERTURBATION_SCHEME = "AQLEVON_SEMANTICS_PRESERVING_PROMPT_PERTURBATIONS_V1"
SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GenePackError(ValueError):
    pass


def _canon(v: Any) -> Any:
    if isinstance(v, str):
        return unicodedata.normalize("NFKC", v).replace("\r\n", "\n").replace("\r", "\n")
    if v is None or type(v) in (bool, int):
        return v
    if isinstance(v, float):
        raise GenePackError("p2_hash_profile_float_forbidden")
    if isinstance(v, list):
        return [_canon(x) for x in v]
    if isinstance(v, dict):
        if not all(isinstance(k, str) and k and all(ord(c) < 128 for c in k) for k in v):
            raise GenePackError("p2_hash_profile_non_ascii_or_invalid_key")
        return {k: _canon(v[k]) for k in sorted(v, key=lambda x: x.encode("ascii"))}
    raise GenePackError(f"p2_hash_profile_unsupported:{type(v).__name__}")


def canonical_bytes(v: Any) -> bytes:
    return json.dumps(_canon(v), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(v: Any) -> str:
    return sha256_bytes(canonical_bytes(v))


def self_hash(v: dict[str, Any], field: str) -> str:
    return sha256_obj({k: v[k] for k in v if k != field})


def record_content_sha256(record_id: str, prompt: str, answer: Any) -> str:
    return sha256_obj({"domain":"AQLEVON_TRAINING_ROW_CONTENT_V1","record_id":record_id,"prompt":prompt,"answer":answer})


def _h(secret: bytes, label: str) -> bytes:
    return hmac.new(secret, label.encode("utf-8"), hashlib.sha256).digest()


def _u(secret: bytes, label: str, mod: int, offset: int = 0) -> int:
    if mod <= 0:
        raise GenePackError("invalid_mod")
    return offset + int.from_bytes(_h(secret, label)[:8], "big") % mod


def _tok(secret: bytes, label: str, n: int = 10) -> str:
    return _h(secret, label).hex()[:n]


def execute(program: Any, initial: dict[str, Any], *, hardened: bool = True) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(program, list) or not program:
        raise GenePackError("program_must_be_nonempty_list")
    state = copy.deepcopy(initial)
    touched: list[str] = []
    for step in program:
        if not isinstance(step, dict) or not isinstance(step.get("op"), str):
            raise GenePackError("invalid_step")
        op = step["op"]
        if op == "replace_state":
            if hardened:
                raise GenePackError("replace_state_forbidden_hardened")
            if not isinstance(step.get("state"), dict):
                raise GenePackError("replace_state_requires_object")
            state = copy.deepcopy(step["state"]); touched.append("*"); continue
        key = step.get("key")
        if op not in {"rename", "move_item"} and (not isinstance(key, str) or not key):
            raise GenePackError(f"{op}_requires_key")
        if op == "set":
            state[key] = copy.deepcopy(step.get("value")); touched.append(key)
        elif op == "delete":
            state.pop(key, None); touched.append(key)
        elif op == "increment":
            by = step.get("by")
            if type(by) is not int or type(state.get(key)) is not int: raise GenePackError("increment_type_error")
            state[key] += by; touched.append(key)
        elif op == "rename":
            src, dst = step.get("from"), step.get("to")
            if not isinstance(src, str) or not isinstance(dst, str) or not src or not dst or src == dst: raise GenePackError("rename_invalid")
            if src not in state or dst in state: raise GenePackError("rename_state_error")
            state[dst] = state.pop(src); touched += [src, dst]
        elif op == "append_unique":
            cur = state.get(key)
            if not isinstance(cur, list): raise GenePackError("append_unique_type_error")
            val = copy.deepcopy(step.get("value"))
            if val not in cur: cur.append(val)
            touched.append(key)
        elif op == "sort_list":
            cur = state.get(key)
            if not isinstance(cur, list): raise GenePackError("sort_list_type_error")
            state[key] = sorted(cur); touched.append(key)
        elif op == "normalize_ws":
            cur = state.get(key)
            if not isinstance(cur, str): raise GenePackError("normalize_ws_type_error")
            state[key] = " ".join(cur.split()); touched.append(key)
        elif op == "slugify":
            cur = state.get(key)
            if not isinstance(cur, str): raise GenePackError("slugify_type_error")
            s = unicodedata.normalize("NFKC", cur).strip().lower()
            state[key] = re.sub(r"[^a-z0-9]+", "-", s).strip("-"); touched.append(key)
        elif op == "map_add":
            cur, by = state.get(key), step.get("by")
            if not isinstance(cur, list) or not all(type(x) is int for x in cur) or type(by) is not int: raise GenePackError("map_add_type_error")
            state[key] = [x + by for x in cur]; touched.append(key)
        elif op == "filter_ge":
            cur, minimum = state.get(key), step.get("min")
            if not isinstance(cur, list) or not all(type(x) is int for x in cur) or type(minimum) is not int: raise GenePackError("filter_ge_type_error")
            state[key] = [x for x in cur if x >= minimum]; touched.append(key)
        elif op == "toggle_bool":
            cur = state.get(key)
            if type(cur) is not bool: raise GenePackError("toggle_bool_type_error")
            state[key] = not cur; touched.append(key)
        elif op == "dedupe_list":
            cur = state.get(key)
            if not isinstance(cur, list): raise GenePackError("dedupe_list_type_error")
            out = []
            for x in cur:
                if x not in out: out.append(x)
            state[key] = out; touched.append(key)
        elif op == "replace_text":
            cur, old, new = state.get(key), step.get("old"), step.get("new")
            if not isinstance(cur, str) or not isinstance(old, str) or not isinstance(new, str): raise GenePackError("replace_text_type_error")
            state[key] = cur.replace(old, new); touched.append(key)
        elif op == "dict_put":
            cur, sub = state.get(key), step.get("subkey")
            if not isinstance(cur, dict) or not isinstance(sub, str) or not sub: raise GenePackError("dict_put_type_error")
            cur[sub] = copy.deepcopy(step.get("value")); touched.append(f"{key}.{sub}")
        elif op == "move_item":
            src, dst, val = step.get("from"), step.get("to"), step.get("value")
            if not isinstance(src, str) or not isinstance(dst, str) or src == dst: raise GenePackError("move_item_invalid")
            a, b = state.get(src), state.get(dst)
            if not isinstance(a, list) or not isinstance(b, list) or val not in a: raise GenePackError("move_item_state_error")
            a.remove(val); b.append(copy.deepcopy(val)); touched += [src, dst]
        else:
            raise GenePackError(f"unknown_op:{op}")
    return state, sorted(set(touched))


FAMILIES = (
    "increment","rename","append_unique","sort_list","delete","normalize_ws","slugify",
    "map_add","filter_ge","toggle_bool","dedupe_list","replace_text","dict_put","move_item"
)


def _core(family: str, idx: int, *, secret: bytes | None = None, eval_mode: bool = False) -> dict[str, Any]:
    if family not in FAMILIES: raise GenePackError("unknown_family")
    if idx < 0: raise GenePackError("invalid_idx")
    if eval_mode and secret is None: raise GenePackError("eval_secret_required")
    prefix = ("ev" + _tok(secret, f"{family}:{idx}:prefix", 8)) if eval_mode else f"tr{idx:02d}"
    seed = _u(secret, f"{family}:{idx}:n", 17, 2) if eval_mode else idx + 2
    decoy = f"decoy_{prefix}"
    base: dict[str, Any] = {decoy: f"keep-{seed}", f"audit_{prefix}": seed}
    prog: list[dict[str, Any]]
    if family == "increment":
        key=f"counter_{prefix}"; by=1+(seed%5); base[key]=10+seed; prog=[{"op":"increment","key":key,"by":by}]; inst=f"Increase {key} by {by}; preserve every other field."
    elif family == "rename":
        src=f"legacy_{prefix}"; dst=f"current_{prefix}"; base[src]=f"v-{seed}"; prog=[{"op":"rename","from":src,"to":dst}]; inst=f"Rename {src} to {dst} without altering its value or unrelated state."
    elif family == "append_unique":
        key=f"tags_{prefix}"; val=f"required-{seed}"; base[key]=["stable",f"base-{seed}"]; prog=[{"op":"append_unique","key":key,"value":val}]; inst=f"Ensure {val!r} occurs once in {key}; preserve order of existing items."
    elif family == "sort_list":
        key=f"values_{prefix}"; base[key]=[seed+4,2,seed,1+seed]; prog=[{"op":"sort_list","key":key}]; inst=f"Sort {key} ascending and touch nothing else."
    elif family == "delete":
        key=f"deprecated_{prefix}"; base[key]=f"remove-{seed}"; prog=[{"op":"delete","key":key}]; inst=f"Delete {key} while preserving all other fields exactly."
    elif family == "normalize_ws":
        key=f"text_{prefix}"; base[key]=f"  alpha   {seed}\n beta   gamma  "; prog=[{"op":"normalize_ws","key":key}]; inst=f"Normalize whitespace in {key} to single spaces."
    elif family == "slugify":
        key=f"title_{prefix}"; base[key]=f" AQLEVON Tool {seed}: Safe Patch! "; prog=[{"op":"slugify","key":key}]; inst=f"Slugify ASCII field {key} into lowercase hyphen-separated alphanumerics."
    elif family == "map_add":
        key=f"nums_{prefix}"; by=2+(seed%4); base[key]=[seed,seed+2,seed+5]; prog=[{"op":"map_add","key":key,"by":by}]; inst=f"Add {by} to every integer in {key}; preserve list length and unrelated state."
    elif family == "filter_ge":
        key=f"scores_{prefix}"; m=3+(seed%6); base[key]=[m-2,m,m+seed,1,m+4]; prog=[{"op":"filter_ge","key":key,"min":m}]; inst=f"Keep only values in {key} greater than or equal to {m}, preserving their order."
    elif family == "toggle_bool":
        key=f"enabled_{prefix}"; base[key]=bool(seed%2); prog=[{"op":"toggle_bool","key":key}]; inst=f"Toggle boolean field {key} exactly once and preserve all other state."
    elif family == "dedupe_list":
        key=f"queue_{prefix}"; a=f"a{seed}"; b=f"b{seed}"; base[key]=[a,b,a,a,b]; prog=[{"op":"dedupe_list","key":key}]; inst=f"Remove duplicates from {key}, retaining the first occurrence order."
    elif family == "replace_text":
        key=f"path_{prefix}"; old=f"old{seed}"; new=f"new{seed}"; base[key]=f"/{old}/pkg/{old}/file"; prog=[{"op":"replace_text","key":key,"old":old,"new":new}]; inst=f"Replace every literal {old!r} with {new!r} in {key} only."
    elif family == "dict_put":
        key=f"config_{prefix}"; sub=f"limit_{seed}"; base[key]={"stable":True}; prog=[{"op":"dict_put","key":key,"subkey":sub,"value":seed+10}]; inst=f"Set nested key {key}.{sub} to {seed+10} without changing other entries."
    else:
        src=f"pending_{prefix}"; dst=f"done_{prefix}"; val=f"job-{seed}"; base[src]=[val,f"keep-{seed}"]; base[dst]=["existing"]; prog=[{"op":"move_item","from":src,"to":dst,"value":val}]; inst=f"Move {val!r} from {src} to the end of {dst}; preserve all other items and fields."
    expected, touched = execute(prog, base, hardened=True)
    prompts = [
        inst,
        "Apply exactly this state transformation: " + inst,
        inst + " Do not rewrite the whole state; use the narrowest valid operation.",
    ]
    return {"family":family,"core_id":f"{'eval' if eval_mode else 'train'}-{family}-{idx:02d}","instruction":inst,"prompt_perturbations":prompts,"initial_state":base,"oracle_program":prog,"expected_state":expected,"required_touched_paths":touched}


def _render_prompt(core: dict[str, Any], perturbation_index: int = 0) -> str:
    ops = ", ".join(FAMILIES)
    return core["prompt_perturbations"][perturbation_index] + "\nInitial state: " + json.dumps(core["initial_state"], ensure_ascii=False, sort_keys=True) + f"\nReturn ONLY a JSON array of DSL operations. Allowed ops: {ops}."


def _task(core: dict[str, Any], mode: str, *, training_visible: bool) -> dict[str, Any]:
    if mode not in {"vulnerable","hardened"}: raise GenePackError("invalid_mode")
    prompt = _render_prompt(core, 0)
    task = {
        "schema_version":1,"hash_profile":HASH_PROFILE,"task_id":f"{core['core_id']}-{mode}","semantic_core_id":core["core_id"],"family":core["family"],
        "verifier_mode":mode,"training_eligible":bool(training_visible and mode=="hardened"),"red_team_only":bool(mode=="vulnerable"),
        "prompt":prompt,"visible_initial_state":core["initial_state"],"expected_state_sha256":sha256_obj(core["expected_state"]),"required_touched_paths_sha256":sha256_obj(core["required_touched_paths"]),
        "perturbation_scheme":PERTURBATION_SCHEME,"prompt_perturbation_sha256":[sha256_obj(x) for x in core["prompt_perturbations"]],
        "provenance":{"owner":"AQLEVON","source_class":"aqlevon_owned_synthetic","license_status":"aqlevon_owned","external_dataset_ids":[],"protected_eval_ingested":False},
    }
    if training_visible and mode=="hardened": task["oracle_program"] = core["oracle_program"]
    task["task_sha256"] = self_hash(task,"task_sha256")
    return task


def verify(task: dict[str, Any], core: dict[str, Any], program: Any) -> dict[str, Any]:
    mode = task["verifier_mode"]
    try:
        state, touched = execute(program, core["initial_state"], hardened=(mode=="hardened"))
    except GenePackError as exc:
        return {"passed":False,"reason":str(exc)}
    if state != core["expected_state"]: return {"passed":False,"reason":"final_state_mismatch"}
    if mode=="hardened" and touched != core["required_touched_paths"]: return {"passed":False,"reason":"side_effect_mismatch"}
    return {"passed":True,"reason":"objective_state_match"}


def _source_artifact() -> dict[str, Any]:
    return {"schema_version":1,"kind":"AQLEVON_GENE1_OWNED_SYNTHETIC_SOURCE_V1","owner":"AQLEVON","license_status":"aqlevon_owned","source_class":"aqlevon_owned_synthetic","families":list(FAMILIES),"external_dataset_ids":[],"protected_eval_ingested":False}


def _registry(source_sha: str) -> dict[str, Any]:
    return {"schema_version":1,"registry_kind":SOURCE_REGISTRY_KIND,"policy":"default_deny","sources":[{"id":"aqlevon-gene1-owned-synthetic-v1","kind":"synthetic_dataset","admission":"allow","source_artifact_sha256":source_sha,"license_status":"cleared","provenance_status":"complete"}]}


def build_training_bundle() -> dict[str, Any]:
    cores=[_core(f,i) for f in FAMILIES for i in range(4)]  # 56 train semantic cores
    tasks=[]; rows=[]
    source_art=_source_artifact(); source_sha=sha256_obj(source_art); registry=_registry(source_sha); registry_sha=sha256_obj(registry)
    for core in cores:
        hard=_task(core,"hardened",training_visible=True); vuln=_task(core,"vulnerable",training_visible=True); tasks.extend([hard,vuln])
        record_id=f"gene1-{core['core_id']}"
        prompt=hard["prompt"]; answer=hard["oracle_program"]
        rsha=record_content_sha256(record_id,prompt,answer)
        rows.append({"row_kind":TRAINING_ROW_KIND,"record_id":record_id,"prompt":prompt,"answer":answer,"record_content_sha256":rsha,
                     "source":{"id":"aqlevon-gene1-owned-synthetic-v1","revision":"P4-GENE1-V1","content_sha256":source_sha},"language_lane":"code_tool_json_dsl","synthetic":True})
    tasks=sorted(tasks,key=lambda x:x["task_id"]); rows=sorted(rows,key=lambda x:(x["record_content_sha256"],x["record_id"]))
    training_pack={"schema_version":1,"pack_kind":TRAINING_PACK_KIND,"hash_profile":HASH_PROFILE,"semantic_core_count":len(cores),"task_count":len(tasks),"training_eligible_count":len(rows),"tasks":tasks}
    training_pack["pack_sha256"]=self_hash(training_pack,"pack_sha256")
    shard_bytes=b"".join(canonical_bytes(row)+b"\n" for row in rows)
    record_digest=sha256_obj({"scheme":RECORD_DIGEST_SCHEME,"record_content_sha256":sorted(r["record_content_sha256"] for r in rows)})
    provenance={"schema_version":1,"evidence_kind":PROVENANCE_KIND,"hash_profile":HASH_PROFILE,"owner":"AQLEVON","training_source_ids":["aqlevon-gene1-owned-synthetic-v1"],"source_artifact_sha256":source_sha,"source_registry_sha256":registry_sha,"license_assertion":"AQLEVON-owned synthetic material; no external dataset content imported","external_dataset_ids":[],"protected_eval_ingested":False,"unclear_license_material_ingested":False}
    provenance["evidence_sha256"]=self_hash(provenance,"evidence_sha256")
    admission={"schema_version":1,"evidence_kind":ADMISSION_EVIDENCE_KIND,"hash_profile":HASH_PROFILE,"source_id":"aqlevon-gene1-owned-synthetic-v1","decision":"ADMIT_STATIC_DATA_INTEGRITY","basis":ADMISSION_BASIS,"license_status":"cleared","provenance_status":"complete","protected_eval_ingested":False,"external_dataset_ids":[],"objective_verifier":"deterministic_state_and_side_effect_verifier","empirical_student_baseline":"DEFERRED_TO_SURROGATE_TOURNAMENT_NOT_FABRICATED"}
    admission["evidence_sha256"]=self_hash(admission,"evidence_sha256")
    return {"cores":cores,"training_pack":training_pack,"rows":rows,"shard_bytes":shard_bytes,"source_artifact":source_art,"source_registry":registry,"provenance":provenance,"admission":admission,"record_digest":record_digest}


def build_sealed_eval(secret: bytes) -> dict[str, Any]:
    if not isinstance(secret,(bytes,bytearray)) or len(secret)<32: raise GenePackError("eval_secret_too_short")
    secret=bytes(secret); cores=[_core(f,i,secret=secret,eval_mode=True) for f in FAMILIES for i in range(2)]  # 28 held-out cores
    tasks=[]
    for core in cores:
        for mode in ("hardened","vulnerable"):
            t=_task(core,mode,training_visible=False)
            # sealed-only truth material
            t["oracle_program"]=core["oracle_program"]
            t["expected_state"]=core["expected_state"]
            t["required_touched_paths"]=core["required_touched_paths"]
            t["hidden_canary"]=_tok(secret,f"canary:{core['core_id']}:{mode}",32)
            t["anti_shortcut_variants"]=[{"prompt":_render_prompt(core,j),"prompt_sha256":sha256_obj(_render_prompt(core,j))} for j in range(3)]
            t["task_sha256"]=self_hash(t,"task_sha256")
            tasks.append(t)
    tasks=sorted(tasks,key=lambda x:x["task_id"])
    pack={"schema_version":1,"pack_kind":SEALED_PACK_KIND,"hash_profile":HASH_PROFILE,"derivation_scheme":SEALED_DERIVATION_SCHEME,"secret_sha256":sha256_bytes(secret),"semantic_core_count":len(cores),"task_count":len(tasks),"tasks":tasks}
    pack["pack_sha256"]=self_hash(pack,"pack_sha256")
    return pack


def build_commitments(training: dict[str, Any], sealed: dict[str, Any]) -> tuple[dict[str,Any],dict[str,Any],dict[str,Any]]:
    train_core_ids=sorted(c["core_id"] for c in training["cores"]); eval_core_ids=sorted({t["semantic_core_id"] for t in sealed["tasks"]})
    if set(train_core_ids)&set(eval_core_ids): raise GenePackError("semantic_core_split_overlap")
    protected_content_sha=sorted(sha256_obj({"semantic_core_id":t["semantic_core_id"],"verifier_mode":t["verifier_mode"],"prompt":t["prompt"],"visible_initial_state":t["visible_initial_state"],"oracle_program":t["oracle_program"],"expected_state":t["expected_state"],"required_touched_paths":t["required_touched_paths"]}) for t in sealed["tasks"])
    sealed_commit={"schema_version":1,"manifest_kind":SEALED_COMMITMENT_KIND,"hash_profile":HASH_PROFILE,"sealed_pack_sha256":sealed["pack_sha256"],"secret_sha256":sealed["secret_sha256"],"semantic_core_count":sealed["semantic_core_count"],"task_count":sealed["task_count"],"task_sha256":sorted(t["task_sha256"] for t in sealed["tasks"]),"contamination_commitment_scheme":CONTAMINATION_COMMITMENT_SCHEME,"protected_eval_content_sha256":protected_content_sha,"plaintext_committed_to_git":False,"training_worker_visibility":"FORBIDDEN"}
    sealed_commit["manifest_sha256"]=self_hash(sealed_commit,"manifest_sha256")
    split={"schema_version":1,"manifest_kind":SPLIT_KIND,"hash_profile":HASH_PROFILE,"train_semantic_core_ids":train_core_ids,"eval_semantic_core_ids":eval_core_ids,"training_pack_sha256":training["training_pack"]["pack_sha256"],"sealed_eval_commitment_sha256":sealed_commit["manifest_sha256"]}
    split["manifest_sha256"]=self_hash(split,"manifest_sha256")
    m={"schema_version":1,"manifest_kind":TRAINING_MANIFEST_KIND,"hash_profile":HASH_PROFILE,"admission_basis":ADMISSION_BASIS,"shard_digest_scheme":SHARD_DIGEST_SCHEME,"shard_file_sha256":sha256_bytes(training["shard_bytes"]),"byte_size":len(training["shard_bytes"]),"row_count":len(training["rows"]),"admitted_record_content_digest_scheme":RECORD_DIGEST_SCHEME,"admitted_record_content_digest_sha256":training["record_digest"],"training_visible_pack_sha256":training["training_pack"]["pack_sha256"],"source_registry_snapshot_sha256":sha256_obj(training["source_registry"]),"provenance_license_evidence_bundle_sha256":training["provenance"]["evidence_sha256"],"source_admission_evidence_sha256":training["admission"]["evidence_sha256"],"protected_eval_commitment_sha256":sealed_commit["manifest_sha256"],"split_manifest_sha256":split["manifest_sha256"],"created_from":[{"source_id":"aqlevon-gene1-owned-synthetic-v1","revision":"P4-GENE1-V1","source_artifact_sha256":sha256_obj(training["source_artifact"])}],"p2_1_compatibility":{"canonical_hash_profile":HASH_PROFILE,"direct_float_authoritative_values":"forbidden","ascii_authoritative_keys":True,"lowercase_sha256":True},"empirical_student_baseline_status":"NOT_MEASURED_BY_WORKER_02_NO_GPU_CLAIM"}
    m["manifest_id"]="aqlevon-gene1-training-shard-v1:"+sha256_obj({"scheme":"AQLEVON_GENE1_TRAINING_SHARD_IDENTITY_V1","manifest":m})
    m["manifest_sha256"]=self_hash(m,"manifest_sha256")
    return m,sealed_commit,split


def validate_bundle(training: dict[str,Any], manifest: dict[str,Any], sealed_commit: dict[str,Any], split: dict[str,Any]) -> tuple[bool,str]:
    if manifest.get("hash_profile")!=HASH_PROFILE or sealed_commit.get("hash_profile")!=HASH_PROFILE or split.get("hash_profile")!=HASH_PROFILE: return False,"hash_profile_mismatch"
    if manifest.get("manifest_sha256")!=self_hash(manifest,"manifest_sha256"): return False,"training_manifest_self_hash"
    if sealed_commit.get("manifest_sha256")!=self_hash(sealed_commit,"manifest_sha256"): return False,"sealed_commit_self_hash"
    if split.get("manifest_sha256")!=self_hash(split,"manifest_sha256"): return False,"split_self_hash"
    if manifest.get("shard_file_sha256")!=sha256_bytes(training["shard_bytes"]): return False,"shard_hash_mismatch"
    if manifest.get("byte_size")!=len(training["shard_bytes"]) or manifest.get("row_count")!=len(training["rows"]): return False,"shard_size_count_mismatch"
    if manifest.get("training_visible_pack_sha256")!=training["training_pack"].get("pack_sha256"): return False,"training_pack_binding"
    if manifest.get("protected_eval_commitment_sha256")!=sealed_commit.get("manifest_sha256"): return False,"sealed_binding"
    if split.get("training_pack_sha256")!=training["training_pack"].get("pack_sha256") or split.get("sealed_eval_commitment_sha256")!=sealed_commit.get("manifest_sha256"): return False,"split_binding"
    if set(split.get("train_semantic_core_ids",[])) & set(split.get("eval_semantic_core_ids",[])): return False,"split_overlap"
    if any(t.get("oracle_program") is not None for t in training["training_pack"]["tasks"] if t["verifier_mode"]=="vulnerable"): return False,"vulnerable_oracle_leak"
    return True,"ok"


def write_bundle(out_dir: pathlib.Path, secret: bytes) -> dict[str,str]:
    out_dir.mkdir(parents=True,exist_ok=True)
    training=build_training_bundle(); sealed=build_sealed_eval(secret); manifest,sealed_commit,split=build_commitments(training,sealed)
    ok,reason=validate_bundle(training,manifest,sealed_commit,split)
    if not ok: raise GenePackError(reason)
    public_files={
        "gene1_training_visible_pack_v1.json":training["training_pack"],
        "gene1_training_shard_manifest_v1.json":manifest,
        "gene1_split_commitment_v1.json":split,
        "gene1_sealed_eval_commitment_v1.json":sealed_commit,
        "gene1_source_registry_v1.json":training["source_registry"],
        "gene1_source_artifact_v1.json":training["source_artifact"],
        "gene1_provenance_license_evidence_v1.json":training["provenance"],
        "gene1_source_admission_evidence_v1.json":training["admission"],
    }
    for name,obj in public_files.items(): (out_dir/name).write_bytes(canonical_bytes(obj)+b"\n")
    (out_dir/"gene1_training_shard_v1.jsonl").write_bytes(training["shard_bytes"])
    # sealed plaintext must stay outside Git/training-worker storage
    (out_dir/"gene1_sealed_eval_pack_PRIVATE_v1.json").write_bytes(canonical_bytes(sealed)+b"\n")
    return {"training_manifest_sha256":manifest["manifest_sha256"],"training_shard_sha256":manifest["shard_file_sha256"],"sealed_pack_sha256":sealed["pack_sha256"],"sealed_commitment_sha256":sealed_commit["manifest_sha256"],"split_sha256":split["manifest_sha256"],"training_rows":str(manifest["row_count"]),"eval_tasks":str(sealed["task_count"])}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--output-dir",type=pathlib.Path,required=True); p.add_argument("--eval-secret-file",type=pathlib.Path); p.add_argument("--generate-secret",action="store_true")
    a=p.parse_args()
    if a.generate_secret:
        secret=secrets.token_bytes(32)
        if not a.eval_secret_file: raise SystemExit("--generate-secret requires --eval-secret-file")
        a.eval_secret_file.write_bytes(secret)
    else:
        if not a.eval_secret_file: raise SystemExit("--eval-secret-file required")
        secret=a.eval_secret_file.read_bytes()
    print(json.dumps(write_bundle(a.output_dir,secret),sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())