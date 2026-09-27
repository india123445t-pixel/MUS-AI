#!/usr/bin/env python3
"""AQLEVON Agent 02 — future-only sealed evaluation custody gate.

This module never generates or reconstructs sealed evaluation material. It only
verifies that FUTURE private files match hashes frozen in a preregistration that
existed before score visibility. The legacy W05 identities are explicitly denied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any

HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
RECORD_KIND = "AQLEVON_FUTURE_SEALED_CUSTODY_PREREGISTRATION_V1"
VERIFY_KIND = "AQLEVON_FUTURE_SEALED_CUSTODY_VERIFICATION_V1"
FUTURE_SCOPE = "FUTURE_CANDIDATE_ONLY"
NO_SCORES = "NO_FUTURE_CANDIDATE_SCORES_OBSERVED"

# Public cryptographic identities only. The corresponding legacy private bytes
# are neither embedded nor reconstructed here.
LEGACY_W05 = {
    "sealed_pack_sha256": "b30b85c59784f9a5b553f4182f8cdc8462c2880dddaadd528ed37ac3aee683bb",
    "sealed_commitment_sha256": "7e0463ddf6068fe66d85b5798b4f8037489c99dcd452376e8144dff0a122f4e5",
    "secret_file_sha256": "e61883f5f794ed6e82bb29b5718b09334ed2f29fa60bc5c1b7f7c6e1e86a8db6",
    "sealed_plaintext_file_sha256": "ce17cdee667f2a53adf38000f2ace652cc1b4659187640a49f04858dceadbd0e",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CustodyGateError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, float):
        raise CustodyGateError("direct_float_forbidden")
    if isinstance(value, str):
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if value is None or type(value) in (bool, int):
        return json.dumps(value, separators=(",", ":")).encode("utf-8")
    if isinstance(value, list):
        return b"[" + b",".join(canonical_bytes(v) for v in value) + b"]"
    if isinstance(value, dict):
        if not all(isinstance(k, str) and k and all(ord(c) < 128 for c in k) for k in value):
            raise CustodyGateError("invalid_authoritative_key")
        parts = []
        for k in sorted(value, key=lambda s: s.encode("ascii")):
            parts.append(canonical_bytes(k) + b":" + canonical_bytes(value[k]))
        return b"{" + b",".join(parts) + b"}"
    raise CustodyGateError(f"unsupported_type:{type(value).__name__}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def self_digest(obj: dict[str, Any], field: str) -> str:
    return sha256_bytes(canonical_bytes({k: v for k, v in obj.items() if k != field}))


def sha256_file(path: pathlib.Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise CustodyGateError("private_material_not_regular_file")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CustodyGateError("anchored_at_utc_invalid")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CustodyGateError("anchored_at_utc_invalid") from exc
    if dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise CustodyGateError("anchored_at_utc_not_utc")
    return dt


def seal_preregistration(body: dict[str, Any]) -> dict[str, Any]:
    record = dict(body)
    record["schema_version"] = 1
    record["record_kind"] = RECORD_KIND
    record["hash_profile"] = HASH_PROFILE
    record["record_sha256"] = self_digest(record, "record_sha256")
    return record


def validate_preregistration(record: Any) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version", "record_kind", "hash_profile", "scope",
        "score_visibility_at_registration", "sealed_pack_sha256",
        "sealed_commitment_sha256", "secret_file_sha256",
        "sealed_plaintext_file_sha256", "anchor_kind", "immutable_reference",
        "anchored_at_utc", "record_sha256",
    }
    if not isinstance(record, dict) or set(record) != required:
        return ["preregistration_schema"]
    if record["schema_version"] != 1 or record["record_kind"] != RECORD_KIND:
        errors.append("preregistration_identity")
    if record["hash_profile"] != HASH_PROFILE:
        errors.append("hash_profile")
    if record["scope"] != FUTURE_SCOPE:
        errors.append("future_scope_required")
    if record["score_visibility_at_registration"] != NO_SCORES:
        errors.append("score_visibility_boundary")
    for field in (
        "sealed_pack_sha256", "sealed_commitment_sha256", "secret_file_sha256",
        "sealed_plaintext_file_sha256", "record_sha256",
    ):
        if not _valid_sha(record.get(field)):
            errors.append(f"invalid_sha256:{field}")
    if record.get("record_sha256") != self_digest(record, "record_sha256"):
        errors.append("preregistration_self_digest")
    if record.get("anchor_kind") not in {"git_commit", "immutable_object", "append_only_ledger"}:
        errors.append("anchor_kind")
    if not isinstance(record.get("immutable_reference"), str) or not record["immutable_reference"].strip():
        errors.append("immutable_reference")
    try:
        _parse_utc(record.get("anchored_at_utc"))
    except CustodyGateError as exc:
        errors.append(str(exc))
    for field, legacy_value in LEGACY_W05.items():
        if record.get(field) == legacy_value:
            errors.append(f"legacy_w05_identity_forbidden:{field}")
    return sorted(set(errors))


def verify_future_material(record: dict[str, Any], secret_file: pathlib.Path, sealed_plaintext_file: pathlib.Path) -> dict[str, Any]:
    errors = validate_preregistration(record)
    if errors:
        raise CustodyGateError("INVALID_PREREGISTRATION:" + ";".join(errors))

    secret_sha = sha256_file(secret_file)
    plaintext_sha = sha256_file(sealed_plaintext_file)
    if secret_sha != record["secret_file_sha256"]:
        raise CustodyGateError("secret_file_sha256_mismatch")
    if plaintext_sha != record["sealed_plaintext_file_sha256"]:
        raise CustodyGateError("sealed_plaintext_file_sha256_mismatch")

    # Verify the future sealed pack's canonical self-digest without emitting any
    # task bodies, prompts, answers, canaries, or paths.
    try:
        pack = json.loads(sealed_plaintext_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CustodyGateError("sealed_plaintext_not_valid_json") from exc
    if not isinstance(pack, dict) or not _valid_sha(pack.get("pack_sha256")):
        raise CustodyGateError("sealed_pack_missing_self_digest")
    if self_digest(pack, "pack_sha256") != pack["pack_sha256"]:
        raise CustodyGateError("sealed_pack_self_digest_mismatch")
    if pack["pack_sha256"] != record["sealed_pack_sha256"]:
        raise CustodyGateError("sealed_pack_preregistration_mismatch")

    body = {
        "schema_version": 1,
        "verification_kind": VERIFY_KIND,
        "hash_profile": HASH_PROFILE,
        "status": "PASS_FUTURE_MATERIAL_HASH_BOUND",
        "preregistration_sha256": record["record_sha256"],
        "sealed_pack_sha256": record["sealed_pack_sha256"],
        "sealed_commitment_sha256": record["sealed_commitment_sha256"],
        "secret_file_sha256": secret_sha,
        "sealed_plaintext_file_sha256": plaintext_sha,
        "private_content_emitted": False,
        "authoritative_for_legacy_w05": False,
        "authoritative_for_capability_gain": False,
    }
    body["verification_sha256"] = self_digest(body, "verification_sha256")
    return body


def _load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify")
    v.add_argument("--preregistration", type=pathlib.Path, required=True)
    v.add_argument("--secret-file", type=pathlib.Path, required=True)
    v.add_argument("--sealed-plaintext-file", type=pathlib.Path, required=True)

    args = ap.parse_args()
    try:
        result = verify_future_material(
            _load(args.preregistration), args.secret_file, args.sealed_plaintext_file
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
