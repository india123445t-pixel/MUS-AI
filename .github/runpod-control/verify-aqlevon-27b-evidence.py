#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

REQUIRED = (
    "candidate/candidate_manifest.json",
    "candidate/training_receipt.json",
    "candidate/adapter/adapter_model.safetensors",
    "candidate/adapter/adapter_config.json",
    "versions.txt",
    "runtime_versions.json",
)
REQUIRED_RUNTIME_PACKAGES = (
    "torch",
    "transformers",
    "peft",
    "accelerate",
    "huggingface-hub",
    "safetensors",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_member(tar: tarfile.TarFile, name: str) -> bytes:
    member = tar.getmember(name)
    if not member.isfile():
        raise ValueError(f"not_regular_file:{name}")
    stream = tar.extractfile(member)
    if stream is None:
        raise ValueError(f"unreadable_member:{name}")
    return stream.read()


def verify(archive: Path, expected_adapter_sha256: str | None = None) -> dict:
    if not archive.is_file() or archive.stat().st_size <= 0:
        raise ValueError("missing_or_empty_archive")
    archive_bytes = archive.read_bytes()
    with tarfile.open(archive, "r:gz") as tar:
        names = set(tar.getnames())
        missing = sorted(set(REQUIRED) - names)
        if missing:
            raise ValueError(f"missing_required_members:{missing}")
        manifest = json.loads(read_member(tar, REQUIRED[0]))
        receipt = json.loads(read_member(tar, REQUIRED[1]))
        adapter = read_member(tar, REQUIRED[2])
        adapter_config = json.loads(read_member(tar, REQUIRED[3]))
        versions_txt = read_member(tar, REQUIRED[4])
        runtime_versions_raw = read_member(tar, REQUIRED[5])
        runtime_versions = json.loads(runtime_versions_raw)

    actual = sha256_bytes(adapter)
    manifest_sha = str(manifest.get("adapter_sha256") or "")
    receipt_sha = str(receipt.get("adapter_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", actual):
        raise ValueError("invalid_actual_sha256")
    if actual != manifest_sha or actual != receipt_sha:
        raise ValueError(
            f"adapter_sha_mismatch:actual={actual}:manifest={manifest_sha}:receipt={receipt_sha}"
        )
    if expected_adapter_sha256 and actual != expected_adapter_sha256:
        raise ValueError(
            f"expected_adapter_sha_mismatch:actual={actual}:expected={expected_adapter_sha256}"
        )
    if manifest.get("base_repo") != receipt.get("base_repo"):
        raise ValueError("base_repo_mismatch")
    if manifest.get("base_revision") != receipt.get("base_revision"):
        raise ValueError("base_revision_mismatch")
    if receipt.get("reload_hash_match") is not True:
        raise ValueError("reload_hash_not_proven")

    if runtime_versions.get("kind") != "AQLEVON_27B_RUNTIME_VERSIONS_V1":
        raise ValueError("invalid_runtime_versions_kind")
    if not str(runtime_versions.get("python") or "").strip():
        raise ValueError("missing_python_runtime_version")
    packages = runtime_versions.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("missing_runtime_packages")
    for name in REQUIRED_RUNTIME_PACKAGES:
        if not str(packages.get(name) or "").strip():
            raise ValueError(f"missing_runtime_package_version:{name}")
    if not versions_txt.strip():
        raise ValueError("empty_versions_txt")

    return {
        "kind": "AQLEVON_27B_ARTIFACT_VERIFICATION_V2",
        "archive_sha256": sha256_bytes(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "adapter_sha256": actual,
        "adapter_bytes": len(adapter),
        "base_repo": manifest.get("base_repo"),
        "base_revision": manifest.get("base_revision"),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "reload_hash_match": True,
        "adapter_config_present": isinstance(adapter_config, dict),
        "versions_txt_sha256": sha256_bytes(versions_txt),
        "runtime_versions_sha256": sha256_bytes(runtime_versions_raw),
        "runtime_versions": runtime_versions,
        "verified": True,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--expected-adapter-sha256")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = verify(args.archive, args.expected_adapter_sha256)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(
        "AQLEVON_27B_ARTIFACT_SHA_VERIFIED",
        result["adapter_sha256"],
        result["archive_sha256"],
        result["runtime_versions_sha256"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
