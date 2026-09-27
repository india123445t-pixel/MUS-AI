#!/usr/bin/env python3
"""AQLEVON Agent 02 — future W05 evaluator hard-binding wrapper.

The scorer is unreachable until every required future-only custody/chronology
check passes. Historical W05 material is neither read nor reconstructed here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import w05_future_sealed_custody_gate_v1 as custody

BINDING_KIND = "AQLEVON_FUTURE_W05_EVALUATOR_HARD_BINDING_V1"
BINDING_STATUS = "PASS_ALL_PRE_SCORE_GATES"
FINAL_STATUS = "PASS_SCORER_INVOKED_AFTER_ALL_GATES"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvaluatorBindingError(RuntimeError):
    pass


def _require_sha256(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EvaluatorBindingError(f"invalid_sha256:{field}")


def run_future_w05_evaluator(
    *,
    repo: Path,
    preregistration_file: Path,
    preregistration_anchor_commit: str,
    preregistration_anchor_path: str,
    evaluation_start_receipt_file: Path,
    evaluation_start_anchor_commit: str,
    evaluation_start_anchor_path: str,
    expected_candidate_manifest_sha256: str,
    expected_evaluation_policy_sha256: str,
    secret_file: Path,
    sealed_plaintext_file: Path,
    scorer: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """Verify all gates, then invoke scorer exactly once.

    The callback receives metadata-only pre-score authorization. It never
    receives the private secret/plaintext paths or private contents.
    """
    if not callable(scorer):
        raise EvaluatorBindingError("scorer_not_callable")
    _require_sha256(expected_candidate_manifest_sha256, "expected_candidate_manifest_sha256")
    _require_sha256(expected_evaluation_policy_sha256, "expected_evaluation_policy_sha256")

    chronology = custody.verify_chronology(
        repo,
        preregistration_file,
        preregistration_anchor_commit,
        preregistration_anchor_path,
        evaluation_start_receipt_file,
        evaluation_start_anchor_commit,
        evaluation_start_anchor_path,
        expected_candidate_manifest_sha256,
    )

    proof = chronology["proof"]
    start_receipt = chronology["evaluation_start_receipt"]
    if proof.get("status") != "PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START":
        raise EvaluatorBindingError("chronology_gate_not_passed")
    if proof.get("candidate_manifest_sha256") != expected_candidate_manifest_sha256:
        raise EvaluatorBindingError("chronology_candidate_manifest_mismatch")
    if start_receipt.get("candidate_manifest_sha256") != expected_candidate_manifest_sha256:
        raise EvaluatorBindingError("evaluation_start_candidate_manifest_mismatch")
    if start_receipt.get("evaluation_policy_sha256") != expected_evaluation_policy_sha256:
        raise EvaluatorBindingError("evaluation_policy_sha256_mismatch")

    material = custody.verify_future_material(
        chronology["preregistration"],
        secret_file,
        sealed_plaintext_file,
        proof,
    )
    if material.get("status") != "PASS_FUTURE_MATERIAL_HASH_BOUND_AND_CHRONOLOGY_PROVEN":
        raise EvaluatorBindingError("material_gate_not_passed")
    if material.get("private_content_emitted") is not False:
        raise EvaluatorBindingError("private_content_boundary_violation")
    if material.get("authoritative_for_legacy_w05") is not False:
        raise EvaluatorBindingError("legacy_w05_authority_violation")

    authorization = {
        "schema_version": 1,
        "binding_kind": BINDING_KIND,
        "status": BINDING_STATUS,
        "preregistration_sha256": chronology["preregistration"]["record_sha256"],
        "chronology_sha256": proof["chronology_sha256"],
        "material_verification_sha256": material["verification_sha256"],
        "candidate_manifest_sha256": expected_candidate_manifest_sha256,
        "evaluation_policy_sha256": expected_evaluation_policy_sha256,
        "private_content_emitted": False,
        "historical_w05_authority": False,
        "scorer_retry_allowed": False,
    }
    authorization["authorization_sha256"] = custody.self_digest(
        authorization, "authorization_sha256"
    )

    # This is the only scorer invocation in the wrapper. No retry/fallback path
    # exists, and execution cannot reach this line until all checks above pass.
    score_result = scorer(dict(authorization))

    return {
        "schema_version": 1,
        "binding_kind": BINDING_KIND,
        "status": FINAL_STATUS,
        "pre_score_authorization": authorization,
        "score_result": score_result,
        "scorer_invocations": 1,
        "authoritative_for_legacy_w05": False,
        "authoritative_for_capability_gain": False,
    }
