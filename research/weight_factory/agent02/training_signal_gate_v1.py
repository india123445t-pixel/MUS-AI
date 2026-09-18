#!/usr/bin/env python3
"""AQLEVON Worker 02 — fail-closed, instance-level training signal admission gate.

This module is research/control-plane tooling. It does not download data, execute
untrusted candidate code, expose protected evaluation text, or modify model weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Iterable

ADMIT = "ADMIT"
QUARANTINE = "QUARANTINE"
DENY = "DENY"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_text(record: dict[str, Any]) -> str:
    answer = record.get("answer", record.get("response", ""))
    if not isinstance(answer, str):
        answer = json.dumps(answer, ensure_ascii=False, sort_keys=True)
    return f"{record.get('prompt', '')}\n{answer}".strip()


def ngram_hashes(text: str, n: int) -> set[str]:
    toks = _norm(text).split()
    if len(toks) < n:
        return set()
    return {sha256_text(" ".join(toks[i:i+n])) for i in range(len(toks) - n + 1)}


def build_protected_manifest(texts: Iterable[str], ngram_size: int, manifest_id: str) -> dict[str, Any]:
    ngrams: set[str] = set()
    short: set[str] = set()
    count = 0
    for text in texts:
        norm = _norm(text)
        if not norm:
            continue
        count += 1
        toks = norm.split()
        if len(toks) < ngram_size:
            short.add(sha256_text(norm))
        else:
            ngrams.update(ngram_hashes(norm, ngram_size))
    payload = {
        "schema_version": 1,
        "manifest_id": manifest_id,
        "ngram_size": ngram_size,
        "record_count": count,
        "ngram_hashes": sorted(ngrams),
        "short_hashes": sorted(short),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["manifest_sha256"] = sha256_text(canonical)
    return payload


def validate_manifest(manifest: dict[str, Any]) -> tuple[bool, str]:
    required = {"schema_version", "manifest_id", "ngram_size", "record_count", "ngram_hashes", "short_hashes", "manifest_sha256"}
    missing = required - set(manifest)
    if missing:
        return False, f"protected_manifest_missing:{','.join(sorted(missing))}"
    payload = {k: manifest[k] for k in manifest if k != "manifest_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if sha256_text(canonical) != manifest["manifest_sha256"]:
        return False, "protected_manifest_digest_mismatch"
    return True, "ok"


def protected_overlap(text: str, manifest: dict[str, Any]) -> dict[str, Any]:
    n = int(manifest["ngram_size"])
    norm = _norm(text)
    toks = norm.split()
    if not norm:
        return {"matched": False, "match_count": 0, "candidate_unit_count": 0}
    if len(toks) < n:
        matched = sha256_text(norm) in set(manifest.get("short_hashes", []))
        return {"matched": matched, "match_count": int(matched), "candidate_unit_count": 1}
    units = ngram_hashes(norm, n)
    protected = set(manifest.get("ngram_hashes", []))
    matches = units & protected
    return {"matched": bool(matches), "match_count": len(matches), "candidate_unit_count": len(units)}


@dataclass
class Decision:
    decision: str
    reasons: list[str]
    metrics: dict[str, Any]


def _missing(record: dict[str, Any], path: tuple[str, ...]) -> bool:
    cur: Any = record
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return True
        cur = cur[key]
    return cur is None or cur == ""


def assess_record(record: dict[str, Any], policy: dict[str, Any], protected_manifest: dict[str, Any]) -> Decision:
    """Return ADMIT / QUARANTINE / DENY with fail-closed reasons.

    DENY is reserved for hard policy violations (protected data, contamination,
    disallowed legal/source state, malformed identity). QUARANTINE means evidence
    is incomplete or the sample is not currently in the configured learning zone.
    """
    reasons: list[str] = []
    metrics: dict[str, Any] = {}

    manifest_ok, manifest_reason = validate_manifest(protected_manifest)
    if not manifest_ok:
        return Decision(DENY, [manifest_reason], metrics)

    required_paths = [
        ("record_id",), ("prompt",), ("source", "id"), ("source", "revision"),
        ("source", "immutable_revision"), ("source", "content_sha256"),
        ("source", "admission"), ("source", "license_status"),
        ("source", "provenance_status"), ("dedup", "is_canonical"),
        ("contamination", "holdout_scan_completed"), ("contamination", "protected_eval_hits"),
        ("baseline", "attempts"), ("baseline", "successes"), ("verifiers",),
    ]
    missing = [".".join(p) for p in required_paths if _missing(record, p)]
    if missing:
        return Decision(DENY, [f"missing_required:{','.join(missing)}"], metrics)

    source = record["source"]
    if source.get("immutable_revision") is not True:
        reasons.append("source_revision_not_immutable")
    if not _SHA256_RE.fullmatch(str(source.get("content_sha256", ""))):
        reasons.append("invalid_source_content_sha256")
    if source.get("admission") not in set(policy["allowed_source_admissions"]):
        reasons.append("source_admission_not_allowed")
    if source.get("license_status") not in set(policy["allowed_license_statuses"]):
        reasons.append("license_not_cleared")
    if source.get("provenance_status") not in set(policy["allowed_provenance_statuses"]):
        reasons.append("provenance_not_cleared")
    if reasons:
        return Decision(DENY, reasons, metrics)

    if record.get("protected_eval") is True:
        return Decision(DENY, ["protected_eval_record"], metrics)

    cont = record["contamination"]
    if cont.get("holdout_scan_completed") is not True:
        return Decision(DENY, ["holdout_scan_not_completed"], metrics)
    if int(cont.get("protected_eval_hits", 0)) != 0:
        return Decision(DENY, ["protected_eval_hit"], metrics)

    overlap = protected_overlap(content_text(record), protected_manifest)
    metrics["protected_overlap"] = overlap
    if overlap["matched"]:
        return Decision(DENY, ["protected_manifest_overlap"], metrics)

    dedup = record["dedup"]
    if dedup.get("is_canonical") is not True:
        return Decision(QUARANTINE, ["noncanonical_duplicate"], metrics)
    sem = dedup.get("semantic_duplicate_score")
    if sem is None:
        return Decision(QUARANTINE, ["missing_semantic_duplicate_score"], metrics)
    if not 0 <= float(sem) <= 1:
        return Decision(DENY, ["invalid_semantic_duplicate_score"], metrics)
    metrics["semantic_duplicate_score"] = float(sem)
    if float(sem) > float(policy["contamination"]["max_semantic_duplicate_score"]):
        return Decision(QUARANTINE, ["semantic_near_duplicate"], metrics)

    verifiers = record.get("verifiers")
    if not isinstance(verifiers, list) or not verifiers:
        return Decision(QUARANTINE, ["missing_verifier_evidence"], metrics)

    hard_types = set(policy["hard_verifier_types"])
    hard_passes = 0
    verifier_reasons: list[str] = []
    for idx, verifier in enumerate(verifiers):
        if not isinstance(verifier, dict):
            verifier_reasons.append(f"verifier_{idx}_malformed")
            continue
        typ = verifier.get("type")
        if verifier.get("passed") is False:
            verifier_reasons.append(f"verifier_{idx}_failed")
        if typ in hard_types and verifier.get("passed") is True:
            if not verifier.get("target_failure_modes"):
                verifier_reasons.append(f"verifier_{idx}_missing_failure_modes")
            elif verifier.get("fault_injection_passed") is not True:
                verifier_reasons.append(f"verifier_{idx}_not_fault_tested")
            elif verifier.get("independent_observation") is not True:
                verifier_reasons.append(f"verifier_{idx}_not_independent_observation")
            else:
                hard_passes += 1
    metrics["hard_verifier_passes"] = hard_passes
    if verifier_reasons:
        return Decision(QUARANTINE, verifier_reasons, metrics)
    if hard_passes < int(policy["verifier"]["min_hard_verifier_passes"]):
        return Decision(QUARANTINE, ["no_qualified_hard_verifier"], metrics)

    baseline = record["baseline"]
    attempts = int(baseline["attempts"])
    successes = int(baseline["successes"])
    if attempts <= 0 or successes < 0 or successes > attempts:
        return Decision(DENY, ["invalid_baseline_counts"], metrics)
    if attempts < int(policy["learnability"]["min_attempts"]):
        return Decision(QUARANTINE, ["insufficient_baseline_attempts"], metrics)
    rate = successes / attempts
    metrics["student_success_rate"] = rate
    lo = float(policy["learnability"]["min_student_success_rate"])
    hi = float(policy["learnability"]["max_student_success_rate"])
    if rate < lo:
        return Decision(QUARANTINE, ["too_hard_or_unstable_for_current_stage"], metrics)
    if rate > hi:
        return Decision(QUARANTINE, ["already_mastered_low_information_gain"], metrics)

    lane = str(record.get("language_lane", "other"))
    if record.get("synthetic") is True and lane in set(policy["language_quality"]["lanes_requiring_audit"]):
        audit = record.get("language_quality_audit", {})
        if audit.get("passed") is not True or not audit.get("auditor_class"):
            return Decision(QUARANTINE, ["language_quality_audit_required"], metrics)

    return Decision(ADMIT, ["all_required_gates_passed"], metrics)


def _load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def cmd_build_manifest(args: argparse.Namespace) -> int:
    rows = _load_jsonl(args.input)
    texts = []
    for row in rows:
        parts = []
        for field in args.text_fields:
            value = row.get(field, "")
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            parts.append(value)
        texts.append("\n".join(parts))
    manifest = build_protected_manifest(texts, args.ngram_size, args.manifest_id)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_id": manifest["manifest_id"], "records": manifest["record_count"], "sha256": manifest["manifest_sha256"]}))
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    policy = _load_json(args.policy)
    manifest = _load_json(args.protected_manifest)
    buckets: dict[str, list[dict[str, Any]]] = {ADMIT: [], QUARANTINE: [], DENY: []}
    for record in _load_jsonl(args.input):
        decision = assess_record(record, policy, manifest)
        out = dict(record)
        out["training_signal_decision"] = asdict(decision)
        buckets[decision.decision].append(out)
    _write_jsonl(args.admitted, buckets[ADMIT])
    _write_jsonl(args.quarantine, buckets[QUARANTINE])
    _write_jsonl(args.denied, buckets[DENY])
    print(json.dumps({"admit": len(buckets[ADMIT]), "quarantine": len(buckets[QUARANTINE]), "deny": len(buckets[DENY])}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    m = sub.add_parser("build-protected-manifest", help="hash protected holdout text; output contains hashes, not raw answers")
    m.add_argument("--input", type=pathlib.Path, required=True)
    m.add_argument("--output", type=pathlib.Path, required=True)
    m.add_argument("--manifest-id", required=True)
    m.add_argument("--ngram-size", type=int, default=8)
    m.add_argument("--text-fields", nargs="+", default=["prompt", "answer"])
    m.set_defaults(func=cmd_build_manifest)

    g = sub.add_parser("gate", help="admit/quarantine/deny candidate training records")
    g.add_argument("--policy", type=pathlib.Path, required=True)
    g.add_argument("--protected-manifest", type=pathlib.Path, required=True)
    g.add_argument("--input", type=pathlib.Path, required=True)
    g.add_argument("--admitted", type=pathlib.Path, required=True)
    g.add_argument("--quarantine", type=pathlib.Path, required=True)
    g.add_argument("--denied", type=pathlib.Path, required=True)
    g.set_defaults(func=cmd_gate)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
