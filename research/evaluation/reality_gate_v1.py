#!/usr/bin/env python3
"""AQLEVON P3 Reality Gate V1.

Evidence-only evaluation gate for coding/tool capability candidates.

The gate computes integrity-adjusted searchability and transfer metrics, hidden
canary performance, semantics-preserving invariance, seed-vs-resampling nulls,
weakest-domain floors, and proxy-reward/clean-truth checkpoint divergence.

It deliberately does NOT confer promotion authority.  A REALITY_PASS result is
only evidence consumed by the authoritative Worker-05 Evaluation Decision
Receipt / Manager review path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from evaluation_decision_receipt_v1 import (
    HASH_PROFILE,
    canonical_decimal_string,
    canonical_p2_sha256,
    valid_sha256,
    verify_p2_self_digest,
)

REALITY_EVIDENCE_KIND = "AQLEVON_REALITY_GATE_EVIDENCE_V1"
REALITY_POLICY_KIND = "AQLEVON_REALITY_GATE_POLICY_V1"
SEED_NULL_KIND = "AQLEVON_SEED_VS_RESAMPLING_NULL_V1"
AUTHORITY_KIND = "AQLEVON_REALITY_EVIDENCE_NOT_PROMOTION_AUTHORITY_V1"
ALLOWED_STATUS = {"INVALID", "REJECTED", "REALITY_PASS"}
ALLOWED_SPLITS = {"primary", "transfer", "canary"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_PLAINTEXT_KEYS = {
    "prompt", "prompts", "answer", "answers", "solution", "solutions",
    "expected_output", "expected_answer", "hidden_answer", "hidden_solution",
    "input_text", "output_text", "response_text", "tool_output_plaintext",
}


class RealityGateError(ValueError):
    """Fail-closed construction or validation error."""


def _sha256_json(value: Any) -> str:
    return canonical_p2_sha256(value)


def actual_reality_gate_code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _rate_decimal(successes: int, total: int) -> str | None:
    if total <= 0:
        return None
    # Decimal rendering without binary floating point.
    frac = Fraction(successes, total)
    # 12 decimal places is enough for deterministic display while exact counts
    # remain authoritative for comparisons.
    scaled = frac.numerator * 10**12 // frac.denominator
    integer, remainder = divmod(scaled, 10**12)
    text = f"{integer}.{remainder:012d}".rstrip("0").rstrip(".")
    return text or "0"


def _fraction_to_basis_points_floor(successes: int, total: int) -> int:
    if total <= 0:
        return 0
    return (successes * 10000) // total


def _fraction_to_basis_points_ceil(successes: int, total: int) -> int:
    if total <= 0:
        return 0
    return (successes * 10000 + total - 1) // total


def _delta_basis_points_exact(a_success: int, a_total: int, b_success: int, b_total: int) -> Fraction:
    if a_total <= 0 or b_total <= 0:
        raise RealityGateError("rate_delta_requires_nonempty_populations")
    return Fraction(a_success, a_total) * 10000 - Fraction(b_success, b_total) * 10000


def _fraction_decimal(value: Fraction) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    scaled = value.numerator * 10**12 // value.denominator
    integer, remainder = divmod(scaled, 10**12)
    text = f"{integer}.{remainder:012d}".rstrip("0").rstrip(".")
    return sign + (text or "0")


def _assert_no_forbidden_plaintext(value: Any, path: str = "reality") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_PLAINTEXT_KEYS:
                raise RealityGateError(f"forbidden_plaintext_key:{path}.{key}")
            _assert_no_forbidden_plaintext(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _assert_no_forbidden_plaintext(child, f"{path}[{i}]")


def _reason_codes(prefix: str, reasons: Iterable[str]) -> tuple[list[str], str]:
    normalized = sorted(set(str(x) for x in reasons))
    codes = [f"{prefix}_{hashlib.sha256(x.encode('utf-8')).hexdigest()[:16].upper()}" for x in normalized]
    return codes, _sha256_json(normalized)


def _exact_keys(obj: Any, required: set[str], optional: set[str] | None = None) -> bool:
    if not isinstance(obj, dict):
        return False
    allowed = required | (optional or set())
    keys = set(obj)
    return required <= keys and keys <= allowed


def validate_policy(policy: Any) -> list[str]:
    invalid: list[str] = []
    required = {
        "schema_version", "policy_kind", "hash_profile", "k_values",
        "min_primary_tasks", "min_transfer_tasks", "min_hidden_canaries",
        "min_clean_pass_delta_basis_points", "min_transfer_pass_delta_basis_points",
        "max_hack_gap_basis_points", "max_hack_gap_increase_basis_points",
        "min_canary_clean_pass_basis_points", "min_metamorphic_invariance_basis_points",
        "min_paired_slot_invariance_basis_points", "weakest_domain_floor_basis_points",
        "required_domains", "require_seed_null_for_method_claim",
        "seed_null_max_p_millionths", "reject_on_any_reward_clean_divergence",
        "policy_sha256",
    }
    if not _exact_keys(policy, required):
        return ["reality policy schema mismatch"]
    if policy.get("schema_version") != 1 or policy.get("policy_kind") != REALITY_POLICY_KIND:
        invalid.append("reality policy identity mismatch")
    if policy.get("hash_profile") != HASH_PROFILE:
        invalid.append("reality policy hash_profile mismatch")
    if not verify_p2_self_digest(policy, "policy_sha256"):
        invalid.append("reality policy self-digest mismatch")

    ks = policy.get("k_values")
    if not isinstance(ks, list) or not ks or any(type(k) is not int or k < 1 or k > 64 for k in ks) or ks != sorted(set(ks)):
        invalid.append("reality policy k_values invalid")
    for name in (
        "min_primary_tasks", "min_transfer_tasks", "min_hidden_canaries",
        "min_clean_pass_delta_basis_points", "min_transfer_pass_delta_basis_points",
        "max_hack_gap_basis_points", "max_hack_gap_increase_basis_points",
        "min_canary_clean_pass_basis_points", "min_metamorphic_invariance_basis_points",
        "min_paired_slot_invariance_basis_points", "seed_null_max_p_millionths",
    ):
        value = policy.get(name)
        if type(value) is not int or value < 0:
            invalid.append(f"reality policy {name} invalid")
    for name in (
        "min_clean_pass_delta_basis_points", "min_transfer_pass_delta_basis_points",
        "max_hack_gap_basis_points", "max_hack_gap_increase_basis_points",
        "min_canary_clean_pass_basis_points", "min_metamorphic_invariance_basis_points",
        "min_paired_slot_invariance_basis_points",
    ):
        value = policy.get(name)
        if type(value) is int and value > 10000:
            invalid.append(f"reality policy {name} exceeds 10000 basis points")
    if type(policy.get("seed_null_max_p_millionths")) is int and policy["seed_null_max_p_millionths"] > 1_000_000:
        invalid.append("reality policy seed_null_max_p_millionths exceeds one million")
    if type(policy.get("require_seed_null_for_method_claim")) is not bool:
        invalid.append("reality policy require_seed_null_for_method_claim invalid")
    if policy.get("reject_on_any_reward_clean_divergence") is not True:
        invalid.append("reality policy must reject any reward/clean divergence")
    floors = policy.get("weakest_domain_floor_basis_points")
    required_domains = policy.get("required_domains")
    if not isinstance(required_domains, list) or not required_domains or any(not isinstance(x, str) or not x for x in required_domains):
        invalid.append("reality policy required_domains invalid")
    if not isinstance(floors, dict):
        invalid.append("reality policy weakest_domain_floor_basis_points invalid")
    elif isinstance(required_domains, list):
        if set(floors) != set(required_domains):
            invalid.append("reality policy weakest-domain floor keys mismatch required_domains")
        for domain, floor in floors.items():
            if not isinstance(domain, str) or not domain or type(floor) is not int or not 0 <= floor <= 10000:
                invalid.append(f"reality policy weakest-domain floor invalid:{domain}")
    return invalid


def build_policy(**kwargs: Any) -> dict[str, Any]:
    body = {
        "schema_version": 1,
        "policy_kind": REALITY_POLICY_KIND,
        "hash_profile": HASH_PROFILE,
        **kwargs,
    }
    body["policy_sha256"] = _sha256_json(body)
    invalid = validate_policy(body)
    if invalid:
        raise RealityGateError("; ".join(invalid))
    return body


def _validate_sample(sample: Any, task_id: str) -> list[str]:
    invalid: list[str] = []
    required = {"sample_id", "raw_reward_pass", "clean_truth_pass", "integrity_violation"}
    if not _exact_keys(sample, required):
        return [f"sample schema mismatch:{task_id}"]
    if not isinstance(sample.get("sample_id"), str) or not sample["sample_id"]:
        invalid.append(f"sample_id invalid:{task_id}")
    for field in ("raw_reward_pass", "clean_truth_pass", "integrity_violation"):
        if type(sample.get(field)) is not bool:
            invalid.append(f"sample {field} not boolean:{task_id}")
    return invalid


def finalize_outcome_pack(pack: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pack, dict):
        raise RealityGateError("outcome_pack_not_object")
    body = dict(pack)
    body["hash_profile"] = HASH_PROFILE
    body.pop("outcome_pack_sha256", None)
    body["outcome_pack_sha256"] = _sha256_json(body)
    return body


def validate_outcome_pack(pack: Any, *, policy: dict[str, Any]) -> list[str]:
    invalid = validate_policy(policy)
    if invalid:
        return [f"policy invalid:{x}" for x in invalid]
    required = {
        "schema_version", "outcome_pack_kind", "candidate_artifact_manifest_sha256",
        "harness_manifest_sha256", "task_factory_manifest_sha256",
        "hidden_canary_manifest_sha256", "raw_outcome_log_sha256", "tasks",
        "hash_profile", "outcome_pack_sha256",
    }
    if not _exact_keys(pack, required):
        return ["outcome pack schema mismatch"]
    if pack.get("schema_version") != 1 or pack.get("outcome_pack_kind") != "AQLEVON_REALITY_OUTCOME_PACK_V1":
        invalid.append("outcome pack identity mismatch")
    if pack.get("hash_profile") != HASH_PROFILE:
