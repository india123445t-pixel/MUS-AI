#!/usr/bin/env python3
"""AQLEVON P4 Gene #1 Reality Tournament V1.

Worker-05 evaluation orchestration for the first Coding + Tool Use capability gene.

This layer freezes a candidate-blind evaluation law, binds the concrete stage and
candidate identities before score inspection, verifies external chronology, and
selects a surrogate recipe or prepares a 27B candidate for Manager review.

It does NOT create model capability by itself and is never promotion authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from evaluation_decision_receipt_v1 import (
    HASH_PROFILE,
    RECEIPT_KIND as P2_RECEIPT_KIND,
    canonical_p2_sha256,
    valid_sha256,
    verify_p2_self_digest,
    validate_evaluation_decision_receipt,
)

LAW_KIND = "AQLEVON_GENE1_EVALUATION_LAW_V1"
STAGE_BINDING_KIND = "AQLEVON_GENE1_STAGE_BINDING_V1"
REGISTRATION_KIND = "AQLEVON_GENE1_CANDIDATE_REGISTRATION_V1"
FREEZE_VERIFICATION_KIND = "AQLEVON_GENE1_FREEZE_VERIFICATION_V1"
ANTI_SHORTCUT_RECEIPT_KIND = "AQLEVON_GENE1_ANTI_SHORTCUT_OUTCOME_RECEIPT_V1"
SCORE_CARD_KIND = "AQLEVON_GENE1_SCORE_CARD_V1"
DECISION_KIND = "AQLEVON_GENE1_TOURNAMENT_DECISION_RECEIPT_V1"
FINAL_SURROGATE_DECISION_KIND = "AQLEVON_GENE1_SURROGATE_RECIPE_DECISION_V1"
AUTHORITY_KIND = "AQLEVON_GENE1_EVIDENCE_NOT_PROMOTION_AUTHORITY_V1"
P3_REALITY_EVIDENCE_KIND = "AQLEVON_REALITY_GATE_EVIDENCE_V1"
P3_REALITY_PASS = "REALITY_PASS"
TARGET_CAPABILITY = "CODING_TOOL_USE"

ALLOWED_STAGES = {"surrogate", "canonical_27b"}
ALLOWED_ROUND_MODES = {"initial12", "extension24", "canonical27b"}
ALLOWED_ANCHOR_KINDS = {"git_commit", "immutable_object", "append_only_ledger"}
ALLOWED_DECISION_STATUS = {
    "INVALID",
    "REJECTED",
    "SURROGATE_SCREEN_RANKING_READY",
    "READY_FOR_MANAGER_PROMOTION_REVIEW",
}
ALLOWED_FINAL_SURROGATE_STATUS = {"INVALID", "REJECTED", "SURROGATE_MORE_EVIDENCE_REQUIRED", "SURROGATE_RECIPE_SELECTED"}

# Exact cross-lane identities frozen before any Gene #1 candidate score exists.
W01_METHOD_TOURNAMENT_SPEC_SHA256 = "7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d"
W02_PUBLIC_PACK_BINDING_SHA256 = "d9a81a9730e1dac02ecf8b032191a8d878e00d9a25547712168afb0a725095e5"
W02_SEALED_EVAL_PACK_SHA256 = "b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb"
W02_SEALED_EVAL_COMMITMENT_SHA256 = "7e0463ddf6068fe66d85b5798b4f8037489c99dcd452376e8144dff0a122f4e5"
W02_P4_BRANCH = "agent/02-p4-gene1-data-verifier-pack-v1"
W02_P4_COMMIT = "abb94ef134e2e97036b6959dbc9db4278d3736b6"
W02_TRAINING_SHARD_FILE_SHA256 = "59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49"
W02_TRAINING_SHARD_MANIFEST_SHA256 = "f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f"
W02_TRAINING_VISIBLE_PACK_SHA256 = "35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
W02_SPLIT_COMMITMENT_SHA256 = "3cd1c0d32cad8cc7edf55c9392292828d54d2b4bd16ad50d0e70e26ba3dd9202"
W02_EVAL_SECRET_FILE_SHA256 = "e61883f5f794ed6e82bb29b5718b09334ed2f29fa60bc5c1b7f7c6e1e86a8db6"
W02_SEALED_EVAL_PLAINTEXT_FILE_SHA256 = "ce17cdee667f2a53adf38000f2ace652cc1b4659187640a49f04858dceadbd0e"

# Accepted P3 exact source identity at Worker-05 P3 head d902566f... .
P3_REALITY_GATE_CODE_SHA256 = "b2ca3d5b1b959b29d2fa0587cc4b10b21a617e7a55e483b12847580cb6299e40"

FORBIDDEN_PRE_SCORE_KEYS = {
    "score", "scores", "candidate_score", "candidate_scores", "reward", "rewards",
    "raw_pass", "clean_pass", "transfer_pass", "hack_gap", "evaluation_result",
    "evaluation_results", "candidate_output", "candidate_outputs",
}
FORBIDDEN_PLAINTEXT_KEYS = {
    "prompt", "prompts", "answer", "answers", "solution", "solutions",
    "hidden_answer", "hidden_solution", "expected_answer", "expected_output",
    "response_text", "tool_output_plaintext",
}


class Gene1TournamentError(ValueError):
    pass


def actual_gene1_tournament_code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _self_digest(value: dict[str, Any], field: str) -> str:
    return canonical_p2_sha256({k: v for k, v in value.items() if k != field})


def _finalize(value: dict[str, Any], field: str) -> dict[str, Any]:
    out = dict(value)
    out["hash_profile"] = HASH_PROFILE
    out.pop(field, None)
    out[field] = canonical_p2_sha256(out)
    return out


def _exact_keys(value: Any, required: set[str], optional: set[str] | None = None) -> bool:
    if not isinstance(value, dict):
        return False
    allowed = required | (optional or set())
    return required <= set(value) and set(value) <= allowed


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Gene1TournamentError(f"{label}_must_be_rfc3339_utc")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise Gene1TournamentError(f"{label}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise Gene1TournamentError(f"{label}_must_be_utc")
    return parsed


def _assert_no_keys(value: Any, forbidden: set[str], *, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in forbidden:
                raise Gene1TournamentError(f"forbidden_key:{path}.{key}")
            _assert_no_keys(child, forbidden, path=f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _assert_no_keys(child, forbidden, path=f"{path}[{i}]")


def _require_hashes(obj: dict[str, Any], fields: list[str], invalid: list[str], prefix: str) -> None:
    for field in fields:
        if not valid_sha256(obj.get(field)):
            invalid.append(f"{prefix} invalid {field}")


def _fraction_gt(a_num: int, a_den: int, b_num: int, b_den: int) -> bool:
    return Fraction(a_num, a_den) > Fraction(b_num, b_den)


def _fraction_ge(a_num: int, a_den: int, b_num: int, b_den: int) -> bool:
    return Fraction(a_num, a_den) >= Fraction(b_num, b_den)


def validate_worker01_method_tournament_spec(spec: Any) -> list[str]:
    invalid: list[str] = []
    if not isinstance(spec, dict):
        return ["Worker-01 method spec must be object"]
    try:
        digest = canonical_p2_sha256(spec)
    except (TypeError, ValueError) as exc:
        return [f"Worker-01 method spec canonicalization failed:{exc}"]
    if digest != W01_METHOD_TOURNAMENT_SPEC_SHA256:
        invalid.append("Worker-01 method spec canonical SHA mismatch")
    if spec.get("spec_kind") != "AQLEVON_P4_METHOD_TOURNAMENT_SPEC_V1" or spec.get("task_id") != "P4-A01-METHOD-TOURNAMENT-DIRECTOR":
        invalid.append("Worker-01 method spec identity mismatch")
    if spec.get("training_seeds") != [1701, 1702, 1703]:
        invalid.append("Worker-01 training seed law mismatch")
    arms = spec.get("arms")
    arm_ids = [arm.get("arm_id") for arm in arms] if isinstance(arms, list) and all(isinstance(arm, dict) for arm in arms) else []
    if arm_ids != ["P4_A0_SFT_LORA_CONTROL", "P4_A1_RLVR_CONTROL", "P4_A2_SDPO_RICH_FEEDBACK"]:
        invalid.append("Worker-01 arm set/order mismatch")
    selection = spec.get("selection_law")
    if not isinstance(selection, dict) or selection.get("hard_gate_first") is not True or selection.get("worker01_winner_claim_allowed") is not False:
        invalid.append("Worker-01 selection authority law mismatch")
    return sorted(set(invalid))


def validate_worker02_public_pack_binding(binding: Any) -> list[str]:
    invalid: list[str] = []
    required = {
        "schema_version", "binding_kind", "hash_profile", "worker02_p4_branch", "worker02_p4_commit",
        "training_shard_file_sha256", "training_shard_manifest_sha256", "training_visible_pack_sha256",
        "split_commitment_sha256", "sealed_eval_pack_sha256", "sealed_eval_commitment_sha256",
        "eval_secret_file_sha256", "sealed_eval_plaintext_file_sha256", "sealed_plaintext_visibility",
        "training_worker_visibility", "binding_sha256",
    }
    if not _exact_keys(binding, required):
        return ["Worker-02 public pack binding schema mismatch"]
    if binding.get("schema_version") != 1 or binding.get("binding_kind") != "AQLEVON_GENE1_WORKER02_PUBLIC_PACK_BINDING_V1":
        invalid.append("Worker-02 public pack binding identity mismatch")
    if binding.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(binding, "binding_sha256"):
        invalid.append("Worker-02 public pack binding self-digest/profile mismatch")
    expected = {
        "worker02_p4_branch": W02_P4_BRANCH,
        "worker02_p4_commit": W02_P4_COMMIT,
        "training_shard_file_sha256": W02_TRAINING_SHARD_FILE_SHA256,
        "training_shard_manifest_sha256": W02_TRAINING_SHARD_MANIFEST_SHA256,
        "training_visible_pack_sha256": W02_TRAINING_VISIBLE_PACK_SHA256,
        "split_commitment_sha256": W02_SPLIT_COMMITMENT_SHA256,
        "sealed_eval_pack_sha256": W02_SEALED_EVAL_PACK_SHA256,
        "sealed_eval_commitment_sha256": W02_SEALED_EVAL_COMMITMENT_SHA256,
        "eval_secret_file_sha256": W02_EVAL_SECRET_FILE_SHA256,
        "sealed_eval_plaintext_file_sha256": W02_SEALED_EVAL_PLAINTEXT_FILE_SHA256,
        "sealed_plaintext_visibility": "MANAGER_AND_WORKER05_ONLY",
        "training_worker_visibility": "FORBIDDEN",
    }
    for key, value in expected.items():
        if binding.get(key) != value:
            invalid.append(f"Worker-02 public pack binding mismatch:{key}")
    return sorted(set(invalid))


def frozen_gene1_evaluation_law() -> dict[str, Any]:
    """Return the immutable, candidate-blind P4 law committed before score inspection."""
    sampling_profile = {
        "profile_kind": "AQLEVON_GENE1_MATCHED_SAMPLING_PROFILE_V1",
        "samples_per_task": 4,
        "k_values": [1, 4],
        "do_sample": True,
        "temperature_decimal": "0.7",
        "top_p_decimal": "0.8",
        "top_k": 20,
        "max_new_tokens": 2048,
        "eval_seed_formula": "100000 + training_seed * 100 + sample_index",
        "sample_index_domain": [0, 1, 2, 3],
        "candidate_pairing_rule": "SAME_TASK_ORDER_AND_SAME_EVAL_SEEDS_FOR_ALL_ARMS_WITHIN_A_TRAINING_SEED",
        "tool_protocol_terminal_stop": True,
    }
    sampling_profile_sha256 = canonical_p2_sha256(sampling_profile)
    law = {
        "schema_version": 1,
        "manifest_kind": LAW_KIND,
        "hash_profile": HASH_PROFILE,
        "law_version": "P4_GENE1_2026_09_19_V1",
        "target_capability": TARGET_CAPABILITY,
        "allowed_stages": ["surrogate", "canonical_27b"],
        "arm_slots": ["control", "challenger_a", "challenger_b"],
        "arm_id_by_slot": {
            "control": "P4_A0_SFT_LORA_CONTROL",
            "challenger_a": "P4_A1_RLVR_CONTROL",
            "challenger_b": "P4_A2_SDPO_RICH_FEEDBACK",
        },
        "worker01_method_tournament_spec_sha256": W01_METHOD_TOURNAMENT_SPEC_SHA256,
        "worker02_public_pack_binding_sha256": W02_PUBLIC_PACK_BINDING_SHA256,
        "worker02_sealed_eval_pack_sha256": W02_SEALED_EVAL_PACK_SHA256,
        "worker02_sealed_eval_commitment_sha256": W02_SEALED_EVAL_COMMITMENT_SHA256,
        "min_surrogate_arms": 2,
        "max_surrogate_arms": 3,
        "k_values": [1, 4],
        "sampling_profile": sampling_profile,
        "sampling_profile_sha256": sampling_profile_sha256,
        "evaluation_population_law": {
            "sealed_eval_commitment_sha256": W02_SEALED_EVAL_COMMITMENT_SHA256,
            "sealed_eval_pack_sha256": W02_SEALED_EVAL_PACK_SHA256,
            "primary_population": "SEALED_HARDENED_ORIGINAL_TASKS",
            "transfer_population": "SEALED_HARDENED_SEMANTICS_PRESERVING_PERTURBATIONS",
            "anti_shortcut_population": "SEALED_VULNERABLE_HARDENED_TWIN_PROBES",
            "hidden_canary_population": "SEALED_TASK_CANARY_CHECKS",
            "protected_plaintext_visibility": "MANAGER_AND_WORKER05_ONLY",
            "training_worker_visibility": "FORBIDDEN",
        },
        "hard_gate_law": {
            "require_p3_reality_pass": True,
            "require_primary_clean_pass_at_1_strict_improvement": True,
            "require_primary_clean_pass_at_4_nonregression": True,
            "require_transfer_clean_pass_at_1_nonregression": True,
            "require_hidden_canary_nonregression": True,
            "require_anti_shortcut_nonregression": True,
            "require_hack_gap_nonincrease_at_all_k": True,
            "require_metamorphic_invariance_nonregression_at_all_k": True,
            "require_paired_slot_invariance_nonregression": True,
            "require_every_domain_clean_pass_at_1_nonregression": True,
            "reject_any_proxy_clean_divergence": True,
            "reject_integrity_authority_mismatch": True,
        },
        "surrogate_selection_law": {
            "screen_seed": 1701,
            "confirmation_seeds": [1702, 1703],
            "screen_order": [
                "MAX_TRANSFER_CLEAN_PASS_AT_4_COUNT",
                "MAX_PRIMARY_CLEAN_PASS_AT_4_COUNT",
                "MIN_HACK_GAP_AT_4_COUNT",
                "MIN_TRAINING_GPU_MILLISECONDS",
                "MIN_SIMPLICITY_RANK",
            ],
            "final_order": [
                "MAX_MEDIAN_TRANSFER_CLEAN_PASS_AT_4_COUNT",
                "MAX_WORST_SEED_TRANSFER_CLEAN_PASS_AT_4_COUNT",
                "MAX_MEDIAN_PRIMARY_CLEAN_PASS_AT_4_COUNT",
                "MAX_WORST_SEED_PRIMARY_CLEAN_PASS_AT_4_COUNT",
                "MIN_MEDIAN_HACK_GAP_AT_4_COUNT",
                "MIN_MEDIAN_TRAINING_GPU_MILLISECONDS",
                "MIN_SIMPLICITY_RANK",
            ],
            "ambiguity_extension_rule": "TOP_TWO_MEDIAN_TRANSFER_AT_4_DIFF_LE_1_AND_MEDIAN_CLEAN_AT_4_DIFF_LE_1_REQUIRES_24_UPDATE_EXTENSION",
            "sdpo_displacement_rule": "SDPO_REQUIRES_STRICTLY_HIGHER_MEDIAN_TRANSFER_AT_4_THAN_BEST_FEASIBLE_CONTROL_AND_NONLOWER_MEDIAN_CLEAN_AT_4",
            "screen_output": "TOP_TWO_SURVIVORS_ONLY_NOT_METHOD_WINNER",
        },
        "tie_policy": "SCREEN_TIE_USES_LOWER_GPU_THEN_SIMPLER_ARM_FINAL_AMBIGUITY_REQUIRES_PREDECLARED_EXTENSION",
        "round_binding_law": {
            "initial12": "NO_CURRENT_ROUND_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED",
            "extension24": "PRIOR_ROUND_SCORES_OBSERVED_CURRENT_EXTENSION_SCORES_NOT_OBSERVED_AND_PARENT_AMBIGUITY_RECEIPT_BOUND",
            "canonical27b": "PRIOR_SURROGATE_SCORES_OBSERVED_CURRENT_27B_SCORES_NOT_OBSERVED_AND_SELECTED_RECIPE_RECEIPT_BOUND",
        },
        "required_stage_bindings": [
            "w01_method_freeze_sha256",
            "w02_gene1_pack_sha256",
            "sealed_eval_pack_manifest_sha256",
            "hidden_canary_manifest_sha256",
            "anti_shortcut_manifest_sha256",
            "metamorphic_manifest_sha256",
            "harness_manifest_sha256",
            "task_factory_manifest_sha256",
            "reality_policy_sha256",
            "sampling_profile_sha256",
            "matched_training_budget_manifest_sha256",
            "baseline_artifact_manifest_sha256",
        ],
        "p3_reality_evidence_kind": P3_REALITY_EVIDENCE_KIND,
        "p3_reality_gate_code_sha256": P3_REALITY_GATE_CODE_SHA256,
        "p2_evaluation_decision_receipt_kind": P2_RECEIPT_KIND,
        "p2_receipt_required_for_27b_manager_review": True,
        "freeze_chronology_requirement": "LAW_STAGE_BINDING_AND_CANDIDATE_REGISTRATION_MUST_BE_MANAGER_VERIFIABLY_ANCHORED_BEFORE_SCORE_INSPECTION",
        "score_visibility_at_law_freeze": "NO_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED",
        "authority": {
            "authority_kind": AUTHORITY_KIND,
            "authoritative_for_model_promotion": False,
            "authoritative_for_arbitrary_runtime_attempts": False,
            "manager_acceptance_required": True,
        },
    }
    return _finalize(law, "law_sha256")


def validate_evaluation_law(law: Any) -> list[str]:
    invalid: list[str] = []
    required = {
        "schema_version", "manifest_kind", "hash_profile", "law_version", "target_capability",
        "allowed_stages", "arm_slots", "arm_id_by_slot", "worker01_method_tournament_spec_sha256",
        "worker02_public_pack_binding_sha256", "worker02_sealed_eval_pack_sha256",
        "worker02_sealed_eval_commitment_sha256", "min_surrogate_arms", "max_surrogate_arms", "k_values",
        "sampling_profile", "sampling_profile_sha256", "evaluation_population_law", "hard_gate_law", "surrogate_selection_law",
        "tie_policy", "round_binding_law", "required_stage_bindings", "p3_reality_evidence_kind",
        "p3_reality_gate_code_sha256", "p2_evaluation_decision_receipt_kind",
        "p2_receipt_required_for_27b_manager_review", "freeze_chronology_requirement",
        "score_visibility_at_law_freeze", "authority", "law_sha256",
    }
    if not _exact_keys(law, required):
        return ["evaluation law schema mismatch"]
    if law.get("schema_version") != 1 or law.get("manifest_kind") != LAW_KIND:
        invalid.append("evaluation law identity mismatch")
    if law.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(law, "law_sha256"):
        invalid.append("evaluation law self-digest/profile mismatch")
    if law.get("target_capability") != TARGET_CAPABILITY:
        invalid.append("evaluation law target capability mismatch")
    if law.get("allowed_stages") != ["surrogate", "canonical_27b"]:
        invalid.append("evaluation law stage set mismatch")
    if law.get("arm_slots") != ["control", "challenger_a", "challenger_b"]:
        invalid.append("evaluation law arm slots mismatch")
    if law.get("arm_id_by_slot") != {
        "control": "P4_A0_SFT_LORA_CONTROL",
        "challenger_a": "P4_A1_RLVR_CONTROL",
        "challenger_b": "P4_A2_SDPO_RICH_FEEDBACK",
    }:
        invalid.append("evaluation law arm-id map mismatch")
    if law.get("worker01_method_tournament_spec_sha256") != W01_METHOD_TOURNAMENT_SPEC_SHA256:
        invalid.append("evaluation law Worker-01 method freeze mismatch")
    if law.get("worker02_public_pack_binding_sha256") != W02_PUBLIC_PACK_BINDING_SHA256:
        invalid.append("evaluation law Worker-02 public pack mismatch")
    if law.get("worker02_sealed_eval_pack_sha256") != W02_SEALED_EVAL_PACK_SHA256 or law.get("worker02_sealed_eval_commitment_sha256") != W02_SEALED_EVAL_COMMITMENT_SHA256:
        invalid.append("evaluation law Worker-02 sealed evaluation identity mismatch")
    if law.get("min_surrogate_arms") != 2 or law.get("max_surrogate_arms") != 3:
        invalid.append("evaluation law surrogate arm bounds mismatch")
    if law.get("k_values") != [1, 4]:
        invalid.append("evaluation law k values mismatch")
    profile = law.get("sampling_profile")
    if not isinstance(profile, dict) or canonical_p2_sha256(profile) != law.get("sampling_profile_sha256"):
        invalid.append("evaluation law sampling profile binding mismatch")
    population_law = law.get("evaluation_population_law")
    if not isinstance(population_law, dict) or population_law.get("sealed_eval_commitment_sha256") != W02_SEALED_EVAL_COMMITMENT_SHA256 or population_law.get("sealed_eval_pack_sha256") != W02_SEALED_EVAL_PACK_SHA256:
        invalid.append("evaluation law population binding mismatch")
    elif population_law.get("training_worker_visibility") != "FORBIDDEN" or population_law.get("protected_plaintext_visibility") != "MANAGER_AND_WORKER05_ONLY":
        invalid.append("evaluation law protected population visibility mismatch")
    if law.get("p3_reality_gate_code_sha256") != P3_REALITY_GATE_CODE_SHA256:
        invalid.append("evaluation law P3 code identity mismatch")
    if law.get("p3_reality_evidence_kind") != P3_REALITY_EVIDENCE_KIND:
        invalid.append("evaluation law P3 evidence kind mismatch")
    if law.get("p2_evaluation_decision_receipt_kind") != P2_RECEIPT_KIND:
        invalid.append("evaluation law P2 receipt kind mismatch")
    if law.get("p2_receipt_required_for_27b_manager_review") is not True:
        invalid.append("evaluation law must require P2 receipt for 27B review")
    if law.get("score_visibility_at_law_freeze") != "NO_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED":
        invalid.append("evaluation law score-visibility boundary mismatch")
    authority = law.get("authority")
    if not isinstance(authority, dict) or authority.get("authority_kind") != AUTHORITY_KIND:
        invalid.append("evaluation law authority kind mismatch")
    elif authority.get("authoritative_for_model_promotion") is not False or authority.get("authoritative_for_arbitrary_runtime_attempts") is not False or authority.get("manager_acceptance_required") is not True:
        invalid.append("evaluation law authority boundary mismatch")
    try:
        _assert_no_keys(law, FORBIDDEN_PRE_SCORE_KEYS, path="law")
        _assert_no_keys(law, FORBIDDEN_PLAINTEXT_KEYS, path="law")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    # V1 is a truly frozen law: a self-consistent alternate law is still invalid.
    # Any policy change requires a new code/law version, never an in-place rehash.
    expected = frozen_gene1_evaluation_law()
    if law != expected:
        invalid.append("evaluation law differs from frozen canonical P4 Gene #1 law")
    return sorted(set(invalid))


def build_stage_binding(
    *, stage: str, experiment_id: str, law_sha256: str, w01_method_freeze_sha256: str,
    w02_gene1_pack_sha256: str, sealed_eval_pack_manifest_sha256: str, sealed_eval_commitment_sha256: str,
    hidden_canary_manifest_sha256: str, anti_shortcut_manifest_sha256: str,
    metamorphic_manifest_sha256: str, harness_manifest_sha256: str, task_factory_manifest_sha256: str,
    reality_policy_sha256: str, sampling_profile_sha256: str, matched_training_budget_manifest_sha256: str, baseline_artifact_manifest_sha256: str,
    round_mode: str | None = None, parent_decision_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    if stage not in ALLOWED_STAGES:
        raise Gene1TournamentError("unsupported_stage")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise Gene1TournamentError("experiment_id_invalid")
    if round_mode is None:
        round_mode = "initial12" if stage == "surrogate" else "canonical27b"
    if round_mode not in ALLOWED_ROUND_MODES:
        raise Gene1TournamentError("unsupported_round_mode")
    if stage == "surrogate" and round_mode not in {"initial12", "extension24"}:
        raise Gene1TournamentError("surrogate_round_mode_invalid")
    if stage == "canonical_27b" and round_mode != "canonical27b":
        raise Gene1TournamentError("canonical_round_mode_invalid")
    if round_mode == "initial12":
        if parent_decision_receipt_sha256 is not None:
            raise Gene1TournamentError("initial12_parent_decision_must_be_null")
        visibility = "NO_CURRENT_ROUND_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED"
    elif round_mode == "extension24":
        if not valid_sha256(parent_decision_receipt_sha256):
            raise Gene1TournamentError("extension24_parent_ambiguity_receipt_required")
        visibility = "PRIOR_ROUND_SCORES_OBSERVED_CURRENT_EXTENSION_SCORES_NOT_OBSERVED"
    else:
        if not valid_sha256(parent_decision_receipt_sha256):
            raise Gene1TournamentError("canonical27b_parent_recipe_receipt_required")
        visibility = "PRIOR_SURROGATE_SCORES_OBSERVED_CURRENT_27B_SCORES_NOT_OBSERVED"
    body = {
        "schema_version": 1,
        "binding_kind": STAGE_BINDING_KIND,
        "hash_profile": HASH_PROFILE,
        "stage": stage,
        "round_mode": round_mode,
        "parent_decision_receipt_sha256": parent_decision_receipt_sha256,
        "experiment_id": experiment_id,
        "law_sha256": law_sha256,
        "w01_method_freeze_sha256": w01_method_freeze_sha256,
        "w02_gene1_pack_sha256": w02_gene1_pack_sha256,
        "sealed_eval_pack_manifest_sha256": sealed_eval_pack_manifest_sha256,
        "sealed_eval_commitment_sha256": sealed_eval_commitment_sha256,
        "hidden_canary_manifest_sha256": hidden_canary_manifest_sha256,
        "anti_shortcut_manifest_sha256": anti_shortcut_manifest_sha256,
        "metamorphic_manifest_sha256": metamorphic_manifest_sha256,
        "harness_manifest_sha256": harness_manifest_sha256,
        "task_factory_manifest_sha256": task_factory_manifest_sha256,
        "reality_policy_sha256": reality_policy_sha256,
        "sampling_profile_sha256": sampling_profile_sha256,
        "matched_training_budget_manifest_sha256": matched_training_budget_manifest_sha256,
        "baseline_artifact_manifest_sha256": baseline_artifact_manifest_sha256,
        "score_visibility_at_binding": visibility,
        "chronology_requirement": "BINDING_AND_REGISTRATION_MUST_BE_EXTERNALLY_ANCHORED_BEFORE_SCORE_INSPECTION",
    }
    return _finalize(body, "stage_binding_sha256")


def validate_stage_binding(binding: Any, *, law: dict[str, Any]) -> list[str]:
    invalid = [f"law invalid:{x}" for x in validate_evaluation_law(law)]
    required = {
        "schema_version", "binding_kind", "hash_profile", "stage", "round_mode", "parent_decision_receipt_sha256", "experiment_id", "law_sha256",
        "w01_method_freeze_sha256", "w02_gene1_pack_sha256", "sealed_eval_pack_manifest_sha256", "sealed_eval_commitment_sha256",
        "hidden_canary_manifest_sha256", "anti_shortcut_manifest_sha256", "metamorphic_manifest_sha256",
        "harness_manifest_sha256", "task_factory_manifest_sha256", "reality_policy_sha256", "sampling_profile_sha256", "matched_training_budget_manifest_sha256",
        "baseline_artifact_manifest_sha256", "score_visibility_at_binding", "chronology_requirement",
        "stage_binding_sha256",
    }
    if not _exact_keys(binding, required):
        return invalid + ["stage binding schema mismatch"]
    if binding.get("schema_version") != 1 or binding.get("binding_kind") != STAGE_BINDING_KIND:
        invalid.append("stage binding identity mismatch")
    if binding.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(binding, "stage_binding_sha256"):
        invalid.append("stage binding self-digest/profile mismatch")
    if binding.get("stage") not in ALLOWED_STAGES:
        invalid.append("stage binding stage invalid")
    round_mode = binding.get("round_mode")
    if round_mode not in ALLOWED_ROUND_MODES:
        invalid.append("stage binding round mode invalid")
    if binding.get("stage") == "surrogate" and round_mode not in {"initial12", "extension24"}:
        invalid.append("stage binding surrogate round mismatch")
    if binding.get("stage") == "canonical_27b" and round_mode != "canonical27b":
        invalid.append("stage binding canonical round mismatch")
    parent = binding.get("parent_decision_receipt_sha256")
    if round_mode == "initial12" and parent is not None:
        invalid.append("stage binding initial12 parent must be null")
    if round_mode in {"extension24", "canonical27b"} and not valid_sha256(parent):
        invalid.append("stage binding parent decision receipt missing")
    if binding.get("law_sha256") != law.get("law_sha256"):
        invalid.append("stage binding law mismatch")
    if binding.get("sampling_profile_sha256") != law.get("sampling_profile_sha256"):
        invalid.append("stage binding sampling profile mismatch")
    if binding.get("w01_method_freeze_sha256") != law.get("worker01_method_tournament_spec_sha256"):
        invalid.append("stage binding Worker-01 method freeze mismatch")
    if binding.get("w02_gene1_pack_sha256") != law.get("worker02_public_pack_binding_sha256"):
        invalid.append("stage binding Worker-02 pack mismatch")
    if binding.get("sealed_eval_pack_manifest_sha256") != law.get("worker02_sealed_eval_pack_sha256"):
        invalid.append("stage binding sealed evaluation pack mismatch")
    if binding.get("sealed_eval_commitment_sha256") != law.get("worker02_sealed_eval_commitment_sha256"):
        invalid.append("stage binding sealed evaluation commitment mismatch")
    _require_hashes(binding, [
        "law_sha256", "w01_method_freeze_sha256", "w02_gene1_pack_sha256",
        "sealed_eval_pack_manifest_sha256", "sealed_eval_commitment_sha256", "hidden_canary_manifest_sha256",
        "anti_shortcut_manifest_sha256", "metamorphic_manifest_sha256", "harness_manifest_sha256",
        "task_factory_manifest_sha256", "reality_policy_sha256", "sampling_profile_sha256",
        "matched_training_budget_manifest_sha256", "baseline_artifact_manifest_sha256",
        "stage_binding_sha256",
    ], invalid, "stage binding")
    expected_visibility = {
        "initial12": "NO_CURRENT_ROUND_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED",
        "extension24": "PRIOR_ROUND_SCORES_OBSERVED_CURRENT_EXTENSION_SCORES_NOT_OBSERVED",
        "canonical27b": "PRIOR_SURROGATE_SCORES_OBSERVED_CURRENT_27B_SCORES_NOT_OBSERVED",
    }.get(round_mode)
    if binding.get("score_visibility_at_binding") != expected_visibility:
        invalid.append("stage binding score-visibility boundary mismatch")
    try:
        _assert_no_keys(binding, FORBIDDEN_PRE_SCORE_KEYS | FORBIDDEN_PLAINTEXT_KEYS, path="stage_binding")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    return invalid


def build_candidate_registration(*, law: dict[str, Any], stage_binding: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    errors = validate_stage_binding(stage_binding, law=law)
    if errors:
        raise Gene1TournamentError("; ".join(errors))
    stage = stage_binding["stage"]
    if not isinstance(entries, list):
        raise Gene1TournamentError("registration_entries_invalid")
    if stage == "surrogate" and not (law["min_surrogate_arms"] <= len(entries) <= law["max_surrogate_arms"]):
        raise Gene1TournamentError("surrogate_arm_count_outside_frozen_bounds")
    if stage == "canonical_27b" and len(entries) != 1:
        raise Gene1TournamentError("canonical_27b_requires_exactly_one_candidate")
    normalized: list[dict[str, Any]] = []
    seen_slots: set[str] = set()
    seen_candidates: set[str] = set()
    for entry in entries:
        required = {
            "candidate_slot", "arm_id", "training_seed", "training_gpu_milliseconds",
            "recipe_spec_sha256", "candidate_artifact_manifest_sha256",
            "training_run_receipt_sha256", "compute_receipt_sha256", "training_budget_manifest_sha256",
        }
        if not _exact_keys(entry, required):
            raise Gene1TournamentError("candidate_registration_entry_schema_mismatch")
        slot = entry["candidate_slot"]
        if slot not in law["arm_slots"]:
            raise Gene1TournamentError("candidate_slot_not_in_frozen_law")
        if entry.get("arm_id") != law["arm_id_by_slot"].get(slot):
            raise Gene1TournamentError("candidate_arm_id_mismatch")
        if type(entry.get("training_seed")) is not int:
            raise Gene1TournamentError("candidate_training_seed_invalid")
        if stage == "surrogate":
            allowed_seeds = [law["surrogate_selection_law"]["screen_seed"], *law["surrogate_selection_law"]["confirmation_seeds"]]
            if entry["training_seed"] not in allowed_seeds:
                raise Gene1TournamentError("candidate_training_seed_not_frozen_surrogate_seed")
        if type(entry.get("training_gpu_milliseconds")) is not int or entry["training_gpu_milliseconds"] < 0:
            raise Gene1TournamentError("candidate_training_gpu_milliseconds_invalid")
        if slot in seen_slots:
            raise Gene1TournamentError("duplicate_candidate_slot")
        seen_slots.add(slot)
        candidate = entry["candidate_artifact_manifest_sha256"]
        if candidate in seen_candidates:
            raise Gene1TournamentError("duplicate_candidate_artifact_identity")
        seen_candidates.add(candidate)
        for field in required - {"candidate_slot", "arm_id", "training_seed", "training_gpu_milliseconds"}:
            if not valid_sha256(entry[field]):
                raise Gene1TournamentError(f"invalid_registration_hash:{field}")
        if entry["training_budget_manifest_sha256"] != stage_binding["matched_training_budget_manifest_sha256"]:
            raise Gene1TournamentError("candidate_training_budget_mismatch")
        normalized.append(dict(entry))
    normalized.sort(key=lambda x: law["arm_slots"].index(x["candidate_slot"]))
    body = {
        "schema_version": 1,
        "registration_kind": REGISTRATION_KIND,
        "hash_profile": HASH_PROFILE,
        "law_sha256": law["law_sha256"],
        "stage_binding_sha256": stage_binding["stage_binding_sha256"],
        "stage": stage,
        "entries": normalized,
        "score_visibility_at_registration": "NO_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED",
        "chronology_requirement": "REGISTRATION_MUST_BE_EXTERNALLY_ANCHORED_BEFORE_SCORE_INSPECTION",
    }
    _assert_no_keys(body, FORBIDDEN_PRE_SCORE_KEYS | FORBIDDEN_PLAINTEXT_KEYS, path="registration")
    return _finalize(body, "candidate_registration_sha256")


def validate_candidate_registration(registration: Any, *, law: dict[str, Any], stage_binding: dict[str, Any]) -> list[str]:
    invalid = validate_stage_binding(stage_binding, law=law)
    if not isinstance(registration, dict):
        return invalid + ["candidate registration must be object"]
    if registration.get("registration_kind") != REGISTRATION_KIND or registration.get("schema_version") != 1:
        invalid.append("candidate registration identity mismatch")
    if registration.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(registration, "candidate_registration_sha256"):
        invalid.append("candidate registration self-digest/profile mismatch")
    if registration.get("law_sha256") != law.get("law_sha256") or registration.get("stage_binding_sha256") != stage_binding.get("stage_binding_sha256"):
        invalid.append("candidate registration parent binding mismatch")
    if registration.get("stage") != stage_binding.get("stage"):
        invalid.append("candidate registration stage mismatch")
    if registration.get("score_visibility_at_registration") != "NO_CANDIDATE_SCORES_OR_OUTPUTS_OBSERVED":
        invalid.append("candidate registration score-visibility boundary mismatch")
    entries = registration.get("entries")
    try:
        rebuilt = build_candidate_registration(law=law, stage_binding=stage_binding, entries=entries)
        if rebuilt != registration:
            invalid.append("candidate registration semantic/self-hash mismatch")
    except (Gene1TournamentError, TypeError, ValueError) as exc:
        invalid.append(f"candidate registration invalid:{exc}")
    return invalid


def finalize_freeze_verification(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body["schema_version"] = 1
    body["verification_kind"] = FREEZE_VERIFICATION_KIND
    body["hash_profile"] = HASH_PROFILE
    return _finalize(body, "verification_record_sha256")


def validate_freeze_verification(
    verification: Any, *, law: dict[str, Any], stage_binding: dict[str, Any], registration: dict[str, Any]
) -> list[str]:
    invalid: list[str] = []
    required = {
        "schema_version", "verification_kind", "hash_profile", "law_sha256", "stage_binding_sha256",
        "candidate_registration_sha256", "anchor_kind", "immutable_reference", "external_evidence_sha256",
        "manager_authority_id", "manager_attestation_sha256", "anchored_at_utc", "scores_unsealed_at_utc",
        "chronology_statement", "verification_record_sha256",
    }
    if not _exact_keys(verification, required):
        return ["freeze verification schema mismatch"]
    if verification.get("schema_version") != 1 or verification.get("verification_kind") != FREEZE_VERIFICATION_KIND:
        invalid.append("freeze verification identity mismatch")
    if verification.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(verification, "verification_record_sha256"):
        invalid.append("freeze verification self-digest/profile mismatch")
    if verification.get("law_sha256") != law.get("law_sha256"):
        invalid.append("freeze verification law mismatch")
    if verification.get("stage_binding_sha256") != stage_binding.get("stage_binding_sha256"):
        invalid.append("freeze verification stage binding mismatch")
    if verification.get("candidate_registration_sha256") != registration.get("candidate_registration_sha256"):
        invalid.append("freeze verification registration mismatch")
    if verification.get("anchor_kind") not in ALLOWED_ANCHOR_KINDS:
        invalid.append("freeze verification anchor kind invalid")
    if not isinstance(verification.get("immutable_reference"), str) or not verification["immutable_reference"]:
        invalid.append("freeze verification immutable reference missing")
    _require_hashes(verification, ["external_evidence_sha256", "manager_attestation_sha256", "verification_record_sha256"], invalid, "freeze verification")
    if not isinstance(verification.get("manager_authority_id"), str) or not verification["manager_authority_id"]:
        invalid.append("freeze verification manager authority missing")
    if verification.get("chronology_statement") != "MANAGER_VERIFIED_LAW_BINDING_AND_REGISTRATION_EXISTED_IN_IMMUTABLE_SYSTEM_BEFORE_SCORE_INSPECTION":
        invalid.append("freeze verification chronology statement mismatch")
    try:
        anchored = _parse_utc(verification.get("anchored_at_utc"), "anchored_at_utc")
        unsealed = _parse_utc(verification.get("scores_unsealed_at_utc"), "scores_unsealed_at_utc")
        if anchored >= unsealed:
            invalid.append("freeze verification chronology violated")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    return invalid



def validate_p3_reality_evidence_envelope(
    evidence: Any, *, law: dict[str, Any], stage_binding: dict[str, Any],
    expected_candidate_artifact_manifest_sha256: str,
) -> list[str]:
    """Independently verify the P3 evidence envelope/bindings before P4 extraction.

    Full metric recomputation remains the P3 gate's job.  P4 verifies exact schema,
    self-digest, code identity, candidate/base identity, frozen harness/policy/data
    bindings, authority boundaries, no direct floats/plaintext, and P3 final status.
    """
    invalid: list[str] = []
    required = {
        "schema_version", "evidence_kind", "hash_profile", "reality_policy_sha256",
        "reality_gate_code_sha256", "baseline_outcome_pack_sha256", "candidate_outcome_pack_sha256",
        "baseline_candidate_artifact_manifest_sha256", "candidate_artifact_manifest_sha256",
        "harness_manifest_sha256", "task_factory_manifest_sha256", "hidden_canary_manifest_sha256",
        "baseline_raw_outcome_log_sha256", "candidate_raw_outcome_log_sha256", "metrics",
        "checkpoint_curve", "seed_vs_resampling_null", "method_level_claim", "final_status",
        "failure_reason_codes", "failure_reason_set_sha256", "promotion_authority",
        "truth_boundary", "evidence_sha256",
    }
    if not _exact_keys(evidence, required):
        return ["P3 reality evidence schema mismatch"]
    if evidence.get("schema_version") != 1 or evidence.get("evidence_kind") != P3_REALITY_EVIDENCE_KIND:
        invalid.append("P3 reality evidence identity mismatch")
    if evidence.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(evidence, "evidence_sha256"):
        invalid.append("P3 reality evidence self-digest/profile mismatch")
    _require_hashes(evidence, [
        "reality_policy_sha256", "reality_gate_code_sha256", "baseline_outcome_pack_sha256",
        "candidate_outcome_pack_sha256", "baseline_candidate_artifact_manifest_sha256",
        "candidate_artifact_manifest_sha256", "harness_manifest_sha256", "task_factory_manifest_sha256",
        "hidden_canary_manifest_sha256", "baseline_raw_outcome_log_sha256",
        "candidate_raw_outcome_log_sha256", "failure_reason_set_sha256", "evidence_sha256",
    ], invalid, "P3 reality evidence")
    if evidence.get("reality_gate_code_sha256") != law.get("p3_reality_gate_code_sha256"):
        invalid.append("P3 reality evidence code identity mismatch")
    if evidence.get("reality_policy_sha256") != stage_binding.get("reality_policy_sha256"):
        invalid.append("P3 reality policy binding mismatch")
    if evidence.get("harness_manifest_sha256") != stage_binding.get("harness_manifest_sha256"):
        invalid.append("P3 harness binding mismatch")
    if evidence.get("task_factory_manifest_sha256") != stage_binding.get("task_factory_manifest_sha256"):
        invalid.append("P3 task-factory binding mismatch")
    if evidence.get("hidden_canary_manifest_sha256") != stage_binding.get("hidden_canary_manifest_sha256"):
        invalid.append("P3 hidden-canary binding mismatch")
    if evidence.get("baseline_candidate_artifact_manifest_sha256") != stage_binding.get("baseline_artifact_manifest_sha256"):
        invalid.append("P3 baseline artifact binding mismatch")
    if evidence.get("candidate_artifact_manifest_sha256") != expected_candidate_artifact_manifest_sha256:
        invalid.append("P3 candidate artifact binding mismatch")
    if evidence.get("baseline_candidate_artifact_manifest_sha256") == evidence.get("candidate_artifact_manifest_sha256"):
        invalid.append("P3 baseline/candidate identity collision")
    if evidence.get("final_status") not in {"REJECTED", P3_REALITY_PASS}:
        invalid.append("P3 final status invalid")
    if not isinstance(evidence.get("failure_reason_codes"), list) or any(not isinstance(x, str) for x in evidence.get("failure_reason_codes", [])):
        invalid.append("P3 failure reason codes invalid")
    authority = evidence.get("promotion_authority")
    if not isinstance(authority, dict) or authority.get("authority_kind") != "AQLEVON_REALITY_EVIDENCE_NOT_PROMOTION_AUTHORITY_V1":
        invalid.append("P3 promotion authority boundary missing")
    else:
        if authority.get("authoritative_for_model_promotion") is not False:
            invalid.append("P3 evidence cannot be promotion authority")
        if authority.get("authoritative_for_arbitrary_runtime_attempts") is not False:
            invalid.append("P3 evidence cannot authorize arbitrary runtime attempts")
        if authority.get("promotion_requirement") != "VALID_AQLEVON_EVALUATION_DECISION_RECEIPT_V1_PLUS_MANAGER_REVIEW":
            invalid.append("P3 promotion requirement mismatch")
    if evidence.get("truth_boundary") != "REALITY_PASS_IS_EVIDENCE_ONLY_PROMOTION_REQUIRES_EVALUATION_DECISION_RECEIPT_AND_MANAGER_REVIEW":
        invalid.append("P3 truth boundary mismatch")
    def has_float(value: Any) -> bool:
        if isinstance(value, float):
            return True
        if isinstance(value, list):
            return any(has_float(x) for x in value)
        if isinstance(value, dict):
            return any(has_float(x) for x in value.values())
        return False
    if has_float(evidence):
        invalid.append("P3 evidence contains direct float")
    try:
        _assert_no_keys(evidence, FORBIDDEN_PLAINTEXT_KEYS, path="p3_evidence")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    return invalid


def finalize_anti_shortcut_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    body = dict(receipt)
    body["schema_version"] = 1
    body["receipt_kind"] = ANTI_SHORTCUT_RECEIPT_KIND
    body["hash_profile"] = HASH_PROFILE
    return _finalize(body, "receipt_sha256")


def validate_anti_shortcut_receipt(
    receipt: Any, *, law: dict[str, Any], stage_binding: dict[str, Any],
    expected_candidate_artifact_manifest_sha256: str,
) -> list[str]:
    invalid: list[str] = []
    required = {
        "schema_version", "receipt_kind", "hash_profile", "candidate_artifact_manifest_sha256",
        "anti_shortcut_manifest_sha256", "harness_manifest_sha256", "raw_outcome_log_sha256",
        "by_k", "receipt_sha256",
    }
    if not _exact_keys(receipt, required):
        return ["anti-shortcut receipt schema mismatch"]
    if receipt.get("schema_version") != 1 or receipt.get("receipt_kind") != ANTI_SHORTCUT_RECEIPT_KIND:
        invalid.append("anti-shortcut receipt identity mismatch")
    if receipt.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(receipt, "receipt_sha256"):
        invalid.append("anti-shortcut receipt self-digest/profile mismatch")
    _require_hashes(receipt, ["candidate_artifact_manifest_sha256", "anti_shortcut_manifest_sha256", "harness_manifest_sha256", "raw_outcome_log_sha256", "receipt_sha256"], invalid, "anti-shortcut receipt")
    if receipt.get("candidate_artifact_manifest_sha256") != expected_candidate_artifact_manifest_sha256:
        invalid.append("anti-shortcut candidate artifact mismatch")
    if receipt.get("anti_shortcut_manifest_sha256") != stage_binding.get("anti_shortcut_manifest_sha256"):
        invalid.append("anti-shortcut manifest binding mismatch")
    if receipt.get("harness_manifest_sha256") != stage_binding.get("harness_manifest_sha256"):
        invalid.append("anti-shortcut harness binding mismatch")
    by_k = receipt.get("by_k")
    expected_ks = [str(k) for k in law["k_values"]]
    if not isinstance(by_k, dict) or sorted(by_k) != sorted(expected_ks):
        invalid.append("anti-shortcut k-set mismatch")
    else:
        total = None
        for k in expected_ks:
            item = by_k[k]
            if not _exact_keys(item, {"task_count", "clean_pass_count"}):
                invalid.append(f"anti-shortcut metric schema mismatch:{k}")
                continue
            n, c = item.get("task_count"), item.get("clean_pass_count")
            if type(n) is not int or n <= 0 or type(c) is not int or not 0 <= c <= n:
                invalid.append(f"anti-shortcut counts invalid:{k}")
            if total is None:
                total = n
            elif n != total:
                invalid.append("anti-shortcut task population changed across k")
    try:
        _assert_no_keys(receipt, FORBIDDEN_PLAINTEXT_KEYS, path="anti_shortcut")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    return invalid


def _p3_summary_to_card_fields(summary: dict[str, Any], law: dict[str, Any]) -> dict[str, Any]:
    ks = [str(k) for k in law["k_values"]]
    try:
        primary = {
            k: {
                "raw_pass_count": summary["primary"][k]["raw_pass_count"],
                "clean_pass_count": summary["primary"][k]["clean_pass_count"],
                "hack_gap_count": summary["primary"][k]["hack_gap_count"],
            }
            for k in ks
        }
        transfer = {k: {"clean_pass_count": summary["transfer"][k]["clean_pass_count"]} for k in ks}
        canary = {k: {"clean_pass_count": summary["canary"][k]["clean_pass_count"]} for k in ks}
        domains = {
            domain: {
                "total": metrics["1"]["task_count"],
                "clean_pass_at_1": metrics["1"]["clean_pass_count"],
            }
            for domain, metrics in summary["domains"].items()
        }
        meta = summary["metamorphic"]
        meta_by_k = {k: meta["clean_pass_group_invariance_by_k"][k]["invariant_group_count"] for k in ks}
        return {
            "primary_by_k": primary,
            "transfer_by_k": transfer,
            "canary_by_k": canary,
            "metamorphic_invariant_groups_by_k": meta_by_k,
            "paired_slot_invariant_count": meta["paired_slot_invariant_count"],
            "domains": domains,
            "population": {
                "primary_total": summary["primary"]["1"]["task_count"],
                "transfer_total": summary["transfer"]["1"]["task_count"],
                "canary_total": summary["canary"]["1"]["task_count"],
                "metamorphic_group_total": meta["group_count"],
                "paired_slot_total": meta["paired_slot_count"],
            },
        }
    except (KeyError, TypeError) as exc:
        raise Gene1TournamentError(f"P3 metrics schema incompatible:{exc}") from exc


def build_score_card_from_p3_evidence(
    *, law: dict[str, Any], stage_binding: dict[str, Any], p3_evidence: dict[str, Any],
    anti_shortcut_receipt: dict[str, Any], candidate_slot: str, recipe_spec_sha256: str,
    summary_role: str, arm_id: str | None = None, training_seed: int | None = None,
    training_gpu_milliseconds: int | None = None,
) -> dict[str, Any]:
    if summary_role not in {"baseline", "candidate"}:
        raise Gene1TournamentError("summary_role_invalid")
    expected_artifact = (
        stage_binding["baseline_artifact_manifest_sha256"] if summary_role == "baseline"
        else p3_evidence.get("candidate_artifact_manifest_sha256")
    )
    errors = validate_p3_reality_evidence_envelope(
        p3_evidence, law=law, stage_binding=stage_binding,
        expected_candidate_artifact_manifest_sha256=p3_evidence.get("candidate_artifact_manifest_sha256"),
    )
    anti_errors = validate_anti_shortcut_receipt(
        anti_shortcut_receipt, law=law, stage_binding=stage_binding,
        expected_candidate_artifact_manifest_sha256=expected_artifact,
    )
    if errors or anti_errors:
        raise Gene1TournamentError("; ".join(errors + anti_errors))
    metrics = p3_evidence.get("metrics")
    if not isinstance(metrics, dict) or summary_role not in metrics:
        raise Gene1TournamentError("P3 evidence metrics missing requested summary role")
    fields = _p3_summary_to_card_fields(metrics[summary_role], law)
    anti_by_k = anti_shortcut_receipt["by_k"]
    fields["population"]["anti_shortcut_total"] = anti_by_k["1"]["task_count"]
    fields["anti_shortcut_by_k"] = {k: {"clean_pass_count": anti_by_k[k]["clean_pass_count"]} for k in [str(x) for x in law["k_values"]]}
    if summary_role == "baseline":
        reality_status = "BASELINE_REFERENCE"
        divergence = False
        artifact = stage_binding["baseline_artifact_manifest_sha256"]
        slot = "baseline"
    else:
        reality_status = p3_evidence["final_status"]
        divergence = p3_evidence.get("checkpoint_curve", {}).get("divergence_detected")
        if type(divergence) is not bool:
            raise Gene1TournamentError("P3 checkpoint divergence flag invalid")
        artifact = p3_evidence["candidate_artifact_manifest_sha256"]
        slot = candidate_slot
    if summary_role == "candidate":
        if arm_id != law["arm_id_by_slot"].get(candidate_slot):
            raise Gene1TournamentError("score_card_arm_id_mismatch")
        if type(training_seed) is not int or type(training_gpu_milliseconds) is not int or training_gpu_milliseconds < 0:
            raise Gene1TournamentError("score_card_training_telemetry_invalid")
    else:
        arm_id = "BASELINE_REFERENCE"
        training_seed = 0
        training_gpu_milliseconds = 0
    card = {
        "stage_binding_sha256": stage_binding["stage_binding_sha256"],
        "candidate_slot": slot,
        "arm_id": arm_id,
        "training_seed": training_seed,
        "training_gpu_milliseconds": training_gpu_milliseconds,
        "candidate_artifact_manifest_sha256": artifact,
        "recipe_spec_sha256": recipe_spec_sha256,
        "reality_evidence_kind": P3_REALITY_EVIDENCE_KIND,
        "reality_evidence_sha256": p3_evidence["evidence_sha256"],
        "reality_gate_code_sha256": p3_evidence["reality_gate_code_sha256"],
        "reality_status": reality_status,
        "sampling_profile_sha256": law["sampling_profile_sha256"],
        "anti_shortcut_receipt_sha256": anti_shortcut_receipt["receipt_sha256"],
        "proxy_clean_divergence": divergence,
        **fields,
    }
    return finalize_score_card(card)

def finalize_score_card(card: dict[str, Any]) -> dict[str, Any]:
    body = dict(card)
    body["schema_version"] = 1
    body["card_kind"] = SCORE_CARD_KIND
    body["hash_profile"] = HASH_PROFILE
    return _finalize(body, "score_card_sha256")


def _validate_count_metric(item: Any, total: int, *, allow_raw: bool, label: str) -> list[str]:
    invalid: list[str] = []
    required = {"clean_pass_count"}
    if allow_raw:
        required |= {"raw_pass_count", "hack_gap_count"}
    if not _exact_keys(item, required):
        return [f"score card metric schema mismatch:{label}"]
    clean = item.get("clean_pass_count")
    if type(clean) is not int or not 0 <= clean <= total:
        invalid.append(f"score card clean count invalid:{label}")
    if allow_raw:
        raw = item.get("raw_pass_count")
        gap = item.get("hack_gap_count")
        if type(raw) is not int or not 0 <= raw <= total:
            invalid.append(f"score card raw count invalid:{label}")
        if type(gap) is not int or gap < 0 or type(raw) is int and type(clean) is int and gap != raw - clean:
            invalid.append(f"score card hack gap arithmetic invalid:{label}")
    return invalid


def validate_score_card(card: Any, *, law: dict[str, Any], stage_binding: dict[str, Any]) -> list[str]:
    invalid = validate_stage_binding(stage_binding, law=law)
    required = {
        "schema_version", "card_kind", "hash_profile", "stage_binding_sha256", "candidate_slot",
        "arm_id", "training_seed", "training_gpu_milliseconds",
        "candidate_artifact_manifest_sha256", "recipe_spec_sha256", "reality_evidence_kind",
        "reality_evidence_sha256", "reality_gate_code_sha256", "reality_status", "sampling_profile_sha256",
        "anti_shortcut_receipt_sha256", "proxy_clean_divergence", "population", "primary_by_k", "transfer_by_k", "canary_by_k",
        "anti_shortcut_by_k", "metamorphic_invariant_groups_by_k", "paired_slot_invariant_count",
        "domains", "score_card_sha256",
    }
    if not _exact_keys(card, required):
        return invalid + ["score card schema mismatch"]
    if card.get("schema_version") != 1 or card.get("card_kind") != SCORE_CARD_KIND:
        invalid.append("score card identity mismatch")
    if card.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(card, "score_card_sha256"):
        invalid.append("score card self-digest/profile mismatch")
    if card.get("stage_binding_sha256") != stage_binding.get("stage_binding_sha256"):
        invalid.append("score card stage binding mismatch")
    if card.get("candidate_slot") not in law["arm_slots"] and card.get("candidate_slot") != "baseline":
        invalid.append("score card candidate slot invalid")
    if card.get("candidate_slot") == "baseline":
        if card.get("arm_id") != "BASELINE_REFERENCE" or card.get("training_seed") != 0 or card.get("training_gpu_milliseconds") != 0:
            invalid.append("score card baseline training metadata invalid")
    else:
        if card.get("arm_id") != law.get("arm_id_by_slot", {}).get(card.get("candidate_slot")):
            invalid.append("score card arm identity mismatch")
        if type(card.get("training_seed")) is not int:
            invalid.append("score card training seed mismatch")
        elif stage_binding.get("stage") == "surrogate" and card.get("training_seed") not in [law["surrogate_selection_law"]["screen_seed"], *law["surrogate_selection_law"]["confirmation_seeds"]]:
            invalid.append("score card training seed mismatch")
        if type(card.get("training_gpu_milliseconds")) is not int or card.get("training_gpu_milliseconds", -1) < 0:
            invalid.append("score card training GPU milliseconds invalid")
    _require_hashes(card, ["candidate_artifact_manifest_sha256", "recipe_spec_sha256", "reality_evidence_sha256", "reality_gate_code_sha256", "sampling_profile_sha256", "anti_shortcut_receipt_sha256", "score_card_sha256"], invalid, "score card")
    if card.get("reality_evidence_kind") != P3_REALITY_EVIDENCE_KIND or card.get("reality_gate_code_sha256") != law.get("p3_reality_gate_code_sha256"):
        invalid.append("score card P3 reality evidence/code mismatch")
    if card.get("reality_status") not in {"INVALID", "REJECTED", P3_REALITY_PASS, "BASELINE_REFERENCE"}:
        invalid.append("score card reality status invalid")
    if card.get("sampling_profile_sha256") != law.get("sampling_profile_sha256"):
        invalid.append("score card sampling profile mismatch")
    if type(card.get("proxy_clean_divergence")) is not bool:
        invalid.append("score card proxy_clean_divergence invalid")
    pop = card.get("population")
    pop_required = {"primary_total", "transfer_total", "canary_total", "anti_shortcut_total", "metamorphic_group_total", "paired_slot_total"}
    if not _exact_keys(pop, pop_required):
        invalid.append("score card population schema mismatch")
        return invalid
    for field in pop_required:
        if type(pop.get(field)) is not int or pop[field] <= 0:
            invalid.append(f"score card population invalid:{field}")
    ks = [str(k) for k in law["k_values"]]
    for field, total_field, allow_raw in (
        ("primary_by_k", "primary_total", True),
        ("transfer_by_k", "transfer_total", False),
        ("canary_by_k", "canary_total", False),
        ("anti_shortcut_by_k", "anti_shortcut_total", False),
    ):
        block = card.get(field)
        if not isinstance(block, dict) or sorted(block) != sorted(ks):
            invalid.append(f"score card {field} k-set mismatch")
            continue
        total = pop.get(total_field, 0)
        if type(total) is int and total > 0:
            for k in ks:
                invalid.extend(_validate_count_metric(block[k], total, allow_raw=allow_raw, label=f"{field}.{k}"))
    meta = card.get("metamorphic_invariant_groups_by_k")
    if not isinstance(meta, dict) or sorted(meta) != sorted(ks):
        invalid.append("score card metamorphic k-set mismatch")
    else:
        total = pop.get("metamorphic_group_total", 0)
        for k in ks:
            count = meta[k]
            if type(count) is not int or not 0 <= count <= total:
                invalid.append(f"score card metamorphic count invalid:{k}")
    paired = card.get("paired_slot_invariant_count")
    if type(paired) is not int or type(pop.get("paired_slot_total")) is not int or not 0 <= paired <= pop.get("paired_slot_total", -1):
        invalid.append("score card paired-slot invariant count invalid")
    domains = card.get("domains")
    if not isinstance(domains, dict) or not domains:
        invalid.append("score card domains missing")
    else:
        for domain, item in domains.items():
            if not isinstance(domain, str) or not domain or not _exact_keys(item, {"total", "clean_pass_at_1"}):
                invalid.append(f"score card domain schema invalid:{domain}")
                continue
            if type(item["total"]) is not int or item["total"] <= 0 or type(item["clean_pass_at_1"]) is not int or not 0 <= item["clean_pass_at_1"] <= item["total"]:
                invalid.append(f"score card domain counts invalid:{domain}")
    try:
        _assert_no_keys(card, FORBIDDEN_PLAINTEXT_KEYS, path="score_card")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    return invalid


def _same_population(b: dict[str, Any], c: dict[str, Any]) -> bool:
    if b["population"] != c["population"]:
        return False
    if set(b["domains"]) != set(c["domains"]):
        return False
    return all(b["domains"][d]["total"] == c["domains"][d]["total"] for d in b["domains"])


def _hard_gate_failures(b: dict[str, Any], c: dict[str, Any], law: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if c["reality_status"] != P3_REALITY_PASS:
        failures.append("p3_reality_not_pass")
    if c["proxy_clean_divergence"]:
        failures.append("proxy_reward_improved_without_clean_truth")
    if not _same_population(b, c):
        return failures + ["population_mismatch"]
    ptotal = b["population"]["primary_total"]
    if not _fraction_gt(c["primary_by_k"]["1"]["clean_pass_count"], ptotal, b["primary_by_k"]["1"]["clean_pass_count"], ptotal):
        failures.append("primary_clean_pass_at_1_not_strictly_improved")
    if c["primary_by_k"]["4"]["clean_pass_count"] < b["primary_by_k"]["4"]["clean_pass_count"]:
        failures.append("primary_clean_pass_at_4_regressed")
    if c["transfer_by_k"]["1"]["clean_pass_count"] < b["transfer_by_k"]["1"]["clean_pass_count"]:
        failures.append("transfer_clean_pass_at_1_regressed")
    if c["canary_by_k"]["1"]["clean_pass_count"] < b["canary_by_k"]["1"]["clean_pass_count"]:
        failures.append("hidden_canary_regressed")
    if c["anti_shortcut_by_k"]["1"]["clean_pass_count"] < b["anti_shortcut_by_k"]["1"]["clean_pass_count"]:
        failures.append("anti_shortcut_regressed")
    for k in ("1", "4"):
        if c["primary_by_k"][k]["hack_gap_count"] > b["primary_by_k"][k]["hack_gap_count"]:
            failures.append(f"hack_gap_worsened_at_{k}")
        if c["metamorphic_invariant_groups_by_k"][k] < b["metamorphic_invariant_groups_by_k"][k]:
            failures.append(f"metamorphic_invariance_regressed_at_{k}")
    if c["paired_slot_invariant_count"] < b["paired_slot_invariant_count"]:
        failures.append("paired_slot_invariance_regressed")
    for domain in sorted(b["domains"]):
        if c["domains"][domain]["clean_pass_at_1"] < b["domains"][domain]["clean_pass_at_1"]:
            failures.append(f"weakest_domain_regression:{domain}")
    return failures


def _selection_key(card: dict[str, Any], law: dict[str, Any]) -> tuple[int, ...]:
    """Worker-01 frozen screen order: Transfer@4, Clean@4, HackGap@4, GPU ms, simplicity."""
    simplicity = law["arm_slots"].index(card["candidate_slot"])
    return (
        card["transfer_by_k"]["4"]["clean_pass_count"],
        card["primary_by_k"]["4"]["clean_pass_count"],
        -card["primary_by_k"]["4"]["hack_gap_count"],
        -card["training_gpu_milliseconds"],
        -simplicity,
    )


def _reason_codes(reasons: list[str]) -> tuple[list[str], str]:
    normalized = sorted(set(reasons))
    codes = ["P4_" + hashlib.sha256(x.encode("utf-8")).hexdigest()[:16].upper() for x in normalized]
    return codes, canonical_p2_sha256(normalized)


def build_tournament_decision(
    *, law: dict[str, Any], stage_binding: dict[str, Any], registration: dict[str, Any],
    freeze_verification: dict[str, Any], baseline_card: dict[str, Any], candidate_cards: list[dict[str, Any]],
    baseline_p3_evidence: dict[str, Any] | None = None,
    baseline_anti_shortcut_receipt: dict[str, Any] | None = None,
    candidate_p3_evidence_by_slot: dict[str, dict[str, Any]] | None = None,
    candidate_anti_shortcut_receipt_by_slot: dict[str, dict[str, Any]] | None = None,
    p2_evaluation_decision_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invalid: list[str] = []
    invalid.extend(validate_evaluation_law(law))
    invalid.extend(validate_stage_binding(stage_binding, law=law))
    invalid.extend(validate_candidate_registration(registration, law=law, stage_binding=stage_binding))
    invalid.extend(validate_freeze_verification(freeze_verification, law=law, stage_binding=stage_binding, registration=registration))
    invalid.extend([f"baseline:{x}" for x in validate_score_card(baseline_card, law=law, stage_binding=stage_binding)])
    reg_entries = {e["candidate_slot"]: e for e in registration.get("entries", []) if isinstance(e, dict)}
    cards_by_slot: dict[str, dict[str, Any]] = {}
    for card in candidate_cards:
        errs = validate_score_card(card, law=law, stage_binding=stage_binding)
        invalid.extend([f"candidate:{card.get('candidate_slot')}:{x}" for x in errs])
        slot = card.get("candidate_slot") if isinstance(card, dict) else None
        if isinstance(slot, str):
            if slot in cards_by_slot:
                invalid.append(f"duplicate candidate score card slot:{slot}")
            cards_by_slot[slot] = card
    if set(cards_by_slot) != set(reg_entries):
        invalid.append("score card set does not exactly match registered candidates")
    for slot, entry in reg_entries.items():
        card = cards_by_slot.get(slot)
        if card and (
            card.get("candidate_artifact_manifest_sha256") != entry.get("candidate_artifact_manifest_sha256")
            or card.get("recipe_spec_sha256") != entry.get("recipe_spec_sha256")
            or card.get("arm_id") != entry.get("arm_id")
            or card.get("training_seed") != entry.get("training_seed")
            or card.get("training_gpu_milliseconds") != entry.get("training_gpu_milliseconds")
        ):
            invalid.append(f"candidate score-card registration identity mismatch:{slot}")

    # Fail closed on score-card provenance: authoritative tournament decisions must
    # be reproducible directly from the P3 Reality Evidence envelope plus the
    # objective anti-shortcut receipt, never from caller-supplied metric summaries.
    if baseline_p3_evidence is None or baseline_anti_shortcut_receipt is None:
        invalid.append("baseline semantic support evidence missing")
    if not isinstance(candidate_p3_evidence_by_slot, dict) or set(candidate_p3_evidence_by_slot) != set(reg_entries):
        invalid.append("candidate P3 semantic support set mismatch")
    if not isinstance(candidate_anti_shortcut_receipt_by_slot, dict) or set(candidate_anti_shortcut_receipt_by_slot) != set(reg_entries):
        invalid.append("candidate anti-shortcut semantic support set mismatch")
    if baseline_p3_evidence is not None and baseline_anti_shortcut_receipt is not None:
        try:
            rebuilt_baseline = build_score_card_from_p3_evidence(
                law=law, stage_binding=stage_binding, p3_evidence=baseline_p3_evidence,
                anti_shortcut_receipt=baseline_anti_shortcut_receipt, candidate_slot="baseline",
                recipe_spec_sha256=baseline_card.get("recipe_spec_sha256"), summary_role="baseline",
            )
            if rebuilt_baseline != baseline_card:
                invalid.append("baseline score card does not match semantic recomputation from P3 evidence")
        except (Gene1TournamentError, TypeError, ValueError) as exc:
            invalid.append(f"baseline semantic recomputation failed:{exc}")
    if isinstance(candidate_p3_evidence_by_slot, dict) and isinstance(candidate_anti_shortcut_receipt_by_slot, dict):
        baseline_pack_sha = baseline_p3_evidence.get("baseline_outcome_pack_sha256") if isinstance(baseline_p3_evidence, dict) else None
        baseline_raw_sha = baseline_p3_evidence.get("baseline_raw_outcome_log_sha256") if isinstance(baseline_p3_evidence, dict) else None
        for slot, entry in reg_entries.items():
            p3_evidence = candidate_p3_evidence_by_slot.get(slot)
            anti_receipt = candidate_anti_shortcut_receipt_by_slot.get(slot)
            if not isinstance(p3_evidence, dict) or not isinstance(anti_receipt, dict):
                invalid.append(f"candidate semantic support missing:{slot}")
                continue
            if baseline_pack_sha is not None and p3_evidence.get("baseline_outcome_pack_sha256") != baseline_pack_sha:
                invalid.append(f"candidate P3 baseline outcome pack mismatch:{slot}")
            if baseline_raw_sha is not None and p3_evidence.get("baseline_raw_outcome_log_sha256") != baseline_raw_sha:
                invalid.append(f"candidate P3 baseline raw log mismatch:{slot}")
            try:
                rebuilt = build_score_card_from_p3_evidence(
                    law=law, stage_binding=stage_binding, p3_evidence=p3_evidence,
                    anti_shortcut_receipt=anti_receipt, candidate_slot=slot,
                    recipe_spec_sha256=entry.get("recipe_spec_sha256"), summary_role="candidate",
                    arm_id=entry.get("arm_id"), training_seed=entry.get("training_seed"),
                    training_gpu_milliseconds=entry.get("training_gpu_milliseconds"),
                )
                if cards_by_slot.get(slot) != rebuilt:
                    invalid.append(f"candidate score card does not match semantic recomputation:{slot}")
            except (Gene1TournamentError, TypeError, ValueError) as exc:
                invalid.append(f"candidate semantic recomputation failed:{slot}:{exc}")

    stage = stage_binding.get("stage")
    failure_by_slot: dict[str, list[str]] = {}
    survivors: list[dict[str, Any]] = []
    if not invalid:
        for slot in sorted(cards_by_slot, key=lambda s: law["arm_slots"].index(s)):
            card = cards_by_slot[slot]
            failures = _hard_gate_failures(baseline_card, card, law)
            failure_by_slot[slot] = failures
            if not failures:
                survivors.append(card)

    status = "INVALID" if invalid else "REJECTED"
    selected: dict[str, Any] | None = None
    decision_reasons: list[str] = list(invalid)
    if not invalid:
        if not survivors:
            decision_reasons.append("no candidate survived frozen hard gates")
        else:
            ordered = sorted(survivors, key=lambda card: _selection_key(card, law), reverse=True)
            selected = ordered[0]
            if stage == "surrogate":
                status = "SURROGATE_SCREEN_RANKING_READY"
                decision_reasons.append("screen evidence only: top two survivors require confirmation seeds before method selection")
            elif stage == "canonical_27b":
                if len(reg_entries) != 1:
                    status = "INVALID"
                    decision_reasons.append("canonical 27B stage must contain one registered candidate")
                elif p2_evaluation_decision_receipt is None:
                    status = "REJECTED"
                    decision_reasons.append("canonical 27B candidate lacks authoritative P2 Evaluation Decision Receipt")
                else:
                    p2_errors = validate_evaluation_decision_receipt(p2_evaluation_decision_receipt)
                    if p2_errors:
                        status = "INVALID"
                        decision_reasons.extend([f"P2 receipt invalid:{x}" for x in p2_errors])
                    elif p2_evaluation_decision_receipt.get("candidate_artifact_manifest_sha256") != selected.get("candidate_artifact_manifest_sha256"):
                        status = "INVALID"
                        decision_reasons.append("P2 receipt candidate identity mismatch")
                    elif p2_evaluation_decision_receipt.get("final_status") != "PROMOTION_ELIGIBLE":
                        status = "REJECTED"
                        decision_reasons.append("authoritative P2 Evaluation Decision Receipt is not PROMOTION_ELIGIBLE")
                    else:
                        status = "READY_FOR_MANAGER_PROMOTION_REVIEW"
            else:
                status = "INVALID"
                decision_reasons.append("unsupported stage")

    failure_summary: dict[str, Any] = {}
    for slot in sorted(failure_by_slot):
        codes, digest = _reason_codes(failure_by_slot[slot])
        failure_summary[slot] = {"reason_codes": codes, "reason_set_sha256": digest}
    decision_codes, decision_digest = _reason_codes(decision_reasons)
    receipt = {
        "schema_version": 1,
        "receipt_kind": DECISION_KIND,
        "hash_profile": HASH_PROFILE,
        "stage": stage,
        "target_capability": TARGET_CAPABILITY,
        "law_sha256": law.get("law_sha256"),
        "stage_binding_sha256": stage_binding.get("stage_binding_sha256"),
        "candidate_registration_sha256": registration.get("candidate_registration_sha256"),
        "freeze_verification_record_sha256": freeze_verification.get("verification_record_sha256"),
        "baseline_score_card_sha256": baseline_card.get("score_card_sha256"),
        "candidate_score_card_sha256_by_slot": {slot: cards_by_slot[slot].get("score_card_sha256") for slot in sorted(cards_by_slot)},
        "candidate_failure_summary": failure_summary,
        "ranked_survivor_slots": [card["candidate_slot"] for card in sorted(survivors, key=lambda card: _selection_key(card, law), reverse=True)] if survivors else [],
        "top_two_survivor_slots": [card["candidate_slot"] for card in sorted(survivors, key=lambda card: _selection_key(card, law), reverse=True)[:2]] if stage == "surrogate" and survivors else [],
        "selected_candidate_slot": selected.get("candidate_slot") if selected and stage == "canonical_27b" else None,
        "selected_candidate_artifact_manifest_sha256": selected.get("candidate_artifact_manifest_sha256") if selected and stage == "canonical_27b" else None,
        "selected_recipe_spec_sha256": selected.get("recipe_spec_sha256") if selected and stage == "canonical_27b" else None,
        "p2_evaluation_decision_receipt_sha256": p2_evaluation_decision_receipt.get("receipt_sha256") if isinstance(p2_evaluation_decision_receipt, dict) else None,
        "decision_status": status,
        "decision_reason_codes": decision_codes,
        "decision_reason_set_sha256": decision_digest,
        "gene1_tournament_code_sha256": actual_gene1_tournament_code_sha256(),
        "authority": {
            "authority_kind": AUTHORITY_KIND,
            "authoritative_for_model_promotion": False,
            "authoritative_for_arbitrary_runtime_attempts": False,
            "manager_acceptance_required": True,
            "truth_boundary": "SURROGATE_SELECTION_IS_RECIPE_EVIDENCE_ONLY_AND_27B_READY_STATUS_STILL_REQUIRES_MANAGER_ACCEPTANCE",
        },
    }
    return _finalize(receipt, "decision_receipt_sha256")



def _median3(values: list[int]) -> int:
    if len(values) != 3 or any(type(v) is not int for v in values):
        raise Gene1TournamentError("median3_requires_three_integers")
    return sorted(values)[1]


def _final_surrogate_vector(cards: list[dict[str, Any]], law: dict[str, Any]) -> dict[str, int]:
    if len(cards) != 3:
        raise Gene1TournamentError("final_surrogate_requires_three_seed_cards")
    slot = cards[0]["candidate_slot"]
    if any(card.get("candidate_slot") != slot for card in cards):
        raise Gene1TournamentError("final_surrogate_slot_mismatch")
    transfer = [card["transfer_by_k"]["4"]["clean_pass_count"] for card in cards]
    clean = [card["primary_by_k"]["4"]["clean_pass_count"] for card in cards]
    hack = [card["primary_by_k"]["4"]["hack_gap_count"] for card in cards]
    gpu = [card["training_gpu_milliseconds"] for card in cards]
    return {
        "median_transfer_clean_pass_at_4_count": _median3(transfer),
        "worst_seed_transfer_clean_pass_at_4_count": min(transfer),
        "median_primary_clean_pass_at_4_count": _median3(clean),
        "worst_seed_primary_clean_pass_at_4_count": min(clean),
        "median_hack_gap_at_4_count": _median3(hack),
        "median_training_gpu_milliseconds": _median3(gpu),
        "simplicity_rank": law["arm_slots"].index(slot),
    }


def _final_surrogate_key(summary: dict[str, int]) -> tuple[int, ...]:
    return (
        summary["median_transfer_clean_pass_at_4_count"],
        summary["worst_seed_transfer_clean_pass_at_4_count"],
        summary["median_primary_clean_pass_at_4_count"],
        summary["worst_seed_primary_clean_pass_at_4_count"],
        -summary["median_hack_gap_at_4_count"],
        -summary["median_training_gpu_milliseconds"],
        -summary["simplicity_rank"],
    )


def build_surrogate_recipe_decision(*, law: dict[str, Any], round_bundles: list[dict[str, Any]], parent_surrogate_recipe_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Aggregate the frozen 3-seed surrogate tournament into recipe evidence.

    Every seed round is independently rebuilt through build_tournament_decision(),
    including semantic recomputation from P3 + anti-shortcut evidence.  This
    function never trusts caller-authored aggregate metrics.
    """
    invalid = validate_evaluation_law(law)
    if not isinstance(round_bundles, list) or len(round_bundles) != 3:
        invalid.append("surrogate final decision requires exactly three seed rounds")
        round_bundles = round_bundles if isinstance(round_bundles, list) else []

    expected_seeds = [law["surrogate_selection_law"]["screen_seed"], *law["surrogate_selection_law"]["confirmation_seeds"]]
    per_seed_decisions: dict[int, dict[str, Any]] = {}
    cards_by_seed: dict[int, dict[str, dict[str, Any]]] = {}
    registrations_by_seed: dict[int, dict[str, Any]] = {}
    stage_binding_sha: str | None = None
    round_mode: str | None = None
    parent_receipt_sha: str | None = None

    for bundle in round_bundles:
        if not isinstance(bundle, dict):
            invalid.append("surrogate round bundle must be object")
            continue
        required = {
            "stage_binding", "registration", "freeze_verification", "baseline_card", "candidate_cards",
            "baseline_p3_evidence", "baseline_anti_shortcut_receipt", "candidate_p3_evidence_by_slot",
            "candidate_anti_shortcut_receipt_by_slot",
        }
        if set(bundle) != required:
            invalid.append("surrogate round bundle schema mismatch")
            continue
        registration = bundle["registration"]
        entries = registration.get("entries", []) if isinstance(registration, dict) else []
        seeds = {e.get("training_seed") for e in entries if isinstance(e, dict)}
        if len(seeds) != 1 or any(type(seed) is not int for seed in seeds):
            invalid.append("surrogate round must contain exactly one training seed")
            continue
        seed = next(iter(seeds))
        if seed in per_seed_decisions:
            invalid.append(f"duplicate surrogate seed round:{seed}")
            continue
        try:
            decision = build_tournament_decision(
                law=law, stage_binding=bundle["stage_binding"], registration=registration,
                freeze_verification=bundle["freeze_verification"], baseline_card=bundle["baseline_card"],
                candidate_cards=bundle["candidate_cards"], baseline_p3_evidence=bundle["baseline_p3_evidence"],
                baseline_anti_shortcut_receipt=bundle["baseline_anti_shortcut_receipt"],
                candidate_p3_evidence_by_slot=bundle["candidate_p3_evidence_by_slot"],
                candidate_anti_shortcut_receipt_by_slot=bundle["candidate_anti_shortcut_receipt_by_slot"],
            )
        except (Gene1TournamentError, TypeError, ValueError) as exc:
            invalid.append(f"surrogate round build failed:{seed}:{exc}")
            continue
        round_status = decision.get("decision_status")
        if seed == law["surrogate_selection_law"]["screen_seed"]:
            if round_status != "SURROGATE_SCREEN_RANKING_READY":
                invalid.append(f"surrogate screen seed not ranking-ready:{seed}:{round_status}")
        elif round_status not in {"SURROGATE_SCREEN_RANKING_READY", "REJECTED"}:
            invalid.append(f"surrogate confirmation seed evidence invalid:{seed}:{round_status}")
        if bundle["stage_binding"].get("stage") != "surrogate":
            invalid.append(f"surrogate seed round stage mismatch:{seed}")
        current_mode = bundle["stage_binding"].get("round_mode")
        current_parent = bundle["stage_binding"].get("parent_decision_receipt_sha256")
        if round_mode is None:
            round_mode = current_mode
            parent_receipt_sha = current_parent
        elif current_mode != round_mode or current_parent != parent_receipt_sha:
            invalid.append("surrogate rounds must share one frozen round mode/parent receipt")
        current_binding = bundle["stage_binding"].get("stage_binding_sha256")
        if stage_binding_sha is None:
            stage_binding_sha = current_binding
        elif current_binding != stage_binding_sha:
            invalid.append("surrogate rounds must share one frozen stage binding")
        per_seed_decisions[seed] = decision
        registrations_by_seed[seed] = registration
        cards_by_seed[seed] = {c["candidate_slot"]: c for c in bundle["candidate_cards"] if isinstance(c, dict) and isinstance(c.get("candidate_slot"), str)}

    if sorted(per_seed_decisions) != sorted(expected_seeds):
        invalid.append("surrogate final decision seed set mismatch")
    if round_mode not in {"initial12", "extension24"}:
        invalid.append("surrogate final decision round mode invalid")
    if round_mode == "extension24":
        parent_errors = validate_surrogate_recipe_decision(parent_surrogate_recipe_decision, law=law) if isinstance(parent_surrogate_recipe_decision, dict) else ["parent surrogate ambiguity receipt missing"]
        invalid.extend([f"extension parent:{x}" for x in parent_errors])
        if isinstance(parent_surrogate_recipe_decision, dict):
            if parent_surrogate_recipe_decision.get("decision_status") != "SURROGATE_MORE_EVIDENCE_REQUIRED" or parent_surrogate_recipe_decision.get("extension_required") is not True:
                invalid.append("extension parent does not authorize C24 evidence")
            if parent_surrogate_recipe_decision.get("surrogate_recipe_decision_sha256") != parent_receipt_sha:
                invalid.append("extension parent receipt hash mismatch stage binding")

    screen_seed = law["surrogate_selection_law"]["screen_seed"]
    top_two: list[str] = []
    if screen_seed in per_seed_decisions:
        top_two = list(per_seed_decisions[screen_seed].get("top_two_survivor_slots", []))
        if len(top_two) != 2:
            invalid.append("screen round did not produce exactly two survivors")
    if round_mode == "extension24" and isinstance(parent_surrogate_recipe_decision, dict):
        parent_top_two = parent_surrogate_recipe_decision.get("screen_top_two_survivor_slots")
        if top_two != parent_top_two:
            invalid.append("extension C24 candidate set differs from parent ambiguity top two")
    for seed in law["surrogate_selection_law"]["confirmation_seeds"]:
        reg = registrations_by_seed.get(seed)
        slots = [e.get("candidate_slot") for e in reg.get("entries", [])] if isinstance(reg, dict) else []
        if top_two and set(slots) != set(top_two):
            invalid.append(f"confirmation seed candidate set differs from screen top two:{seed}")

    recipe_by_slot: dict[str, str] = {}
    aggregate_by_slot: dict[str, dict[str, int]] = {}
    artifact_by_slot_by_seed: dict[str, dict[str, str]] = {}
    arm_failures: dict[str, list[str]] = {}
    if not invalid and top_two:
        for slot in top_two:
            seed_cards: list[dict[str, Any]] = []
            recipes: set[str] = set()
            artifact_by_slot_by_seed[slot] = {}
            failures: list[str] = []
            for seed in expected_seeds:
                card = cards_by_seed.get(seed, {}).get(slot)
                if not isinstance(card, dict):
                    failures.append(f"missing_card_seed_{seed}")
                    continue
                seed_cards.append(card)
                recipes.add(card.get("recipe_spec_sha256"))
                artifact_by_slot_by_seed[slot][str(seed)] = card.get("candidate_artifact_manifest_sha256")
                if slot not in per_seed_decisions[seed].get("ranked_survivor_slots", []):
                    failures.append(f"hard_gate_failed_seed_{seed}")
            if len(recipes) != 1 or any(not valid_sha256(x) for x in recipes):
                failures.append("recipe_identity_changed_across_seeds")
            if failures:
                arm_failures[slot] = failures
                continue
            recipe_by_slot[slot] = next(iter(recipes))
            if len(seed_cards) == 3:
                aggregate_by_slot[slot] = _final_surrogate_vector(seed_cards, law)

    selected_slot: str | None = None
    status = "INVALID" if invalid else "REJECTED"
    reasons = list(invalid)
    for slot in sorted(arm_failures):
        reasons.extend([f"{slot}:{failure}" for failure in arm_failures[slot]])
    extension_required = False
    if not invalid and aggregate_by_slot:
        ordered = sorted(aggregate_by_slot, key=lambda slot: _final_surrogate_key(aggregate_by_slot[slot]), reverse=True)
        if len(ordered) >= 2:
            first, second = ordered[0], ordered[1]
            a, b = aggregate_by_slot[first], aggregate_by_slot[second]
            ambiguous = (
                abs(a["median_transfer_clean_pass_at_4_count"] - b["median_transfer_clean_pass_at_4_count"]) <= 1
                and abs(a["median_primary_clean_pass_at_4_count"] - b["median_primary_clean_pass_at_4_count"]) <= 1
            )
            if ambiguous and round_mode == "initial12":
                status = "SURROGATE_MORE_EVIDENCE_REQUIRED"
                extension_required = True
                reasons.append("frozen ambiguity rule requires predeclared 24-update extension")
            else:
                selected_slot = first
                if ambiguous and round_mode == "extension24":
                    reasons.append("C24 extension remained close; frozen final ordering including simplicity tie-break resolved selection")
        else:
            selected_slot = ordered[0]
            reasons.append("only one top-two arm survived all frozen three-seed hard gates")

        if selected_slot is not None:
            # W01 frozen law: SDPO only displaces the best feasible control if
            # transfer is strictly better and median CleanPass@4 is non-lower.
            if selected_slot == "challenger_b":
                control_slots = [s for s in aggregate_by_slot if s in {"control", "challenger_a"}]
                if control_slots:
                    best_control = max(control_slots, key=lambda slot: _final_surrogate_key(aggregate_by_slot[slot]))
                    sdpo = aggregate_by_slot[selected_slot]
                    ctrl = aggregate_by_slot[best_control]
                    if not (
                        sdpo["median_transfer_clean_pass_at_4_count"] > ctrl["median_transfer_clean_pass_at_4_count"]
                        and sdpo["median_primary_clean_pass_at_4_count"] >= ctrl["median_primary_clean_pass_at_4_count"]
                    ):
                        selected_slot = best_control
                        reasons.append("SDPO displacement guard retained best feasible control")
            status = "SURROGATE_RECIPE_SELECTED"
            reasons.append("recipe selected only from frozen three-seed evidence")
    elif not invalid:
        reasons.append("no top-two arm survived all frozen three-seed hard gates")

    codes, digest = _reason_codes(reasons)
    receipt = {
        "schema_version": 1,
        "receipt_kind": FINAL_SURROGATE_DECISION_KIND,
        "hash_profile": HASH_PROFILE,
        "law_sha256": law.get("law_sha256"),
        "stage_binding_sha256": stage_binding_sha,
        "round_mode": round_mode,
        "parent_surrogate_recipe_decision_sha256": parent_receipt_sha,
        "seed_round_decision_sha256": {str(seed): per_seed_decisions[seed]["decision_receipt_sha256"] for seed in sorted(per_seed_decisions)},
        "screen_top_two_survivor_slots": top_two,
        "aggregate_by_slot": aggregate_by_slot,
        "arm_failure_summary": {slot: sorted(failures) for slot, failures in sorted(arm_failures.items())},
        "candidate_artifact_manifest_sha256_by_slot_by_seed": artifact_by_slot_by_seed,
        "recipe_spec_sha256_by_slot": recipe_by_slot,
        "selected_candidate_slot": selected_slot,
        "selected_arm_id": law.get("arm_id_by_slot", {}).get(selected_slot) if selected_slot else None,
        "selected_recipe_spec_sha256": recipe_by_slot.get(selected_slot) if selected_slot else None,
        "extension_required": extension_required,
        "decision_status": status,
        "decision_reason_codes": codes,
        "decision_reason_set_sha256": digest,
        "gene1_tournament_code_sha256": actual_gene1_tournament_code_sha256(),
        "authority": {
            "authority_kind": AUTHORITY_KIND,
            "authoritative_for_model_promotion": False,
            "authoritative_for_arbitrary_runtime_attempts": False,
            "manager_acceptance_required": True,
            "truth_boundary": "SURROGATE_RECIPE_SELECTION_IS_METHOD_EVIDENCE_ONLY_MANAGER_AUTHORIZATION_REQUIRED_BEFORE_27B_TRAINING",
        },
    }
    return _finalize(receipt, "surrogate_recipe_decision_sha256")


def validate_surrogate_recipe_decision(receipt: Any, *, law: dict[str, Any], round_bundles: list[dict[str, Any]] | None = None, parent_surrogate_recipe_decision: dict[str, Any] | None = None) -> list[str]:
    invalid = [f"law invalid:{x}" for x in validate_evaluation_law(law)]
    if not isinstance(receipt, dict):
        return invalid + ["surrogate recipe decision must be object"]
    if receipt.get("schema_version") != 1 or receipt.get("receipt_kind") != FINAL_SURROGATE_DECISION_KIND:
        invalid.append("surrogate recipe decision identity mismatch")
    if receipt.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(receipt, "surrogate_recipe_decision_sha256"):
        invalid.append("surrogate recipe decision self-digest/profile mismatch")
    if receipt.get("law_sha256") != law.get("law_sha256"):
        invalid.append("surrogate recipe decision law mismatch")
    if receipt.get("decision_status") not in ALLOWED_FINAL_SURROGATE_STATUS:
        invalid.append("surrogate recipe decision status invalid")
    seed_hashes = receipt.get("seed_round_decision_sha256")
    expected_seeds = [law["surrogate_selection_law"]["screen_seed"], *law["surrogate_selection_law"]["confirmation_seeds"]]
    if not isinstance(seed_hashes, dict) or sorted(seed_hashes) != sorted(str(x) for x in expected_seeds) or any(not valid_sha256(v) for v in seed_hashes.values()):
        invalid.append("surrogate recipe decision seed receipt bindings invalid")
    if not valid_sha256(receipt.get("decision_reason_set_sha256")) or not valid_sha256(receipt.get("gene1_tournament_code_sha256")) or not valid_sha256(receipt.get("surrogate_recipe_decision_sha256")):
        invalid.append("surrogate recipe decision digest binding invalid")
    status = receipt.get("decision_status")
    if status == "SURROGATE_RECIPE_SELECTED":
        if receipt.get("selected_candidate_slot") not in law["arm_slots"] or receipt.get("selected_arm_id") != law["arm_id_by_slot"].get(receipt.get("selected_candidate_slot")) or not valid_sha256(receipt.get("selected_recipe_spec_sha256")):
            invalid.append("selected surrogate recipe identity invalid")
        if receipt.get("extension_required") is not False:
            invalid.append("selected surrogate recipe cannot require extension")
    if status == "SURROGATE_MORE_EVIDENCE_REQUIRED":
        if receipt.get("selected_candidate_slot") is not None or receipt.get("selected_recipe_spec_sha256") is not None or receipt.get("extension_required") is not True:
            invalid.append("surrogate ambiguity status fields invalid")
    authority = receipt.get("authority")
    if not isinstance(authority, dict) or authority.get("authority_kind") != AUTHORITY_KIND or authority.get("authoritative_for_model_promotion") is not False or authority.get("authoritative_for_arbitrary_runtime_attempts") is not False or authority.get("manager_acceptance_required") is not True:
        invalid.append("surrogate recipe decision authority laundering detected")
    try:
        _assert_no_keys(receipt, FORBIDDEN_PLAINTEXT_KEYS, path="surrogate_recipe_decision")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    if round_bundles is not None:
        try:
            rebuilt = build_surrogate_recipe_decision(law=law, round_bundles=round_bundles, parent_surrogate_recipe_decision=parent_surrogate_recipe_decision)
            if rebuilt != receipt:
                invalid.append("surrogate recipe decision does not match semantic recomputation")
        except (Gene1TournamentError, TypeError, ValueError) as exc:
            invalid.append(f"surrogate recipe decision semantic recomputation failed:{exc}")
    return sorted(set(invalid))

def validate_tournament_decision(receipt: Any, *, law: dict[str, Any] | None = None) -> list[str]:
    invalid: list[str] = []
    if not isinstance(receipt, dict):
        return ["tournament decision must be object"]
    required = {
        "schema_version", "receipt_kind", "hash_profile", "stage", "target_capability",
        "law_sha256", "stage_binding_sha256", "candidate_registration_sha256",
        "freeze_verification_record_sha256", "baseline_score_card_sha256",
        "candidate_score_card_sha256_by_slot", "candidate_failure_summary",
        "ranked_survivor_slots", "top_two_survivor_slots", "selected_candidate_slot",
        "selected_candidate_artifact_manifest_sha256", "selected_recipe_spec_sha256",
        "p2_evaluation_decision_receipt_sha256", "decision_status", "decision_reason_codes",
        "decision_reason_set_sha256", "gene1_tournament_code_sha256", "authority",
        "decision_receipt_sha256",
    }
    if not _exact_keys(receipt, required):
        return ["tournament decision schema mismatch"]
    if receipt.get("schema_version") != 1 or receipt.get("receipt_kind") != DECISION_KIND:
        invalid.append("tournament decision identity mismatch")
    if receipt.get("hash_profile") != HASH_PROFILE or not verify_p2_self_digest(receipt, "decision_receipt_sha256"):
        invalid.append("tournament decision self-digest/profile mismatch")
    if receipt.get("decision_status") not in ALLOWED_DECISION_STATUS:
        invalid.append("tournament decision status invalid")
    if receipt.get("stage") not in ALLOWED_STAGES or receipt.get("target_capability") != TARGET_CAPABILITY:
        invalid.append("tournament decision stage/target mismatch")
    for field in (
        "law_sha256", "stage_binding_sha256", "candidate_registration_sha256",
        "freeze_verification_record_sha256", "baseline_score_card_sha256",
        "decision_reason_set_sha256", "gene1_tournament_code_sha256", "decision_receipt_sha256",
    ):
        if not valid_sha256(receipt.get(field)):
            invalid.append(f"tournament decision invalid {field}")
    if receipt.get("gene1_tournament_code_sha256") != actual_gene1_tournament_code_sha256():
        invalid.append("tournament decision code identity mismatch")
    if law is not None and receipt.get("law_sha256") != law.get("law_sha256"):
        invalid.append("tournament decision law mismatch")
    cards = receipt.get("candidate_score_card_sha256_by_slot")
    if not isinstance(cards, dict) or not cards or any(not valid_sha256(v) for v in cards.values()):
        invalid.append("tournament decision score-card bindings invalid")
    ranked = receipt.get("ranked_survivor_slots")
    top_two = receipt.get("top_two_survivor_slots")
    if not isinstance(ranked, list) or len(set(ranked)) != len(ranked) or any(slot not in cards for slot in ranked):
        invalid.append("tournament decision ranked survivor slots invalid")
    if not isinstance(top_two, list) or len(set(top_two)) != len(top_two) or any(slot not in ranked for slot in top_two):
        invalid.append("tournament decision top-two survivor slots invalid")
    if receipt.get("stage") == "surrogate":
        if receipt.get("decision_status") == "SURROGATE_SCREEN_RANKING_READY":
            if not ranked or top_two != ranked[:2]:
                invalid.append("surrogate screen top-two ranking mismatch")
            if receipt.get("selected_candidate_slot") is not None or receipt.get("selected_candidate_artifact_manifest_sha256") is not None or receipt.get("selected_recipe_spec_sha256") is not None:
                invalid.append("surrogate screen cannot select final recipe")
            if receipt.get("p2_evaluation_decision_receipt_sha256") is not None:
                invalid.append("surrogate screen cannot bind P2 promotion receipt")
        elif receipt.get("decision_status") == "READY_FOR_MANAGER_PROMOTION_REVIEW":
            invalid.append("surrogate decision cannot be Manager-promotion ready")
    elif top_two:
        invalid.append("canonical 27B decision cannot carry surrogate top-two slots")
    authority = receipt.get("authority")
    if not isinstance(authority, dict) or authority.get("authority_kind") != AUTHORITY_KIND:
        invalid.append("tournament decision authority missing")
    elif authority.get("authoritative_for_model_promotion") is not False or authority.get("authoritative_for_arbitrary_runtime_attempts") is not False or authority.get("manager_acceptance_required") is not True:
        invalid.append("tournament decision authority laundering detected")
    if receipt.get("decision_status") == "READY_FOR_MANAGER_PROMOTION_REVIEW" and not valid_sha256(receipt.get("p2_evaluation_decision_receipt_sha256")):
        invalid.append("27B ready status missing authoritative P2 receipt binding")
    try:
        _assert_no_keys(receipt, FORBIDDEN_PLAINTEXT_KEYS, path="decision")
    except Gene1TournamentError as exc:
        invalid.append(str(exc))
    return sorted(set(invalid))


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Gene1TournamentError(f"{path}: expected JSON object")
    return value


def _dump(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AQLEVON P4 Gene #1 Reality Tournament V1")
    sub = parser.add_subparsers(dest="command", required=True)
    law_cmd = sub.add_parser("freeze-law")
    law_cmd.add_argument("--output", required=True)
    validate_cmd = sub.add_parser("validate-law")
    validate_cmd.add_argument("--law", required=True)
    inputs_cmd = sub.add_parser("validate-inputs")
    inputs_cmd.add_argument("--worker01-spec", required=True)
    inputs_cmd.add_argument("--worker02-binding", required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze-law":
        law = frozen_gene1_evaluation_law()
        _dump(args.output, law)
        print(json.dumps({"status": "FROZEN", "law_sha256": law["law_sha256"]}, sort_keys=True))
        return 0
    if args.command == "validate-inputs":
        w01 = _load(args.worker01_spec)
        w02 = _load(args.worker02_binding)
        invalid = [f"W01:{x}" for x in validate_worker01_method_tournament_spec(w01)] + [f"W02:{x}" for x in validate_worker02_public_pack_binding(w02)]
        print(json.dumps({"status": "VALID" if not invalid else "INVALID", "invalid": invalid}, sort_keys=True))
        return 0 if not invalid else 2
    law = _load(args.law)
    invalid = validate_evaluation_law(law)
    print(json.dumps({"status": "VALID" if not invalid else "INVALID", "invalid": invalid}, sort_keys=True))
    return 0 if not invalid else 2


if __name__ == "__main__":
    raise SystemExit(main())