#!/usr/bin/env python3
"""AQLEVON Worker 02 — deterministic Training Shard Manifest V1 producer.

Consumes the three fail-closed admission outputs from training_signal_gate_v1 and
emits a deterministic canonical training shard plus an immutable, self-hashed
manifest. It exports identities/evidence only; it never consumes Worker-05
private release-evaluation prompts or answers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from typing import Any
from dataclasses import asdict

import training_signal_gate_v1 as gate_module
from training_signal_gate_v1 import (
    ADMIT,
    DENY,
    QUARANTINE,
    assess_record,
    canonical_json_bytes,
    record_content_sha256,
    source_registry_sha256,
    validate_manifest as validate_protected_manifest,
    validate_policy,
    validate_registry,
)

MANIFEST_KIND = "AQLEVON_TRAINING_SHARD_MANIFEST_V1"
SCHEMA_VERSION = 1
RECORD_DIGEST_SCHEME = "AQLEVON_SORTED_RECORD_CONTENT_SHA256_LIST_V1"
DECISION_LOG_SCHEME = "AQLEVON_ADMISSION_DECISION_LOG_V1"
MANIFEST_ID_SCHEME = "AQLEVON_TRAINING_SHARD_IDENTITY_V1"
SHARD_ROW_KIND = "AQLEVON_TRAINING_SHARD_ROW_V1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DECISIONS = (ADMIT, QUARANTINE, DENY)


class ManifestError(ValueError):
    """Fail-closed manifest construction/validation error."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: pathlib.Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _require_sha256(value: Any, name: str) -> str:
    if not _valid_sha256(value):
        raise ManifestError(f"invalid_sha256:{name}")
    return value


def _load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ManifestError(f"jsonl_row_not_object:{path.name}:{line_no}")
        rows.append(value)
    return rows


def _canonical_json_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _decision_of(row: dict[str, Any]) -> str:
    evidence = row.get("training_signal_decision")
    if not isinstance(evidence, dict):
        raise ManifestError("missing_training_signal_decision")
    decision = evidence.get("decision")
    if decision not in _DECISIONS:
        raise ManifestError("invalid_training_signal_decision")
    reasons = evidence.get("reasons")
    metrics = evidence.get("metrics")
    if not isinstance(reasons, list) or not all(isinstance(x, str) and x for x in reasons):
        raise ManifestError("invalid_training_signal_decision_reasons")
    if not isinstance(metrics, dict):
        raise ManifestError("invalid_training_signal_decision_metrics")
    return decision


def _validate_partition(
    rows: list[dict[str, Any]],
    expected: str,
    policy: dict[str, Any],
    protected_manifest: dict[str, Any],
    registry: dict[str, Any],
) -> None:
    for row in rows:
        actual = _decision_of(row)
        if actual != expected:
            raise ManifestError(f"decision_partition_mismatch:{expected}:{actual}")
        replay = asdict(assess_record(row, policy, protected_manifest, registry))
        if replay != row.get("training_signal_decision"):
            raise ManifestError(f"admission_replay_mismatch:{expected}")


def _decision_log_digest(
    admitted: list[dict[str, Any]],
    quarantined: list[dict[str, Any]],
    denied: list[dict[str, Any]],
) -> tuple[str, dict[str, int]]:
    partitions = {ADMIT: admitted, QUARANTINE: quarantined, DENY: denied}
    event_hashes: list[str] = []
    counts: dict[str, int] = {}
    seen_record_ids: set[str] = set()
    for decision in _DECISIONS:
        rows = partitions[decision]
        counts[decision] = len(rows)
        for row in rows:
            rid = row.get("record_id")
            if isinstance(rid, str) and rid:
                if rid in seen_record_ids:
                    raise ManifestError(f"duplicate_record_id_across_decisions:{rid}")
                seen_record_ids.add(rid)
            event_hashes.append(_canonical_json_sha256(row))
    payload = {
        "scheme": DECISION_LOG_SCHEME,
        "decision_counts": counts,
        "decision_event_sha256": sorted(event_hashes),
    }
    return _canonical_json_sha256(payload), counts


def _validate_admitted_rows(
    rows: list[dict[str, Any]],
    policy: dict[str, Any],
    registry: dict[str, Any],
    registry_sha256: str,
) -> tuple[list[str], list[dict[str, str]], list[str]]:
    if not rows:
        raise ManifestError("empty_admitted_shard")

    record_hashes: list[str] = []
    source_revisions: set[tuple[str, str, str]] = set()
    language_receipts: set[str] = set()
    seen_record_hashes: set[str] = set()
    seen_record_ids: set[str] = set()
    audit_lanes = set(policy["language_quality"]["lanes_requiring_audit"])
    registry_ids = {entry["id"] for entry in registry["sources"]}
    require_synth_only = policy["language_quality"].get("require_for_synthetic_only") is True

    for row in rows:
        if _decision_of(row) != ADMIT:
            raise ManifestError("non_admit_row_in_admitted_partition")
        rid = row.get("record_id")
        if not isinstance(rid, str) or not rid:
            raise ManifestError("admitted_row_missing_record_id")
        if rid in seen_record_ids:
            raise ManifestError(f"duplicate_admitted_record_id:{rid}")
        seen_record_ids.add(rid)

        claimed = _require_sha256(row.get("record_content_sha256"), "record_content_sha256")
        try:
            recomputed = record_content_sha256(row)
        except (TypeError, ValueError, KeyError) as exc:
            raise ManifestError("admitted_row_content_uncanonicalizable") from exc
        if claimed != recomputed:
            raise ManifestError(f"admitted_record_content_hash_mismatch:{rid}")
        if claimed in seen_record_hashes:
            raise ManifestError(f"duplicate_admitted_record_content:{claimed}")
        seen_record_hashes.add(claimed)
        record_hashes.append(claimed)

        source = row.get("source")
        if not isinstance(source, dict):
            raise ManifestError(f"admitted_source_not_object:{rid}")
        if source.get("immutable_revision") is not True:
            raise ManifestError(f"admitted_source_revision_not_immutable:{rid}")
        source_id = source.get("id")
        revision = source.get("revision")
        if not isinstance(source_id, str) or not source_id:
            raise ManifestError(f"admitted_source_id_invalid:{rid}")
        if source_id not in registry_ids:
            raise ManifestError(f"admitted_source_not_in_registry:{rid}")
        if not isinstance(revision, str) or not revision:
            raise ManifestError(f"admitted_source_revision_invalid:{rid}")
        source_artifact_sha = _require_sha256(source.get("content_sha256"), "source.content_sha256")
        if source.get("registry_sha256") != registry_sha256:
            raise ManifestError(f"admitted_source_registry_hash_mismatch:{rid}")
        source_revisions.add((source_id, revision, source_artifact_sha))

        lane = row.get("language_lane", "other")
        if not isinstance(lane, str):
            raise ManifestError(f"invalid_language_lane:{rid}")
        audit_required = lane in audit_lanes and (not require_synth_only or row.get("synthetic") is True)
        audit = row.get("language_quality_audit")
        if audit_required:
            if not isinstance(audit, dict) or audit.get("passed") is not True:
                raise ManifestError(f"required_language_audit_missing:{rid}")
            receipt = _require_sha256(audit.get("receipt_sha256"), "language_quality_audit.receipt_sha256")
            language_receipts.add(receipt)
        elif isinstance(audit, dict) and audit.get("receipt_sha256") is not None:
            language_receipts.add(_require_sha256(audit.get("receipt_sha256"), "language_quality_audit.receipt_sha256"))

    created_from = [
        {"source_id": sid, "revision": rev, "source_artifact_sha256": sha}
        for sid, rev, sha in sorted(source_revisions)
    ]
    return sorted(record_hashes), created_from, sorted(language_receipts)


def _record_content_digest(record_hashes: list[str]) -> str:
    for value in record_hashes:
        _require_sha256(value, "admitted_record_content_sha256")
    payload = {"scheme": RECORD_DIGEST_SCHEME, "record_content_sha256": sorted(record_hashes)}
    return _canonical_json_sha256(payload)


def _training_row_projection(row: dict[str, Any]) -> dict[str, Any]:
    """Project an admitted gate row into the only plaintext allowed in the training shard.

    Decision evidence, verifier traces, contamination details, language-audit bodies, and
    arbitrary extra metadata are intentionally excluded. Their identities are bound by the
    manifest/decision-log hashes instead of being copied into the trainable artifact.
    """
    source = row.get("source")
    if not isinstance(source, dict):
        raise ManifestError("shard_projection_source_not_object")
    if "answer" in row:
        answer = row["answer"]
    elif "response" in row:
        answer = row["response"]
    else:
        raise ManifestError("shard_projection_missing_answer")
    return {
        "row_kind": SHARD_ROW_KIND,
        "record_id": row["record_id"],
        "prompt": row["prompt"],
        "answer": answer,
        "record_content_sha256": row["record_content_sha256"],
        "source": {
            "id": source["id"],
            "revision": source["revision"],
            "content_sha256": source["content_sha256"],
        },
        "language_lane": row.get("language_lane", "other"),
        "synthetic": row.get("synthetic") is True,
    }


def _canonical_shard_bytes(admitted: list[dict[str, Any]]) -> bytes:
    projected = [_training_row_projection(row) for row in admitted]
    ordered = sorted(projected, key=lambda r: (r["record_content_sha256"], r["record_id"]))
    return b"".join(canonical_json_bytes(row) + b"\n" for row in ordered)


def _manifest_identity_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    # Bind every semantic manifest field, not a hand-maintained subset. This makes
    # manifest_id robust to future accidental omission of a required identity field.
    payload = {k: manifest[k] for k in manifest if k not in {"manifest_id", "manifest_sha256"}}
    return {"scheme": MANIFEST_ID_SCHEME, "manifest": payload}


def _manifest_id(manifest: dict[str, Any]) -> str:
    return f"aqlevon-training-shard-v1:{_canonical_json_sha256(_manifest_identity_payload(manifest))}"


def build_training_shard_manifest(
    *,
    admitted: list[dict[str, Any]],
    quarantined: list[dict[str, Any]],
    denied: list[dict[str, Any]],
    policy: dict[str, Any],
    registry: dict[str, Any],
    protected_contamination_manifest: dict[str, Any],
    admission_gate_code: bytes,
    provenance_license_evidence_bundle: Any,
) -> tuple[dict[str, Any], bytes]:
    ok, reason = validate_policy(policy)
    if not ok:
        raise ManifestError(f"invalid_admission_policy:{reason}")
    ok, reason = validate_registry(registry)
    if not ok:
        raise ManifestError(f"invalid_source_registry:{reason}")
    ok, reason = validate_protected_manifest(protected_contamination_manifest)
    if not ok:
        raise ManifestError(f"invalid_protected_contamination_manifest:{reason}")

    local_gate_code = pathlib.Path(gate_module.__file__).read_bytes()
    if _sha256_bytes(admission_gate_code) != _sha256_bytes(local_gate_code):
        raise ManifestError("admission_gate_code_does_not_match_executed_gate")

    registry_sha = source_registry_sha256(registry)
    record_hashes, created_from, language_receipts = _validate_admitted_rows(
        admitted, policy, registry, registry_sha
    )

    _validate_partition(admitted, ADMIT, policy, protected_contamination_manifest, registry)
    _validate_partition(quarantined, QUARANTINE, policy, protected_contamination_manifest, registry)
    _validate_partition(denied, DENY, policy, protected_contamination_manifest, registry)

    decision_log_sha, decision_counts = _decision_log_digest(admitted, quarantined, denied)
    if decision_counts[ADMIT] != len(admitted):
        raise ManifestError("decision_count_admit_mismatch")

    receipts: list[str] = []  # P1 gate uses the validated protected manifest directly; it emits no separate scan receipt.
    protected_manifest_sha = _require_sha256(
        protected_contamination_manifest.get("manifest_sha256"),
        "protected_training_contamination_manifest_sha256",
    )

    shard_bytes = _canonical_shard_bytes(admitted)
    shard_sha = _sha256_bytes(shard_bytes)
    record_digest = _record_content_digest(record_hashes)

    policy_id = policy.get("policy_id")
    if not isinstance(policy_id, str) or not policy_id:
        raise ManifestError("admission_policy_id_missing")
    admission_policy_sha = _canonical_json_sha256(policy)
    gate_code_sha = _sha256_bytes(admission_gate_code)
    if not isinstance(provenance_license_evidence_bundle, dict) or not provenance_license_evidence_bundle:
        raise ManifestError("invalid_provenance_license_evidence_bundle")
    provenance_sha = _canonical_json_sha256(provenance_license_evidence_bundle)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "manifest_id": "",
        "admission_policy_id": policy_id,
        "admission_policy_sha256": admission_policy_sha,
        "source_registry_snapshot_sha256": registry_sha,
        "protected_training_contamination_manifest_sha256": protected_manifest_sha,
        "protected_training_contamination_receipt_sha256": receipts,
        "admission_gate_code_sha256": gate_code_sha,
        "shard_file_sha256": shard_sha,
        "byte_size": len(shard_bytes),
        "row_count": len(admitted),
        "admitted_record_content_digest_scheme": RECORD_DIGEST_SCHEME,
        "admitted_record_content_digest_sha256": record_digest,
        "decision_log_scheme": DECISION_LOG_SCHEME,
        "decision_log_sha256": decision_log_sha,
        "decision_counts": decision_counts,
        "provenance_license_evidence_bundle_sha256": provenance_sha,
        "language_audit_receipt_sha256": language_receipts,
        "created_from": created_from,
    }
    manifest["manifest_id"] = _manifest_id(manifest)
    manifest["manifest_sha256"] = _canonical_json_sha256(manifest)

    ok, reason = validate_training_shard_manifest(manifest)
    if not ok:
        raise ManifestError(f"internal_manifest_validation_failed:{reason}")
    return manifest, shard_bytes


def validate_training_shard_manifest(manifest: Any) -> tuple[bool, str]:
    if not isinstance(manifest, dict):
        return False, "manifest_not_object"
    required = {
        "schema_version", "manifest_kind", "manifest_id", "admission_policy_id",
        "admission_policy_sha256", "source_registry_snapshot_sha256",
        "protected_training_contamination_manifest_sha256",
        "protected_training_contamination_receipt_sha256", "admission_gate_code_sha256",
        "shard_file_sha256", "byte_size", "row_count",
        "admitted_record_content_digest_scheme", "admitted_record_content_digest_sha256",
        "decision_log_scheme", "decision_log_sha256", "decision_counts",
        "provenance_license_evidence_bundle_sha256", "language_audit_receipt_sha256",
        "created_from", "manifest_sha256",
    }
    missing = sorted(required - set(manifest))
    if missing:
        return False, "manifest_missing:" + ",".join(missing)
    extra = sorted(set(manifest) - required)
    if extra:
        return False, "manifest_extra:" + ",".join(extra)
    if manifest["schema_version"] != SCHEMA_VERSION or type(manifest["schema_version"]) is not int:
        return False, "invalid_schema_version"
    if manifest["manifest_kind"] != MANIFEST_KIND:
        return False, "invalid_manifest_kind"
    if not isinstance(manifest["manifest_id"], str) or not manifest["manifest_id"].startswith("aqlevon-training-shard-v1:"):
        return False, "invalid_manifest_id"
    if not isinstance(manifest["admission_policy_id"], str) or not manifest["admission_policy_id"]:
        return False, "invalid_admission_policy_id"
    for name in (
        "admission_policy_sha256", "source_registry_snapshot_sha256", "admission_gate_code_sha256",
        "shard_file_sha256", "admitted_record_content_digest_sha256", "decision_log_sha256",
        "provenance_license_evidence_bundle_sha256", "manifest_sha256",
    ):
        if not _valid_sha256(manifest[name]):
            return False, f"invalid_sha256:{name}"
    if type(manifest["byte_size"]) is not int or manifest["byte_size"] <= 0:
        return False, "invalid_byte_size"
    if type(manifest["row_count"]) is not int or manifest["row_count"] <= 0:
        return False, "invalid_row_count"
    if manifest["admitted_record_content_digest_scheme"] != RECORD_DIGEST_SCHEME:
        return False, "invalid_record_digest_scheme"
    if manifest["decision_log_scheme"] != DECISION_LOG_SCHEME:
        return False, "invalid_decision_log_scheme"

    counts = manifest["decision_counts"]
    if not isinstance(counts, dict) or set(counts) != set(_DECISIONS):
        return False, "invalid_decision_counts"
    if any(type(counts[d]) is not int or counts[d] < 0 for d in _DECISIONS):
        return False, "invalid_decision_count_values"
    if counts[ADMIT] != manifest["row_count"]:
        return False, "row_count_decision_count_mismatch"

    if not _valid_sha256(manifest["protected_training_contamination_manifest_sha256"]):
        return False, "invalid_contamination_manifest_sha256"
    receipts = manifest["protected_training_contamination_receipt_sha256"]
    if not isinstance(receipts, list) or receipts != sorted(set(receipts)) or not all(_valid_sha256(x) for x in receipts):
        return False, "invalid_contamination_receipt_sha256"

    language = manifest["language_audit_receipt_sha256"]
    if not isinstance(language, list) or language != sorted(set(language)) or not all(_valid_sha256(x) for x in language):
        return False, "invalid_language_audit_receipts"

    created_from = manifest["created_from"]
    if not isinstance(created_from, list) or not created_from:
        return False, "invalid_created_from"
    normalized_sources: list[tuple[str, str, str]] = []
    for entry in created_from:
        if not isinstance(entry, dict) or set(entry) != {"source_id", "revision", "source_artifact_sha256"}:
            return False, "invalid_created_from_entry"
        sid, rev, sha = entry["source_id"], entry["revision"], entry["source_artifact_sha256"]
        if not isinstance(sid, str) or not sid or not isinstance(rev, str) or not rev or not _valid_sha256(sha):
            return False, "invalid_created_from_value"
        normalized_sources.append((sid, rev, sha))
    if normalized_sources != sorted(set(normalized_sources)):
        return False, "created_from_not_sorted_unique"

    try:
        expected_id = _manifest_id(manifest)
        without_self = {k: manifest[k] for k in manifest if k != "manifest_sha256"}
        expected_self = _canonical_json_sha256(without_self)
    except (KeyError, TypeError, ValueError):
        return False, "manifest_uncanonicalizable"
    if manifest["manifest_id"] != expected_id:
        return False, "manifest_id_mismatch"
    if manifest["manifest_sha256"] != expected_self:
        return False, "manifest_digest_mismatch"
    return True, "ok"


def validate_training_shard_artifact(manifest: Any, shard_bytes: bytes) -> tuple[bool, str]:
    """Validate the manifest and the exact shard bytes it claims to identify."""
    ok, reason = validate_training_shard_manifest(manifest)
    if not ok:
        return False, reason
    if not isinstance(shard_bytes, (bytes, bytearray)):
        return False, "shard_not_bytes"
    shard_bytes = bytes(shard_bytes)
    if len(shard_bytes) != manifest["byte_size"]:
        return False, "shard_byte_size_mismatch"
    if _sha256_bytes(shard_bytes) != manifest["shard_file_sha256"]:
        return False, "shard_file_sha256_mismatch"
    try:
        lines = shard_bytes.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False, "shard_not_utf8"
    if len(lines) != manifest["row_count"]:
        return False, "shard_row_count_mismatch"
    rows: list[dict[str, Any]] = []
    record_hashes: list[str] = []
    expected_keys = {"row_kind", "record_id", "prompt", "answer", "record_content_sha256", "source", "language_lane", "synthetic"}
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return False, "shard_invalid_jsonl"
        if not isinstance(row, dict) or set(row) != expected_keys:
            return False, "shard_row_schema_invalid"
        if row.get("row_kind") != SHARD_ROW_KIND:
            return False, "shard_row_kind_invalid"
        source = row.get("source")
        if not isinstance(source, dict) or set(source) != {"id", "revision", "content_sha256"}:
            return False, "shard_source_schema_invalid"
        if not all(isinstance(source.get(k), str) and source[k] for k in ("id", "revision")):
            return False, "shard_source_identity_invalid"
        if not _valid_sha256(source.get("content_sha256")):
            return False, "shard_source_hash_invalid"
        if not isinstance(row.get("record_id"), str) or not row["record_id"] or not isinstance(row.get("prompt"), str):
            return False, "shard_row_identity_invalid"
        if not isinstance(row.get("language_lane"), str) or type(row.get("synthetic")) is not bool:
            return False, "shard_row_metadata_invalid"
        if not _valid_sha256(row.get("record_content_sha256")):
            return False, "shard_record_hash_invalid"
        try:
            recomputed = record_content_sha256({
                "record_id": row["record_id"], "prompt": row["prompt"], "answer": row["answer"]
            })
        except (TypeError, ValueError, KeyError):
            return False, "shard_record_uncanonicalizable"
        if recomputed != row["record_content_sha256"]:
            return False, "shard_record_content_hash_mismatch"
        record_hashes.append(row["record_content_sha256"])
        rows.append(row)
    if len(record_hashes) != len(set(record_hashes)):
        return False, "shard_duplicate_record_content"
    if _record_content_digest(sorted(record_hashes)) != manifest["admitted_record_content_digest_sha256"]:
        return False, "shard_record_content_digest_mismatch"
    canonical = b"".join(canonical_json_bytes(row) + b"\n" for row in sorted(rows, key=lambda r: (r["record_content_sha256"], r["record_id"])))
    if canonical != shard_bytes:
        return False, "shard_not_canonical"
    return True, "ok"


def _write_atomic(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def cmd_build(args: argparse.Namespace) -> int:
    try:
        admitted = _load_jsonl(args.admitted)
        quarantined = _load_jsonl(args.quarantine)
        denied = _load_jsonl(args.denied)
        policy = _load_json(args.policy)
        registry = _load_json(args.source_registry)
        protected = _load_json(args.protected_contamination_manifest)
        provenance = _load_json(args.provenance_license_evidence)
        gate_code = args.admission_gate_code.read_bytes()
        manifest, shard_bytes = build_training_shard_manifest(
            admitted=admitted,
            quarantined=quarantined,
            denied=denied,
            policy=policy,
            registry=registry,
            protected_contamination_manifest=protected,
            admission_gate_code=gate_code,
            provenance_license_evidence_bundle=provenance,
        )
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
        _write_atomic(args.output_shard, shard_bytes)
        _write_atomic(args.output_manifest, manifest_bytes)
    except (OSError, json.JSONDecodeError, ManifestError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "DENY", "reason": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "OK",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "shard_file_sha256": manifest["shard_file_sha256"],
        "row_count": manifest["row_count"],
        "decision_counts": manifest["decision_counts"],
    }, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build deterministic shard + AQLEVON_TRAINING_SHARD_MANIFEST_V1")
    b.add_argument("--admitted", type=pathlib.Path, required=True)
    b.add_argument("--quarantine", type=pathlib.Path, required=True)
    b.add_argument("--denied", type=pathlib.Path, required=True)
    b.add_argument("--policy", type=pathlib.Path, required=True)
    b.add_argument("--source-registry", type=pathlib.Path, required=True)
    b.add_argument("--protected-contamination-manifest", type=pathlib.Path, required=True)
    b.add_argument("--admission-gate-code", type=pathlib.Path, required=True)
    b.add_argument("--provenance-license-evidence", type=pathlib.Path, required=True)
    b.add_argument("--output-shard", type=pathlib.Path, required=True)
    b.add_argument("--output-manifest", type=pathlib.Path, required=True)
    b.set_defaults(func=cmd_build)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())