#!/usr/bin/env python3
"""AQLEVON Agent 02 — future-only sealed evaluation custody/chronology gate.

This module never generates or reconstructs sealed evaluation material. It verifies:
1) a FUTURE preregistration record is byte-for-byte anchored in Git,
2) a FUTURE evaluation-start receipt is byte-for-byte anchored in a later Git commit,
3) the start receipt binds the exact preregistration anchor/hash and candidate identity,
4) private future files match the preregistered hashes and sealed-pack self-digest.

Legacy W05 identities are explicitly denied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any

HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
RECORD_KIND = "AQLEVON_FUTURE_SEALED_CUSTODY_PREREGISTRATION_V2"
START_RECEIPT_KIND = "AQLEVON_FUTURE_EVALUATION_START_RECEIPT_V1"
VERIFY_KIND = "AQLEVON_FUTURE_SEALED_CUSTODY_VERIFICATION_V2"
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
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SAFE_REPO_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[^\x00]+$")


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


def _valid_commit(value: Any) -> bool:
    return isinstance(value, str) and bool(_GIT_COMMIT.fullmatch(value))


def _valid_repo_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and bool(_SAFE_REPO_PATH.fullmatch(value))


def seal_preregistration(body: dict[str, Any]) -> dict[str, Any]:
    record = dict(body)
    record["schema_version"] = 2
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
        "sealed_plaintext_file_sha256", "record_sha256",
    }
    if not isinstance(record, dict) or set(record) != required:
        return ["preregistration_schema"]
    if record["schema_version"] != 2 or record["record_kind"] != RECORD_KIND:
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
    for field, legacy_value in LEGACY_W05.items():
        if record.get(field) == legacy_value:
            errors.append(f"legacy_w05_identity_forbidden:{field}")
    return sorted(set(errors))


def seal_evaluation_start_receipt(body: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(body)
    receipt["schema_version"] = 1
    receipt["receipt_kind"] = START_RECEIPT_KIND
    receipt["hash_profile"] = HASH_PROFILE
    receipt["receipt_sha256"] = self_digest(receipt, "receipt_sha256")
    return receipt


def validate_evaluation_start_receipt(receipt: Any) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version", "receipt_kind", "hash_profile",
        "score_visibility_at_receipt", "evaluation_started",
        "preregistration_sha256", "preregistration_anchor_commit",
        "preregistration_anchor_path", "candidate_manifest_sha256",
        "evaluation_policy_sha256", "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != required:
        return ["evaluation_start_receipt_schema"]
    if receipt["schema_version"] != 1 or receipt["receipt_kind"] != START_RECEIPT_KIND:
        errors.append("evaluation_start_receipt_identity")
    if receipt["hash_profile"] != HASH_PROFILE:
        errors.append("hash_profile")
    if receipt["score_visibility_at_receipt"] != NO_SCORES:
        errors.append("evaluation_start_score_visibility_boundary")
    if receipt["evaluation_started"] is not False:
        errors.append("evaluation_already_started")
    for field in (
        "preregistration_sha256", "candidate_manifest_sha256",
        "evaluation_policy_sha256", "receipt_sha256",
    ):
        if not _valid_sha(receipt.get(field)):
            errors.append(f"invalid_sha256:{field}")
    if not _valid_commit(receipt.get("preregistration_anchor_commit")):
        errors.append("invalid_preregistration_anchor_commit")
    if not _valid_repo_path(receipt.get("preregistration_anchor_path")):
        errors.append("invalid_preregistration_anchor_path")
    if receipt.get("receipt_sha256") != self_digest(receipt, "receipt_sha256"):
        errors.append("evaluation_start_receipt_self_digest")
    return sorted(set(errors))


def _git(repo: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    if repo.is_symlink() or not repo.is_dir():
        raise CustodyGateError("anchor_repo_not_directory")
    cp = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and cp.returncode != 0:
        msg = cp.stderr.decode("utf-8", "replace").strip()
        raise CustodyGateError(f"git_command_failed:{args[0]}:{msg or cp.returncode}")
    return cp


def _require_git_commit(repo: pathlib.Path, commit: str, error_code: str) -> None:
    if not _valid_commit(commit):
        raise CustodyGateError(f"{error_code}_syntax")
    cp = _git(repo, "cat-file", "-e", f"{commit}^{{commit}}", check=False)
    if cp.returncode != 0:
        raise CustodyGateError(error_code)


def _git_file_bytes(repo: pathlib.Path, commit: str, repo_path: str, error_code: str) -> bytes:
    if not _valid_repo_path(repo_path):
        raise CustodyGateError(f"{error_code}_path")
    cp = _git(repo, "show", f"{commit}:{repo_path}", check=False)
    if cp.returncode != 0:
        raise CustodyGateError(error_code)
    return cp.stdout


def _is_strict_ancestor(repo: pathlib.Path, older: str, newer: str) -> bool:
    if older == newer:
        return False
    cp = _git(repo, "merge-base", "--is-ancestor", older, newer, check=False)
    if cp.returncode == 0:
        return True
    if cp.returncode == 1:
        return False
    raise CustodyGateError("git_ancestry_check_failed")


def verify_chronology(
    repo: pathlib.Path,
    preregistration_file: pathlib.Path,
    preregistration_anchor_commit: str,
    preregistration_anchor_path: str,
    evaluation_start_receipt_file: pathlib.Path,
    evaluation_start_anchor_commit: str,
    evaluation_start_anchor_path: str,
    expected_candidate_manifest_sha256: str,
) -> dict[str, Any]:
    _require_git_commit(repo, preregistration_anchor_commit, "preregistration_anchor_not_found")
    _require_git_commit(repo, evaluation_start_anchor_commit, "evaluation_start_anchor_not_found")

    prereg_local = preregistration_file.read_bytes()
    prereg_anchored = _git_file_bytes(
        repo, preregistration_anchor_commit, preregistration_anchor_path,
        "preregistration_anchor_content_not_found",
    )
    if prereg_local != prereg_anchored:
        raise CustodyGateError("preregistration_anchor_bytes_mismatch")

    try:
        prereg = json.loads(prereg_local.decode("utf-8"))
    except Exception as exc:
        raise CustodyGateError("preregistration_not_valid_json") from exc
    prereg_errors = validate_preregistration(prereg)
    if prereg_errors:
        raise CustodyGateError("INVALID_PREREGISTRATION:" + ";".join(prereg_errors))

    start_local = evaluation_start_receipt_file.read_bytes()
    start_anchored = _git_file_bytes(
        repo, evaluation_start_anchor_commit, evaluation_start_anchor_path,
        "evaluation_start_anchor_content_not_found",
    )
    if start_local != start_anchored:
        raise CustodyGateError("evaluation_start_anchor_bytes_mismatch")

    try:
        start = json.loads(start_local.decode("utf-8"))
    except Exception as exc:
        raise CustodyGateError("evaluation_start_receipt_not_valid_json") from exc
    start_errors = validate_evaluation_start_receipt(start)
    if start_errors:
        raise CustodyGateError("INVALID_EVALUATION_START_RECEIPT:" + ";".join(start_errors))

    if start["preregistration_sha256"] != prereg["record_sha256"]:
        raise CustodyGateError("evaluation_start_preregistration_hash_mismatch")
    if start["preregistration_anchor_commit"] != preregistration_anchor_commit:
        raise CustodyGateError("evaluation_start_preregistration_anchor_commit_mismatch")
    if start["preregistration_anchor_path"] != preregistration_anchor_path:
        raise CustodyGateError("evaluation_start_preregistration_anchor_path_mismatch")
    if not _valid_sha(expected_candidate_manifest_sha256):
        raise CustodyGateError("expected_candidate_manifest_sha256_invalid")
    if start["candidate_manifest_sha256"] != expected_candidate_manifest_sha256:
        raise CustodyGateError("evaluation_start_candidate_manifest_mismatch")
    if not _is_strict_ancestor(repo, preregistration_anchor_commit, evaluation_start_anchor_commit):
        raise CustodyGateError("preregistration_anchor_not_before_evaluation_start")

    body = {
        "schema_version": 1,
        "chronology_kind": "AQLEVON_FUTURE_EVALUATION_CHRONOLOGY_PROOF_V1",
        "status": "PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START",
        "preregistration_sha256": prereg["record_sha256"],
        "preregistration_anchor_commit": preregistration_anchor_commit,
        "preregistration_anchor_path": preregistration_anchor_path,
        "evaluation_start_receipt_sha256": start["receipt_sha256"],
        "evaluation_start_anchor_commit": evaluation_start_anchor_commit,
        "evaluation_start_anchor_path": evaluation_start_anchor_path,
        "candidate_manifest_sha256": expected_candidate_manifest_sha256,
        "chronology_authority": "GIT_BYTE_ANCHOR_PLUS_STRICT_ANCESTRY",
        "caller_supplied_timestamp_authoritative": False,
    }
    body["chronology_sha256"] = self_digest(body, "chronology_sha256")
    return {"preregistration": prereg, "evaluation_start_receipt": start, "proof": body}


def verify_future_material(
    record: dict[str, Any],
    secret_file: pathlib.Path,
    sealed_plaintext_file: pathlib.Path,
    chronology_proof: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_preregistration(record)
    if errors:
        raise CustodyGateError("INVALID_PREREGISTRATION:" + ";".join(errors))
    if chronology_proof.get("status") != "PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START":
        raise CustodyGateError("chronology_proof_required")
    if chronology_proof.get("preregistration_sha256") != record["record_sha256"]:
        raise CustodyGateError("chronology_preregistration_hash_mismatch")

    secret_sha = sha256_file(secret_file)
    plaintext_sha = sha256_file(sealed_plaintext_file)
    if secret_sha != record["secret_file_sha256"]:
        raise CustodyGateError("secret_file_sha256_mismatch")
    if plaintext_sha != record["sealed_plaintext_file_sha256"]:
        raise CustodyGateError("sealed_plaintext_file_sha256_mismatch")

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
        "schema_version": 2,
        "verification_kind": VERIFY_KIND,
        "hash_profile": HASH_PROFILE,
        "status": "PASS_FUTURE_MATERIAL_HASH_BOUND_AND_CHRONOLOGY_PROVEN",
        "preregistration_sha256": record["record_sha256"],
        "chronology_sha256": chronology_proof["chronology_sha256"],
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
    v.add_argument("--repo", type=pathlib.Path, required=True)
    v.add_argument("--preregistration", type=pathlib.Path, required=True)
    v.add_argument("--preregistration-anchor-commit", required=True)
    v.add_argument("--preregistration-anchor-path", required=True)
    v.add_argument("--evaluation-start-receipt", type=pathlib.Path, required=True)
    v.add_argument("--evaluation-start-anchor-commit", required=True)
    v.add_argument("--evaluation-start-anchor-path", required=True)
    v.add_argument("--candidate-manifest-sha256", required=True)
    v.add_argument("--secret-file", type=pathlib.Path, required=True)
    v.add_argument("--sealed-plaintext-file", type=pathlib.Path, required=True)

    args = ap.parse_args()
    try:
        chronology = verify_chronology(
            args.repo,
            args.preregistration,
            args.preregistration_anchor_commit,
            args.preregistration_anchor_path,
            args.evaluation_start_receipt,
            args.evaluation_start_anchor_commit,
            args.evaluation_start_anchor_path,
            args.candidate_manifest_sha256,
        )
        result = verify_future_material(
            chronology["preregistration"],
            args.secret_file,
            args.sealed_plaintext_file,
            chronology["proof"],
        )
        print(json.dumps({"chronology": chronology["proof"], "material": result}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
