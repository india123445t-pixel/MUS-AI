#!/usr/bin/env python3
"""AQLEVON P4.1 Worker-05 surrogate evaluation hot path.

This module does NOT change the frozen P4 evaluation law. It closes the
candidate-ingestion gap before hidden evaluation compute is spent:

W03 physical artifact -> exact identity/provenance ingest -> P4 candidate
registration -> Manager-verifiable freeze -> hidden evaluation -> existing P4
reality/tournament decision.

It is fail-closed and never confers promotion authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import gene1_reality_tournament_v1 as p4
from evaluation_decision_receipt_v1 import (
    HASH_PROFILE,
    canonical_p2_sha256,
    valid_sha256,
    verify_p2_self_digest,
    validate_candidate_artifact_manifest,
)

HOTPATH_KIND = "AQLEVON_P4_1_SURROGATE_CANDIDATE_INGEST_RECEIPT_V1"
HOTPATH_AUTHORITY_KIND = "AQLEVON_P4_1_INGEST_NOT_EVALUATION_OR_PROMOTION_AUTHORITY_V1"
HOTPATH_REGISTRATION_KIND = "AQLEVON_P4_1_SINGLE_CANDIDATE_REGISTRATION_V1"
HOTPATH_FREEZE_KIND = "AQLEVON_P4_1_SINGLE_CANDIDATE_FREEZE_VERIFICATION_V1"
W03_RUN_MANIFEST_KIND = "AQLEVON_P4_SURROGATE_RUN_MANIFEST_V1"
W03_COMMAND_LOCK_KIND = "AQLEVON_P4_GENE1_COMMAND_LOCK_V1"
W03_TASK_ID = "P4-A03-GENE1-PHYSICAL-TRAINER"
W03_TESTED_SOURCE_COMMIT = "4c56b8f738c51d57de981e9ae9a8a1a5f4e887ab"
A1_ARM_ID = "P4_A1_RLVR_CONTROL"
A1_SLOT = "challenger_a"
A1_SEED = 1701
A1_PROFILE = "p4-surrogate-1x24"
A1_PLAN_SHA256 = "3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095"
A1_RUN_MANIFEST_SHA256 = "7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45"
A1_COMMAND_SHA256 = "3ad2fd2cd5303e1eb4ea71f3e25edf07d38269df1b5b3c8b6e98c8553e017400"
A1_COMMAND_LOCK_SHA256 = "f1d05b53d0e00b07f7f4d60c90a6bf489f4cd2bd118b2b6a6b38c66026cee44e"
SURROGATE_REPO = "Qwen/Qwen3.5-4B-Base"
SURROGATE_REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
W02_TRAINING_MANIFEST_SHA256 = p4.W02_TRAINING_SHARD_MANIFEST_SHA256

ALLOWED_ARTIFACT_STAGES = {
    "probe_only", "reproducible_gene", "promotion_candidate",
    "merge_candidate", "release_candidate",
}
FORBIDDEN_TRAINING_KEYS = {
    "sealed_eval_plaintext", "eval_secret", "private_eval", "hidden_answer",
    "hidden_solution", "canary_plaintext", "sealed_test_body", "protected_answer",
    "protected_solution", "expected_answer", "expected_output",
}
PRIVATE_FILE_HASHES = {
    p4.W02_EVAL_SECRET_FILE_SHA256,
    p4.W02_SEALED_EVAL_PLAINTEXT_FILE_SHA256,
}
PRE_SCORE_FORBIDDEN_KEYS = set(p4.FORBIDDEN_PRE_SCORE_KEYS) | set(p4.FORBIDDEN_PLAINTEXT_KEYS)

STATE_INVALID_CANDIDATE = "INVALID_CANDIDATE"
STATE_INVALID_EVALUATION = "INVALID_EVALUATION"
STATE_READY_TO_REGISTER = "READY_TO_REGISTER_PRE_SCORE"
STATE_READY_FOR_HIDDEN_EVAL = "READY_FOR_HIDDEN_EVALUATION"
STATE_REJECTED_ARM = "REJECTED_ARM"
STATE_EVIDENCE_READY = "EVIDENCE_SUPPORTS_MANAGER_RECIPE_DECISION"


class HotPathError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _exact_keys(obj: Any, required: set[str]) -> bool:
    return isinstance(obj, dict) and set(obj) == required


def _seal(body: dict[str, Any], field: str) -> dict[str, Any]:
    out = dict(body)
    out.pop(field, None)
    out[field] = canonical_p2_sha256(out)
    return out


def _canonical_legacy_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _collect_key_values(value: Any, key: str) -> list[Any]:
    out: list[Any] = []
    if isinstance(value, dict):
        for k, child in value.items():
            if k == key:
                out.append(child)
            out.extend(_collect_key_values(child, key))
    elif isinstance(value, list):
        for child in value:
            out.extend(_collect_key_values(child, key))
    return out


def _require_unique_value(value: Any, keys: tuple[str, ...], expected: Any, label: str) -> list[str]:
    observed: list[Any] = []
    for key in keys:
        observed.extend(_collect_key_values(value, key))
    if not observed:
        return [f"training_receipt_missing_binding:{label}"]
    if any(item != expected for item in observed):
        return [f"training_receipt_binding_mismatch:{label}"]
    return []


def _scan_forbidden_training_material(value: Any, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if any(token in normalized for token in FORBIDDEN_TRAINING_KEYS):
                errors.append(f"forbidden_training_material_key:{path}.{key}")
            errors.extend(_scan_forbidden_training_material(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            errors.extend(_scan_forbidden_training_material(child, f"{path}[{i}]"))
    elif isinstance(value, str) and value in PRIVATE_FILE_HASHES:
        errors.append(f"private_eval_file_identity_leaked:{path}")
    return errors


def _scan_pre_score_leakage(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in PRE_SCORE_FORBIDDEN_KEYS:
                errors.append(f"pre_score_value_forbidden:{path}.{key}")
            errors.extend(_scan_pre_score_leakage(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            errors.extend(_scan_pre_score_leakage(child, f"{path}[{i}]"))
    return errors


def validate_a1_run_manifest(run_manifest: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(run_manifest, dict):
        return ["run_manifest_not_object"]
    if run_manifest.get("manifest_kind") != W03_RUN_MANIFEST_KIND:
        errors.append("run_manifest_kind")
    if run_manifest.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(run_manifest, "manifest_sha256"):
        errors.append("run_manifest_self_digest")
    if run_manifest.get("manifest_sha256") != A1_RUN_MANIFEST_SHA256:
        errors.append("run_manifest_identity")
    expected = {
        "task_id": W03_TASK_ID,
        "arm_id": A1_ARM_ID,
        "seed": A1_SEED,
        "profile_id": A1_PROFILE,
        "training_plan_sha256": A1_PLAN_SHA256,
        "command_sha256": A1_COMMAND_SHA256,
        "worker01_method_spec_canonical_sha256": p4.W01_METHOD_TOURNAMENT_SPEC_SHA256,
        "worker02_training_manifest_sha256": W02_TRAINING_MANIFEST_SHA256,
        "worker02_training_shard_sha256": p4.W02_TRAINING_SHARD_FILE_SHA256,
        "worker02_training_visible_pack_sha256": p4.W02_TRAINING_VISIBLE_PACK_SHA256,
        "worker02_split_sha256": p4.W02_SPLIT_COMMITMENT_SHA256,
        "worker02_sealed_eval_commitment_sha256": p4.W02_SEALED_EVAL_COMMITMENT_SHA256,
        "worker05_evaluation_law_sha256": p4.frozen_gene1_evaluation_law()["law_sha256"],
        "worker05_sampling_profile_sha256": p4.frozen_gene1_evaluation_law()["sampling_profile_sha256"],
        "worker06_compute_profile": A1_PROFILE,
        "sealed_eval_consumed": False,
        "g1_rerun": False,
        "automatic_fallback": False,
        "paid_compute_requires_manager_authorization": True,
        "capability_gain_claim": False,
    }
    for key, wanted in expected.items():
        if run_manifest.get(key) != wanted:
            errors.append(f"run_manifest_binding:{key}")
    model = run_manifest.get("student_model") or {}
    if model != {"repo": SURROGATE_REPO, "revision": SURROGATE_REVISION, "precision": "bf16", "quantization": "none"}:
        errors.append("run_manifest_student_model")
    budget = run_manifest.get("budget") or {}
    if budget.get("optimizer_updates") != 12 or budget.get("prompts_per_update") != 4 or budget.get("rollouts_per_prompt") != 4:
        errors.append("run_manifest_budget")
    data_prep = run_manifest.get("data_preparation") or {}
    if data_prep.get("sealed_eval_consumed") is not False:
        errors.append("run_manifest_data_prep_sealed_eval")
    errors.extend(_scan_forbidden_training_material(run_manifest, "run_manifest"))
    errors.extend(_scan_pre_score_leakage(run_manifest, "run_manifest"))
    return sorted(set(errors))


def validate_a1_command_lock(command_lock: Any, *, run_manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(command_lock, dict):
        return ["command_lock_not_object"]
    if command_lock.get("record_kind") != W03_COMMAND_LOCK_KIND:
        errors.append("command_lock_kind")
    if command_lock.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(command_lock, "lock_sha256"):
        errors.append("command_lock_self_digest")
    if command_lock.get("lock_sha256") != A1_COMMAND_LOCK_SHA256:
        errors.append("command_lock_identity")
    expected = {
        "task_id": W03_TASK_ID,
        "training_plan_sha256": A1_PLAN_SHA256,
        "run_manifest_sha256": A1_RUN_MANIFEST_SHA256,
        "arm_id": A1_ARM_ID,
        "seed": A1_SEED,
        "profile": A1_PROFILE,
        "model_scope": "surrogate",
        "command_sha256": A1_COMMAND_SHA256,
        "automatic_fallback": False,
        "g1_rerun": False,
    }
    for key, wanted in expected.items():
        if command_lock.get(key) != wanted:
            errors.append(f"command_lock_binding:{key}")
    if run_manifest.get("command_sha256") != command_lock.get("command_sha256"):
        errors.append("command_lock_run_manifest_command_mismatch")
    argv = command_lock.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        errors.append("command_lock_argv")
    elif canonical_p2_sha256(argv) != A1_COMMAND_SHA256:
        errors.append("command_lock_argv_command_sha")
    errors.extend(_scan_forbidden_training_material(command_lock, "command_lock"))
    errors.extend(_scan_pre_score_leakage(command_lock, "command_lock"))
    return sorted(set(errors))


def _candidate_manifest_id(candidate: dict[str, Any]) -> str:
    semantic = {k: v for k, v in candidate.items() if k not in {"manifest_id", "manifest_sha256"}}
    return "aqlevon-candidate-artifact-v1:sha256:" + canonical_p2_sha256({
        "scheme": "AQLEVON_CANDIDATE_ARTIFACT_IDENTITY_V1",
        "manifest": semantic,
    })


def validate_a1_candidate_manifest(candidate: Any) -> list[str]:
    errors = list(validate_candidate_artifact_manifest(candidate))
    if not isinstance(candidate, dict):
        return sorted(set(errors + ["candidate_manifest_not_object"]))
    expected_keys = {
        "schema_version", "manifest_kind", "manifest_id", "hash_profile", "artifact_type", "artifact_stage",
        "base", "tokenizer_sha256", "config_sha256", "training_shard_manifest_sha256",
        "training_run_receipt_sha256", "merge_recipe_sha256", "parameter_layout_sha256", "topology_class",
        "artifact_files", "artifact_file_tree_sha256", "adapter_state_sha256", "checkpoint_state_sha256",
        "parent_candidate_artifact_manifest_sha256", "environment_toolchain_manifest_sha256", "manifest_sha256",
    }
    if set(candidate) != expected_keys:
        errors.append("candidate_manifest_schema")
    if candidate.get("artifact_type") != "adapter":
        errors.append("candidate_artifact_type")
    if candidate.get("artifact_stage") not in ALLOWED_ARTIFACT_STAGES:
        errors.append("candidate_artifact_stage")
    base = candidate.get("base") or {}
    if base.get("repo") != SURROGATE_REPO or base.get("revision") != SURROGATE_REVISION:
        errors.append("candidate_base_identity")
    if candidate.get("training_shard_manifest_sha256") != W02_TRAINING_MANIFEST_SHA256:
        errors.append("candidate_training_shard_binding")
    if not valid_sha256(candidate.get("training_run_receipt_sha256")):
        errors.append("candidate_training_receipt_identity")
    if candidate.get("merge_recipe_sha256") is not None or candidate.get("checkpoint_state_sha256") is not None:
        errors.append("candidate_adapter_semantics")
    if not valid_sha256(candidate.get("adapter_state_sha256")):
        errors.append("candidate_adapter_state_identity")
    for field in ("tokenizer_sha256", "config_sha256", "parameter_layout_sha256", "environment_toolchain_manifest_sha256", "artifact_file_tree_sha256"):
        if not valid_sha256(candidate.get(field)):
            errors.append(f"candidate_hash:{field}")
    files = candidate.get("artifact_files")
    if not isinstance(files, list) or not files:
        errors.append("candidate_artifact_files")
    else:
        paths: list[str] = []
        for item in files:
            if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
                errors.append("candidate_artifact_file_entry")
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in path.split("/"):
                errors.append("candidate_artifact_file_path")
            else:
                paths.append(path)
            if type(item.get("size")) is not int or item.get("size", -1) < 0 or not valid_sha256(item.get("sha256")):
                errors.append("candidate_artifact_file_identity")
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            errors.append("candidate_artifact_file_order")
        if _canonical_legacy_sha(files) != candidate.get("artifact_file_tree_sha256"):
            errors.append("candidate_artifact_file_tree")
    if candidate.get("manifest_id") != _candidate_manifest_id(candidate):
        errors.append("candidate_manifest_id")
    errors.extend(_scan_forbidden_training_material(candidate, "candidate_manifest"))
    errors.extend(_scan_pre_score_leakage(candidate, "candidate_manifest"))
    return sorted(set(errors))


def validate_training_receipt(training_receipt_bytes: bytes, *, candidate: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if sha256_bytes(training_receipt_bytes) != candidate.get("training_run_receipt_sha256"):
        errors.append("training_receipt_raw_sha_mismatch")
    try:
        receipt = json.loads(training_receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, sorted(set(errors + ["training_receipt_not_utf8_json"]))
    if not isinstance(receipt, dict):
        return None, sorted(set(errors + ["training_receipt_not_object"]))
    errors.extend(_scan_forbidden_training_material(receipt, "training_receipt"))
    errors.extend(_scan_pre_score_leakage(receipt, "training_receipt"))
    errors.extend(_require_unique_value(receipt, ("run_manifest_sha256",), A1_RUN_MANIFEST_SHA256, "run_manifest"))
    errors.extend(_require_unique_value(receipt, ("training_plan_sha256", "plan_sha256"), A1_PLAN_SHA256, "training_plan"))
    errors.extend(_require_unique_value(receipt, ("arm_id",), A1_ARM_ID, "arm_id"))
    errors.extend(_require_unique_value(receipt, ("seed", "training_seed"), A1_SEED, "seed"))
    errors.extend(_require_unique_value(receipt, ("sealed_eval_consumed",), False, "sealed_eval_consumed"))
    errors.extend(_require_unique_value(receipt, ("capability_gain_claim",), False, "capability_gain_claim"))
    errors.extend(_require_unique_value(receipt, ("reload_hash_match",), True, "reload_hash_match"))
    errors.extend(_require_unique_value(receipt, ("optimizer_updates",), 12, "optimizer_updates"))
    changed = _collect_key_values(receipt, "changed_elements")
    if not changed or any(type(x) is not int or x <= 0 for x in changed):
        errors.append("training_receipt_nonzero_delta_missing")
    candidate_state = candidate.get("adapter_state_sha256")
    state_values: list[Any] = []
    for key in ("adapter_state_sha256", "saved_adapter_state_sha256", "post_state_sha256", "reloaded_adapter_state_sha256"):
        state_values.extend(_collect_key_values(receipt, key))
    if candidate_state not in state_values:
        errors.append("training_receipt_candidate_state_mismatch")
    return receipt, sorted(set(errors))


def validate_surrogate_stage_binding(stage_binding: Any, *, law: dict[str, Any]) -> list[str]:
    errors = list(p4.validate_stage_binding(stage_binding, law=law))
    if not isinstance(stage_binding, dict):
        return sorted(set(errors + ["stage_binding_not_object"]))
    if stage_binding.get("stage") != "surrogate" or stage_binding.get("round_mode") != "initial12":
        errors.append("stage_binding_not_a1_initial12")
    if stage_binding.get("sampling_profile_sha256") != law.get("sampling_profile_sha256"):
        errors.append("stage_binding_sampling_profile")
    for field in ("harness_manifest_sha256", "task_factory_manifest_sha256", "hidden_canary_manifest_sha256", "anti_shortcut_manifest_sha256", "metamorphic_manifest_sha256", "reality_policy_sha256"):
        if not valid_sha256(stage_binding.get(field)):
            errors.append(f"stage_binding_eval_identity:{field}")
    return sorted(set(errors))


def build_a1_ingest_receipt(
    *, law: dict[str, Any], stage_binding: dict[str, Any], run_manifest: dict[str, Any], command_lock: dict[str, Any],
    candidate: dict[str, Any], training_receipt_bytes: bytes, recipe_spec_sha256: str,
    compute_receipt_sha256: str, training_budget_manifest_sha256: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if law != p4.frozen_gene1_evaluation_law():
        errors.append("frozen_law_byte_semantics_mismatch")
    errors.extend(p4.validate_evaluation_law(law))
    errors.extend(validate_surrogate_stage_binding(stage_binding, law=law))
    errors.extend(validate_a1_run_manifest(run_manifest))
    errors.extend(validate_a1_command_lock(command_lock, run_manifest=run_manifest))
    errors.extend(validate_a1_candidate_manifest(candidate))
    receipt, receipt_errors = validate_training_receipt(training_receipt_bytes, candidate=candidate)
    errors.extend(receipt_errors)
    for field, value in (
        ("recipe_spec_sha256", recipe_spec_sha256),
        ("compute_receipt_sha256", compute_receipt_sha256),
        ("training_budget_manifest_sha256", training_budget_manifest_sha256),
    ):
        if not valid_sha256(value):
            errors.append(f"invalid_input_hash:{field}")
    if training_budget_manifest_sha256 != stage_binding.get("matched_training_budget_manifest_sha256"):
        errors.append("training_budget_stage_binding_mismatch")
    if errors:
        raise HotPathError(STATE_INVALID_CANDIDATE + ":" + ";".join(sorted(set(errors))))
    body = {
        "schema_version": 1,
        "receipt_kind": HOTPATH_KIND,
        "hash_profile": HASH_PROFILE,
        "task_id": "P4.1-A05-SURROGATE-EVAL-HOTPATH",
        "parent_task_id": "P4-A05-GENE1-REALITY-TOURNAMENT",
        "state": STATE_READY_TO_REGISTER,
        "law_sha256": law["law_sha256"],
        "stage_binding_sha256": stage_binding["stage_binding_sha256"],
        "candidate_slot": A1_SLOT,
        "arm_id": A1_ARM_ID,
        "training_seed": A1_SEED,
        "w03_tested_source_commit": W03_TESTED_SOURCE_COMMIT,
        "training_plan_sha256": A1_PLAN_SHA256,
        "run_manifest_sha256": A1_RUN_MANIFEST_SHA256,
        "command_sha256": A1_COMMAND_SHA256,
        "command_lock_sha256": A1_COMMAND_LOCK_SHA256,
        "candidate_artifact_manifest_sha256": candidate["manifest_sha256"],
        "training_run_receipt_sha256": candidate["training_run_receipt_sha256"],
        "recipe_spec_sha256": recipe_spec_sha256,
        "compute_receipt_sha256": compute_receipt_sha256,
        "training_budget_manifest_sha256": training_budget_manifest_sha256,
        "base_repo": SURROGATE_REPO,
        "base_revision": SURROGATE_REVISION,
        "harness_manifest_sha256": stage_binding["harness_manifest_sha256"],
        "sampling_profile_sha256": law["sampling_profile_sha256"],
        "sealed_eval_consumed_by_training": False,
        "hidden_eval_compute_authorized_by_this_receipt": False,
        "next_requirement": "BUILD_CANDIDATE_REGISTRATION_AND_MANAGER_VERIFIABLE_FREEZE_BEFORE_SCORE_UNSEAL",
        "authority": {
            "authority_kind": HOTPATH_AUTHORITY_KIND,
            "authoritative_for_evaluation_result": False,
            "authoritative_for_model_promotion": False,
            "manager_acceptance_required": True,
        },
    }
    _ = receipt  # parsed and semantically checked above; plaintext is never copied into ingest evidence.
    return _seal(body, "ingest_receipt_sha256")


def build_a1_single_candidate_registration(*, law: dict[str, Any], stage_binding: dict[str, Any], ingest: dict[str, Any]) -> dict[str, Any]:
    """Pre-register exactly one A1 candidate before any hidden score is opened.

    This P4.1 overlay exists because the frozen P4 batch tournament registration
   