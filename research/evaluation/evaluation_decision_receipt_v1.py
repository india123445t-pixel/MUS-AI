#!/usr/bin/env python3
"""AQLEVON Evaluation Decision Receipt V1 + preregistration anchor interface.

P2 synthesis control-plane only.

This module deliberately does not export protected prompts/answers or paired raw
outcomes.  It binds the accepted P1 evaluation gate outputs to immutable artifact,
experiment, policy, harness, provenance, contamination, red-team, and run evidence.

A preregistration self-hash is never treated as chronology proof.  Receipt creation
requires a Manager-verifiable anchor verification record that points to external
immutable evidence and a separately stored Manager attestation by digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval_truth_gate import evaluate_release as evaluate_release_p1

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
RECEIPT_KIND = "AQLEVON_EVALUATION_DECISION_RECEIPT_V1"
ANCHOR_REQUEST_KIND = "AQLEVON_PREREGISTRATION_ANCHOR_REQUEST_V1"
ANCHOR_VERIFICATION_KIND = "AQLEVON_PREREGISTRATION_ANCHOR_VERIFICATION_V1"
CANDIDATE_MANIFEST_KIND = "AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1"
HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
EVALUATION_EFFICIENCY_SCOPE_KIND = "AQLEVON_EVALUATION_HARNESS_EFFICIENCY_SCOPE_V1"
EVALUATION_EFFICIENCY_POPULATION_KIND = "AQLEVON_FROZEN_EVALUATION_ITEM_POPULATION_V1"
RUNTIME_ATTEMPT_AUTHORITY_KIND = "AQLEVON_CANDIDATE_LEVEL_EVAL_NOT_ATTEMPT_AUTHORITY_V1"
ALLOWED_FINAL_STATUS = {"INVALID", "REJECTED", "PROMOTION_ELIGIBLE"}
ALLOWED_ANCHOR_KINDS = {"git_commit", "immutable_object", "append_only_ledger"}
FORBIDDEN_PLAINTEXT_KEYS = {
    "prompt", "prompts", "answer", "answers", "protected_prompt", "protected_answer",
    "raw_prompt", "raw_answer", "input_text", "output_text", "response_text",
}


def canonical_json_bytes(value: Any) -> bytes:
    """Legacy/P1 canonical JSON helper retained for inherited policy/evidence hashes."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Legacy/P1 hash helper. P2.1 self-digests MUST use canonical_p2_sha256()."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _normalize_p2_string(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")


def canonical_decimal_string(value: int | float | Decimal | str) -> str:
    """Return Manager-profile decimal text: no exponent, +, redundant zeros, or -0."""
    if isinstance(value, bool):
        raise TypeError("boolean_is_not_numeric")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("non_finite_number")
        if value == 0:
            return "0"
        raw = str(value)
    elif isinstance(value, (int, Decimal)):
        raw = str(value)
    elif isinstance(value, str):
        raw = value.strip()
    else:
        raise TypeError("unsupported_numeric_type")
    if raw.startswith("+"):
        raw = raw[1:]
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise TypeError("invalid_decimal") from exc
    if not number.is_finite():
        raise TypeError("non_finite_number")
    if number == 0:
        return "0"
    text = format(number, "f")
    sign = ""
    if text.startswith("-"):
        sign, text = "-", text[1:]
    integer, dot, fraction = text.partition(".")
    integer = integer.lstrip("0") or "0"
    fraction = fraction.rstrip("0")
    return f"{sign}{integer}{('.' + fraction) if fraction else ''}"


def _canonical_profile_value(value: Any) -> Any:
    """Normalize producer data before it becomes an authoritative P2.1 hash payload."""
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("non_finite_number")
        if value.is_integer():
            return int(value)
        return canonical_decimal_string(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise TypeError("non_finite_number")
        if value == value.to_integral_value():
            return int(value)
        return canonical_decimal_string(value)
    if isinstance(value, str):
        return _normalize_p2_string(value)
    if isinstance(value, list):
        return [_canonical_profile_value(item) for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: item.encode("ascii") if isinstance(item, str) else b""):
            if not isinstance(key, str) or not key or any(ord(ch) >= 128 for ch in key):
                raise TypeError("non_ascii_or_invalid_object_key")
            out[key] = _canonical_profile_value(value[key])
        return out
    raise TypeError(f"unsupported_json_value:{type(value).__name__}")


def _assert_authoritative_p2_payload(value: Any) -> None:
    """Reject direct floats and invalid keys in already-materialized authoritative payloads."""
    if value is None or type(value) in (bool, int, str):
        return
    if isinstance(value, float) or isinstance(value, Decimal):
        raise TypeError("direct_non_integral_numeric_forbidden")
    if isinstance(value, list):
        for item in value:
            _assert_authoritative_p2_payload(item)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key or any(ord(ch) >= 128 for ch in key):
                raise TypeError("non_ascii_or_invalid_object_key")
            _assert_authoritative_p2_payload(child)
        return
    raise TypeError(f"unsupported_json_value:{type(value).__name__}")


def canonical_p2_json_bytes(value: Any) -> bytes:
    """Manager-frozen AQLEVON_CANONICAL_JSON_SHA256_V1 serialization."""
    _assert_authoritative_p2_payload(value)
    normalized = _canonical_profile_value(value)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_p2_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_p2_json_bytes(value)).hexdigest()


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def actual_evaluation_code_sha256() -> str:
    return hashlib.sha256(Path(__file__).with_name("eval_truth_gate.py").read_bytes()).hexdigest()


def _p2_self_digest(value: dict[str, Any], field: str) -> str:
    if not isinstance(value, dict):
        raise TypeError("self_digest_payload_not_object")
    body = {key: child for key, child in value.items() if key != field}
    return canonical_p2_sha256(body)


def verify_p2_self_digest(value: Any, field: str) -> bool:
    if not isinstance(value, dict) or value.get("hash_profile") != HASH_PROFILE:
        return False
    digest = value.get(field)
    if not valid_sha256(digest):
        return False
    try:
        return _p2_self_digest(value, field) == digest
    except (TypeError, ValueError):
        return False


_CANONICAL_DECIMAL_RE = re.compile(r"^-?(?:0|[1-9]\d*)\.\d*[1-9]$")


def _is_canonical_numeric_repr(value: Any, *, allow_none: bool = False) -> bool:
    if value is None:
        return allow_none
    if type(value) is int:
        return True
    if isinstance(value, str) and _CANONICAL_DECIMAL_RE.fullmatch(value):
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            return False
        return parsed.is_finite() and parsed != parsed.to_integral_value() and canonical_decimal_string(value) == value
    return False




def _parse_utc_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid RFC3339 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{label} must be UTC")
    return parsed

def _reason_codes(prefix: str, reasons: Any) -> tuple[list[str], str]:
    if not isinstance(reasons, list) or any(not isinstance(x, str) for x in reasons):
        raise ValueError(f"{prefix.lower()} reasons must be a list of strings")
    normalized = sorted(set(reasons))
    codes = [f"{prefix}_{hashlib.sha256(x.encode('utf-8')).hexdigest()[:16].upper()}" for x in normalized]
    return codes, canonical_sha256(normalized)


def _assert_no_forbidden_plaintext(value: Any, path: str = "receipt") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_PLAINTEXT_KEYS:
                raise ValueError(f"protected/raw plaintext key forbidden at {path}.{key}")
            _assert_no_forbidden_plaintext(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_plaintext(child, f"{path}[{index}]")


def validate_candidate_artifact_manifest(manifest: Any) -> list[str]:
    """Validate shared P2.1 identity/integrity, not Worker-03 artifact semantics.

    Worker 03 remains authority for artifact type/stage/layout/tree semantics. P2.1
    now freezes the shared self-hash profile, so Worker 05 may verify the manifest
    kind/profile/self-digest without retyping those semantic rules.
    """
    invalid: list[str] = []
    if not isinstance(manifest, dict):
        return ["candidate artifact manifest must be an object"]
    if manifest.get("manifest_kind") != CANDIDATE_MANIFEST_KIND:
        invalid.append("candidate artifact manifest kind mismatch")
    if manifest.get("hash_profile") != HASH_PROFILE:
        invalid.append("candidate artifact manifest hash_profile mismatch")
    if not valid_sha256(manifest.get("manifest_sha256")):
        invalid.append("candidate artifact manifest SHA-256 identity invalid")
    elif not verify_p2_self_digest(manifest, "manifest_sha256"):
        invalid.append("candidate artifact manifest self-digest mismatch")
    return invalid


def build_anchor_request(
    *,
    experiment_manifest_sha256: str,
    evaluation_policy_sha256: str,
    candidate_artifact_manifest_sha256: str,
    requested_anchor_kind: str,
) -> dict[str, Any]:
    for label, value in (
        ("experiment_manifest_sha256", experiment_manifest_sha256),
        ("evaluation_policy_sha256", evaluation_policy_sha256),
        ("candidate_artifact_manifest_sha256", candidate_artifact_manifest_sha256),
    ):
        if not valid_sha256(value):
            raise ValueError(f"invalid {label}")
    if requested_anchor_kind not in ALLOWED_ANCHOR_KINDS:
        raise ValueError("unsupported preregistration anchor kind")
    request = _canonical_profile_value({
        "schema_version": 1,
        "request_kind": ANCHOR_REQUEST_KIND,
        "hash_profile": HASH_PROFILE,
        "experiment_manifest_sha256": experiment_manifest_sha256,
        "evaluation_policy_sha256": evaluation_policy_sha256,
        "candidate_artifact_manifest_sha256": candidate_artifact_manifest_sha256,
        "requested_anchor_kind": requested_anchor_kind,
        "chronology_requirement": "ANCHOR_MUST_EXIST_IN_MANAGER_VERIFIABLE_IMMUTABLE_SYSTEM_BEFORE_CANDIDATE_OUTPUT_INSPECTION",
    })
    request["request_sha256"] = canonical_p2_sha256(request)
    return request


def finalize_anchor_verification(payload: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize a Manager verification record.

    This helper does not confer authority.  It only makes the attestation tamper-
    evident.  The Manager must independently resolve immutable_reference and verify
    external_evidence_sha256 + manager_attestation_sha256.
    """
    if payload.get("hash_profile") not in (None, HASH_PROFILE):
        raise ValueError("unknown preregistration anchor hash_profile")
    record = dict(payload)
    record["hash_profile"] = HASH_PROFILE
    record = _canonical_profile_value(record)
    record["verification_record_sha256"] = canonical_p2_sha256(record)
    return record


def validate_anchor_request(anchor_request: Any) -> list[str]:
    invalid: list[str] = []
    if not isinstance(anchor_request, dict):
        return ["preregistration anchor request must be an object"]
    if anchor_request.get("schema_version") != 1 or anchor_request.get("request_kind") != ANCHOR_REQUEST_KIND:
        invalid.append("preregistration anchor request identity/schema mismatch")
    if anchor_request.get("hash_profile") != HASH_PROFILE:
        invalid.append("preregistration anchor request hash_profile mismatch")
    for field in ("experiment_manifest_sha256", "evaluation_policy_sha256", "candidate_artifact_manifest_sha256"):
        if not valid_sha256(anchor_request.get(field)):
            invalid.append(f"preregistration anchor request missing/invalid {field}")
    if anchor_request.get("requested_anchor_kind") not in ALLOWED_ANCHOR_KINDS:
        invalid.append("preregistration anchor request kind unsupported")
    if anchor_request.get("chronology_requirement") != "ANCHOR_MUST_EXIST_IN_MANAGER_VERIFIABLE_IMMUTABLE_SYSTEM_BEFORE_CANDIDATE_OUTPUT_INSPECTION":
        invalid.append("preregistration anchor chronology requirement mismatch")
    if not verify_p2_self_digest(anchor_request, "request_sha256"):
        invalid.append("preregistration anchor request self-digest mismatch")
    return invalid


def validate_anchor_verification(
    verification: Any,
    anchor_request: dict[str, Any],
) -> list[str]:
    invalid: list[str] = []
    invalid.extend(validate_anchor_request(anchor_request))
    if not isinstance(verification, dict):
        return invalid + ["preregistration anchor verification must be an object"]
    if verification.get("schema_version") != 1 or verification.get("verification_kind") != ANCHOR_VERIFICATION_KIND:
        invalid.append("preregistration anchor verification identity/schema mismatch")
    if verification.get("hash_profile") != HASH_PROFILE:
        invalid.append("preregistration anchor verification hash_profile mismatch")
    if verification.get("verification_status") != "VERIFIED":
        invalid.append("preregistration anchor is not Manager-verified")
    if verification.get("anchor_kind") not in ALLOWED_ANCHOR_KINDS:
        invalid.append("preregistration anchor kind unsupported")
    if verification.get("anchor_kind") != anchor_request.get("requested_anchor_kind"):
        invalid.append("preregistration anchor kind does not match request")
    if verification.get("anchor_request_sha256") != anchor_request.get("request_sha256"):
        invalid.append("preregistration anchor request binding mismatch")
    for field in (
        "experiment_manifest_sha256", "evaluation_policy_sha256", "candidate_artifact_manifest_sha256",
    ):
        if verification.get(field) != anchor_request.get(field):
            invalid.append(f"preregistration anchor {field} binding mismatch")
    if not isinstance(verification.get("immutable_reference"), str) or not verification.get("immutable_reference"):
        invalid.append("preregistration anchor immutable_reference missing")
    if not isinstance(verification.get("manager_authority_id"), str) or not verification.get("manager_authority_id"):
        invalid.append("preregistration anchor manager_authority_id missing")
    for field in ("external_evidence_sha256", "manager_attestation_sha256"):
        if not valid_sha256(verification.get(field)):
            invalid.append(f"preregistration anchor missing/invalid {field}")
    try:
        anchored_at = _parse_utc_timestamp(verification.get("anchored_at_utc"), "anchored_at_utc")
        verified_at = _parse_utc_timestamp(verification.get("verified_at_utc"), "verified_at_utc")
        if verified_at < anchored_at:
            invalid.append("preregistration anchor verified_at_utc precedes anchored_at_utc")
    except ValueError as exc:
        invalid.append(str(exc))
    if not verify_p2_self_digest(verification, "verification_record_sha256"):
        invalid.append("preregistration anchor verification self-digest mismatch")
    return invalid


def red_team_evidence_root(report: dict[str, Any], required_classes: list[str] | None = None) -> str:
    red = report.get("red_team") or {}
    classes = red.get("classes") or {}
    if not valid_sha256(red.get("manifest_sha256")) or not isinstance(classes, dict) or not classes:
        raise ValueError("red-team evidence incomplete")
    if required_classes is not None and set(classes) != set(required_classes):
        raise ValueError("red-team evidence classes do not exactly match policy")
    class_evidence: list[dict[str, str]] = []
    for class_id in sorted(classes):
        evidence = classes[class_id]
        if not isinstance(evidence, dict) or evidence.get("evaluated") is not True or not valid_sha256(evidence.get("evidence_sha256")):
            raise ValueError(f"red-team class evidence incomplete: {class_id}")
        class_evidence.append({"class_id": class_id, "evidence_sha256": evidence["evidence_sha256"]})
    return canonical_sha256({
        "root_schema": "AQLEVON_RED_TEAM_EVIDENCE_ROOT_V1",
        "manifest_sha256": red["manifest_sha256"],
        "class_evidence": class_evidence,
    })


def _canonical_metric_number(value: Any, label: str, *, allow_none: bool = False) -> Any:
    if value is None and allow_none:
        return None
    if type(value) is bool or not isinstance(value, (int, float)):
        raise ValueError(f"numeric metric invalid: {label}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"numeric metric non-finite: {label}")
    return _canonical_profile_value(value)


def _domain_summary(gate_result: dict[str, Any], experiment_manifest: dict[str, Any]) -> dict[str, Any]:
    diagnostics = ((gate_result.get("diagnostics") or {}).get("domains") or {})
    manifest_domains = experiment_manifest.get("domains") or {}
    if not isinstance(diagnostics, dict) or not isinstance(manifest_domains, dict):
        raise ValueError("domain diagnostics/manifest missing")
    summary: dict[str, Any] = {}
    required_numeric = (
        "n", "baseline_rate", "candidate_rate", "delta_pp", "improvements", "regressions",
        "discordant_pairs", "p_improvement_one_sided", "delta_ci95_low_pp", "delta_ci95_high_pp",
        "baseline_noise_sd_pp", "allowed_regression_pp",
    )
    for domain_id in sorted(manifest_domains):
        stat = diagnostics.get(domain_id)
        cfg = manifest_domains[domain_id]
        if not isinstance(stat, dict) or not isinstance(cfg, dict):
            raise ValueError(f"missing domain diagnostics: {domain_id}")
        if stat.get("role") != cfg.get("role"):
            raise ValueError(f"domain role mismatch: {domain_id}")
        item: dict[str, Any] = {}
        for field in required_numeric:
            item[field] = _canonical_metric_number(stat.get(field), f"{domain_id}.{field}")
        item["role"] = stat["role"]
        threshold = stat.get("target_effect_threshold_pp")
        if item["role"] == "target":
            if type(stat.get("holm_significant")) is not bool:
                raise ValueError(f"target significance diagnostics missing: {domain_id}")
            item["target_effect_threshold_pp"] = _canonical_metric_number(threshold, f"{domain_id}.target_effect_threshold_pp")
            item["holm_significant"] = stat["holm_significant"]
        else:
            item["target_effect_threshold_pp"] = None
            item["holm_significant"] = None
        summary[domain_id] = item
    return _canonical_profile_value(summary)


def _evaluation_efficiency_scope(
    *,
    experiment_manifest: dict[str, Any],
    base_run: dict[str, Any],
    candidate_run: dict[str, Any],
    domain_summary: dict[str, Any],
) -> dict[str, Any]:
    item_counts: dict[str, int] = {}
    for domain_id, item in sorted(domain_summary.items()):
        count = item.get("n")
        if type(count) is not int or count < 0:
            raise ValueError(f"evaluation efficiency population count invalid: {domain_id}")
        item_counts[domain_id] = count
    root_body = _canonical_profile_value({
        "hash_profile": HASH_PROFILE,
        "population_kind": EVALUATION_EFFICIENCY_POPULATION_KIND,
        "experiment_manifest_sha256": experiment_manifest["manifest_sha256"],
        "harness_manifest_sha256": experiment_manifest["harness_manifest_sha256"],
        "base_raw_outputs_sha256": base_run["raw_outputs_sha256"],
        "base_run_trace_sha256": base_run["run_trace_sha256"],
        "candidate_raw_outputs_sha256": candidate_run["raw_outputs_sha256"],
        "candidate_run_trace_sha256": candidate_run["run_trace_sha256"],
        "required_domain_item_counts": item_counts,
    })
    population_scope = dict(root_body)
    population_scope["population_root_sha256"] = canonical_p2_sha256(root_body)
    return {
        "hash_profile": HASH_PROFILE,
        "efficiency_scope_kind": EVALUATION_EFFICIENCY_SCOPE_KIND,
        "population_scope": population_scope,
        "metric_evidence_kind": "AQLEVON_EVALUATION_REPORT_AGGREGATE_EFFICIENCY_V1",
        "runtime_evidence_consumed": False,
        "runtime_attempt_set_sha256": None,
        "evidence_population_boundary": "FROZEN_EVALUATION_HARNESS_ONLY_NOT_OPERATIONAL_RUNTIME_ATTEMPTS",
    }


def _efficiency_summary(report: dict[str, Any], gate_result: dict[str, Any]) -> dict[str, Any]:
    raw = report.get("efficiency") or {}
    diagnostics = ((gate_result.get("diagnostics") or {}).get("efficiency") or {})
    metrics = ("cost_per_verified_success", "p95_latency_ms", "output_tokens_per_verified_success")
    summary: dict[str, Any] = {}
    for metric in metrics:
        pair = raw.get(metric)
        diag = diagnostics.get(metric)
        if not isinstance(pair, dict) or not isinstance(diag, dict):
            raise ValueError(f"efficiency evidence missing: {metric}")
        summary[metric] = {
            "baseline": _canonical_metric_number(pair.get("baseline"), f"efficiency.{metric}.baseline"),
            "candidate": _canonical_metric_number(pair.get("candidate"), f"efficiency.{metric}.candidate"),
            "ratio": _canonical_metric_number(diag.get("ratio"), f"efficiency.{metric}.ratio", allow_none=True),
            "limit": _canonical_metric_number(diag.get("limit"), f"efficiency.{metric}.limit"),
        }
    return _canonical_profile_value(summary)


def _runtime_attempt_authority_boundary() -> dict[str, Any]:
    return {
        "authority_kind": RUNTIME_ATTEMPT_AUTHORITY_KIND,
        "authoritative_for_arbitrary_runtime_attempts": False,
        "attempt_set_root_sha256": None,
        "attempt_level_truth_requirement": "MANAGER_APPROVED_PER_ATTEMPT_OBJECTIVE_VERIFIER_OR_FUTURE_APPROVED_ATTEMPT_SET_EXTENSION",
    }


def build_evaluation_decision_receipt(
    *,
    candidate_artifact_manifest: dict[str, Any],
    experiment_manifest: dict[str, Any],
    policy: dict[str, Any],
    evaluation_code_sha256: str,
    anchor_request: dict[str, Any],
    anchor_verification: dict[str, Any],
    report: dict[str, Any],
    gate_result: dict[str, Any],
    scan_receipt: dict[str, Any],
) -> dict[str, Any]:
    invalid = validate_candidate_artifact_manifest(candidate_artifact_manifest)
    if invalid:
        raise ValueError("; ".join(invalid))
    candidate_manifest_sha = candidate_artifact_manifest["manifest_sha256"]
    policy_sha = canonical_sha256(policy)
    experiment_sha = experiment_manifest.get("manifest_sha256")
    if not valid_sha256(experiment_sha):
        raise ValueError("experiment manifest SHA-256 missing/invalid")
    if experiment_manifest.get("policy_sha256") != policy_sha:
        raise ValueError("experiment manifest policy binding mismatch")
    if not valid_sha256(evaluation_code_sha256):
        raise ValueError("evaluation_code_sha256 invalid")
    actual_code_sha = actual_evaluation_code_sha256()
    if evaluation_code_sha256 != actual_code_sha:
        raise ValueError("evaluation_code_sha256 does not identify the P1 gate code executing this receipt")

    expected_request = build_anchor_request(
        experiment_manifest_sha256=experiment_sha,
        evaluation_policy_sha256=policy_sha,
        candidate_artifact_manifest_sha256=candidate_manifest_sha,
        requested_anchor_kind=anchor_request.get("requested_anchor_kind"),
    )
    if anchor_request != expected_request:
        raise ValueError("anchor request content/self-digest mismatch")
    anchor_invalid = validate_anchor_verification(anchor_verification, anchor_request)
    if anchor_invalid:
        raise ValueError("; ".join(anchor_invalid))

    if report.get("experiment_manifest_sha256") != experiment_sha:
        raise ValueError("report/experiment manifest binding mismatch")
    recomputed_gate_result = evaluate_release_p1(report, policy, experiment_manifest, scan_receipt)
    if gate_result != recomputed_gate_result:
        raise ValueError("gate result does not exactly match a fresh P1 evaluation recomputation")
    if gate_result.get("experiment_manifest_sha256") != experiment_sha:
        raise ValueError("gate result/experiment manifest binding mismatch")
    if gate_result.get("policy_id") != policy.get("policy_id"):
        raise ValueError("gate result policy_id mismatch")
    final_status = gate_result.get("status")
    if final_status not in ALLOWED_FINAL_STATUS:
        raise ValueError("gate result final status invalid")

    harness_sha = experiment_manifest.get("harness_manifest_sha256")
    if not valid_sha256(harness_sha):
        raise ValueError("harness manifest SHA-256 invalid")
    runs = report.get("runs") or {}
    base_run = runs.get("base") or {}
    candidate_run = runs.get("candidate") or {}
    for label, run in (("base", base_run), ("candidate", candidate_run)):
        if run.get("harness_manifest_sha256") != harness_sha:
            raise ValueError(f"{label} run harness binding mismatch")
        for field in ("raw_outputs_sha256", "run_trace_sha256"):
            if not valid_sha256(run.get(field)):
                raise ValueError(f"{label} run missing/invalid {field}")

    provenance = report.get("provenance") or {}
    provenance_receipt = provenance.get("license_provenance_receipt") or {}
    provenance_sha = provenance_receipt.get("receipt_sha256")
    if not valid_sha256(provenance_sha) or provenance.get("license_provenance_receipt_sha256") != provenance_sha:
        raise ValueError("provenance receipt binding mismatch")

    scan_sha = scan_receipt.get("receipt_sha256")
    contamination = report.get("contamination") or {}
    if not valid_sha256(scan_sha) or contamination.get("scan_receipt_sha256") != scan_sha:
        raise ValueError("contamination scan receipt binding mismatch")

    red_root = red_team_evidence_root(report, list(((policy.get("red_team") or {}).get("catastrophic_classes") or [])))
    invalid_codes, invalid_digest = _reason_codes("INVALID", gate_result.get("invalid_reasons"))
    failure_codes, failure_digest = _reason_codes("FAILURE", gate_result.get("failures"))
    domain_summary = _domain_summary(gate_result, experiment_manifest)
    efficiency_summary = _efficiency_summary(report, gate_result)
    efficiency_scope = _evaluation_efficiency_scope(
        experiment_manifest=experiment_manifest,
        base_run=base_run,
        candidate_run=candidate_run,
        domain_summary=domain_summary,
    )

    receipt = {
        "schema_version": 1,
        "receipt_kind": RECEIPT_KIND,
        "hash_profile": HASH_PROFILE,
        "candidate_artifact_manifest_sha256": candidate_manifest_sha,
        "experiment_manifest_sha256": experiment_sha,
        "preregistration_anchor": {
            "anchor_request_sha256": anchor_request["request_sha256"],
            "anchor_kind": anchor_verification["anchor_kind"],
            "immutable_reference": anchor_verification["immutable_reference"],
            "external_evidence_sha256": anchor_verification["external_evidence_sha256"],
            "manager_authority_id": anchor_verification["manager_authority_id"],
            "manager_attestation_sha256": anchor_verification["manager_attestation_sha256"],
            "anchored_at_utc": anchor_verification["anchored_at_utc"],
            "verification_record_sha256": anchor_verification["verification_record_sha256"],
        },
        "evaluation_policy_sha256": policy_sha,
        "evaluation_code_sha256": evaluation_code_sha256,
        "harness_manifest_sha256": harness_sha,
        "provenance_receipt_sha256": provenance_sha,
        "contamination_scan_receipt_sha256": scan_sha,
        "red_team_evidence_root_sha256": red_root,
        "base_run": {
            "raw_outputs_sha256": base_run["raw_outputs_sha256"],
            "run_trace_sha256": base_run["run_trace_sha256"],
        },
        "candidate_run": {
            "raw_outputs_sha256": candidate_run["raw_outputs_sha256"],
            "run_trace_sha256": candidate_run["run_trace_sha256"],
        },
        "domain_metric_summary": domain_summary,
        "efficiency_scope": efficiency_scope,
        "efficiency_metric_summary": efficiency_summary,
        "runtime_attempt_authority": _runtime_attempt_authority_boundary(),
        "final_status": final_status,
        "invalid_reason_codes": invalid_codes,
        "invalid_reason_set_sha256": invalid_digest,
        "failure_reason_codes": failure_codes,
        "failure_reason_set_sha256": failure_digest,
        "truth_boundary": "PROMOTION_ELIGIBLE_REQUIRES_MANAGER_REVIEW_AND_INDEPENDENT_RERUN",
    }
    receipt = _canonical_profile_value(receipt)
    _assert_no_forbidden_plaintext(receipt)
    receipt["receipt_sha256"] = canonical_p2_sha256(receipt)
    return receipt


def validate_evaluation_decision_receipt(
    receipt: Any,
    *,
    candidate_artifact_manifest: dict[str, Any] | None = None,
    experiment_manifest: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    anchor_request: dict[str, Any] | None = None,
    anchor_verification: dict[str, Any] | None = None,
) -> list[str]:
    invalid: list[str] = []
    if not isinstance(receipt, dict):
        return ["evaluation decision receipt must be an object"]
    if receipt.get("schema_version") != 1 or receipt.get("receipt_kind") != RECEIPT_KIND:
        invalid.append("evaluation decision receipt identity/schema mismatch")
    if receipt.get("hash_profile") != HASH_PROFILE:
        invalid.append("evaluation decision receipt hash_profile mismatch")
    if not verify_p2_self_digest(receipt, "receipt_sha256"):
        invalid.append("evaluation decision receipt self-digest mismatch")
    if receipt.get("final_status") not in ALLOWED_FINAL_STATUS:
        invalid.append("evaluation decision receipt final_status invalid")
    for field in (
        "candidate_artifact_manifest_sha256", "experiment_manifest_sha256", "evaluation_policy_sha256",
        "evaluation_code_sha256", "harness_manifest_sha256", "provenance_receipt_sha256",
        "contamination_scan_receipt_sha256", "red_team_evidence_root_sha256",
        "invalid_reason_set_sha256", "failure_reason_set_sha256",
    ):
        if not valid_sha256(receipt.get(field)):
            invalid.append(f"evaluation decision receipt missing/invalid {field}")
    for code_field, prefix in (("invalid_reason_codes", "INVALID_"), ("failure_reason_codes", "FAILURE_")):
        codes = receipt.get(code_field)
        if not isinstance(codes, list) or any(not isinstance(x, str) or not x.startswith(prefix) for x in codes):
            invalid.append(f"evaluation decision receipt {code_field} invalid")
    for run_name in ("base_run", "candidate_run"):
        run = receipt.get(run_name)
        if not isinstance(run, dict):
            invalid.append(f"evaluation decision receipt {run_name} missing")
            continue
        for field in ("raw_outputs_sha256", "run_trace_sha256"):
            if not valid_sha256(run.get(field)):
                invalid.append(f"evaluation decision receipt {run_name}.{field} invalid")
    domain_summary = receipt.get("domain_metric_summary")
    if not isinstance(domain_summary, dict) or not domain_summary:
        invalid.append("evaluation decision receipt domain metric summary missing")
    else:
        for domain_id, item in domain_summary.items():
            if not isinstance(item, dict):
                invalid.append(f"evaluation decision receipt domain metric invalid: {domain_id}")
                continue
            for field in ("n", "baseline_rate", "candidate_rate", "delta_pp", "improvements", "regressions",
                          "discordant_pairs", "p_improvement_one_sided", "delta_ci95_low_pp", "delta_ci95_high_pp",
                          "baseline_noise_sd_pp", "allowed_regression_pp"):
                if not _is_canonical_numeric_repr(item.get(field)):
                    invalid.append(f"evaluation decision receipt noncanonical domain numeric: {domain_id}.{field}")
            threshold = item.get("target_effect_threshold_pp")
            if threshold is not None and not _is_canonical_numeric_repr(threshold):
                invalid.append(f"evaluation decision receipt noncanonical target threshold: {domain_id}")
    efficiency = receipt.get("efficiency_metric_summary")
    if not isinstance(efficiency, dict) or not efficiency:
        invalid.append("evaluation decision receipt efficiency summary missing")
    else:
        for metric, item in efficiency.items():
            if not isinstance(item, dict):
                invalid.append(f"evaluation decision receipt efficiency metric invalid: {metric}")
                continue
            for field in ("baseline", "candidate", "limit"):
                if not _is_canonical_numeric_repr(item.get(field)):
                    invalid.append(f"evaluation decision receipt noncanonical efficiency numeric: {metric}.{field}")
            if item.get("ratio") is not None and not _is_canonical_numeric_repr(item.get("ratio")):
                invalid.append(f"evaluation decision receipt noncanonical efficiency ratio: {metric}")
    scope = receipt.get("efficiency_scope")
    if not isinstance(scope, dict):
        invalid.append("evaluation decision receipt efficiency scope missing")
    else:
        if scope.get("hash_profile") != HASH_PROFILE:
            invalid.append("evaluation decision receipt efficiency scope hash_profile mismatch")
        if scope.get("efficiency_scope_kind") != EVALUATION_EFFICIENCY_SCOPE_KIND:
            invalid.append("evaluation decision receipt efficiency scope kind mismatch")
        if scope.get("metric_evidence_kind") != "AQLEVON_EVALUATION_REPORT_AGGREGATE_EFFICIENCY_V1":
            invalid.append("evaluation decision receipt efficiency metric evidence kind mismatch")
        if scope.get("runtime_evidence_consumed") is not False or scope.get("runtime_attempt_set_sha256") is not None:
            invalid.append("evaluation decision receipt runtime efficiency evidence boundary mismatch")
        if scope.get("evidence_population_boundary") != "FROZEN_EVALUATION_HARNESS_ONLY_NOT_OPERATIONAL_RUNTIME_ATTEMPTS":
            invalid.append("evaluation decision receipt efficiency population boundary mismatch")
        pop = scope.get("population_scope")
        if not isinstance(pop, dict):
            invalid.append("evaluation decision receipt population scope missing")
        else:
            if pop.get("hash_profile") != HASH_PROFILE or pop.get("population_kind") != EVALUATION_EFFICIENCY_POPULATION_KIND:
                invalid.append("evaluation decision receipt population identity mismatch")
            root = pop.get("population_root_sha256")
            body = {k: v for k, v in pop.items() if k != "population_root_sha256"}
            try:
                if not valid_sha256(root) or canonical_p2_sha256(body) != root:
                    invalid.append("evaluation decision receipt population root mismatch")
            except (TypeError, ValueError):
                invalid.append("evaluation decision receipt population root invalid")
    runtime_authority = receipt.get("runtime_attempt_authority")
    if not isinstance(runtime_authority, dict):
        invalid.append("evaluation decision receipt runtime attempt authority boundary missing")
    else:
        if runtime_authority.get("authority_kind") != RUNTIME_ATTEMPT_AUTHORITY_KIND:
            invalid.append("evaluation decision receipt runtime attempt authority kind mismatch")
        if runtime_authority.get("authoritative_for_arbitrary_runtime_attempts") is not False:
            invalid.append("evaluation decision receipt cannot authorize arbitrary runtime attempts")
        if runtime_authority.get("attempt_set_root_sha256") is not None:
            invalid.append("evaluation decision receipt unexpected runtime attempt-set binding")
        if runtime_authority.get("attempt_level_truth_requirement") != "MANAGER_APPROVED_PER_ATTEMPT_OBJECTIVE_VERIFIER_OR_FUTURE_APPROVED_ATTEMPT_SET_EXTENSION":
            invalid.append("evaluation decision receipt runtime attempt truth requirement mismatch")
    try:
        _assert_no_forbidden_plaintext(receipt)
    except ValueError as exc:
        invalid.append(str(exc))

    if candidate_artifact_manifest is not None:
        invalid.extend(validate_candidate_artifact_manifest(candidate_artifact_manifest))
        if candidate_artifact_manifest.get("manifest_sha256") != receipt.get("candidate_artifact_manifest_sha256"):
            invalid.append("receipt candidate artifact binding mismatch")
    if experiment_manifest is not None:
        if experiment_manifest.get("manifest_sha256") != receipt.get("experiment_manifest_sha256"):
            invalid.append("receipt experiment manifest binding mismatch")
        if experiment_manifest.get("harness_manifest_sha256") != receipt.get("harness_manifest_sha256"):
            invalid.append("receipt harness manifest binding mismatch")
    if policy is not None and canonical_sha256(policy) != receipt.get("evaluation_policy_sha256"):
        invalid.append("receipt evaluation policy binding mismatch")
    if anchor_request is not None and anchor_verification is not None:
        invalid.extend(validate_anchor_verification(anchor_verification, anchor_request))
        anchor = receipt.get("preregistration_anchor") or {}
        if anchor.get("anchor_request_sha256") != anchor_request.get("request_sha256"):
            invalid.append("receipt preregistration anchor request mismatch")
        if anchor.get("verification_record_sha256") != anchor_verification.get("verification_record_sha256"):
            invalid.append("receipt preregistration verification record mismatch")
        for field in (
            "anchor_kind", "immutable_reference", "external_evidence_sha256", "manager_authority_id",
            "manager_attestation_sha256", "anchored_at_utc",
        ):
            if anchor.get(field) != anchor_verification.get(field):
                invalid.append(f"receipt preregistration anchor {field} mismatch")
    return invalid


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _dump(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AQLEVON Evaluation Decision Receipt V1")
    sub = parser.add_subparsers(dest="command", required=True)

    req = sub.add_parser("anchor-request", help="Create the self-hashed preregistration anchor request")
    req.add_argument("--experiment-manifest", required=True)
    req.add_argument("--policy", required=True)
    req.add_argument("--candidate-artifact-manifest", required=True)
    req.add_argument("--anchor-kind", choices=sorted(ALLOWED_ANCHOR_KINDS), required=True)
    req.add_argument("--output", required=True)

    anchor_check = sub.add_parser("validate-anchor", help="Validate Manager-verifiable preregistration anchor bindings")
    anchor_check.add_argument("--anchor-request", required=True)
    anchor_check.add_argument("--anchor-verification", required=True)

    build = sub.add_parser("build-receipt", help="Build AQLEVON_EVALUATION_DECISION_RECEIPT_V1")
    build.add_argument("--candidate-artifact-manifest", required=True)
    build.add_argument("--experiment-manifest", required=True)
    build.add_argument("--policy", required=True)
    build.add_argument("--evaluation-code", required=True)
    build.add_argument("--anchor-request", required=True)
    build.add_argument("--anchor-verification", required=True)
    build.add_argument("--report", required=True)
    build.add_argument("--gate-result", required=True)
    build.add_argument("--scan-receipt", required=True)
    build.add_argument("--output", required=True)

    verify = sub.add_parser("validate-receipt", help="Validate receipt self-integrity and optional bindings")
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--candidate-artifact-manifest")
    verify.add_argument("--experiment-manifest")
    verify.add_argument("--policy")
    verify.add_argument("--anchor-request")
    verify.add_argument("--anchor-verification")

    args = parser.parse_args(argv)
    if args.command == "anchor-request":
        experiment = _load(args.experiment_manifest)
        policy = _load(args.policy)
        candidate = _load(args.candidate_artifact_manifest)
        invalid = validate_candidate_artifact_manifest(candidate)
        if invalid:
            raise SystemExit("; ".join(invalid))
        request = build_anchor_request(
            experiment_manifest_sha256=experiment.get("manifest_sha256"),
            evaluation_policy_sha256=canonical_sha256(policy),
            candidate_artifact_manifest_sha256=candidate.get("manifest_sha256"),
            requested_anchor_kind=args.anchor_kind,
        )
        _dump(args.output, request)
        return 0

    if args.command == "validate-anchor":
        request = _load(args.anchor_request)
        verification = _load(args.anchor_verification)
        invalid = validate_anchor_verification(verification, request)
        print(json.dumps({"status": "VALID" if not invalid else "INVALID", "invalid_reasons": invalid}, indent=2, sort_keys=True))
        return 0 if not invalid else 1

    if args.command == "build-receipt":
        candidate = _load(args.candidate_artifact_manifest)
        experiment = _load(args.experiment_manifest)
        policy = _load(args.policy)
        request = _load(args.anchor_request)
        verification = _load(args.anchor_verification)
        report = _load(args.report)
        gate_result = _load(args.gate_result)
        scan = _load(args.scan_receipt)
        code_sha = hashlib.sha256(Path(args.evaluation_code).read_bytes()).hexdigest()
        if code_sha != actual_evaluation_code_sha256():
            raise SystemExit("--evaluation-code must be byte-identical to the P1 eval_truth_gate.py used by this receipt builder")
        receipt = build_evaluation_decision_receipt(
            candidate_artifact_manifest=candidate,
            experiment_manifest=experiment,
            policy=policy,
            evaluation_code_sha256=code_sha,
            anchor_request=request,
            anchor_verification=verification,
            report=report,
            gate_result=gate_result,
            scan_receipt=scan,
        )
        _dump(args.output, receipt)
        return 0

    receipt = _load(args.receipt)
    kwargs: dict[str, Any] = {}
    if args.candidate_artifact_manifest:
        kwargs["candidate_artifact_manifest"] = _load(args.candidate_artifact_manifest)
    if args.experiment_manifest:
        kwargs["experiment_manifest"] = _load(args.experiment_manifest)
    if args.policy:
        kwargs["policy"] = _load(args.policy)
    if bool(args.anchor_request) != bool(args.anchor_verification):
        raise SystemExit("anchor-request and anchor-verification must be supplied together")
    if args.anchor_request:
        kwargs["anchor_request"] = _load(args.anchor_request)
        kwargs["anchor_verification"] = _load(args.anchor_verification)
    invalid = validate_evaluation_decision_receipt(receipt, **kwargs)
    print(json.dumps({"status": "VALID" if not invalid else "INVALID", "invalid_reasons": invalid}, indent=2, sort_keys=True))
    return 0 if not invalid else 1


if __name__ == "__main__":
    raise SystemExit(main())