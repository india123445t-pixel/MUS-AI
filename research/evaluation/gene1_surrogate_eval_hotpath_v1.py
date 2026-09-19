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
        "worker02_sealed_eval_commitment_sha256": p4.W02_SEALED_EVAL_COMMITMENT_SHA256