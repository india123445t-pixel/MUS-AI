#!/usr/bin/env python3
"""Fail-closed metadata gate for AQLEVON adapter and merge candidates.

The gate validates lineage, topology, evidence, and merge-promotion artifacts. Numerical
weight identity and behavioral quality must be produced by the training/merge/evaluation
runners and recorded in the candidate manifest.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def load_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _valid_sha256(value) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value.strip()) is not None


def _normalized_sha256(value: str) -> str:
    return value.strip().lower()


def _is_nonnegative_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def default_policy_path() -> Path:
    root = Path(__file__).resolve().parent
    for name in ("merge_safety_policy_v4.json", "merge_safety_policy_v3.json", "merge_safety_policy_v2.json"):
        path = root / name
        if path.exists():
            return path
    raise FileNotFoundError("no merge safety policy found")


def _validate_parameter_layout(candidate: dict, policy: dict, errors: list[str]) -> None:
    architecture = policy.get("architecture_compatibility", {})
    if not architecture.get("direct_tensor_merge_requires_compatible_parameter_layout"):
        return

    layout = candidate.get("parameter_layout")
    if not isinstance(layout, dict):
        errors.append("merge promotion missing parameter_layout proof")
        return
    if layout.get("compatible") is not True:
        errors.append("merge promotion requires parameter_layout.compatible=true")
    if layout.get("algorithm") != "sha256":
        errors.append("merge promotion requires parameter_layout.algorithm=sha256")

    base_hash = layout.get("base_layout_sha256")
    candidate_hash = layout.get("candidate_layout_sha256")
    if not _valid_sha256(base_hash):
        errors.append("merge promotion missing/invalid parameter_layout.base_layout_sha256")
    if not _valid_sha256(candidate_hash):
        errors.append("merge promotion missing/invalid parameter_layout.candidate_layout_sha256")
    if _valid_sha256(base_hash) and _valid_sha256(candidate_hash):
        if _normalized_sha256(base_hash) != _normalized_sha256(candidate_hash):
            errors.append("parameter layout fingerprint mismatch")


def _validate_hard_rejection_counts(candidate: dict, policy: dict, errors: list[str]) -> None:
    thresholds = policy.get("hard_rejection_thresholds", {})
    if not thresholds:
        return
    counts = candidate.get("hard_rejection_counts")
    if not isinstance(counts, dict):
        errors.append("merge promotion missing hard_rejection_counts")
        return

    for threshold_key, maximum in thresholds.items():
        if not threshold_key.endswith("_max") or not _is_nonnegative_int(maximum):
            errors.append(f"invalid policy hard rejection threshold: {threshold_key}")
            continue
        count_key = threshold_key[:-4]
        value = counts.get(count_key)
        if not _is_nonnegative_int(value):
            errors.append(f"merge promotion missing/invalid hard_rejection_counts.{count_key}")
            continue
        if value > maximum:
            errors.append(f"hard rejection threshold exceeded: {count_key}={value} > {maximum}")


def validate_candidate(candidate: dict, policy: dict) -> list[str]:
    errors: list[str] = []
    base = candidate.get("base", {})
    expected = policy["base"]
    for key in ("repo", "revision", "family"):
        if base.get(key) != expected.get(key):
            errors.append(f"base.{key} mismatch")

    topology = candidate.get("topology_class")
    if topology not in set(policy["topology_classes"]):
        errors.append("invalid topology_class")

    targets = set(candidate.get("target_suffixes", []))
    if not targets:
        errors.append("target_suffixes missing")
    forbidden_hits = []
    for scope in candidate.get("target_scopes", []):
        if any(bad in scope for bad in policy["forbidden_scopes"]):
            forbidden_hits.append(scope)
    if forbidden_hits:
        errors.append("forbidden target scope: " + ",".join(sorted(forbidden_hits)))

    if topology == "FULL_HYBRID_TEXT":
        missing = set(policy["full_hybrid_required_suffixes"]) - targets
        if missing:
            errors.append("full hybrid coverage missing: " + ",".join(sorted(missing)))

    training = candidate.get("training_method")
    if training == "qlora_4bit" and not candidate.get("quantization_regression_pass"):
        errors.append("qlora_4bit requires quantization_regression_pass")

    merge = candidate.get("merge", {})
    backend = merge.get("backend")
    if backend:
        backend_state = policy["merge_backends"].get(backend, "deny")
        if backend_state != "allow":
            errors.append(f"merge backend blocked: {backend}")

        combination = merge.get("combination_type")
        rule = policy["peft_combination_rules"].get(combination)
        if backend == "peft_native" and rule is None:
            errors.append(f"unknown PEFT combination_type: {combination}")
        if rule and candidate.get("rank_pattern") and rule["rank_pattern"] == "forbidden":
            errors.append(f"rank_pattern forbidden for {combination}")

    evidence = candidate.get("evidence", {})
    for key in policy["required_integrity_evidence"]:
        val = evidence.get(key)
        if key.endswith("hash"):
            if not _valid_sha256(val):
                errors.append(f"missing/invalid SHA-256 evidence.{key}")
        elif val is not True:
            errors.append(f"missing evidence.{key}")

    if candidate.get("promotion_requested"):
        for key in policy["required_promotion_evidence"]:
            if evidence.get(key) is not True:
                errors.append(f"promotion missing evidence.{key}")

    if candidate.get("merge_promotion_requested"):
        if not candidate.get("promotion_requested"):
            errors.append("merge promotion requires promotion_requested")
        if not backend:
            errors.append("merge promotion requires merge.backend")

        _validate_parameter_layout(candidate, policy, errors)
        _validate_hard_rejection_counts(candidate, policy, errors)

        for key in policy.get("required_merge_promotion_evidence", []):
            if evidence.get(key) is not True:
                errors.append(f"merge promotion missing evidence.{key}")
        artifacts = candidate.get("artifacts", {})
        for key in policy.get("required_merge_artifacts", []):
            if not _valid_sha256(artifacts.get(key)):
                errors.append(f"merge promotion missing/invalid SHA-256 artifacts.{key}")

        rep = candidate.get("interference_input_representation")
        expected_rep = policy.get("interference_policy", {}).get("input_representation")
        if expected_rep and rep != expected_rep:
            errors.append(f"merge promotion requires interference_input_representation={expected_rep}")

    return errors


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("candidate")
    p.add_argument("--policy", default=str(default_policy_path()))
    args = p.parse_args()
    policy = load_json(args.policy)
    candidate = load_json(args.candidate)
    errors = validate_candidate(candidate, policy)
    if errors:
        raise SystemExit("MERGE_SAFETY_FAIL\n" + "\n".join(errors))
    print("MERGE_SAFETY_PASS")


if __name__ == "__main__":
    main()
