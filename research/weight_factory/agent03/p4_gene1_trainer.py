#!/usr/bin/env python3
"""AQLEVON Worker 03 — P4 Gene #1 frozen-input/authorization control plane.

Consumes the exact Worker-01/W02/W05 P4 public handoffs.  It never reads sealed
P4 evaluation plaintext.  G1 is historical evidence only and cannot be rerun
from this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
TASK_ID = "P4-A03-GENE1-PHYSICAL-TRAINER"
W01_TASK_ID = "P4-A01-METHOD-TOURNAMENT-DIRECTOR"
SURROGATE_MODEL = "Qwen/Qwen3.5-4B-Base"
SURROGATE_REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
CANONICAL_MODEL = "Qwen/Qwen3.8-27B"
CANONICAL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
G1_COMMIT = "4a7a5fa2c2c4ba5f291564251c290e2c416ce6ec"
G1_STATUS = "ALREADY_PASSED_DO_NOT_RERUN"
METHOD_SPEC_KIND = "AQLEVON_P4_METHOD_TOURNAMENT_SPEC_V1"
W01_CANONICAL_SHA256 = "7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d"
W01_SNAPSHOT_FILE_SHA256 = "4f51eed6107dac85046a432f99edee54f01d3b8100c443eeedd0cb6c56394668"
W02_MANIFEST_KIND = "AQLEVON_GENE1_TRAINING_SHARD_MANIFEST_V1"
W02_ROW_KIND = "AQLEVON_P3_SFT_CONTROL_RECORD_V1"
W02_MANIFEST_SHA256 = "f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f"
W02_SHARD_SHA256 = "59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49"
W02_PACK_SHA256 = "35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
W02_SPLIT_SHA256 = "3cd1c0d32cad8cc7edf55c9392292828d54d2b4bd16ad50d0e70e26ba3dd9202"
W02_SEALED_COMMITMENT_SHA256 = "7e0463ddf6068fe66d85b5798b4f8037489c99dcd452376e8144dff0a122f4e5"
W02_SEALED_PACK_SHA256 = "b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb"
W02_BINDING_SHA256 = "d9a81a9730e1dac02ecf8b032191a8d878e00d9a25547712168afb0a725095e5"
W05_LAW_SHA256 = "70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0"
W05_SAMPLING_SHA256 = "4dde4741da4c1c469ee6fe555ea9041ad985de829eefb76b702ff0c82e528903"
SDPO_REPO = "lasgroup/SDPO"
SDPO_COMMIT = "7c457fc1b1f636ae794eb0362ba37d4743b06fbc"
PROFILE = "p4-surrogate-1x24"
FROZEN_PLAN_KIND = "AQLEVON_P4_GENE1_FROZEN_TRAINING_PLAN_V1"
COMMAND_LOCK_KIND = "AQLEVON_P4_GENE1_COMMAND_LOCK_V1"
AUTH_KIND = "AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
ARMS = (
    "P4_A0_SFT_LORA_CONTROL",
    "P4_A1_RLVR_CONTROL",
    "P4_A2_SDPO_RICH_FEEDBACK",
)
EXECUTION_ORDER = (
    "P4_A1_RLVR_CONTROL",
    "P4_A0_SFT_LORA_CONTROL",
    "P4_A2_SDPO_RICH_FEEDBACK",
)
FORBIDDEN_PRIVATE_KEYS = (
    "sealed_eval_plaintext", "eval_secret", "private_eval", "hidden_answer",
    "canary_plaintext", "sealed_test_body",
)

class ContractError(ValueError):
    pass

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def _canon(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, float):
        raise ContractError("direct_float_forbidden_in_authoritative_hash_payload")
    if isinstance(value, list):
        return [_canon(x) for x in value]
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str) or not k or any(ord(c) >= 128 for c in k):
                raise ContractError("authoritative_keys_must_be_nonempty_ascii")
        return {k: _canon(value[k]) for k in sorted(value, key=lambda x: x.encode("ascii"))}
    raise ContractError(f"unsupported_authoritative_type:{type(value).__name__}")

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canon(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))

def seal(obj: dict[str, Any], field: str) -> dict[str, Any]:
    out = dict(obj)
    out[field] = ""
    out[field] = canonical_sha256({k: out[k] for k in out if k != field})
    return out

def verify_self_digest(obj: Any, field: str) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get(field), str) and bool(_SHA.fullmatch(obj[field])) and canonical_sha256({k: obj[k] for k in obj if k != field}) == obj[field]

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _private_reference_hits(value: Any, path: str = "root") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k).casefold().replace("-", "_")
            if any(tok in key for tok in FORBIDDEN_PRIVATE_KEYS):
                hits.append(f"{path}.{k}")
            hits.extend(_private_reference_hits(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            hits.extend(_private_reference_hits(v, f"{path}[{i}]"))
    return hits

def validate_w01_spec(spec: Any, raw_bytes: bytes | None = None) -> list[str]:
    e: list[str] = []
    if not isinstance(spec, dict): return ["w01_spec_not_object"]
    if str(spec.get("schema_version")) != "1": e.append("w01_schema_version")
    if spec.get("spec_kind") != METHOD_SPEC_KIND: e.append("w01_spec_kind")
    if spec.get("task_id") != W01_TASK_ID: e.append("w01_task_id")
    if canonical_sha256(spec) != W01_CANONICAL_SHA256: e.append("w01_canonical_sha256")
    if raw_bytes is not None and sha256_bytes(raw_bytes) != W01_SNAPSHOT_FILE_SHA256: e.append("w01_snapshot_file_sha256")
    arms = spec.get("arms")
    if not isinstance(arms, list) or [x.get("arm_id") for x in arms if isinstance(x, dict)] != list(ARMS): e.append("w01_arm_set_or_order")
    if spec.get("execution_order", [])[:3] != [
        "P4_A1_RLVR_CONTROL seed1701 to establish C12",
        "P4_A0_SFT_LORA_CONTROL seed1701",
        "P4_A2_SDPO_RICH_FEEDBACK seed1701 if preflight passes",
    ]: e.append("w01_execution_order")
    student = spec.get("student_model") or {}
    if student.get("repo") != SURROGATE_MODEL or student.get("revision") != SURROGATE_REVISION or student.get("precision") != "bf16" or student.get("quantization") != "none": e.append("w01_student_identity")
    common = spec.get("common_adapter") or {}
    if common.get("type") != "lora" or common.get("r") != 4 or common.get("alpha") != 4 or common.get("target_scope") != "model.language_model full-attention q_proj + v_proj only": e.append("w01_adapter_contract")
    budget = spec.get("screen_budget") or {}
    if budget.get("seed") != 1701 or budget.get("max_optimizer_updates") != 12 or budget.get("examples_or_prompts_per_update") != 4 or budget.get("rl_rollouts_per_prompt") != 4 or budget.get("sft_example_exposure_ceiling") != 48: e.append("w01_screen_budget")
    if spec.get("training_seeds") != [1701,1702,1703]: e.append("w01_training_seeds")
    stack = spec.get("common_stack") or {}
    wanted = {"transformers":"5.17.0","peft":"0.21.0","accelerate":"1.15.0"}
    for k,v in wanted.items():
        if (stack.get(k) or {}).get("version") != v: e.append(f"w01_stack_{k}")
    sdpo = stack.get("sdpo_reference") or {}
    if sdpo.get("repo") != SDPO_REPO or sdpo.get("commit") != SDPO_COMMIT or sdpo.get("license") != "Apache-2.0": e.append("w01_sdpo_reference")
    return e

def validate_w02_inputs(manifest: Any, shard: bytes, pack: Any, split: Any, binding: Any) -> list[str]:
    e: list[str] = []
    if not isinstance(manifest, dict) or manifest.get("manifest_kind") != W02_MANIFEST_KIND: return ["w02_manifest_kind"]
    if manifest.get("hash_profile") != HASH_PROFILE: e.append("w02_hash_profile")
    if not verify_self_digest(manifest, "manifest_sha256") or manifest.get("manifest_sha256") != W02_MANIFEST_SHA256: e.append("w02_manifest_sha256")
    if manifest.get("shard_file_sha256") != W02_SHARD_SHA256 or sha256_bytes(shard) != W02_SHARD_SHA256: e.append("w02_shard_sha256")
    if manifest.get("row_count") != 56 or manifest.get("byte_size") != len(shard): e.append("w02_shard_size_count")
    if manifest.get("training_visible_pack_sha256") != W02_PACK_SHA256: e.append("w02_pack_binding")
    if manifest.get("split_manifest_sha256") != W02_SPLIT_SHA256: e.append("w02_split_binding")
    if manifest.get("protected_eval_commitment_sha256") != W02_SEALED_COMMITMENT_SHA256: e.append("w02_sealed_commitment_binding")
    if not isinstance(pack, dict) or pack.get("pack_kind") != "AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1" or not verify_self_digest(pack,"pack_sha256") or pack.get("pack_sha256") != W02_PACK_SHA256: e.append("w02_training_pack")
    if not isinstance(split, dict) or not verify_self_digest(split,"manifest_sha256") or split.get("manifest_sha256") != W02_SPLIT_SHA256: e.append("w02_split")
    if set(split.get("train_semantic_core_ids",[])) & set(split.get("eval_semantic_core_ids",[])): e.append("w02_split_overlap")
    if not isinstance(binding, dict) or not verify_self_digest(binding,"binding_sha256") or binding.get("binding_sha256") != W02_BINDING_SHA256: e.append("w02_public_binding")
    if binding.get("sealed_eval_pack_sha256") != W02_SEALED_PACK_SHA256 or binding.get("sealed_eval_commitment_sha256") != W02_SEALED_COMMITMENT_SHA256 or binding.get("training_worker_visibility") != "FORBIDDEN": e.append("w02_sealed_boundary")
    if _private_reference_hits(pack) or _private_reference_hits(manifest): e.append("w02_private_plaintext_reference")
    rows=[]
    for i,line in enumerate(shard.decode("utf-8").splitlines()):
        if not line.strip(): continue
        try: row=json.loads(line)
        except json.JSONDecodeError: e.append(f"w02_row_{i}_json"); continue
        if row.get("row_kind") != W02_ROW_KIND or not isinstance(row.get("prompt"),str) or "answer" not in row: e.append(f"w02_row_{i}_shape")
        rows.append(row)
    if len(rows)!=56: e.append("w02_row_count")
    return e

def validate_w05_law(law: Any, w01_spec: Any, w02_binding: Any) -> list[str]:
    e=[]
    if not isinstance(law,dict) or law.get("manifest_kind")!="AQLEVON_GENE1_EVALUATION_LAW_V1": return ["w05_law_kind"]
    if not verify_self_digest(law,"law_sha256") or law.get("law_sha256")!=W05_LAW_SHA256: e.append("w05_law_sha256")
    if law.get("worker01_method_tournament_spec_sha256")!=canonical_sha256(w01_spec): e.append("w05_w01_binding")
    if law.get("worker02_public_pack_binding_sha256")!=w02_binding.get("binding_sha256"): e.append("w05_w02_binding")
    if law.get("sampling_profile_sha256")!=W05_SAMPLING_SHA256: e.append("w05_sampling_profile")
    if law.get("score_visibility_at_law_freeze")!="NO_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED": e.append("w05_candidate_blind_freeze")
    return e

def freeze_plan(*, method_spec_path:Path, shard_manifest_path:Path, shard_path:Path, pack_path:Path, split_path:Path, binding_path:Path, law_path:Path, output:Path) -> dict[str,Any]:
    spec=load_json(method_spec_path); raw=method_spec_path.read_bytes(); manifest=load_json(shard_manifest_path); shard=shard_path.read_bytes(); pack=load_json(pack_path); split=load_json(split_path); binding=load_json(binding_path); law=load_json(law_path)
    errors=validate_w01_spec(spec,raw)+validate_w02_inputs(manifest,shard,pack,split,binding)+validate_w05_law(law,spec,binding)
    if errors: raise ContractError("FAIL-CLOSED:"+";".join(errors))
    plan={
      "schema_version":1,"plan_kind":FROZEN_PLAN_KIND,"hash_profile":HASH_PROFILE,"task_id":TASK_ID,
      "g1_status":G1_STATUS,"g1_source_commit":G1_COMMIT,
      "w01_method_spec_canonical_sha256":W01_CANONICAL_SHA256,"w01_method_spec_file_sha256":sha256_file(method_spec_path),
      "w02_training_manifest_sha256":manifest["manifest_sha256"],"w02_training_manifest_file_sha256":sha256_file(shard_manifest_path),
      "w02_training_shard_sha256":W02_SHARD_SHA256,"w02_training_visible_pack_sha256":W02_PACK_SHA256,"w02_split_sha256":W02_SPLIT_SHA256,
      "w02_public_binding_sha256":W02_BINDING_SHA256,"w02_sealed_eval_commitment_sha256":W02_SEALED_COMMITMENT_SHA256,"w02_sealed_eval_pack_sha256":W02_SEALED_PACK_SHA256,
      "w05_evaluation_law_sha256":W05_LAW_SHA256,"w05_sampling_profile_sha256":W05_SAMPLING_SHA256,
      "surrogate_model":{"repo":SURROGATE_MODEL,"revision":SURROGATE_REVISION,"precision":"bf16","quantization":"none"},
      "common_adapter":spec["common_adapter"],"common_stack":spec["common_stack"],"screen_budget":spec["screen_budget"],"generation":spec["generation"],
      "training_seeds":spec["training_seeds"],"arms":spec["arms"],"execution_order":list(EXECUTION_ORDER),
      "profile":PROFILE,"sealed_eval_consumed":False,"automatic_recipe_mutation":False,"automatic_budget_mutation":False,"automatic_model_revision_mutation":False,
      "capability_claim_authority":"WORKER05_EVIDENCE_PLUS_MANAGER_ACCEPTANCE_ONLY",
    }
    plan=seal(plan,"plan_sha256")
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(plan,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return plan

def build_command_lock(argv:list[str],*,plan_sha256:str,run_manifest_sha256:str,arm_id:str,seed:int,profile:str=PROFILE)->dict[str,Any]:
    if arm_id not in ARMS or seed not in (1701,1702,1703): raise ContractError("invalid_arm_or_seed")
    if not isinstance(plan_sha256,str) or not _SHA.fullmatch(plan_sha256): raise ContractError("invalid_plan_sha256")
    if not isinstance(run_manifest_sha256,str) or not _SHA.fullmatch(run_manifest_sha256): raise ContractError("invalid_run_manifest_sha256")
    obj={"schema_version":1,"record_kind":COMMAND_LOCK_KIND,"hash_profile":HASH_PROFILE,"task_id":TASK_ID,"training_plan_sha256":plan_sha256,"run_manifest_sha256":run_manifest_sha256,"arm_id":arm_id,"seed":seed,"profile":profile,"model_scope":"surrogate","argv":argv,"command_sha256":canonical_sha256(argv),"automatic_fallback":False,"g1_rerun":False}
    return seal(obj,"lock_sha256")

def validate_manager_authorization(auth:Any,*,lock:dict[str,Any])->list[str]:
    """Validate Worker06 AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1.

    Worker06 binds paid authority to task + frozen run-manifest + compute
    profile + economic ceilings. Worker03's command lock separately binds argv.
    """
    e=[]
    if not isinstance(auth,dict):
        return ["authorization_not_object"]
    exact={
        "schema_version","authorization_kind","hash_profile","authorization_id",
        "run_task_id","run_manifest_sha256","profile_id","compute_origin",
        "max_billed_seconds","max_total_cost_usd","max_hourly_rate_usd",
        "max_artifact_egress_bytes","single_use","authorization_sha256",
    }
    if set(auth)!=exact:
        e.append("authorization_schema")
    if auth.get("schema_version")!=1:
        e.append("authorization_schema_version")
    if auth.get("authorization_kind")!=AUTH_KIND:
        e.append("authorization_kind")
    if auth.get("hash_profile")!=HASH_PROFILE:
        e.append("authorization_hash_profile")
    if not isinstance(auth.get("authorization_id"),str) or not auth["authorization_id"]:
        e.append("authorization_id")
    if auth.get("run_task_id")!=TASK_ID:
        e.append("authorization_task")
    if auth.get("run_manifest_sha256")!=lock.get("run_manifest_sha256"):
        e.append("authorization_plan")
    if auth.get("profile_id")!=lock.get("profile"):
        e.append("authorization_profile")
    if auth.get("compute_origin")!="paid_manager_authorized":
        e.append("authorization_compute_origin")
    if type(auth.get("max_billed_seconds")) is not int or not (1<=auth["max_billed_seconds"]<=604800):
        e.append("authorization_max_billed_seconds")
    for fld in ("max_total_cost_usd","max_hourly_rate_usd"):
        val=auth.get(fld)
        try:
            n=float(val)
        except (TypeError,ValueError):
            n=-1
        if not isinstance(val,str) or not val or n<0:
            e.append("authorization_"+fld)
    if type(auth.get("max_artifact_egress_bytes")) is not int or auth["max_artifact_egress_bytes"]<0:
        e.append("authorization_max_artifact_egress_bytes")
    if auth.get("single_use") is not True:
        e.append("authorization_single_use")
    if not verify_self_digest(auth,"authorization_sha256"):
        e.append("authorization_self_digest")
    return e

def run_locked(lock:dict[str,Any],*,paid:bool,authorization:dict[str,Any]|None,cwd:Path)->int:
    if not verify_self_digest(lock,"lock_sha256") or lock.get("g1_rerun") is not False: raise ContractError("invalid_command_lock")
    if paid:
        if authorization is None: raise ContractError("paid_run_requires_exact_manager_authorization")
        errors=validate_manager_authorization(authorization,lock=lock)
        if errors: raise ContractError("FAIL-CLOSED:"+";".join(errors))
    argv=lock.get("argv")
    if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv): raise ContractError("invalid_argv")
    return int(subprocess.run(argv,cwd=str(cwd)).returncode)

def main()->int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("freeze-plan")
    for name in ("method-spec","training-shard-manifest","training-shard","training-pack","split","w02-binding","w05-law"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    try:
        plan=freeze_plan(method_spec_path=args.method_spec,shard_manifest_path=args.training_shard_manifest,shard_path=args.training_shard,pack_path=args.training_pack,split_path=args.split,binding_path=args.w02_binding,law_path=args.w05_law,output=args.output)
        print(json.dumps({"status":"PASS","plan_sha256":plan["plan_sha256"]},sort_keys=True)); return 0
    except Exception as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":f"{type(exc).__name__}: {exc}"},sort_keys=True)); return 2

if __name__=="__main__": raise SystemExit(main())
