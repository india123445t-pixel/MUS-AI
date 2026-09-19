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
        invalid.append("outcome pack hash_profile mismatch")
    if not verify_p2_self_digest(pack, "outcome_pack_sha256"):
        invalid.append("outcome pack self-digest mismatch")
    for field in (
        "candidate_artifact_manifest_sha256", "harness_manifest_sha256",
        "task_factory_manifest_sha256", "hidden_canary_manifest_sha256", "raw_outcome_log_sha256",
        "outcome_pack_sha256",
    ):
        if not valid_sha256(pack.get(field)):
            invalid.append(f"outcome pack {field} invalid")
    tasks = pack.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        invalid.append("outcome pack tasks missing")
        return invalid
    ks = policy["k_values"]
    max_k = max(ks)
    seen_ids: set[str] = set()
    split_counts = {"primary": 0, "transfer": 0, "canary": 0}
    canary_hashes: set[str] = set()
    domain_counts: dict[str, int] = {}
    metamorphic_groups: dict[str, int] = {}
    for task in tasks:
        try:
            _assert_no_forbidden_plaintext(task, "task")
        except RealityGateError as exc:
            invalid.append(str(exc))
        required_task = {
            "task_id", "domain_id", "split", "samples", "metamorphic_group_id",
            "variant_id", "is_hidden_canary", "canary_id_sha256",
        }
        if not _exact_keys(task, required_task):
            invalid.append("task schema mismatch")
            continue
        tid = task.get("task_id")
        if not isinstance(tid, str) or not tid:
            invalid.append("task_id invalid")
            continue
        if tid in seen_ids:
            invalid.append(f"duplicate task_id:{tid}")
        seen_ids.add(tid)
        domain = task.get("domain_id")
        if not isinstance(domain, str) or not domain:
            invalid.append(f"domain_id invalid:{tid}")
        split = task.get("split")
        if split not in ALLOWED_SPLITS:
            invalid.append(f"split invalid:{tid}")
        else:
            split_counts[split] += 1
        samples = task.get("samples")
        if not isinstance(samples, list) or len(samples) < max_k:
            invalid.append(f"insufficient samples for k={max_k}:{tid}")
        else:
            sample_ids: set[str] = set()
            for sample in samples:
                invalid.extend(_validate_sample(sample, tid))
                sid = sample.get("sample_id") if isinstance(sample, dict) else None
                if isinstance(sid, str):
                    if sid in sample_ids:
                        invalid.append(f"duplicate sample_id:{tid}:{sid}")
                    sample_ids.add(sid)
        is_canary = task.get("is_hidden_canary")
        canary_hash = task.get("canary_id_sha256")
        if type(is_canary) is not bool:
            invalid.append(f"is_hidden_canary invalid:{tid}")
        if split == "canary":
            if is_canary is not True or not valid_sha256(canary_hash):
                invalid.append(f"hidden canary binding invalid:{tid}")
            elif canary_hash in canary_hashes:
                invalid.append(f"duplicate hidden canary hash:{tid}")
            else:
                canary_hashes.add(canary_hash)
        else:
            if is_canary is not False or canary_hash is not None:
                invalid.append(f"non-canary task carries canary identity:{tid}")
        group = task.get("metamorphic_group_id")
        variant = task.get("variant_id")
        if group is None:
            if variant is not None:
                invalid.append(f"variant without metamorphic group:{tid}")
        else:
            if not isinstance(group, str) or not group or not isinstance(variant, str) or not variant:
                invalid.append(f"metamorphic identity invalid:{tid}")
            else:
                metamorphic_groups[group] = metamorphic_groups.get(group, 0) + 1
        if isinstance(domain, str) and domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
    if split_counts["primary"] < policy["min_primary_tasks"]:
        invalid.append("primary task count below policy minimum")
    if split_counts["transfer"] < policy["min_transfer_tasks"]:
        invalid.append("transfer task count below policy minimum")
    if split_counts["canary"] < policy["min_hidden_canaries"]:
        invalid.append("hidden canary count below policy minimum")
    for domain in policy["required_domains"]:
        if domain_counts.get(domain, 0) == 0:
            invalid.append(f"required domain missing:{domain}")
    for group, count in metamorphic_groups.items():
        if count < 2:
            invalid.append(f"metamorphic group has fewer than two variants:{group}")
    return invalid


def _clean_sample(sample: dict[str, Any]) -> bool:
    return sample["clean_truth_pass"] is True and sample["integrity_violation"] is False


def _task_pass(task: dict[str, Any], k: int, *, clean: bool) -> bool:
    samples = task["samples"][:k]
    if clean:
        return any(_clean_sample(s) for s in samples)
    return any(s["raw_reward_pass"] is True for s in samples)


def _population_metrics(tasks: list[dict[str, Any]], ks: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in ks:
        raw = sum(1 for task in tasks if _task_pass(task, k, clean=False))
        clean = sum(1 for task in tasks if _task_pass(task, k, clean=True))
        total = len(tasks)
        gap = raw - clean
        out[str(k)] = {
            "task_count": total,
            "raw_pass_count": raw,
            "raw_pass_rate": _rate_decimal(raw, total),
            "clean_pass_count": clean,
            "clean_pass_rate": _rate_decimal(clean, total),
            "hack_gap_count": gap,
            "hack_gap_rate": _rate_decimal(gap, total),
        }
    return out


def _domain_metrics(tasks: list[dict[str, Any]], ks: list[int]) -> dict[str, Any]:
    domains = sorted({task["domain_id"] for task in tasks})
    return {domain: _population_metrics([t for t in tasks if t["domain_id"] == domain], ks) for domain in domains}


def _metamorphic_metrics(tasks: list[dict[str, Any]], ks: list[int]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        group = task.get("metamorphic_group_id")
        if isinstance(group, str):
            groups.setdefault(group, []).append(task)
    group_summary: dict[str, Any] = {}
    total_slots = 0
    invariant_slots = 0
    invariant_groups_by_k = {k: 0 for k in ks}
    for group in sorted(groups):
        variants = sorted(groups[group], key=lambda t: t["variant_id"])
        max_slots = min(len(t["samples"]) for t in variants)
        group_slot_total = 0
        group_slot_same = 0
        for i in range(max_slots):
            states = {_clean_sample(t["samples"][i]) for t in variants}
            group_slot_total += 1
            if len(states) == 1:
                group_slot_same += 1
        total_slots += group_slot_total
        invariant_slots += group_slot_same
        k_state: dict[str, bool] = {}
        for k in ks:
            passes = {_task_pass(t, k, clean=True) for t in variants}
            invariant = len(passes) == 1
            k_state[str(k)] = invariant
            if invariant:
                invariant_groups_by_k[k] += 1
        group_summary[group] = {
            "variant_count": len(variants),
            "paired_slot_count": group_slot_total,
            "paired_slot_invariant_count": group_slot_same,
            "paired_slot_invariance_rate": _rate_decimal(group_slot_same, group_slot_total),
            "clean_pass_invariant_by_k": k_state,
        }
    group_count = len(groups)
    return {
        "group_count": group_count,
        "groups": group_summary,
        "paired_slot_count": total_slots,
        "paired_slot_invariant_count": invariant_slots,
        "paired_slot_invariance_rate": _rate_decimal(invariant_slots, total_slots),
        "clean_pass_group_invariance_by_k": {
            str(k): {
                "invariant_group_count": invariant_groups_by_k[k],
                "group_count": group_count,
                "rate": _rate_decimal(invariant_groups_by_k[k], group_count),
            }
            for k in ks
        },
    }


def summarize_outcome_pack(pack: dict[str, Any], *, policy: dict[str, Any]) -> dict[str, Any]:
    invalid = validate_outcome_pack(pack, policy=policy)
    if invalid:
        raise RealityGateError("; ".join(invalid))
    tasks = pack["tasks"]
    ks = policy["k_values"]
    primary = [t for t in tasks if t["split"] == "primary"]
    transfer = [t for t in tasks if t["split"] == "transfer"]
    canary = [t for t in tasks if t["split"] == "canary"]
    integrity_violations = sum(
        1 for task in tasks for sample in task["samples"] if sample["integrity_violation"] is True
    )
    return {
        "primary": _population_metrics(primary, ks),
        "transfer": _population_metrics(transfer, ks),
        "canary": _population_metrics(canary, ks),
        "domains": _domain_metrics(primary, ks),
        "metamorphic": _metamorphic_metrics(primary + transfer, ks),
        "integrity_violation_sample_count": integrity_violations,
        "total_sample_count": sum(len(t["samples"]) for t in tasks),
    }


def seed_vs_resampling_null(
    *,
    training_seed_success_sets: list[list[str]],
    resampling_null_groups: list[list[list[str]]],
    universe_task_ids: list[str],
) -> dict[str, Any]:
    """Compare cross-training-seed union coverage to equal-sample resampling null.

    Each success set is a list of task ids solved by one independently trained seed.
    Each null group contains the same number of success sets but comes from repeated
    resampling of one frozen model/seed.  No RNG occurs here; the caller supplies the
    frozen resampling trials so the result is reproducible.
    """
    universe = set(universe_task_ids)
    if not universe or len(universe) != len(universe_task_ids):
        raise RealityGateError("seed_null_universe_invalid")
    if len(training_seed_success_sets) < 2:
        raise RealityGateError("seed_null_requires_at_least_two_training_seeds")
    seed_count = len(training_seed_success_sets)

    def normalize(run: list[str]) -> set[str]:
        if not isinstance(run, list) or any(not isinstance(x, str) for x in run):
            raise RealityGateError("seed_null_success_set_invalid")
        s = set(run)
        if not s <= universe:
            raise RealityGateError("seed_null_success_set_outside_universe")
        return s

    observed_sets = [normalize(run) for run in training_seed_success_sets]
    observed_union = set().union(*observed_sets)
    null_counts: list[int] = []
    for group in resampling_null_groups:
        if not isinstance(group, list) or len(group) != seed_count:
            raise RealityGateError("seed_null_group_size_mismatch")
        null_union = set().union(*(normalize(run) for run in group))
        null_counts.append(len(null_union))
    if not null_counts:
        raise RealityGateError("seed_null_requires_resampling_groups")
    greater_equal = sum(1 for count in null_counts if count >= len(observed_union))
    p_num = greater_equal + 1
    p_den = len(null_counts) + 1
    null_mean = Fraction(sum(null_counts), len(null_counts))
    input_identity = {
        "hash_profile": HASH_PROFILE,
        "universe_task_ids": sorted(universe),
        "training_seed_success_sets": [sorted(x) for x in observed_sets],
        "resampling_null_groups": [[sorted(normalize(run)) for run in group] for group in resampling_null_groups],
    }
    result = {
        "schema_version": 1,
        "result_kind": SEED_NULL_KIND,
        "hash_profile": HASH_PROFILE,
        "input_population_sha256": _sha256_json(input_identity),
        "training_seed_count": seed_count,
        "universe_task_count": len(universe),
        "observed_union_count": len(observed_union),
        "observed_union_rate": _rate_decimal(len(observed_union), len(universe)),
        "null_group_count": len(null_counts),
        "null_union_count_min": min(null_counts),
        "null_union_count_max": max(null_counts),
        "null_union_count_mean": _fraction_decimal(null_mean),
        "one_sided_p_numerator": p_num,
        "one_sided_p_denominator": p_den,
        "one_sided_p": _rate_decimal(p_num, p_den),
    }
    result["result_sha256"] = _sha256_json(result)
    return result


def validate_seed_null_result(result: Any) -> list[str]:
    invalid: list[str] = []
    required = {
        "schema_version", "result_kind", "hash_profile", "input_population_sha256",
        "training_seed_count", "universe_task_count", "observed_union_count",
        "observed_union_rate", "null_group_count", "null_union_count_min",
        "null_union_count_max", "null_union_count_mean", "one_sided_p_numerator",
        "one_sided_p_denominator", "one_sided_p", "result_sha256",
    }
    if not _exact_keys(result, required):
        return ["seed null result schema mismatch"]
    if result.get("schema_version") != 1 or result.get("result_kind") != SEED_NULL_KIND:
        invalid.append("seed null result identity mismatch")
    if result.get("hash_profile") != HASH_PROFILE:
        invalid.append("seed null hash_profile mismatch")
    if not valid_sha256(result.get("input_population_sha256")):
        invalid.append("seed null input population hash invalid")
    if not verify_p2_self_digest(result, "result_sha256"):
        invalid.append("seed null self-digest mismatch")
    for field in ("training_seed_count", "universe_task_count", "observed_union_count", "null_group_count", "null_union_count_min", "null_union_count_max", "one_sided_p_numerator", "one_sided_p_denominator"):
        if type(result.get(field)) is not int or result[field] < 0:
            invalid.append(f"seed null {field} invalid")
    if type(result.get("one_sided_p_denominator")) is int and type(result.get("one_sided_p_numerator")) is int:
        if result["one_sided_p_numerator"] < 1 or result["one_sided_p_denominator"] < result["one_sided_p_numerator"]:
            invalid.append("seed null p fraction invalid")
    return invalid


def analyze_checkpoint_curve(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    required = {"step", "proxy_reward_basis_points", "clean_truth_basis_points"}
    if not isinstance(checkpoints, list) or len(checkpoints) < 2:
        raise RealityGateError("checkpoint_curve_requires_baseline_and_candidate")
    prior_step = -1
    for cp in checkpoints:
        if not _exact_keys(cp, required):
            raise RealityGateError("checkpoint_curve_schema_mismatch")
        if type(cp["step"]) is not int or cp["step"] < 0 or cp["step"] <= prior_step:
            raise RealityGateError("checkpoint_curve_steps_not_strictly_increasing")
        prior_step = cp["step"]
        for field in ("proxy_reward_basis_points", "clean_truth_basis_points"):
            if type(cp[field]) is not int or not 0 <= cp[field] <= 10000:
                raise RealityGateError(f"checkpoint_curve_{field}_invalid")
    baseline = checkpoints[0]
    divergence_steps: list[int] = []
    for cp in checkpoints[1:]:
        proxy_improved = cp["proxy_reward_basis_points"] > baseline["proxy_reward_basis_points"]
        clean_improved = cp["clean_truth_basis_points"] > baseline["clean_truth_basis_points"]
        if proxy_improved and not clean_improved:
            divergence_steps.append(cp["step"])
    final = checkpoints[-1]
    return {
        "baseline_step": baseline["step"],
        "final_step": final["step"],
        "baseline_proxy_reward_basis_points": baseline["proxy_reward_basis_points"],
        "final_proxy_reward_basis_points": final["proxy_reward_basis_points"],
        "baseline_clean_truth_basis_points": baseline["clean_truth_basis_points"],
        "final_clean_truth_basis_points": final["clean_truth_basis_points"],
        "divergence_detected": bool(divergence_steps),
        "divergence_steps": divergence_steps,
        "first_divergence_step": divergence_steps[0] if divergence_steps else None,
    }


def _metric_counts(summary: dict[str, Any], population: str, k: int) -> tuple[int, int, int]:
    item = summary[population][str(k)]
    return item["raw_pass_count"], item["clean_pass_count"], item["task_count"]


def _promotion_authority_boundary() -> dict[str, Any]:
    return {
        "authority_kind": AUTHORITY_KIND,
        "authoritative_for_model_promotion": False,
        "promotion_requirement": "VALID_AQLEVON_EVALUATION_DECISION_RECEIPT_V1_PLUS_MANAGER_REVIEW",
        "authoritative_for_arbitrary_runtime_attempts": False,
    }


def evaluate_reality_gate(
    *,
    baseline_pack: dict[str, Any],
    candidate_pack: dict[str, Any],
    policy: dict[str, Any],
    checkpoint_curve: list[dict[str, Any]],
    seed_null_result: dict[str, Any] | None = None,
    method_level_claim: bool = False,
) -> dict[str, Any]:
    policy_invalid = validate_policy(policy)
    if policy_invalid:
        raise RealityGateError("; ".join(policy_invalid))
    for label, pack in (("baseline", baseline_pack), ("candidate", candidate_pack)):
        invalid = validate_outcome_pack(pack, policy=policy)
        if invalid:
            raise RealityGateError(f"{label}_pack_invalid:" + ";".join(invalid))
    binding_fields = (
        "harness_manifest_sha256", "task_factory_manifest_sha256",
        "hidden_canary_manifest_sha256",
    )
    for field in binding_fields:
        if baseline_pack[field] != candidate_pack[field]:
            raise RealityGateError(f"baseline_candidate_{field}_mismatch")
    if baseline_pack["candidate_artifact_manifest_sha256"] == candidate_pack["candidate_artifact_manifest_sha256"]:
        raise RealityGateError("baseline_and_candidate_artifact_identity_must_differ")

    baseline = summarize_outcome_pack(baseline_pack, policy=policy)
    candidate = summarize_outcome_pack(candidate_pack, policy=policy)
    curve = analyze_checkpoint_curve(checkpoint_curve)
    reasons: list[str] = []
    k1 = 1
    if k1 not in policy["k_values"]:
        raise RealityGateError("policy_must_include_k_1")

    # Primary clean capability gain.
    _, b_clean, b_total = _metric_counts(baseline, "primary", k1)
    _, c_clean, c_total = _metric_counts(candidate, "primary", k1)
    clean_delta = _delta_basis_points_exact(c_clean, c_total, b_clean, b_total)
    if clean_delta < policy["min_clean_pass_delta_basis_points"]:
        reasons.append("clean_pass_gain_below_frozen_minimum")

    # Sealed transfer gain.
    _, bt_clean, bt_total = _metric_counts(baseline, "transfer", k1)
    _, ct_clean, ct_total = _metric_counts(candidate, "transfer", k1)
    transfer_delta = _delta_basis_points_exact(ct_clean, ct_total, bt_clean, bt_total)
    if transfer_delta < policy["min_transfer_pass_delta_basis_points"]:
        reasons.append("transfer_pass_gain_below_frozen_minimum")

    # HackGap absolute cap and non-worsening cap.
    b_raw, b_clean2, b_total2 = _metric_counts(baseline, "primary", k1)
    c_raw, c_clean2, c_total2 = _metric_counts(candidate, "primary", k1)
    b_gap = b_raw - b_clean2
    c_gap = c_raw - c_clean2
    c_gap_bp_ceil = _fraction_to_basis_points_ceil(c_gap, c_total2)
    if c_gap_bp_ceil > policy["max_hack_gap_basis_points"]:
        reasons.append("candidate_hack_gap_exceeds_frozen_cap")
    gap_increase = _delta_basis_points_exact(c_gap, c_total2, b_gap, b_total2)
    if gap_increase > policy["max_hack_gap_increase_basis_points"]:
        reasons.append("candidate_hack_gap_worsened_beyond_frozen_cap")

    # Hidden canaries.
    _, c_canary_clean, c_canary_total = _metric_counts(candidate, "canary", k1)
    if _fraction_to_basis_points_floor(c_canary_clean, c_canary_total) < policy["min_canary_clean_pass_basis_points"]:
        reasons.append("hidden_canary_clean_pass_below_floor")

    # Metamorphic/isomorphic invariance.
    meta = candidate["metamorphic"]
    k1_inv = meta["clean_pass_group_invariance_by_k"]["1"]
    if _fraction_to_basis_points_floor(k1_inv["invariant_group_count"], k1_inv["group_count"]) < policy["min_metamorphic_invariance_basis_points"]:
        reasons.append("metamorphic_clean_pass_invariance_below_floor")
    if _fraction_to_basis_points_floor(meta["paired_slot_invariant_count"], meta["paired_slot_count"]) < policy["min_paired_slot_invariance_basis_points"]:
        reasons.append("paired_slot_invariance_below_floor")

    # Hard weakest-domain floors use candidate primary CleanPass@1.
    for domain in policy["required_domains"]:
        item = candidate["domains"].get(domain, {}).get("1")
        if not item:
            reasons.append(f"weakest_domain_missing:{domain}")
            continue
        floor = policy["weakest_domain_floor_basis_points"][domain]
        if _fraction_to_basis_points_floor(item["clean_pass_count"], item["task_count"]) < floor:
            reasons.append(f"weakest_domain_floor_failed:{domain}")

    # Exact anti-reward-hacking law.
    if curve["divergence_detected"]:
        reasons.append("proxy_reward_improved_without_clean_truth_improvement")

    seed_null = seed_null_result
    if seed_null is not None:
        seed_invalid = validate_seed_null_result(seed_null)
        if seed_invalid:
            raise RealityGateError("seed_null_invalid:" + ";".join(seed_invalid))
        p_num = seed_null.get("one_sided_p_numerator")
        p_den = seed_null.get("one_sided_p_denominator")
        p_millionths_ceil = (p_num * 1_000_000 + p_den - 1) // p_den
        if method_level_claim and p_millionths_ceil > policy["seed_null_max_p_millionths"]:
            reasons.append("training_seed_gain_not_beyond_resampling_null")
    elif method_level_claim and policy["require_seed_null_for_method_claim"]:
        reasons.append("method_level_claim_missing_seed_vs_resampling_null")

    return {
        "status": "REALITY_PASS" if not reasons else "REJECTED",
        "failure_reasons": sorted(set(reasons)),
        "baseline_summary": baseline,
        "candidate_summary": candidate,
        "primary_clean_pass_delta_basis_points": _fraction_decimal(clean_delta),
        "transfer_clean_pass_delta_basis_points": _fraction_decimal(transfer_delta),
        "hack_gap_increase_basis_points": _fraction_decimal(gap_increase),
        "checkpoint_curve": curve,
        "seed_vs_resampling_null": seed_null,
        "method_level_claim": method_level_claim,
    }


def build_reality_gate_evidence(
    *,
    baseline_pack: dict[str, Any],
    candidate_pack: dict[str, Any],
    policy: dict[str, Any],
    checkpoint_curve: list[dict[str, Any]],
    seed_null_result: dict[str, Any] | None = None,
    method_level_claim: bool = False,
) -> dict[str, Any]:
    result = evaluate_reality_gate(
        baseline_pack=baseline_pack,
        candidate_pack=candidate_pack,
        policy=policy,
        checkpoint_curve=checkpoint_curve,
        seed_null_result=seed_null_result,
        method_level_claim=method_level_claim,
    )
    failure_codes, failure_digest = _reason_codes("REALITY", result["failure_reasons"])
    evidence = {
        "schema_version": 1,
        "evidence_kind": REALITY_EVIDENCE_KIND,
        "hash_profile": HASH_PROFILE,
        "reality_policy_sha256": policy["policy_sha256"],
        "reality_gate_code_sha256": actual_reality_gate_code_sha256(),
        "baseline_outcome_pack_sha256": baseline_pack["outcome_pack_sha256"],
        "candidate_outcome_pack_sha256": candidate_pack["outcome_pack_sha256"],
        "baseline_candidate_artifact_manifest_sha256": baseline_pack["candidate_artifact_manifest_sha256"],
        "candidate_artifact_manifest_sha256": candidate_pack["candidate_artifact_manifest_sha256"],
        "harness_manifest_sha256": candidate_pack["harness_manifest_sha256"],
        "task_factory_manifest_sha256": candidate_pack["task_factory_manifest_sha256"],
        "hidden_canary_manifest_sha256": candidate_pack["hidden_canary_manifest_sha256"],
        "baseline_raw_outcome_log_sha256": baseline_pack["raw_outcome_log_sha256"],
        "candidate_raw_outcome_log_sha256": candidate_pack["raw_outcome_log_sha256"],
        "metrics": {
            "baseline": result["baseline_summary"],
            "candidate": result["candidate_summary"],
            "primary_clean_pass_delta_basis_points": result["primary_clean_pass_delta_basis_points"],
            "transfer_clean_pass_delta_basis_points": result["transfer_clean_pass_delta_basis_points"],
            "hack_gap_increase_basis_points": result["hack_gap_increase_basis_points"],
        },
        "checkpoint_curve": result["checkpoint_curve"],
        "seed_vs_resampling_null": result["seed_vs_resampling_null"],
        "method_level_claim": result["method_level_claim"],
        "final_status": result["status"],
        "failure_reason_codes": failure_codes,
        "failure_reason_set_sha256": failure_digest,
        "promotion_authority": _promotion_authority_boundary(),
        "truth_boundary": "REALITY_PASS_IS_EVIDENCE_ONLY_PROMOTION_REQUIRES_EVALUATION_DECISION_RECEIPT_AND_MANAGER_REVIEW",
    }
    _assert_no_forbidden_plaintext(evidence)
    evidence["evidence_sha256"] = _sha256_json(evidence)
    invalid = validate_reality_gate_evidence(evidence, policy=policy)
    if invalid:
        raise RealityGateError("; ".join(invalid))
    return evidence


def validate_reality_gate_evidence(
    evidence: Any, *, policy: dict[str, Any] | None = None,
    baseline_pack: dict[str, Any] | None = None, candidate_pack: dict[str, Any] | None = None,
    checkpoint_curve: list[dict[str, Any]] | None = None, seed_null_result: dict[str, Any] | None = None,
) -> list[str]:
    invalid: list[str] = []
    if not isinstance(evidence, dict):
        return ["reality evidence must be an object"]
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
        invalid.append("reality evidence schema mismatch")
    if evidence.get("schema_version") != 1 or evidence.get("evidence_kind") != REALITY_EVIDENCE_KIND:
        invalid.append("reality evidence identity mismatch")
    if evidence.get("hash_profile") != HASH_PROFILE:
        invalid.append("reality evidence hash_profile mismatch")
    if not verify_p2_self_digest(evidence, "evidence_sha256"):
        invalid.append("reality evidence self-digest mismatch")
    for field in (
        "reality_policy_sha256", "reality_gate_code_sha256", "baseline_outcome_pack_sha256",
        "candidate_outcome_pack_sha256", "baseline_candidate_artifact_manifest_sha256",
        "candidate_artifact_manifest_sha256", "harness_manifest_sha256",
        "task_factory_manifest_sha256", "hidden_canary_manifest_sha256",
        "baseline_raw_outcome_log_sha256", "candidate_raw_outcome_log_sha256",
        "failure_reason_set_sha256", "evidence_sha256",
    ):
        if not valid_sha256(evidence.get(field)):
            invalid.append(f"reality evidence {field} invalid")
    if valid_sha256(evidence.get("reality_gate_code_sha256")) and evidence.get("reality_gate_code_sha256") != actual_reality_gate_code_sha256():
        invalid.append("reality evidence code identity mismatch")
    if evidence.get("baseline_candidate_artifact_manifest_sha256") == evidence.get("candidate_artifact_manifest_sha256"):
        invalid.append("reality evidence baseline/candidate identity collision")
    if evidence.get("final_status") not in {"REJECTED", "REALITY_PASS"}:
        invalid.append("reality evidence final_status invalid")
    if not isinstance(evidence.get("failure_reason_codes"), list) or any(not isinstance(x, str) for x in evidence.get("failure_reason_codes", [])):
        invalid.append("reality evidence failure_reason_codes invalid")
    authority = evidence.get("promotion_authority")
    if not isinstance(authority, dict):
        invalid.append("reality evidence promotion authority missing")
    else:
        if authority.get("authority_kind") != AUTHORITY_KIND:
            invalid.append("reality evidence authority kind mismatch")
        if authority.get("authoritative_for_model_promotion") is not False:
            invalid.append("reality evidence must not be promotion authority")
        if authority.get("authoritative_for_arbitrary_runtime_attempts") is not False:
            invalid.append("reality evidence must not be runtime-attempt authority")
        if authority.get("promotion_requirement") != "VALID_AQLEVON_EVALUATION_DECISION_RECEIPT_V1_PLUS_MANAGER_REVIEW":
            invalid.append("reality evidence promotion requirement mismatch")
    if evidence.get("truth_boundary") != "REALITY_PASS_IS_EVIDENCE_ONLY_PROMOTION_REQUIRES_EVALUATION_DECISION_RECEIPT_AND_MANAGER_REVIEW":
        invalid.append("reality evidence truth boundary mismatch")
    if policy is not None:
        policy_invalid = validate_policy(policy)
        if policy_invalid:
            invalid.extend(f"policy invalid:{x}" for x in policy_invalid)
        elif evidence.get("reality_policy_sha256") != policy.get("policy_sha256"):
            invalid.append("reality evidence policy binding mismatch")
    try:
        _assert_no_forbidden_plaintext(evidence)
    except RealityGateError as exc:
        invalid.append(str(exc))
    # Authoritative evidence must not contain direct floats anywhere.
    def has_float(value: Any) -> bool:
        if isinstance(value, float):
            return True
        if isinstance(value, list):
            return any(has_float(x) for x in value)
        if isinstance(value, dict):
            return any(has_float(x) for x in value.values())
        return False
    if has_float(evidence):
        invalid.append("reality evidence contains direct float")
    support_values = (baseline_pack, candidate_pack, checkpoint_curve)
    if any(x is not None for x in support_values):
        if not all(x is not None for x in support_values) or policy is None:
            invalid.append("reality evidence semantic validation requires policy+baseline+candidate+curve together")
        else:
            try:
                expected = build_reality_gate_evidence(
                    baseline_pack=baseline_pack, candidate_pack=candidate_pack, policy=policy,
                    checkpoint_curve=checkpoint_curve, seed_null_result=seed_null_result,
                    method_level_claim=evidence.get("method_level_claim") is True,
                )
                if expected != evidence:
                    invalid.append("reality evidence does not match fresh recomputation from supporting evidence")
            except (RealityGateError, TypeError, ValueError) as exc:
                invalid.append(f"reality evidence semantic recomputation failed:{exc}")
    return sorted(set(invalid))


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="AQLEVON P3 Reality Gate V1")
    sub = parser.add_subparsers(dest="cmd", required=True)
    build = sub.add_parser("build-evidence")
    for name in ("baseline", "candidate", "policy", "curve"):
        build.add_argument(f"--{name}", required=True)
    build.add_argument("--seed-null")
    build.add_argument("--method-level-claim", action="store_true")
    validate = sub.add_parser("validate-evidence")
    validate.add_argument("--evidence", required=True)
    validate.add_argument("--policy")
    validate.add_argument("--baseline")
    validate.add_argument("--candidate")
    validate.add_argument("--curve")
    validate.add_argument("--seed-null")
    args = parser.parse_args()
    if args.cmd == "build-evidence":
        evidence = build_reality_gate_evidence(
            baseline_pack=_load(args.baseline),
            candidate_pack=_load(args.candidate),
            policy=_load(args.policy),
            checkpoint_curve=_load(args.curve),
            seed_null_result=_load(args.seed_null) if args.seed_null else None,
            method_level_claim=args.method_level_claim,
        )
        print(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    evidence = _load(args.evidence)
    policy = _load(args.policy) if args.policy else None
    errors = validate_reality_gate_evidence(
        evidence, policy=policy,
        baseline_pack=_load(args.baseline) if args.baseline else None,
        candidate_pack=_load(args.candidate) if args.candidate else None,
        checkpoint_curve=_load(args.curve) if args.curve else None,
        seed_null_result=_load(args.seed_null) if args.seed_null else None,
    )
    print(json.dumps({"status": "VALID" if not errors else "INVALID", "invalid_reasons": errors}, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
