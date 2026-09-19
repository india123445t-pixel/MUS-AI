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
    requires >=2 arms. It does not modify that law and cannot select a method.
    """
    errors = p4.validate_evaluation_law(law) + validate_surrogate_stage_binding(stage_binding, law=law)
    if not isinstance(ingest, dict) or ingest.get("receipt_kind") != HOTPATH_KIND or not verify_p2_self_digest(ingest, "ingest_receipt_sha256"):
        errors.append("ingest_receipt_invalid")
    elif ingest.get("law_sha256") != law.get("law_sha256") or ingest.get("stage_binding_sha256") != stage_binding.get("stage_binding_sha256"):
        errors.append("ingest_parent_binding_mismatch")
    if errors:
        raise HotPathError(STATE_INVALID_EVALUATION + ":" + ";".join(sorted(set(errors))))
    body = {
        "schema_version": 1,
        "registration_kind": HOTPATH_REGISTRATION_KIND,
        "hash_profile": HASH_PROFILE,
        "law_sha256": law["law_sha256"],
        "stage_binding_sha256": stage_binding["stage_binding_sha256"],
        "candidate_slot": A1_SLOT,
        "arm_id": A1_ARM_ID,
        "training_seed": A1_SEED,
        "candidate_artifact_manifest_sha256": ingest["candidate_artifact_manifest_sha256"],
        "training_run_receipt_sha256": ingest["training_run_receipt_sha256"],
        "run_manifest_sha256": ingest["run_manifest_sha256"],
        "command_lock_sha256": ingest["command_lock_sha256"],
        "harness_manifest_sha256": stage_binding["harness_manifest_sha256"],
        "sampling_profile_sha256": law["sampling_profile_sha256"],
        "score_visibility_at_registration": "NO_A1_HIDDEN_SCORES_OR_OUTPUTS_OBSERVED",
        "selection_authority": "NONE_SINGLE_CANDIDATE_REALITY_EVIDENCE_ONLY",
        "chronology_requirement": "THIS_REGISTRATION_MUST_BE_MANAGER_VERIFIABLY_ANCHORED_BEFORE_A1_SCORE_UNSEAL",
    }
    return _seal(body, "registration_sha256")


def validate_a1_single_candidate_registration(registration: Any, *, law: dict[str, Any], stage_binding: dict[str, Any], ingest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version", "registration_kind", "hash_profile", "law_sha256", "stage_binding_sha256",
        "candidate_slot", "arm_id", "training_seed", "candidate_artifact_manifest_sha256",
        "training_run_receipt_sha256", "run_manifest_sha256", "command_lock_sha256",
        "harness_manifest_sha256", "sampling_profile_sha256", "score_visibility_at_registration",
        "selection_authority", "chronology_requirement", "registration_sha256",
    }
    if not _exact_keys(registration, required):
        return ["a1_registration_schema"]
    if registration.get("schema_version") != 1 or registration.get("registration_kind") != HOTPATH_REGISTRATION_KIND:
        errors.append("a1_registration_identity")
    if registration.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(registration, "registration_sha256"):
        errors.append("a1_registration_self_digest")
    expected = {
        "law_sha256": law.get("law_sha256"),
        "stage_binding_sha256": stage_binding.get("stage_binding_sha256"),
        "candidate_slot": A1_SLOT,
        "arm_id": A1_ARM_ID,
        "training_seed": A1_SEED,
        "candidate_artifact_manifest_sha256": ingest.get("candidate_artifact_manifest_sha256"),
        "training_run_receipt_sha256": ingest.get("training_run_receipt_sha256"),
        "run_manifest_sha256": ingest.get("run_manifest_sha256"),
        "command_lock_sha256": ingest.get("command_lock_sha256"),
        "harness_manifest_sha256": stage_binding.get("harness_manifest_sha256"),
        "sampling_profile_sha256": law.get("sampling_profile_sha256"),
        "score_visibility_at_registration": "NO_A1_HIDDEN_SCORES_OR_OUTPUTS_OBSERVED",
        "selection_authority": "NONE_SINGLE_CANDIDATE_REALITY_EVIDENCE_ONLY",
    }
    for key, wanted in expected.items():
        if registration.get(key) != wanted:
            errors.append(f"a1_registration_binding:{key}")
    errors.extend(_scan_pre_score_leakage(registration, "a1_registration"))
    return sorted(set(errors))


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise HotPathError(f"{label}_must_be_rfc3339_utc")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise HotPathError(f"{label}_invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise HotPathError(f"{label}_not_utc")
    return dt


def finalize_a1_freeze_verification(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body["schema_version"] = 1
    body["verification_kind"] = HOTPATH_FREEZE_KIND
    body["hash_profile"] = HASH_PROFILE
    return _seal(body, "verification_record_sha256")


def validate_a1_freeze_verification(verification: Any, *, law: dict[str, Any], stage_binding: dict[str, Any], registration: dict[str, Any], ingest: dict[str, Any]) -> list[str]:
    errors = validate_a1_single_candidate_registration(registration, law=law, stage_binding=stage_binding, ingest=ingest)
    required = {
        "schema_version", "verification_kind", "hash_profile", "law_sha256", "stage_binding_sha256",
        "registration_sha256", "anchor_kind", "immutable_reference", "external_evidence_sha256",
        "manager_authority_id", "manager_attestation_sha256", "anchored_at_utc", "scores_unsealed_at_utc",
        "chronology_statement", "verification_record_sha256",
    }
    if not _exact_keys(verification, required):
        return sorted(set(errors + ["a1_freeze_verification_schema"]))
    if verification.get("schema_version") != 1 or verification.get("verification_kind") != HOTPATH_FREEZE_KIND:
        errors.append("a1_freeze_verification_identity")
    if verification.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(verification, "verification_record_sha256"):
        errors.append("a1_freeze_verification_self_digest")
    if verification.get("law_sha256") != law.get("law_sha256") or verification.get("stage_binding_sha256") != stage_binding.get("stage_binding_sha256") or verification.get("registration_sha256") != registration.get("registration_sha256"):
        errors.append("a1_freeze_verification_parent_binding")
    if verification.get("anchor_kind") not in {"git_commit", "immutable_object", "append_only_ledger"}:
        errors.append("a1_freeze_verification_anchor_kind")
    if not isinstance(verification.get("immutable_reference"), str) or not verification["immutable_reference"]:
        errors.append("a1_freeze_verification_reference")
    for field in ("external_evidence_sha256", "manager_attestation_sha256"):
        if not valid_sha256(verification.get(field)):
            errors.append(f"a1_freeze_verification_hash:{field}")
    if not isinstance(verification.get("manager_authority_id"), str) or not verification["manager_authority_id"]:
        errors.append("a1_freeze_verification_manager")
    try:
        anchored = _parse_utc(verification.get("anchored_at_utc"), "anchored_at_utc")
        unsealed = _parse_utc(verification.get("scores_unsealed_at_utc"), "scores_unsealed_at_utc")
        if not anchored < unsealed:
            errors.append("a1_freeze_verification_chronology")
    except HotPathError as exc:
        errors.append(str(exc))
    if verification.get("chronology_statement") != "MANAGER_VERIFIED_A1_REGISTRATION_EXISTED_IN_IMMUTABLE_SYSTEM_BEFORE_A1_SCORE_INSPECTION":
        errors.append("a1_freeze_verification_statement")
    return sorted(set(errors))


def registration_entry_from_ingest(ingest: dict[str, Any], *, training_gpu_milliseconds: int) -> dict[str, Any]:
    if not isinstance(ingest, dict) or ingest.get("receipt_kind") != HOTPATH_KIND or not verify_p2_self_digest(ingest, "ingest_receipt_sha256"):
        raise HotPathError("invalid_ingest_receipt")
    if ingest.get("state") != STATE_READY_TO_REGISTER:
        raise HotPathError("ingest_not_ready_to_register")
    if type(training_gpu_milliseconds) is not int or training_gpu_milliseconds < 0:
        raise HotPathError("invalid_training_gpu_milliseconds")
    return {
        "candidate_slot": ingest["candidate_slot"],
        "arm_id": ingest["arm_id"],
        "training_seed": ingest["training_seed"],
        "training_gpu_milliseconds": training_gpu_milliseconds,
        "recipe_spec_sha256": ingest["recipe_spec_sha256"],
        "candidate_artifact_manifest_sha256": ingest["candidate_artifact_manifest_sha256"],
        "training_run_receipt_sha256": ingest["training_run_receipt_sha256"],
        "compute_receipt_sha256": ingest["compute_receipt_sha256"],
        "training_budget_manifest_sha256": ingest["training_budget_manifest_sha256"],
    }


def hidden_eval_readiness(
    *, law: dict[str, Any], stage_binding: dict[str, Any], registration: dict[str, Any],
    freeze_verification: dict[str, Any], ingest: dict[str, Any],
) -> dict[str, Any]:
    invalid: list[str] = []
    invalid.extend(p4.validate_evaluation_law(law))
    invalid.extend(validate_surrogate_stage_binding(stage_binding, law=law))
    invalid.extend(validate_a1_single_candidate_registration(registration, law=law, stage_binding=stage_binding, ingest=ingest))
    invalid.extend(validate_a1_freeze_verification(freeze_verification, law=law, stage_binding=stage_binding, registration=registration, ingest=ingest))
    if invalid:
        return {"state": STATE_INVALID_EVALUATION, "reasons": sorted(set(invalid))}
    return {
        "state": STATE_READY_FOR_HIDDEN_EVAL,
        "reasons": [],
        "law_sha256": law["law_sha256"],
        "stage_binding_sha256": stage_binding["stage_binding_sha256"],
        "a1_registration_sha256": registration["registration_sha256"],
        "freeze_verification_sha256": freeze_verification["verification_record_sha256"],
        "candidate_artifact_manifest_sha256": ingest["candidate_artifact_manifest_sha256"],
        "harness_manifest_sha256": stage_binding["harness_manifest_sha256"],
        "sampling_profile_sha256": law["sampling_profile_sha256"],
        "selection_authority": "NONE_SINGLE_CANDIDATE_REALITY_EVIDENCE_ONLY",
        "authority": "READINESS_ONLY_EXISTING_P4_REALITY_THRESHOLDS_UNCHANGED",
    }

def classify_existing_p4_score_card(score_card: Any, *, law: dict[str, Any], stage_binding: dict[str, Any]) -> str:
    errors = p4.validate_score_card(score_card, law=law, stage_binding=stage_binding)
    if errors:
        return STATE_INVALID_EVALUATION
    status = score_card.get("reality_status")
    if status in {"INVALID"}:
        return STATE_INVALID_EVALUATION
    if status in {"REJECTED"}:
        return STATE_REJECTED_ARM
    if status == "REALITY_PASS":
        return STATE_EVIDENCE_READY
    return STATE_INVALID_EVALUATION


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path | None, value: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate-a1-ingest")
    v.add_argument("--law", type=Path, required=True)
    v.add_argument("--stage-binding", type=Path, required=True)
    v.add_argument("--run-manifest", type=Path, required=True)
    v.add_argument("--command-lock", type=Path, required=True)
    v.add_argument("--candidate-manifest", type=Path, required=True)
    v.add_argument("--training-receipt", type=Path, required=True)
    v.add_argument("--recipe-spec-sha256", required=True)
    v.add_argument("--compute-receipt-sha256", required=True)
    v.add_argument("--training-budget-manifest-sha256", required=True)
    v.add_argument("--output", type=Path)

    r = sub.add_parser("build-a1-registration")
    r.add_argument("--law", type=Path, required=True)
    r.add_argument("--stage-binding", type=Path, required=True)
    r.add_argument("--ingest", type=Path, required=True)
    r.add_argument("--output", type=Path, required=True)

    h = sub.add_parser("check-hidden-eval-readiness")
    h.add_argument("--law", type=Path, required=True)
    h.add_argument("--stage-binding", type=Path, required=True)
    h.add_argument("--ingest", type=Path, required=True)
    h.add_argument("--registration", type=Path, required=True)
    h.add_argument("--freeze-verification", type=Path, required=True)
    h.add_argument("--output", type=Path)

    c = sub.add_parser("classify-score-card")
    c.add_argument("--law", type=Path, required=True)
    c.add_argument("--stage-binding", type=Path, required=True)
    c.add_argument("--score-card", type=Path, required=True)

    args = ap.parse_args()
    try:
        if args.cmd == "validate-a1-ingest":
            ingest = build_a1_ingest_receipt(
                law=_load(args.law), stage_binding=_load(args.stage_binding), run_manifest=_load(args.run_manifest),
                command_lock=_load(args.command_lock), candidate=_load(args.candidate_manifest),
                training_receipt_bytes=args.training_receipt.read_bytes(), recipe_spec_sha256=args.recipe_spec_sha256,
                compute_receipt_sha256=args.compute_receipt_sha256,
                training_budget_manifest_sha256=args.training_budget_manifest_sha256,
            )
            _write_json(args.output, ingest)
            print(json.dumps({"state": ingest["state"], "ingest_receipt_sha256": ingest["ingest_receipt_sha256"]}, sort_keys=True))
            return 0

        if args.cmd == "build-a1-registration":
            registration = build_a1_single_candidate_registration(
                law=_load(args.law), stage_binding=_load(args.stage_binding), ingest=_load(args.ingest)
            )
            _write_json(args.output, registration)
            print(json.dumps({"state": STATE_READY_TO_REGISTER, "registration_sha256": registration["registration_sha256"]}, sort_keys=True))
            return 0

        if args.cmd == "check-hidden-eval-readiness":
            readiness = hidden_eval_readiness(
                law=_load(args.law), stage_binding=_load(args.stage_binding), registration=_load(args.registration),
                freeze_verification=_load(args.freeze_verification), ingest=_load(args.ingest),
            )
            _write_json(args.output, readiness)
            print(json.dumps(readiness, sort_keys=True))
            return 0 if readiness.get("state") == STATE_READY_FOR_HIDDEN_EVAL else 2

        if args.cmd == "classify-score-card":
            state = classify_existing_p4_score_card(
                _load(args.score_card), law=_load(args.law), stage_binding=_load(args.stage_binding)
            )
            print(json.dumps({"state": state}, sort_keys=True))
            return 0 if state in {STATE_REJECTED_ARM, STATE_EVIDENCE_READY} else 2

        raise HotPathError("unknown_command")
    except Exception as exc:
        fail_state = STATE_INVALID_EVALUATION if args.cmd in {"check-hidden-eval-readiness", "classify-score-card"} else STATE_INVALID_CANDIDATE
        print(json.dumps({"state": fail_state, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())