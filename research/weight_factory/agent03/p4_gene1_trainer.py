#!/usr/bin/env python3
"""AQLEVON Worker 03 — P4 Gene #1 physical trainer control plane.

This module prepares and locks the Worker-01 method specs + Worker-02 training
shard before any surrogate/27B execution.  It deliberately cannot consume
sealed evaluation assets and cannot authorize paid compute or a 27B run.

Physical method-specific training is allowed only after exact P4 dependencies
exist. G1 is complete and this module has no G1 command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
TASK_ID = "P4-A03-GENE1-PHYSICAL-TRAINER"
SURROGATE_MODEL = "Qwen/Qwen3.5-4B-Base"
SURROGATE_REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
CANONICAL_MODEL = "Qwen/Qwen3.8-27B"
CANONICAL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
G1_COMMIT = "4a7a5fa2c2c4ba5f291564251c290e2c416ce6ec"
METHOD_SPEC_KIND = "AQLEVON_P4_GENE1_METHOD_TOURNAMENT_SPEC_V1"
FROZEN_PLAN_KIND = "AQLEVON_P4_GENE1_FROZEN_TRAINING_PLAN_V1"
RUN_RECEIPT_KIND = "AQLEVON_P4_GENE1_TRAINING_RUN_RECEIPT_V1"
AUTH_KIND = "AQLEVON_MANAGER_PAID_RUN_AUTHORIZATION_V1"
TRAINING_SHARD_KIND = "AQLEVON_TRAINING_SHARD_MANIFEST_V1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_EVAL_TOKENS = (
    "sealed_eval", "sealed-eval", "sealed_transfer", "hidden_canary",
    "hidden_answer", "protected_eval", "private_eval", "eval_answer",
)
SUPPORTED_METHODS = {
    "SFT_LORA_CONTROL",
    "RLVR_CONTROL",
    "SDPO_RICH_FEEDBACK",
    "OPSA_TEACHER_FREE",
    "SEQUENTIAL_OPD_THEN_RLVR",
    "VERIFIER_TRIGGERED_TRD",
}

class ContractError(ValueError):
    pass


def _sha256_bytes(data: bytes) -> str:
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
        raise ContractError("direct_float_forbidden_in_authoritative_payload")
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
    return _sha256_bytes(canonical_bytes(value))


def seal(obj: dict[str, Any], digest_field: str) -> dict[str, Any]:
    out = dict(obj)
    out[digest_field] = ""
    payload = {k: out[k] for k in out if k != digest_field}
    out[digest_field] = canonical_sha256(payload)
    return out


def verify_self_digest(obj: dict[str, Any], field: str) -> bool:
    value = obj.get(field)
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        return False
    return canonical_sha256({k: obj[k] for k in obj if k != field}) == value


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_eval_reference(value: Any, path: str = "root") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            kl = str(k).casefold()
            if any(tok in kl for tok in FORBIDDEN_EVAL_TOKENS):
                hits.append(f"{path}.{k}")
            hits.extend(_forbidden_eval_reference(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            hits.extend(_forbidden_eval_reference(v, f"{path}[{i}]"))
    elif isinstance(value, str):
        s = value.casefold().replace(" ", "_")
        if any(tok in s for tok in FORBIDDEN_EVAL_TOKENS):
            hits.append(path)
    return hits


def validate_method_spec(spec: Any) -> list[str]:
    e: list[str] = []
    if not isinstance(spec, dict):
        return ["method_spec_not_object"]
    if spec.get("schema_version") != 1:
        e.append("method_spec_schema_version")
    if spec.get("spec_kind") != METHOD_SPEC_KIND:
        e.append("method_spec_kind")
    if spec.get("hash_profile") != HASH_PROFILE:
        e.append("method_spec_hash_profile")
    if spec.get("worker_id") != "01" or spec.get("task_id") != "P4-A01-METHOD-TOURNAMENT-DIRECTOR":
        e.append("method_spec_authority_identity")
    if not verify_self_digest(spec, "spec_sha256"):
        e.append("method_spec_self_digest")
    arms = spec.get("arms")
    if not isinstance(arms, list) or not 1 <= len(arms) <= 3:
        e.append("method_spec_arm_count_must_be_1_to_3")
        arms = []
    seen = set()
    for i, arm in enumerate(arms):
        if not isinstance(arm, dict):
            e.append(f"arm_{i}_not_object"); continue
        aid = arm.get("arm_id")
        method = arm.get("method")
        if not isinstance(aid, str) or not aid or aid in seen:
            e.append(f"arm_{i}_invalid_or_duplicate_id")
        seen.add(aid)
        if method not in SUPPORTED_METHODS:
            e.append(f"arm_{i}_unsupported_method")
        for fld in ("seed_policy", "budget", "optimizer", "stop_conditions", "runner_parameters"):
            if fld not in arm:
                e.append(f"arm_{i}_missing_{fld}")
        if _forbidden_eval_reference(arm):
            e.append(f"arm_{i}_contains_forbidden_eval_reference")
    return e


def validate_training_shard(manifest: Any, shard_bytes: bytes) -> list[str]:
    e: list[str] = []
    if not isinstance(manifest, dict):
        return ["training_shard_manifest_not_object"]
    required = {
        "schema_version","manifest_kind","hash_profile","manifest_id","admission_policy_id",
        "admission_policy_sha256","source_registry_snapshot_sha256",
        "protected_training_contamination_manifest_sha256",
        "protected_training_contamination_receipt_sha256","admission_gate_code_sha256",
        "shard_digest_scheme","shard_file_sha256","byte_size","row_count",
        "admitted_record_content_digest_scheme","admitted_record_content_digest_sha256",
        "decision_log_scheme","decision_log_sha256","decision_counts",
        "provenance_license_evidence_bundle_sha256","source_revision_encoding_scheme",
        "contamination_evidence_scheme","language_audit_applicability_scheme",
        "language_audit_receipt_sha256","created_from","manifest_sha256",
    }
    missing=sorted(required-set(manifest)); extra=sorted(set(manifest)-required)
    if missing: e.append("training_shard_manifest_missing:"+",".join(missing))
    if extra: e.append("training_shard_manifest_extra:"+",".join(extra))
    if manifest.get("schema_version") != 1:
        e.append("training_shard_schema_version")
    if manifest.get("manifest_kind") != TRAINING_SHARD_KIND:
        e.append("training_shard_manifest_kind")
    if manifest.get("hash_profile") != HASH_PROFILE:
        e.append("training_shard_hash_profile")
    if not isinstance(manifest.get("manifest_id"),str) or not manifest["manifest_id"].startswith("aqlevon-training-shard-v1:"):
        e.append("training_shard_manifest_id")
    if not verify_self_digest(manifest, "manifest_sha256"):
        e.append("training_shard_manifest_self_digest")
    for fld in ("admission_policy_sha256","source_registry_snapshot_sha256","protected_training_contamination_manifest_sha256","admission_gate_code_sha256","shard_file_sha256","admitted_record_content_digest_sha256","decision_log_sha256","provenance_license_evidence_bundle_sha256"):
        if not isinstance(manifest.get(fld),str) or not _SHA.fullmatch(manifest[fld]): e.append("training_shard_invalid_sha256:"+fld)
    counts=manifest.get("decision_counts")
    if not isinstance(counts,dict) or set(counts)!={"ADMIT","QUARANTINE","DENY"}: e.append("training_shard_decision_counts")
    elif counts.get("ADMIT") != manifest.get("row_count"): e.append("training_shard_admit_count_mismatch")
    if not isinstance(manifest.get("created_from"),list) or not manifest["created_from"]: e.append("training_shard_created_from")
    if manifest.get("shard_file_sha256") != _sha256_bytes(shard_bytes):
        e.append("training_shard_bytes_hash_mismatch")
    if manifest.get("byte_size") != len(shard_bytes):
        e.append("training_shard_byte_size_mismatch")
    try:
        text = shard_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return e + ["training_shard_not_utf8"]
    rows = [line for line in text.splitlines() if line.strip()]
    if manifest.get("row_count") != len(rows) or not rows:
        e.append("training_shard_row_count_mismatch")
    for i, line in enumerate(rows):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            e.append(f"training_row_{i}_invalid_json")
            continue
        if not isinstance(row, dict):
            e.append(f"training_row_{i}_not_object")
            continue
        if row.get("row_kind") != "AQLEVON_TRAINING_SHARD_ROW_V1":
            e.append(f"training_row_{i}_kind")
        if _forbidden_eval_reference(row):
            e.append(f"training_row_{i}_forbidden_eval_reference")
        if not isinstance(row.get("prompt"), str) or "answer" not in row:
            e.append(f"training_row_{i}_missing_trainable_fields")
    return e


def freeze_plan(method_spec_path: Path, shard_manifest_path: Path, shard_path: Path, out: Path) -> dict[str, Any]:
    spec = _load(method_spec_path)
    manifest = _load(shard_manifest_path)
    shard_bytes = shard_path.read_bytes()
    errors = validate_method_spec(spec) + validate_training_shard(manifest, shard_bytes)
    if errors:
        raise ContractError("FAIL-CLOSED:" + ";".join(errors))
    plan = {
        "schema_version": 1,
        "plan_kind": FROZEN_PLAN_KIND,
        "hash_profile": HASH_PROFILE,
        "task_id": TASK_ID,
        "method_spec_sha256": spec["spec_sha256"],
        "method_spec_file_sha256": sha256_file(method_spec_path),
        "training_shard_manifest_sha256": manifest["manifest_sha256"],
        "training_shard_manifest_file_sha256": sha256_file(shard_manifest_path),
        "training_shard_file_sha256": manifest["shard_file_sha256"],
        "training_shard_file_bytes_sha256": sha256_file(shard_path),
        "surrogate_model": {"repo": SURROGATE_MODEL, "revision": SURROGATE_REVISION, "precision": "bf16"},
        "canonical_model": {"repo": CANONICAL_MODEL, "revision": CANONICAL_REVISION, "precision": "bf16"},
        "g1_status": "ALREADY_PASSED_DO_NOT_RERUN",
        "g1_source_commit": G1_COMMIT,
        "arms": spec["arms"],
        "sealed_eval_consumed": False,
        "automatic_recipe_mutation": False,
        "automatic_budget_mutation": False,
        "automatic_model_revision_mutation": False,
        "capability_claim_authority": "WORKER05_EVIDENCE_PLUS_MANAGER_ACCEPTANCE_ONLY",
    }
    plan = seal(plan, "plan_sha256")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def validate_manager_authorization(auth: Any, *, expected_command_sha256: str, expected_profile: str, expected_plan_sha256: str) -> list[str]:
    e: list[str] = []
    if not isinstance(auth, dict):
        return ["authorization_not_object"]
    if auth.get("schema_version") != 1 or auth.get("authorization_kind") != AUTH_KIND:
        e.append("authorization_identity")
    if auth.get("hash_profile") != HASH_PROFILE:
        e.append("authorization_hash_profile")
    if not verify_self_digest(auth, "authorization_sha256"):
        e.append("authorization_self_digest")
    if auth.get("status") != "AUTHORIZED":
        e.append("authorization_status")
    if auth.get("task_id") != TASK_ID:
        e.append("authorization_task_id")
    if auth.get("training_plan_sha256") != expected_plan_sha256:
        e.append("authorization_plan_binding")
    if auth.get("command_sha256") != expected_command_sha256:
        e.append("authorization_command_binding")
    if auth.get("profile") != expected_profile:
        e.append("authorization_profile_binding")
    for fld in ("manager_authority_id", "provider", "max_budget_usd", "max_wall_seconds", "authorized_at_utc"):
        if fld not in auth:
            e.append(f"authorization_missing_{fld}")
    return e


def build_command_lock(command: list[str], *, plan_sha256: str, arm_id: str, profile: str, model_scope: str) -> dict[str, Any]:
    if model_scope not in {"surrogate", "canonical_27b"}:
        raise ContractError("invalid_model_scope")
    payload = {
        "schema_version": 1,
        "record_kind": "AQLEVON_P4_GENE1_COMMAND_LOCK_V1",
        "hash_profile": HASH_PROFILE,
        "task_id": TASK_ID,
        "training_plan_sha256": plan_sha256,
        "arm_id": arm_id,
        "profile": profile,
        "model_scope": model_scope,
        "argv": command,
        "command_sha256": canonical_sha256(command),
        "automatic_fallback": False,
        "g1_rerun": False,
    }
    return seal(payload, "lock_sha256")


def run_locked(command_lock: dict[str, Any], *, authorization: dict[str, Any] | None, paid: bool, cwd: Path) -> int:
    if command_lock.get("g1_rerun") is not False:
        raise ContractError("G1_rerun_forbidden")
    if not verify_self_digest(command_lock, "lock_sha256"):
        raise ContractError("command_lock_self_digest_invalid")
    if command_lock.get("training_plan_sha256") is None:
        raise ContractError("command_lock_missing_plan")
    if paid:
        if authorization is None:
            raise ContractError("paid_run_requires_manager_authorization")
        errors = validate_manager_authorization(
            authorization,
            expected_command_sha256=command_lock["command_sha256"],
            expected_profile=command_lock["profile"],
            expected_plan_sha256=command_lock["training_plan_sha256"],
        )
        if errors:
            raise ContractError("FAIL-CLOSED:" + ";".join(errors))
    elif authorization is not None and authorization.get("status") == "AUTHORIZED":
        pass
    argv = command_lock.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        raise ContractError("invalid_locked_argv")
    cp = subprocess.run(argv, cwd=str(cwd))
    return int(cp.returncode)


def build_run_receipt(*, plan_sha256: str, command_lock: dict[str, Any], candidate_manifest_sha256: str, training_run_artifact_sha256: str, runtime_receipt_sha256: str | None, status: str) -> dict[str, Any]:
    if status not in {"COMPLETED_ARTIFACT_PENDING_EVALUATION", "FAILED", "INVALID"}:
        raise ContractError("invalid_run_receipt_status")
    for label, val in (("plan_sha256",plan_sha256),("candidate_manifest_sha256",candidate_manifest_sha256),("training_run_artifact_sha256",training_run_artifact_sha256)):
        if not isinstance(val, str) or not _SHA.fullmatch(val):
            raise ContractError(f"invalid_{label}")
    if runtime_receipt_sha256 is not None and not _SHA.fullmatch(runtime_receipt_sha256):
        raise ContractError("invalid_runtime_receipt_sha256")
    rec = {
        "schema_version": 1,
        "receipt_kind": RUN_RECEIPT_KIND,
        "hash_profile": HASH_PROFILE,
        "task_id": TASK_ID,
        "training_plan_sha256": plan_sha256,
        "command_lock_sha256": command_lock["lock_sha256"],
        "command_sha256": command_lock["command_sha256"],
        "candidate_artifact_manifest_sha256": candidate_manifest_sha256,
        "training_run_artifact_sha256": training_run_artifact_sha256,
        "runtime_receipt_sha256": runtime_receipt_sha256,
        "status": status,
        "evaluation_status": "NOT_EVALUATED_BY_WORKER05",
        "capability_gain_claim": False,
        "authority_boundary": "TRAINING_ARTIFACT_ONLY_WORKER05_PLUS_MANAGER_REQUIRED_FOR_GAIN",
    }
    return seal(rec, "receipt_sha256")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze-plan")
    f.add_argument("--method-spec", type=Path, required=True)
    f.add_argument("--training-shard-manifest", type=Path, required=True)
    f.add_argument("--training-shard", type=Path, required=True)
    f.add_argument("--output", type=Path, required=True)
    v = sub.add_parser("validate-inputs")
    v.add_argument("--method-spec", type=Path, required=True)
    v.add_argument("--training-shard-manifest", type=Path, required=True)
    v.add_argument("--training-shard", type=Path, required=True)
    args = ap.parse_args()
    try:
        if args.command == "freeze-plan":
            plan = freeze_plan(args.method_spec,args.training_shard_manifest,args.training_shard,args.output)
            print(json.dumps({"status":"PASS","plan_sha256":plan["plan_sha256"]},sort_keys=True))
            return 0
        spec=_load(args.method_spec); man=_load(args.training_shard_manifest); shard=args.training_shard.read_bytes()
        errors=validate_method_spec(spec)+validate_training_shard(man,shard)
        if errors:
            raise ContractError(";".join(errors))
        print(json.dumps({"status":"PASS","method_spec_sha256":spec["spec_sha256"],"training_shard_manifest_sha256":man["manifest_sha256"]},sort_keys=True))
        return 0
    except (OSError,json.JSONDecodeError,ContractError) as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(exc)},sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
