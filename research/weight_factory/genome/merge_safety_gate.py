#!/usr/bin/env python3
"""Fail-closed metadata gate for AQLEVON adapter and merge candidates.

The gate validates lineage, topology, evidence, and merge-promotion artifacts. Numerical
weight identity and behavioral quality must be produced by the training/merge/evaluation
runners and recorded in the candidate manifest.
"""
from __future__ import annotations
import json
from pathlib import Path


def load_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _valid_hash(value) -> bool:
    return isinstance(value, str) and len(value.strip()) >= 16


def default_policy_path() -> Path:
    root = Path(__file__).resolve().parent
    for name in ("merge_safety_policy_v4.json", "merge_safety_policy_v3.json", "merge_safety_policy_v2.json"):
        path = root / name
        if path.exists():
            return path
    raise FileNotFoundError("no merge safety policy found")


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
            if not _valid_hash(val):
                errors.append(f"missing evidence.{key}")
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
        for key in policy.get("required_merge_promotion_evidence", []):
            if evidence.get(key) is not True:
                errors.append(f"merge promotion missing evidence.{key}")
        artifacts = candidate.get("artifacts", {})
        for key in policy.get("required_merge_artifacts", []):
            if not _valid_hash(artifacts.get(key)):
                errors.append(f"merge promotion missing artifacts.{key}")

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
