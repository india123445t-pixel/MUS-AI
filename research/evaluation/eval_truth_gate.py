#!/usr/bin/env python3
"""AQLEVON evaluation truth / contamination / release gate.

Research-control plane only. Protected benchmark plaintext never needs to leave the
sealed fingerprinting environment. Every release decision fails closed when a
required manifest, receipt, compatibility identity, or coverage proof is absent.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import re
import statistics
import unicodedata
from pathlib import Path
from typing import Any, Iterable

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
PACK_SCHEMA_VERSION = 2
PACK_KIND = "AQLEVON_EVAL_FINGERPRINT_PACK"
PACK_ALGORITHM = "HMAC-SHA256"
PACK_NORMALIZATION = "NFKC_CASEFOLD_WS_V1"
PACK_DOMAIN = "AQLEVON_EVAL_FINGERPRINT_V1"
SCANNER_ID = "AQLEVON_EVAL_SCANNER_V2"
SCAN_RECEIPT_KIND = "AQLEVON_CONTAMINATION_SCAN_RECEIPT"
EXPERIMENT_KIND = "AQLEVON_EVAL_EXPERIMENT_MANIFEST"
PROVENANCE_RECEIPT_KIND = "AQLEVON_PROVENANCE_DECISION_RECEIPT"


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _self_digest(value: dict[str, Any], digest_field: str) -> str:
    payload = {k: v for k, v in value.items() if k != digest_field}
    return canonical_sha256(payload)


def _normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _hmac_hex(key: bytes, domain: str, purpose: str, value: str) -> str:
    msg = f"{domain}\x00{purpose}\x00{value}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def key_identity(key: bytes, domain_separator: str = PACK_DOMAIN) -> str:
    if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
        raise ValueError("fingerprint key must contain at least 32 bytes of secret material")
    return _hmac_hex(bytes(key), domain_separator, "KEY_ID_V1", "AQLEVON")


def build_fingerprint_pack(
    records: Iterable[dict[str, Any]],
    key: bytes,
    *,
    shingle_n: int = 13,
    domain_separator: str = PACK_DOMAIN,
) -> dict[str, Any]:
    if type(shingle_n) is not int or shingle_n < 1:
        raise ValueError("shingle_n must be a positive integer")
    key_id = key_identity(key, domain_separator)
    packed_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} must be an object")
        record_id = record.get("id")
        field = record.get("field")
        text = record.get("text")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"record {index} id must be a non-empty string")
        if not isinstance(field, str) or not field:
            raise ValueError(f"record {index} field must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"record {index} text must be a non-empty string")
        norm = _normalize_text(text)
        tokens = norm.split()
        shingles = [" ".join(tokens[i:i + shingle_n]) for i in range(max(0, len(tokens) - shingle_n + 1))]
        packed_records.append({
            "id_hmac_sha256": _hmac_hex(key, domain_separator, "RECORD_ID_V1", record_id),
            "field": field,
            "exact_hmac_sha256": _hmac_hex(key, domain_separator, "EXACT_TEXT_V1", norm),
            "shingle_n": shingle_n,
            "shingle_hmac_sha256": sorted({_hmac_hex(key, domain_separator, "SHINGLE_V1", s) for s in shingles}),
        })
    if not packed_records:
        raise ValueError("fingerprint pack cannot be empty")
    pack = {
        "schema_version": PACK_SCHEMA_VERSION,
        "pack_kind": PACK_KIND,
        "algorithm": PACK_ALGORITHM,
        "normalization": PACK_NORMALIZATION,
        "domain_separator": domain_separator,
        "key_id_hmac_sha256": key_id,
        "plaintext_included": False,
        "shingle_n": shingle_n,
        "records": packed_records,
    }
    pack["pack_sha256"] = canonical_sha256(pack)
    return pack


def _validate_fingerprint_pack(pack: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(pack, dict):
        raise ValueError(f"{label}: pack must be a JSON object")
    allowed_top = {
        "schema_version", "pack_kind", "algorithm", "normalization", "domain_separator",
        "key_id_hmac_sha256", "plaintext_included", "shingle_n", "records", "pack_sha256",
    }
    unexpected = set(pack) - allowed_top
    if unexpected:
        raise ValueError(f"{label}: unexpected top-level fields: {sorted(unexpected)}")
    if pack.get("schema_version") != PACK_SCHEMA_VERSION:
        raise ValueError(f"{label}: incompatible schema_version")
    if pack.get("pack_kind") != PACK_KIND:
        raise ValueError(f"{label}: incompatible pack_kind")
    if pack.get("algorithm") != PACK_ALGORITHM:
        raise ValueError(f"{label}: incompatible algorithm")
    if pack.get("normalization") != PACK_NORMALIZATION:
        raise ValueError(f"{label}: incompatible normalization")
    if not isinstance(pack.get("domain_separator"), str) or not pack.get("domain_separator"):
        raise ValueError(f"{label}: domain_separator must be non-empty")
    if not _valid_sha256(pack.get("key_id_hmac_sha256")):
        raise ValueError(f"{label}: invalid key_id_hmac_sha256")
    if pack.get("plaintext_included") is not False:
        raise ValueError(f"{label}: plaintext_included must be false")
    shingle_n = pack.get("shingle_n")
    if type(shingle_n) is not int or shingle_n < 1:
        raise ValueError(f"{label}: shingle_n must be a positive integer")
    if not _valid_sha256(pack.get("pack_sha256")) or _self_digest(pack, "pack_sha256") != pack.get("pack_sha256"):
        raise ValueError(f"{label}: pack_sha256 mismatch")
    records = pack.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError(f"{label}: records must be a non-empty list")
    allowed_rec = {"id_hmac_sha256", "field", "exact_hmac_sha256", "shingle_n", "shingle_hmac_sha256"}
    seen_ids: set[tuple[str, str]] = set()
    for index, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"{label}: record {index} must be an object")
        unexpected_rec = set(rec) - allowed_rec
        if unexpected_rec:
            raise ValueError(f"{label}: record {index} unexpected fields: {sorted(unexpected_rec)}")
        if not _valid_sha256(rec.get("id_hmac_sha256")):
            raise ValueError(f"{label}: record {index} invalid id_hmac_sha256")
        if not _valid_sha256(rec.get("exact_hmac_sha256")):
            raise ValueError(f"{label}: record {index} invalid exact_hmac_sha256")
        if not isinstance(rec.get("field"), str) or not rec.get("field"):
            raise ValueError(f"{label}: record {index} field must be non-empty")
        if rec.get("shingle_n") != shingle_n:
            raise ValueError(f"{label}: record {index} shingle_n mismatch")
        shingles = rec.get("shingle_hmac_sha256")
        if not isinstance(shingles, list) or any(not _valid_sha256(x) for x in shingles):
            raise ValueError(f"{label}: record {index} invalid shingle_hmac_sha256")
        if len(shingles) != len(set(shingles)):
            raise ValueError(f"{label}: record {index} duplicate shingle hashes")
        key = (rec["id_hmac_sha256"], rec["field"])
        if key in seen_ids:
            raise ValueError(f"{label}: duplicate record identity/field")
        seen_ids.add(key)
    return records


def _scan_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def scan_fingerprint_packs(protected: Any, candidate: Any, fuzzy_threshold: float = 0.8) -> dict[str, Any]:
    if not isinstance(fuzzy_threshold, (int, float)) or not 0.0 <= float(fuzzy_threshold) <= 1.0:
        return _scan_receipt({
            "schema_version": 1, "receipt_kind": SCAN_RECEIPT_KIND, "scanner_id": SCANNER_ID,
            "status": "INVALID", "scan_complete": False, "invalid_reasons": ["fuzzy_threshold must be in [0,1]"],
            "exact_overlap_count": 0, "fuzzy_overlap_count": 0, "fuzzy_threshold": fuzzy_threshold,
            "protected_pack_sha256": None, "candidate_pack_sha256": None, "compatibility": {},
        })
    try:
        protected_records = _validate_fingerprint_pack(protected, "protected")
        candidate_records = _validate_fingerprint_pack(candidate, "candidate")
    except (TypeError, ValueError) as exc:
        return _scan_receipt({
            "schema_version": 1, "receipt_kind": SCAN_RECEIPT_KIND, "scanner_id": SCANNER_ID,
            "status": "INVALID", "scan_complete": False, "invalid_reasons": [str(exc)],
            "exact_overlap_count": 0, "fuzzy_overlap_count": 0, "fuzzy_threshold": float(fuzzy_threshold),
            "protected_pack_sha256": protected.get("pack_sha256") if isinstance(protected, dict) else None,
            "candidate_pack_sha256": candidate.get("pack_sha256") if isinstance(candidate, dict) else None,
            "compatibility": {},
        })

    compatibility_fields = (
        "schema_version", "pack_kind", "algorithm", "normalization", "domain_separator",
        "key_id_hmac_sha256", "shingle_n",
    )
    mismatches = [field for field in compatibility_fields if protected.get(field) != candidate.get(field)]
    compatibility = {field: protected.get(field) for field in compatibility_fields}
    compatibility["matched"] = not mismatches
    if mismatches:
        return _scan_receipt({
            "schema_version": 1, "receipt_kind": SCAN_RECEIPT_KIND, "scanner_id": SCANNER_ID,
            "status": "INVALID", "scan_complete": False,
            "invalid_reasons": [f"incompatible fingerprint packs: {','.join(mismatches)}"],
            "exact_overlap_count": 0, "fuzzy_overlap_count": 0, "fuzzy_threshold": float(fuzzy_threshold),
            "protected_pack_sha256": protected["pack_sha256"], "candidate_pack_sha256": candidate["pack_sha256"],
            "compatibility": compatibility,
        })

    exact_index: dict[str, list[dict[str, Any]]] = {}
    shingle_index: dict[str, set[int]] = {}
    for idx, rec in enumerate(protected_records):
        exact_index.setdefault(rec["exact_hmac_sha256"], []).append(rec)
        for shingle in rec["shingle_hmac_sha256"]:
            shingle_index.setdefault(shingle, set()).add(idx)

    exact_matches: list[dict[str, Any]] = []
    fuzzy_matches: list[dict[str, Any]] = []
    seen_fuzzy: set[tuple[str, str, str, str]] = set()
    for cand in candidate_records:
        for prot in exact_index.get(cand["exact_hmac_sha256"], []):
            exact_matches.append({
                "protected_id_hmac_sha256": prot["id_hmac_sha256"], "protected_field": prot["field"],
                "candidate_id_hmac_sha256": cand["id_hmac_sha256"], "candidate_field": cand["field"],
            })
        cand_shingles = set(cand["shingle_hmac_sha256"])
        if not cand_shingles:
            continue
        possible: set[int] = set()
        for shingle in cand_shingles:
            possible.update(shingle_index.get(shingle, set()))
        for idx in possible:
            prot = protected_records[idx]
            prot_shingles = set(prot["shingle_hmac_sha256"])
            if not prot_shingles:
                continue
            union = len(cand_shingles | prot_shingles)
            jaccard = len(cand_shingles & prot_shingles) / union if union else 0.0
            key = (prot["id_hmac_sha256"], prot["field"], cand["id_hmac_sha256"], cand["field"])
            if jaccard >= float(fuzzy_threshold) and key not in seen_fuzzy:
                seen_fuzzy.add(key)
                fuzzy_matches.append({
                    "protected_id_hmac_sha256": prot["id_hmac_sha256"], "protected_field": prot["field"],
                    "candidate_id_hmac_sha256": cand["id_hmac_sha256"], "candidate_field": cand["field"],
                    "jaccard": round(jaccard, 6),
                })

    contaminated = bool(exact_matches or fuzzy_matches)
    return _scan_receipt({
        "schema_version": 1, "receipt_kind": SCAN_RECEIPT_KIND, "scanner_id": SCANNER_ID,
        "status": "CONTAMINATED" if contaminated else "CLEAN", "scan_complete": True,
        "invalid_reasons": [], "exact_overlap_count": len(exact_matches), "fuzzy_overlap_count": len(fuzzy_matches),
        "fuzzy_threshold": float(fuzzy_threshold), "protected_pack_sha256": protected["pack_sha256"],
        "candidate_pack_sha256": candidate["pack_sha256"], "compatibility": compatibility,
        "protected_records": len(protected_records), "candidate_records": len(candidate_records),
        "exact_matches": exact_matches, "fuzzy_matches": fuzzy_matches,
    })


def validate_scan_receipt(receipt: Any, policy: dict[str, Any]) -> tuple[list[str], list[str]]:
    invalid: list[str] = []
    failures: list[str] = []
    if not isinstance(receipt, dict):
        return ["scan receipt must be a JSON object"], []
    if receipt.get("schema_version") != 1 or receipt.get("receipt_kind") != SCAN_RECEIPT_KIND or receipt.get("scanner_id") != SCANNER_ID:
        invalid.append("scan receipt identity/schema mismatch")
    if not _valid_sha256(receipt.get("receipt_sha256")) or _self_digest(receipt, "receipt_sha256") != receipt.get("receipt_sha256"):
        invalid.append("scan receipt digest mismatch")
    status = receipt.get("status")
    if status not in {"CLEAN", "CONTAMINATED", "INVALID"}:
        invalid.append("scan receipt status invalid")
    if status == "INVALID" or receipt.get("scan_complete") is not True:
        invalid.append("contamination scan is not valid/complete")
    for field in ("protected_pack_sha256", "candidate_pack_sha256"):
        if not _valid_sha256(receipt.get(field)):
            invalid.append(f"scan receipt missing/invalid {field}")
    comp = receipt.get("compatibility")
    fp = (policy.get("contamination") or {}).get("fingerprint") or {}
    if not isinstance(comp, dict) or comp.get("matched") is not True:
        invalid.append("scan receipt fingerprint compatibility is not proven")
    else:
        expected = {
            "schema_version": int(fp.get("schema_version", PACK_SCHEMA_VERSION)),
            "pack_kind": fp.get("pack_kind", PACK_KIND),
            "algorithm": fp.get("algorithm", PACK_ALGORITHM),
            "normalization": fp.get("normalization", PACK_NORMALIZATION),
            "domain_separator": fp.get("domain_separator", PACK_DOMAIN),
            "shingle_n": int(fp.get("shingle_n", 13)),
        }
        for key, value in expected.items():
            if comp.get(key) != value:
                invalid.append(f"scan receipt incompatible fingerprint {key}")
        if not _valid_sha256(comp.get("key_id_hmac_sha256")):
            invalid.append("scan receipt invalid key identity")
    exact = receipt.get("exact_overlap_count")
    fuzzy = receipt.get("fuzzy_overlap_count")
    if type(exact) is not int or exact < 0 or type(fuzzy) is not int or fuzzy < 0:
        invalid.append("scan receipt overlap counts invalid")
    elif not invalid:
        cp = policy.get("contamination") or {}
        if exact > int(cp.get("max_exact_overlaps", 0)):
            failures.append("exact protected-eval overlap detected")
        if fuzzy > int(cp.get("max_fuzzy_overlaps", 0)):
            failures.append("fuzzy protected-eval overlap detected")
        if status == "CONTAMINATED" and exact == 0 and fuzzy == 0:
            invalid.append("scan receipt status/counts inconsistent")
        if status == "CLEAN" and (exact or fuzzy):
            invalid.append("scan receipt clean status/counts inconsistent")
    return invalid, failures


def finalize_experiment_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    manifest = dict(payload)
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def validate_experiment_manifest(manifest: Any, policy: dict[str, Any]) -> list[str]:
    invalid: list[str] = []
    if not isinstance(manifest, dict):
        return ["experiment manifest must be a JSON object"]
    if manifest.get("schema_version") != 1 or manifest.get("manifest_kind") != EXPERIMENT_KIND:
        invalid.append("experiment manifest identity/schema mismatch")
    if manifest.get("policy_id") != policy.get("policy_id"):
        invalid.append("experiment manifest policy_id mismatch")
    expected_policy_sha = canonical_sha256(policy)
    if manifest.get("policy_sha256") != expected_policy_sha:
        invalid.append("experiment manifest policy_sha256 mismatch")
    if not _valid_sha256(manifest.get("manifest_sha256")) or _self_digest(manifest, "manifest_sha256") != manifest.get("manifest_sha256"):
        invalid.append("experiment manifest digest mismatch")
    for field in (
        "harness_manifest_sha256", "provenance_manifest_sha256", "training_data_manifest_sha256",
        "source_registry_snapshot_sha256", "red_team_manifest_sha256",
    ):
        if not _valid_sha256(manifest.get(field)):
            invalid.append(f"experiment manifest missing/invalid {field}")
    domains = manifest.get("domains")
    if not isinstance(domains, dict):
        return invalid + ["experiment manifest domains must be an object"]
    required = set(policy.get("required_domains") or [])
    missing = required - set(domains)
    if missing:
        invalid.append(f"experiment manifest missing required domains: {','.join(sorted(missing))}")
    targets = 0
    for domain_id, cfg in domains.items():
        if not isinstance(cfg, dict):
            invalid.append(f"{domain_id}: experiment domain config must be object")
            continue
        role = cfg.get("role")
        if role not in {"target", "protected"}:
            invalid.append(f"{domain_id}: role must be target or protected")
        if role == "target":
            targets += 1
            if not isinstance(cfg.get("min_effect_pp"), (int, float)) or float(cfg.get("min_effect_pp")) < 0:
                invalid.append(f"{domain_id}: target min_effect_pp missing/invalid in frozen manifest")
        elif cfg.get("min_effect_pp") not in (None,):
            invalid.append(f"{domain_id}: protected domain min_effect_pp must be null")
        if not isinstance(cfg.get("max_regression_pp"), (int, float)) or float(cfg.get("max_regression_pp")) < 0:
            invalid.append(f"{domain_id}: max_regression_pp missing/invalid in frozen manifest")
        if not isinstance(cfg.get("stochastic"), bool):
            invalid.append(f"{domain_id}: stochastic must be boolean in frozen manifest")
    if targets < 1:
        invalid.append("experiment manifest requires at least one target domain")
    return invalid


def finalize_provenance_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(payload)
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def validate_provenance_receipt(receipt: Any, manifest: dict[str, Any]) -> list[str]:
    invalid: list[str] = []
    if not isinstance(receipt, dict):
        return ["provenance receipt must be a JSON object"]
    if receipt.get("schema_version") != 1 or receipt.get("receipt_kind") != PROVENANCE_RECEIPT_KIND:
        invalid.append("provenance receipt identity/schema mismatch")
    if receipt.get("status") != "PASS":
        invalid.append("license/provenance decision is not PASS")
    if not _valid_sha256(receipt.get("receipt_sha256")) or _self_digest(receipt, "receipt_sha256") != receipt.get("receipt_sha256"):
        invalid.append("provenance receipt digest mismatch")
    bindings = (
        "provenance_manifest_sha256", "training_data_manifest_sha256", "source_registry_snapshot_sha256",
    )
    for field in bindings:
        if not _valid_sha256(receipt.get(field)) or receipt.get(field) != manifest.get(field):
            invalid.append(f"provenance receipt {field} not bound to experiment manifest")
    if not _valid_sha256(receipt.get("license_evidence_bundle_sha256")):
        invalid.append("provenance receipt missing/invalid license_evidence_bundle_sha256")
    if not isinstance(receipt.get("auditor_id"), str) or not receipt.get("auditor_id"):
        invalid.append("provenance receipt auditor_id missing")
    return invalid


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


def _mean_bool(values: list[bool]) -> float:
    return sum(1 for v in values if v) / len(values)


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
    p_one_sided = sum(math.comb(discordant, k) for k in range(improvements, discordant + 1)) / (2 ** discordant) if discordant else 1.0
    differences = [int(c) - int(b) for b, c in zip(baseline, candidate)]
    se = statistics.stdev(differences) / math.sqrt(n) if n > 1 else 0.0
    if abs(confidence_level - 0.95) > 1e-9:
        raise ValueError("only 95% confidence is supported in V1")
    margin = 1.959963984540054 * se
    return {
        "n": n, "baseline_rate": base_rate, "candidate_rate": cand_rate, "delta_pp": delta * 100.0,
        "improvements": improvements, "regressions": regressions, "discordant_pairs": discordant,
        "p_improvement_one_sided": p_one_sided,
        "delta_ci95_low_pp": (delta - margin) * 100.0, "delta_ci95_high_pp": (delta + margin) * 100.0,
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
        if p_value <= alpha / (m - rank):
            result[name] = True
        else:
            break
    return result


def evaluate_release(
    report: dict[str, Any],
    policy: dict[str, Any],
    experiment_manifest: dict[str, Any],
    scan_receipt: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    invalid: list[str] = []
    diagnostics: dict[str, Any] = {"domains": {}}

    invalid.extend(validate_experiment_manifest(experiment_manifest, policy))
    exp_sha = experiment_manifest.get("manifest_sha256")
    if report.get("schema_version") != 2:
        invalid.append("report.schema_version must equal 2")
    if report.get("policy_id") != policy.get("policy_id"):
        invalid.append("report.policy_id does not match policy")
    if report.get("experiment_manifest_sha256") != exp_sha:
        invalid.append("report is not bound to the frozen experiment manifest")

    # Candidate report may not carry mutable thresholds or role/stochastic controls.
    report_domains = report.get("domains") or {}
    for domain_id, domain in report_domains.items():
        if isinstance(domain, dict):
            forbidden = {"min_effect_pp", "max_regression_pp", "role", "stochastic"} & set(domain)
            if forbidden:
                invalid.append(f"{domain_id}: run-specific controls must come only from frozen experiment manifest: {','.join(sorted(forbidden))}")

    harness_hash = experiment_manifest.get("harness_manifest_sha256")
    runs = report.get("runs") or {}
    for run_name in ("base", "candidate"):
        run = runs.get(run_name)
        if not isinstance(run, dict):
            invalid.append(f"runs.{run_name} missing")
            continue
        if run.get("harness_manifest_sha256") != harness_hash:
            invalid.append(f"runs.{run_name} harness manifest mismatch")
        for field in ("run_trace_sha256", "raw_outputs_sha256"):
            if not _valid_sha256(run.get(field)):
                invalid.append(f"runs.{run_name} missing/invalid {field}")

    provenance = report.get("provenance") or {}
    for field in ("base_checkpoint_sha256", "candidate_checkpoint_sha256", "tokenizer_sha256"):
        if not _valid_sha256(provenance.get(field)):
            invalid.append(f"provenance missing/invalid {field}")
    receipt = provenance.get("license_provenance_receipt")
    invalid.extend(validate_provenance_receipt(receipt, experiment_manifest))
    if isinstance(receipt, dict) and provenance.get("license_provenance_receipt_sha256") != receipt.get("receipt_sha256"):
        invalid.append("provenance receipt reference hash mismatch")

    scan_invalid, scan_failures = validate_scan_receipt(scan_receipt, policy)
    invalid.extend(scan_invalid)
    failures.extend(scan_failures)
    contamination = report.get("contamination") or {}
    if contamination.get("scan_receipt_sha256") != scan_receipt.get("receipt_sha256"):
        invalid.append("report contamination is not bound to scanner receipt")
    if contamination.get("protected_answers_exported") is not False:
        failures.append("protected evaluation answers may not be exported into candidate/training artifacts")
    forbidden_counts = {"exact_overlap_count", "fuzzy_overlap_count", "scan_complete", "keyed_fingerprints"} & set(contamination)
    if forbidden_counts:
        invalid.append("candidate report may not assert contamination scan counts/status independently")

    red_team = report.get("red_team") or {}
    if red_team.get("manifest_sha256") != experiment_manifest.get("red_team_manifest_sha256"):
        invalid.append("red-team manifest hash mismatch")
    classes = red_team.get("classes")
    required_classes = (policy.get("red_team") or {}).get("catastrophic_classes") or []
    if not isinstance(classes, dict):
        invalid.append("red_team.classes must be an object")
    else:
        total_failures = 0
        for class_id in required_classes:
            evidence = classes.get(class_id)
            if not isinstance(evidence, dict):
                invalid.append(f"red-team class missing: {class_id}")
                continue
            if evidence.get("evaluated") is not True:
                invalid.append(f"red-team class not evaluated: {class_id}")
            count = evidence.get("failure_count")
            if type(count) is not int or count < 0:
                invalid.append(f"red-team class invalid failure_count: {class_id}")
            else:
                total_failures += count
            if not _valid_sha256(evidence.get("evidence_sha256")):
                invalid.append(f"red-team class missing/invalid evidence hash: {class_id}")
        if total_failures > int((policy.get("red_team") or {}).get("max_catastrophic_failures", 0)):
            failures.append(f"catastrophic red-team failures: {total_failures}")

    manifest_domains = experiment_manifest.get("domains") or {}
    required_domains = policy.get("required_domains") or []
    for domain_id in required_domains:
        if domain_id not in report_domains:
            invalid.append(f"required domain missing: {domain_id}")

    target_p_values: dict[str, float] = {}
    computed: dict[str, dict[str, Any]] = {}
    for domain_id, domain in report_domains.items():
        cfg = manifest_domains.get(domain_id)
        if not isinstance(cfg, dict):
            invalid.append(f"{domain_id}: no frozen experiment config")
            continue
        try:
            baseline = _strict_binary(domain.get("baseline_outcomes"), f"{domain_id}.baseline_outcomes")
            candidate = _strict_binary(domain.get("candidate_outcomes"), f"{domain_id}.candidate_outcomes")
            stats = _paired_stats(baseline, candidate, float(policy.get("confidence_level", 0.95)))
            if stats["n"] < int(policy.get("minimum_items_per_domain", 30)):
                invalid.append(f"{domain_id}: too few paired items ({stats['n']})")
            noise_pp = _baseline_noise_pp(
                [float(x) for x in domain.get("baseline_repeat_rates", [])],
                bool(cfg["stochastic"]), int(policy.get("minimum_stochastic_baseline_repeats", 3)),
            )
            allowed_regression_pp = max(float(cfg["max_regression_pp"]), float(policy.get("noise_multiplier", 2.0)) * noise_pp)
            role = cfg["role"]
            threshold_pp = None
            if role == "target":
                threshold_pp = max(float(cfg["min_effect_pp"]), float(policy.get("noise_multiplier", 2.0)) * noise_pp)
                target_p_values[domain_id] = float(stats["p_improvement_one_sided"])
            if float(stats["delta_pp"]) < -allowed_regression_pp:
                failures.append(f"{domain_id}: regression {stats['delta_pp']:.3f}pp exceeds allowed {allowed_regression_pp:.3f}pp")
            computed[domain_id] = {
                **stats, "role": role, "baseline_noise_sd_pp": noise_pp,
                "target_effect_threshold_pp": threshold_pp, "allowed_regression_pp": allowed_regression_pp,
            }
        except (KeyError, TypeError, ValueError, statistics.StatisticsError) as exc:
            invalid.append(f"{domain_id}: {exc}")

    if not target_p_values:
        invalid.append("at least one target domain is required")
    significant = _holm_significant(target_p_values, float(policy.get("alpha", 0.05))) if target_p_values else {}
    for domain_id, stats in computed.items():
        if stats["role"] != "target":
            continue
        threshold = float(stats["target_effect_threshold_pp"] or 0.0)
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
        base, cand = pair.get("baseline"), pair.get("candidate")
        try:
            if base is None or cand is None or float(base) < 0 or float(cand) < 0:
                raise ValueError
            base_f, cand_f = float(base), float(cand)
        except (TypeError, ValueError):
            invalid.append(f"efficiency.{metric} baseline/candidate missing or invalid")
            continue
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

    status = "INVALID" if invalid else ("REJECTED" if failures else "PROMOTION_ELIGIBLE")
    return {
        "policy_id": policy.get("policy_id"), "experiment_manifest_sha256": exp_sha,
        "status": status, "invalid_reasons": invalid, "failures": failures, "diagnostics": diagnostics,
    }


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AQLEVON evaluation truth gate")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Compare sealed protected/candidate fingerprint packs")
    scan.add_argument("--protected-pack", required=True)
    scan.add_argument("--candidate-pack", required=True)
    scan.add_argument("--fuzzy-threshold", type=float, default=0.8)
    gate = sub.add_parser("gate", help="Evaluate release evidence against frozen manifests")
    gate.add_argument("--policy", required=True)
    gate.add_argument("--experiment-manifest", required=True)
    gate.add_argument("--scan-receipt", required=True)
    gate.add_argument("--report", required=True)
    args = parser.parse_args(argv)

    if args.command == "scan":
        result = scan_fingerprint_packs(_load_json(args.protected_pack), _load_json(args.candidate_pack), args.fuzzy_threshold)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 2 if result["status"] == "INVALID" else (1 if result["status"] == "CONTAMINATED" else 0)

    policy = _load_json(args.policy)
    manifest = _load_json(args.experiment_manifest)
    receipt = _load_json(args.scan_receipt)
    report = _load_json(args.report)
    result = evaluate_release(report, policy, manifest, receipt)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PROMOTION_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())