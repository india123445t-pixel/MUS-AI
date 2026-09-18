#!/usr/bin/env python3
"""AQLEVON evaluation truth gate.

Research/control-plane only. It never embeds protected benchmark prompts or answers.
It provides two independent controls:
  1) keyed HMAC + 13-token-shingle fingerprint packs for leakage scans;
  2) a deterministic release gate over paired base/candidate outcomes.

The gate intentionally fails closed when required evidence is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _validate_fingerprint_pack(pack: dict[str, Any], label: str) -> list[dict[str, Any]]:
    if not isinstance(pack, dict):
        raise ValueError(f"{label} pack must be a JSON object")
    if pack.get("algorithm") != "HMAC-SHA256 + keyed token shingles":
        raise ValueError(f"{label} pack algorithm must be HMAC-SHA256 + keyed token shingles")
    if pack.get("plaintext_included") is not False:
        raise ValueError(f"{label} pack must explicitly declare plaintext_included=false")
    shingle_n = pack.get("shingle_n")
    if type(shingle_n) is not int or shingle_n < 1:
        raise ValueError(f"{label} pack shingle_n must be a positive integer")
    records = pack.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{label} pack records must be a list")
    allowed = {"id_hmac_sha256", "field", "exact_hmac_sha256", "shingle_n", "shingle_hmac_sha256"}
    for index, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"{label} record {index} must be an object")
        unexpected = set(rec) - allowed
        if unexpected:
            raise ValueError(f"{label} record {index} has unexpected fields: {sorted(unexpected)}")
        for field in ("id_hmac_sha256", "exact_hmac_sha256"):
            if not _valid_sha256(rec.get(field)):
                raise ValueError(f"{label} record {index} invalid {field}")
        if rec.get("shingle_n") != shingle_n:
            raise ValueError(f"{label} record {index} shingle_n mismatch")
        shingles = rec.get("shingle_hmac_sha256")
        if not isinstance(shingles, list) or any(not _valid_sha256(x) for x in shingles):
            raise ValueError(f"{label} record {index} invalid shingle_hmac_sha256")
        if not isinstance(rec.get("field"), str) or not rec.get("field"):
            raise ValueError(f"{label} record {index} field must be non-empty string")
    return records


def scan_fingerprint_packs(protected: dict[str, Any], candidate: dict[str, Any], fuzzy_threshold: float = 0.8) -> dict[str, Any]:
    protected_records = _validate_fingerprint_pack(protected, "protected")
    candidate_records = _validate_fingerprint_pack(candidate, "candidate")
    if protected.get("shingle_n") != candidate.get("shingle_n"):
        raise ValueError("protected/candidate fingerprint packs must use the same shingle_n")
    exact_index: dict[str, list[dict[str, Any]]] = {}
    shingle_index: dict[str, set[int]] = {}

    for idx, rec in enumerate(protected_records):
        exact_index.setdefault(rec.get("exact_hmac_sha256", ""), []).append(rec)
        for shingle in rec.get("shingle_hmac_sha256") or []:
            shingle_index.setdefault(shingle, set()).add(idx)

    exact_matches: list[dict[str, Any]] = []
    fuzzy_matches: list[dict[str, Any]] = []
    seen_fuzzy: set[tuple[str, str, str, str]] = set()

    for cand in candidate_records:
        digest = cand.get("exact_hmac_sha256", "")
        for prot in exact_index.get(digest, []):
            exact_matches.append({
                "protected_id_hmac_sha256": prot.get("id_hmac_sha256"), "protected_field": prot.get("field"),
                "candidate_id_hmac_sha256": cand.get("id_hmac_sha256"), "candidate_field": cand.get("field"),
            })

        cand_shingles = set(cand.get("shingle_hmac_sha256") or [])
        if not cand_shingles:
            continue
        possible: set[int] = set()
        for shingle in cand_shingles:
            possible.update(shingle_index.get(shingle, set()))
        for idx in possible:
            prot = protected_records[idx]
            prot_shingles = set(prot.get("shingle_hmac_sha256") or [])
            if not prot_shingles:
                continue
            intersection = len(cand_shingles & prot_shingles)
            union = len(cand_shingles | prot_shingles)
            jaccard = intersection / union if union else 0.0
            key = (str(prot.get("id_hmac_sha256")), str(prot.get("field")), str(cand.get("id_hmac_sha256")), str(cand.get("field")))
            if jaccard >= fuzzy_threshold and key not in seen_fuzzy:
                seen_fuzzy.add(key)
                fuzzy_matches.append({
                    "protected_id_hmac_sha256": prot.get("id_hmac_sha256"), "protected_field": prot.get("field"),
                    "candidate_id_hmac_sha256": cand.get("id_hmac_sha256"), "candidate_field": cand.get("field"),
                    "jaccard": round(jaccard, 6),
                })

    return {
        "scan_complete": True,
        "protected_records": len(protected_records),
        "candidate_records": len(candidate_records),
        "exact_overlap_count": len(exact_matches),
        "fuzzy_overlap_count": len(fuzzy_matches),
        "exact_matches": exact_matches,
        "fuzzy_matches": fuzzy_matches,
    }


def _mean_bool(values: list[bool]) -> float:
    return sum(1 for v in values if v) / len(values)


def _strict_binary(values: Any, label: str) -> list[bool]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a JSON list of booleans")
    parsed: list[bool] = []
    for index, value in enumerate(values):
        if isinstance(value, bool):
            parsed.append(value)
        elif type(value) is int and value in (0, 1):
            parsed.append(bool(value))
        else:
            raise ValueError(f"{label}[{index}] must be boolean or 0/1")
    return parsed


def _paired_stats(baseline: list[bool], candidate: list[bool], confidence_level: float = 0.95) -> dict[str, float | int]:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired baseline/candidate outcomes must be non-empty and equal length")
    improvements = sum((not b) and c for b, c in zip(baseline, candidate))
    regressions = sum(b and (not c) for b, c in zip(baseline, candidate))
    n = len(baseline)
    base_rate = _mean_bool(baseline)
    cand_rate = _mean_bool(candidate)
    delta = cand_rate - base_rate

    discordant = improvements + regressions
    if discordant:
        p_one_sided = sum(math.comb(discordant, k) for k in range(improvements, discordant + 1)) / (2 ** discordant)
    else:
        p_one_sided = 1.0

    differences = [int(c) - int(b) for b, c in zip(baseline, candidate)]
    if n > 1:
        se = statistics.stdev(differences) / math.sqrt(n)
    else:
        se = 0.0
    # Fixed 95% z by policy today; reject unsupported confidence settings rather than silently misstate it.
    if abs(confidence_level - 0.95) > 1e-9:
        raise ValueError("only 95% confidence is supported in V1")
    margin = 1.959963984540054 * se
    return {
        "n": n,
        "baseline_rate": base_rate,
        "candidate_rate": cand_rate,
        "delta_pp": delta * 100.0,
        "improvements": improvements,
        "regressions": regressions,
        "discordant_pairs": discordant,
        "p_improvement_one_sided": p_one_sided,
        "delta_ci95_low_pp": (delta - margin) * 100.0,
        "delta_ci95_high_pp": (delta + margin) * 100.0,
    }


def _baseline_noise_pp(repeat_rates: list[float], stochastic: bool, minimum_repeats: int) -> float:
    if stochastic and len(repeat_rates) < minimum_repeats:
        raise ValueError(f"stochastic domain needs at least {minimum_repeats} untouched-base repeats")
    if not repeat_rates:
        return 0.0
    for rate in repeat_rates:
        if not 0.0 <= float(rate) <= 1.0:
            raise ValueError("baseline_repeat_rates values must be in [0,1]")
    return statistics.stdev(repeat_rates) * 100.0 if len(repeat_rates) > 1 else 0.0


def _holm_significant(p_values: dict[str, float], alpha: float) -> dict[str, bool]:
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    result = {name: False for name in p_values}
    m = len(ordered)
    for rank, (name, p_value) in enumerate(ordered):
        threshold = alpha / (m - rank)
        if p_value <= threshold:
            result[name] = True
        else:
            break
    return result


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def evaluate_release(report: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    invalid: list[str] = []
    diagnostics: dict[str, Any] = {"domains": {}}

    if report.get("schema_version") != 1:
        invalid.append("report.schema_version must equal 1")
    if report.get("policy_id") != policy.get("policy_id"):
        invalid.append("report.policy_id does not match policy")

    provenance = report.get("provenance") or {}
    if provenance.get("license_clean") is not True:
        invalid.append("license/provenance gate is not clean")
    if provenance.get("same_harness_for_base_and_candidate") is not True:
        invalid.append("base/candidate were not evaluated under the same harness")
    for field in policy.get("required_hash_fields") or []:
        if not _valid_sha256(provenance.get(field)):
            invalid.append(f"missing/invalid SHA256 provenance field: {field}")

    contamination = report.get("contamination") or {}
    cp = policy.get("contamination") or {}
    if cp.get("require_scan_complete") and contamination.get("scan_complete") is not True:
        invalid.append("contamination scan incomplete")
    if cp.get("require_keyed_fingerprints") and contamination.get("keyed_fingerprints") is not True:
        invalid.append("contamination scan did not use keyed fingerprints")
    if contamination.get("protected_answers_exported") is True and not cp.get("protected_answers_may_be_exported", False):
        failures.append("protected evaluation answers were exported into candidate/training artifacts")
    if int(contamination.get("exact_overlap_count", -1)) > int(cp.get("max_exact_overlaps", 0)):
        failures.append("exact protected-eval overlap detected")
    if int(contamination.get("fuzzy_overlap_count", -1)) > int(cp.get("max_fuzzy_overlaps", 0)):
        failures.append("fuzzy protected-eval overlap detected")
    if int(contamination.get("exact_overlap_count", -1)) < 0 or int(contamination.get("fuzzy_overlap_count", -1)) < 0:
        invalid.append("contamination overlap counts missing")
    for field in cp.get("required_hash_fields") or []:
        if not _valid_sha256(contamination.get(field)):
            invalid.append(f"missing/invalid contamination SHA256 field: {field}")

    red_team = report.get("red_team") or {}
    catastrophic = int(red_team.get("catastrophic_failures", -1))
    if catastrophic < 0:
        invalid.append("red_team.catastrophic_failures missing")
    elif catastrophic > int((policy.get("red_team") or {}).get("max_catastrophic_failures", 0)):
        failures.append(f"catastrophic red-team failures: {catastrophic}")

    domains = report.get("domains") or {}
    required_domains = policy.get("required_domains") or []
    for domain_id in required_domains:
        if domain_id not in domains:
            invalid.append(f"required domain missing: {domain_id}")

    target_p_values: dict[str, float] = {}
    computed: dict[str, dict[str, Any]] = {}
    for domain_id, domain in domains.items():
        try:
            baseline = _strict_binary(domain.get("baseline_outcomes"), f"{domain_id}.baseline_outcomes")
            candidate = _strict_binary(domain.get("candidate_outcomes"), f"{domain_id}.candidate_outcomes")
            stats = _paired_stats(baseline, candidate, float(policy.get("confidence_level", 0.95)))
            if stats["n"] < int(policy.get("minimum_items_per_domain", 30)):
                invalid.append(f"{domain_id}: too few paired items ({stats['n']})")
            if not isinstance(domain.get("stochastic"), bool):
                raise ValueError("stochastic must be explicitly true or false")
            stochastic = domain["stochastic"]
            noise_pp = _baseline_noise_pp(
                [float(x) for x in domain.get("baseline_repeat_rates", [])],
                stochastic,
                int(policy.get("minimum_stochastic_baseline_repeats", 3)),
            )
            max_regression_pp = domain.get("max_regression_pp")
            if max_regression_pp is None:
                invalid.append(f"{domain_id}: max_regression_pp was not predeclared")
                max_regression_pp = 0.0
            if float(max_regression_pp) < 0:
                raise ValueError("max_regression_pp must be >= 0")
            allowed_regression_pp = max(float(max_regression_pp), float(policy.get("noise_multiplier", 2.0)) * noise_pp)
            role = domain.get("role")
            if role not in {"target", "protected"}:
                raise ValueError("role must be target or protected")
            threshold_pp = None
            if role == "target":
                if domain.get("min_effect_pp") is None:
                    invalid.append(f"{domain_id}: target min_effect_pp was not predeclared")
                    min_effect_pp = 0.0
                else:
                    min_effect_pp = float(domain.get("min_effect_pp"))
                    if min_effect_pp < 0:
                        raise ValueError("min_effect_pp must be >= 0")
                threshold_pp = max(min_effect_pp, float(policy.get("noise_multiplier", 2.0)) * noise_pp)
                target_p_values[domain_id] = float(stats["p_improvement_one_sided"])
            if float(stats["delta_pp"]) < -allowed_regression_pp:
                failures.append(f"{domain_id}: regression {stats['delta_pp']:.3f}pp exceeds allowed {allowed_regression_pp:.3f}pp")
            computed[domain_id] = {
                **stats,
                "role": role,
                "baseline_noise_sd_pp": noise_pp,
                "target_effect_threshold_pp": threshold_pp,
                "allowed_regression_pp": allowed_regression_pp,
            }
        except (TypeError, ValueError, statistics.StatisticsError) as exc:
            invalid.append(f"{domain_id}: {exc}")

    if not target_p_values:
        invalid.append("at least one target domain is required")
    significant = _holm_significant(target_p_values, float(policy.get("alpha", 0.05))) if target_p_values else {}
    for domain_id, stats in computed.items():
        if stats.get("role") != "target":
            continue
        threshold = float(stats.get("target_effect_threshold_pp") or 0.0)
        if float(stats["delta_pp"]) < threshold:
            failures.append(f"{domain_id}: target gain {stats['delta_pp']:.3f}pp below required {threshold:.3f}pp")
        if float(stats["delta_ci95_low_pp"]) <= 0.0:
            failures.append(f"{domain_id}: 95% paired delta CI does not exclude zero")
        if not significant.get(domain_id, False):
            failures.append(f"{domain_id}: target gain not significant after Holm correction")
        stats["holm_significant"] = bool(significant.get(domain_id, False))
    diagnostics["domains"] = computed

    eff = report.get("efficiency") or {}
    ep = policy.get("efficiency") or {}
    for metric, limit_key in (
        ("cost_per_verified_success", "max_cost_per_verified_success_ratio"),
        ("p95_latency_ms", "max_p95_latency_ratio"),
        ("output_tokens_per_verified_success", "max_output_tokens_per_verified_success_ratio"),
    ):
        pair = eff.get(metric) or {}
        base = pair.get("baseline")
        cand = pair.get("candidate")
        if base is None or cand is None or float(base) < 0 or float(cand) < 0:
            invalid.append(f"efficiency.{metric} baseline/candidate missing or invalid")
            continue
        base_f, cand_f = float(base), float(cand)
        if base_f == 0.0:
            if metric != "cost_per_verified_success":
                invalid.append(f"efficiency.{metric} baseline must be > 0")
                continue
            if cand_f == 0.0:
                ratio = 1.0
            else:
                diagnostics.setdefault("efficiency", {})[metric] = {"ratio": None, "limit": float(ep[limit_key]), "zero_cost_baseline": True}
                failures.append("efficiency.cost_per_verified_success introduced positive cost over a zero-cost baseline")
                continue
        else:
            ratio = cand_f / base_f
        diagnostics.setdefault("efficiency", {})[metric] = {"ratio": ratio, "limit": float(ep[limit_key])}
        if ratio > float(ep[limit_key]):
            failures.append(f"efficiency.{metric} ratio {ratio:.4f} exceeds {ep[limit_key]:.4f}")

    if invalid:
        status = "INVALID"
    elif failures:
        status = "REJECTED"
    else:
        status = "PROMOTION_ELIGIBLE"
    return {
        "policy_id": policy.get("policy_id"),
        "status": status,
        "invalid_reasons": invalid,
        "failures": failures,
        "diagnostics": diagnostics,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(value)
    return rows


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _dump_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AQLEVON evaluation truth gate")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Compare protected and candidate keyed fingerprint packs")
    scan.add_argument("--protected-pack", required=True)
    scan.add_argument("--candidate-pack", required=True)
    scan.add_argument("--fuzzy-threshold", type=float, default=0.8)

    gate = sub.add_parser("gate", help="Evaluate a release report")
    gate.add_argument("--policy", required=True)
    gate.add_argument("--report", required=True)

    args = parser.parse_args(argv)
    if args.command == "scan":
        protected_path = Path(args.protected_pack)
        candidate_path = Path(args.candidate_pack)
        result = scan_fingerprint_packs(_load_json(protected_path), _load_json(candidate_path), args.fuzzy_threshold)
        result["protected_pack_sha256"] = hashlib.sha256(protected_path.read_bytes()).hexdigest()
        result["candidate_pack_sha256"] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 1 if result["exact_overlap_count"] or result["fuzzy_overlap_count"] else 0
    result = evaluate_release(_load_json(args.report), _load_json(args.policy))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PROMOTION_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
