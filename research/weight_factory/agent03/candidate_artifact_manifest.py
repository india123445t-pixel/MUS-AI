#!/usr/bin/env python3
"""AQLEVON Candidate Artifact Manifest V1 producer / validator.

P2 authority boundary
---------------------
This module owns artifact *identity and lineage only*. It does not originate
quality, evaluation, promotion eligibility, release approval, or runtime truth.
Those facts belong to Worker 05 / Manager / objective-verifier receipts under
AQLEVON_P2_INTEGRATION_CONTRACTS_V1.

The manifest is deterministic and self-hashed. All artifact bytes are described
by an ordered file tree of relative paths, sizes and SHA-256 digests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import numbers
import os
import re
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
MANIFEST_KIND = "AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1"
MANIFEST_ID_PREFIX = "aqlevon-candidate-artifact-v1:sha256:"
MANIFEST_ID_SCHEME = "AQLEVON_CANDIDATE_ARTIFACT_IDENTITY_V1"
HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"

ARTIFACT_TYPES = {
    "adapter",
    "full_checkpoint",
    "merge",
    "quantized_serving_artifact",
}
ARTIFACT_STAGES = {
    "probe_only",
    "reproducible_gene",
    "promotion_candidate",
    "merge_candidate",
    "release_candidate",
}

# Existing AQLEVON topology vocabulary from accepted P1 merge-safety policy.
# The producer validates names but does not decide whether a topology is merge-safe.
TOPOLOGY_CLASSES = {
    "FULL_HYBRID_TEXT",
    "ATTENTION_MLP_PARTIAL",
    "MLP_ONLY",
    "CUSTOM_EXPERIMENTAL",
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Candidate identity must never retype evaluation/release truth.
FORBIDDEN_TRUTH_FIELDS = {
    "verified",
    "quality_pass",
    "promotion_eligible",
    "release_approved",
    "evaluation_status",
    "evaluation_decision",
    "correctness",
}


SPEC_FIELDS = {
    "artifact_type",
    "artifact_stage",
    "base",
    "tokenizer_sha256",
    "config_sha256",
    "training_shard_manifest_sha256",
    "training_run_receipt_sha256",
    "merge_recipe_sha256",
    "parameter_layout_sha256",
    "topology_class",
    "adapter_state_sha256",
    "checkpoint_state_sha256",
    "parent_candidate_artifact_manifest_sha256",
    "environment_toolchain_manifest_sha256",
}

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "manifest_kind",
    "manifest_id",
    "hash_profile",
    "artifact_type",
    "artifact_stage",
    "base",
    "tokenizer_sha256",
    "config_sha256",
    "training_shard_manifest_sha256",
    "training_run_receipt_sha256",
    "merge_recipe_sha256",
    "parameter_layout_sha256",
    "topology_class",
    "artifact_files",
    "artifact_file_tree_sha256",
    "adapter_state_sha256",
    "checkpoint_state_sha256",
    "parent_candidate_artifact_manifest_sha256",
    "environment_toolchain_manifest_sha256",
    "manifest_sha256",
}


def canonical_json_bytes(value: Any) -> bytes:
    """Legacy deterministic JSON helper for non-self-hash evidence digests.

    P2 manifest self-digests MUST use ``canonical_p2_json_bytes`` below.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _normalize_p2_string(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")


def canonical_decimal_string(value: str) -> str:
    """Return the Manager-profile canonical decimal-string representation.

    Direct non-integral numeric objects are forbidden in authoritative hash
    payloads. Lanes that need a fractional value must first encode it as a
    canonical decimal string. Candidate Artifact Manifest V1 currently has no
    fractional numeric field; this helper exists to make the P2.1 law explicit
    and testable rather than inviting ad-hoc future formatting.
    """
    if not isinstance(value, str):
        raise ValueError("canonical decimal input must be a string")
    value = _normalize_p2_string(value)
    if "\n" in value or not re.fullmatch(r"-?(?:0|[0-9]+)(?:\.[0-9]+)?", value):
        raise ValueError("invalid decimal string: exponent/plus/non-decimal syntax forbidden")
    negative = value.startswith("-")
    body = value[1:] if negative else value
    integer, dot, fraction = body.partition(".")
    integer = integer.lstrip("0") or "0"
    fraction = fraction.rstrip("0") if dot else ""
    if integer == "0" and not fraction:
        return "0"
    out = integer + (("." + fraction) if fraction else "")
    return ("-" if negative else "") + out


def _p2_canon(value: Any) -> Any:
    """Canonicalize one authoritative hash payload per Manager P2.1 profile."""
    if isinstance(value, str):
        return _normalize_p2_string(value)
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if isinstance(value, numbers.Number):
        raise ValueError(
            "P2 canonical hash payload forbids direct non-integral numeric values; "
            "use a canonical decimal string"
        )
    if isinstance(value, list):
        return [_p2_canon(item) for item in value]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str) or not key or any(ord(ch) >= 128 for ch in key):
                raise ValueError("P2 canonical hash object keys must be non-empty ASCII strings")
        return {
            key: _p2_canon(value[key])
            for key in sorted(value, key=lambda item: item.encode("ascii"))
        }
    raise ValueError(f"P2 canonical hash payload type is unsupported: {type(value).__name__}")


def canonical_p2_json_bytes(value: Any) -> bytes:
    """Serialize the Manager-frozen AQLEVON_CANONICAL_JSON_SHA256_V1 profile."""
    return json.dumps(
        _p2_canon(value),
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_p2_json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_p2_json_bytes(value))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _require_sha256(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not _is_sha256(value):
        raise ValueError(f"{field} must be a lowercase 64-hex SHA-256")
    return value


def _normalize_relpath(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact path must be a non-empty string")
    if "\\" in value:
        raise ValueError(f"artifact path must use POSIX separators: {value!r}")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts):
        raise ValueError(f"unsafe artifact path: {value!r}")
    normalized = p.as_posix()
    if normalized != value:
        raise ValueError(f"artifact path is not canonical POSIX form: {value!r}")
    return normalized


def build_artifact_file_tree(root: str | Path) -> list[dict[str, Any]]:
    """Hash all regular files below root, rejecting symlinks/special files."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"artifact root must be an existing directory: {root}")

    entries: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        # Reject symlinked directories before os.walk can hide their semantics.
        for name in list(dirnames):
            child = d / name
            if child.is_symlink():
                raise ValueError(f"artifact tree contains symlink directory: {child}")
        for name in filenames:
            path = d / name
            if path.is_symlink():
                raise ValueError(f"artifact tree contains symlink file: {path}")
            st = path.stat()
            if not stat.S_ISREG(st.st_mode):
                raise ValueError(f"artifact tree contains non-regular file: {path}")
            rel = _normalize_relpath(path.relative_to(root).as_posix())
            entries.append({
                "path": rel,
                "size": int(st.st_size),
                "sha256": sha256_file(path),
            })

    entries.sort(key=lambda item: item["path"])
    if not entries:
        raise ValueError("artifact tree must contain at least one regular file")
    return entries


def artifact_file_tree_sha256(entries: list[dict[str, Any]]) -> str:
    return canonical_json_sha256(entries)


def _manifest_identity_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    semantic = {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_id", "manifest_sha256"}
    }
    return {"scheme": MANIFEST_ID_SCHEME, "manifest": semantic}


def compute_manifest_identity_sha256(manifest: dict[str, Any]) -> str:
    return canonical_p2_json_sha256(_manifest_identity_payload(manifest))


def compute_manifest_id(manifest: dict[str, Any]) -> str:
    return MANIFEST_ID_PREFIX + compute_manifest_identity_sha256(manifest)


def _manifest_payload_for_self_hash(manifest: dict[str, Any]) -> dict[str, Any]:
    # P2.1 exact exclusion rule: omit ONLY the self-digest field. manifest_id
    # remains inside the authoritative self-hash payload.
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return payload


def compute_manifest_sha256(manifest: dict[str, Any]) -> str:
    return canonical_p2_json_sha256(_manifest_payload_for_self_hash(manifest))


def seal_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    out = dict(manifest)
    out["hash_profile"] = HASH_PROFILE
    out["manifest_id"] = ""
    out["manifest_sha256"] = ""
    out["manifest_id"] = compute_manifest_id(out)
    out["manifest_sha256"] = compute_manifest_sha256(out)
    return out


def _normalize_parent_hashes(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("parent_candidate_artifact_manifest_sha256 must be a list")
    normalized: list[str] = []
    for i, value in enumerate(values):
        normalized.append(_require_sha256(value, f"parent_candidate_artifact_manifest_sha256[{i}]") or "")
    if len(set(normalized)) != len(normalized):
        raise ValueError("parent candidate manifest hashes must be unique")
    return sorted(normalized)


def _validate_artifact_entries(entries: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(entries, list) or not entries:
        return ["artifact_files must be a non-empty list"]
    seen: set[str] = set()
    previous: str | None = None
    for i, item in enumerate(entries):
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            errors.append(f"artifact_files[{i}] must contain exactly path,size,sha256")
            continue
        try:
            path = _normalize_relpath(item.get("path"))
        except ValueError as exc:
            errors.append(f"artifact_files[{i}]: {exc}")
            continue
        if path in seen:
            errors.append(f"duplicate artifact path: {path}")
        seen.add(path)
        if previous is not None and path <= previous:
            errors.append("artifact_files must be strictly sorted by path")
        previous = path
        size = item.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append(f"artifact_files[{i}].size must be a non-negative integer")
        if not _is_sha256(item.get("sha256")):
            errors.append(f"artifact_files[{i}].sha256 must be lowercase SHA-256")
    return errors


def validate_manifest(manifest: Any, artifact_root: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]

    forbidden = sorted(FORBIDDEN_TRUTH_FIELDS.intersection(manifest))
    if forbidden:
        errors.append("candidate manifest cannot originate evaluation/release truth fields: " + ",".join(forbidden))

    missing = sorted(REQUIRED_TOP_LEVEL - set(manifest))
    unknown = sorted(set(manifest) - REQUIRED_TOP_LEVEL)
    if missing:
        errors.append("missing top-level fields: " + ",".join(missing))
    if unknown:
        errors.append("unknown top-level fields for V1: " + ",".join(unknown))
    if missing or unknown:
        # Keep validating common fields for useful diagnostics, but avoid KeyError.
        pass

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")
    if manifest.get("manifest_kind") != MANIFEST_KIND:
        errors.append(f"manifest_kind must equal {MANIFEST_KIND}")
    if manifest.get("hash_profile") != HASH_PROFILE:
        errors.append(f"hash_profile must equal {HASH_PROFILE}")

    artifact_type = manifest.get("artifact_type")
    stage = manifest.get("artifact_stage")
    if artifact_type not in ARTIFACT_TYPES:
        errors.append("invalid artifact_type")
    if stage not in ARTIFACT_STAGES:
        errors.append("invalid artifact_stage")

    base = manifest.get("base")
    if not isinstance(base, dict) or set(base) != {"repo", "revision", "base_manifest_sha256"}:
        errors.append("base must contain exactly repo,revision,base_manifest_sha256")
    else:
        if not isinstance(base.get("repo"), str) or not base["repo"].strip():
            errors.append("base.repo must be non-empty")
        if not isinstance(base.get("revision"), str) or not base["revision"].strip():
            errors.append("base.revision must be non-empty")
        if not _is_sha256(base.get("base_manifest_sha256")):
            errors.append("base.base_manifest_sha256 must be lowercase SHA-256")

    for field in (
        "tokenizer_sha256",
        "config_sha256",
        "parameter_layout_sha256",
        "environment_toolchain_manifest_sha256",
        "artifact_file_tree_sha256",
    ):
        if not _is_sha256(manifest.get(field)):
            errors.append(f"{field} must be lowercase SHA-256")

    for field in (
        "training_shard_manifest_sha256",
        "training_run_receipt_sha256",
        "merge_recipe_sha256",
        "adapter_state_sha256",
        "checkpoint_state_sha256",
    ):
        value = manifest.get(field)
        if value is not None and not _is_sha256(value):
            errors.append(f"{field} must be null or lowercase SHA-256")

    topology = manifest.get("topology_class")
    if topology not in TOPOLOGY_CLASSES:
        errors.append("topology_class is not in the accepted AQLEVON topology vocabulary")

    parents = manifest.get("parent_candidate_artifact_manifest_sha256")
    if not isinstance(parents, list):
        errors.append("parent_candidate_artifact_manifest_sha256 must be a list")
        parents = []
    else:
        if parents != sorted(parents):
            errors.append("parent candidate manifest hashes must be lexicographically sorted")
        if len(set(parents)) != len(parents):
            errors.append("parent candidate manifest hashes must be unique")
        for i, value in enumerate(parents):
            if not _is_sha256(value):
                errors.append(f"parent_candidate_artifact_manifest_sha256[{i}] must be lowercase SHA-256")

    entries = manifest.get("artifact_files")
    errors.extend(_validate_artifact_entries(entries))
    if isinstance(entries, list) and entries:
        if manifest.get("artifact_file_tree_sha256") != artifact_file_tree_sha256(entries):
            errors.append("artifact_file_tree_sha256 mismatch")

    training_shard = manifest.get("training_shard_manifest_sha256")
    training_run = manifest.get("training_run_receipt_sha256")
    merge_recipe = manifest.get("merge_recipe_sha256")
    adapter_state = manifest.get("adapter_state_sha256")
    checkpoint_state = manifest.get("checkpoint_state_sha256")

    # Applicability / type semantics. These rules prevent an adapter from being
    # silently retyped as a checkpoint and force lineage for transforms.
    if artifact_type == "adapter":
        if not _is_sha256(adapter_state):
            errors.append("adapter requires adapter_state_sha256")
        if checkpoint_state is not None:
            errors.append("adapter must not claim checkpoint_state_sha256")
        if merge_recipe is not None:
            errors.append("adapter must not claim merge_recipe_sha256")
        if (training_shard is None) != (training_run is None):
            errors.append("adapter training bindings are atomic: training_shard_manifest_sha256 and training_run_receipt_sha256 must both be set or both be null")
    elif artifact_type == "full_checkpoint":
        if adapter_state is not None:
            errors.append("full_checkpoint must not claim adapter_state_sha256")
        if not _is_sha256(checkpoint_state):
            errors.append("full_checkpoint requires checkpoint_state_sha256")
        if merge_recipe is not None:
            errors.append("full_checkpoint must not claim merge_recipe_sha256")
        if (training_shard is None) != (training_run is None):
            errors.append("full_checkpoint training bindings are atomic: training_shard_manifest_sha256 and training_run_receipt_sha256 must both be set or both be null")
    elif artifact_type == "merge":
        if not _is_sha256(merge_recipe):
            errors.append("merge requires merge_recipe_sha256")
        if len(parents) < 2:
            errors.append("merge requires at least two parent candidate manifests")
        if training_shard is not None or training_run is not None:
            errors.append("merge identity must not retype training receipts; use parent lineage + merge_recipe_sha256")
        if (adapter_state is None) == (checkpoint_state is None):
            errors.append("merge requires exactly one state identity: adapter_state_sha256 or checkpoint_state_sha256")
    elif artifact_type == "quantized_serving_artifact":
        if len(parents) != 1:
            errors.append("quantized_serving_artifact requires exactly one parent candidate manifest")
        if adapter_state is not None:
            errors.append("quantized_serving_artifact must not claim adapter_state_sha256")
        if not _is_sha256(checkpoint_state):
            errors.append("quantized_serving_artifact requires checkpoint_state_sha256")
        if training_shard is not None or training_run is not None or merge_recipe is not None:
            errors.append("quantized_serving_artifact identity must use parent lineage; training/merge receipts belong to parent")

    if manifest.get("hash_profile") == HASH_PROFILE:
        try:
            expected_id = compute_manifest_id(manifest)
            expected_digest = compute_manifest_sha256(manifest)
        except ValueError as exc:
            errors.append(f"P2 canonical hash payload invalid: {exc}")
        else:
            if manifest.get("manifest_id") != expected_id:
                errors.append("manifest_id identity digest mismatch")
            if manifest.get("manifest_sha256") != expected_digest:
                errors.append("manifest_sha256 self-digest mismatch")
    # Unknown/missing hash profiles are never guessed or validated under a fallback.

    if artifact_root is not None:
        try:
            observed = build_artifact_file_tree(artifact_root)
        except (OSError, ValueError) as exc:
            errors.append(f"artifact root validation failed: {exc}")
        else:
            if entries != observed:
                errors.append("artifact_files do not match current artifact_root bytes")

    return errors


def build_manifest(spec: dict[str, Any], artifact_root: str | Path) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object")

    forbidden = FORBIDDEN_TRUTH_FIELDS.intersection(spec)
    if forbidden:
        raise ValueError("spec cannot originate evaluation/release truth fields: " + ",".join(sorted(forbidden)))
    unknown = sorted(set(spec) - SPEC_FIELDS)
    if unknown:
        raise ValueError("unknown spec fields for V1: " + ",".join(unknown))

    entries = build_artifact_file_tree(artifact_root)
    base = spec.get("base")
    if not isinstance(base, dict):
        raise ValueError("spec.base is required")
    if set(base) != {"repo", "revision", "base_manifest_sha256"}:
        raise ValueError("spec.base must contain exactly repo,revision,base_manifest_sha256")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "hash_profile": HASH_PROFILE,
        "manifest_id": "",
        "artifact_type": spec.get("artifact_type"),
        "artifact_stage": spec.get("artifact_stage"),
        "base": {
            "repo": base.get("repo"),
            "revision": base.get("revision"),
            "base_manifest_sha256": base.get("base_manifest_sha256"),
        },
        "tokenizer_sha256": spec.get("tokenizer_sha256"),
        "config_sha256": spec.get("config_sha256"),
        "training_shard_manifest_sha256": spec.get("training_shard_manifest_sha256"),
        "training_run_receipt_sha256": spec.get("training_run_receipt_sha256"),
        "merge_recipe_sha256": spec.get("merge_recipe_sha256"),
        "parameter_layout_sha256": spec.get("parameter_layout_sha256"),
        "topology_class": spec.get("topology_class"),
        "artifact_files": entries,
        "artifact_file_tree_sha256": artifact_file_tree_sha256(entries),
        "adapter_state_sha256": spec.get("adapter_state_sha256"),
        "checkpoint_state_sha256": spec.get("checkpoint_state_sha256"),
        "parent_candidate_artifact_manifest_sha256": _normalize_parent_hashes(
            spec.get("parent_candidate_artifact_manifest_sha256", [])
        ),
        "environment_toolchain_manifest_sha256": spec.get("environment_toolchain_manifest_sha256"),
        "manifest_sha256": "",
    }
    sealed = seal_manifest(manifest)
    errors = validate_manifest(sealed, artifact_root=artifact_root)
    if errors:
        raise ValueError("CANDIDATE_MANIFEST_FAIL\n" + "\n".join(errors))
    return sealed


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_probe_only_manifest_from_g1(
    report_path: str | Path,
    artifact_root: str | Path,
    bindings: dict[str, Any],
) -> dict[str, Any]:
    """Integrate canonical BF16 G1 output without promoting its stage.

    This function intentionally refuses the experimental QLoRA success status.
    Experimental artifacts can be described by the generic producer, but they
    are not silently retyped as canonical G1 evidence.
    """
    report_path = Path(report_path)
    report = _load_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("G1 report must be a JSON object")
    if report.get("status") != "PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL":
        raise ValueError("G1 integration requires canonical BF16 PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL")

    plan = report.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("G1 report.plan missing")
    if plan.get("mode") != "bf16" or plan.get("policy_state", {}).get("canonical_preferred") is not True:
        raise ValueError("G1 report must prove canonical BF16 policy state")

    artifact = report.get("artifact")
    environment = report.get("environment")
    if not isinstance(artifact, dict) or not isinstance(environment, dict):
        raise ValueError("G1 report missing artifact/environment evidence")
    adapter_state = artifact.get("saved_adapter_state_sha256")
    _require_sha256(adapter_state, "G1 artifact.saved_adapter_state_sha256")
    if artifact.get("reload_hash_match") is not True:
        raise ValueError("G1 report requires reload_hash_match=true")
    if artifact.get("reloaded_adapter_state_sha256") != adapter_state:
        raise ValueError("G1 saved/reloaded adapter state hashes differ")

    # The report's artifact file map must match bytes on disk exactly.
    observed = build_artifact_file_tree(artifact_root)
    observed_map = {item["path"]: item["sha256"] for item in observed}
    report_map = artifact.get("file_sha256")
    if report_map != observed_map:
        raise ValueError("G1 report artifact.file_sha256 does not match artifact_root")

    required_bindings = (
        "base_manifest_sha256",
        "tokenizer_sha256",
        "config_sha256",
        "training_shard_manifest_sha256",
        "parameter_layout_sha256",
    )
    for field in required_bindings:
        _require_sha256(bindings.get(field), f"bindings.{field}")

    # Hash of the immutable G1 report is the training-run receipt identity.
    training_run_receipt_sha256 = sha256_file(report_path)
    # The environment object is itself the toolchain manifest carried by G1.
    environment_toolchain_manifest_sha256 = canonical_json_sha256(environment)

    spec = {
        "artifact_type": "adapter",
        "artifact_stage": "probe_only",  # forced by P2 contract
        "base": {
            "repo": plan.get("model"),
            "revision": plan.get("revision"),
            "base_manifest_sha256": bindings["base_manifest_sha256"],
        },
        "tokenizer_sha256": bindings["tokenizer_sha256"],
        "config_sha256": bindings["config_sha256"],
        "training_shard_manifest_sha256": bindings["training_shard_manifest_sha256"],
        "training_run_receipt_sha256": training_run_receipt_sha256,
        "merge_recipe_sha256": None,
        "parameter_layout_sha256": bindings["parameter_layout_sha256"],
        # G1 q/v-only LoRA is intentionally not represented as full-hybrid.
        "topology_class": "CUSTOM_EXPERIMENTAL",
        "adapter_state_sha256": adapter_state,
        "checkpoint_state_sha256": None,
        "parent_candidate_artifact_manifest_sha256": bindings.get(
            "parent_candidate_artifact_manifest_sha256", []
        ),
        "environment_toolchain_manifest_sha256": environment_toolchain_manifest_sha256,
    }
    return build_manifest(spec, artifact_root)


def _assert_output_outside_artifact_root(output: str | Path, artifact_root: str | Path) -> None:
    output_path = Path(output).resolve()
    root = Path(artifact_root).resolve()
    try:
        output_path.relative_to(root)
    except ValueError:
        return
    raise ValueError("manifest output must be outside artifact_root to avoid self-referential artifact identity")


def _cmd_generate(args: argparse.Namespace) -> None:
    _assert_output_outside_artifact_root(args.output, args.artifact_root)
    manifest = build_manifest(_load_json(args.spec), args.artifact_root)
    _write_json(args.output, manifest)
    print(manifest["manifest_sha256"])


def _cmd_validate(args: argparse.Namespace) -> None:
    manifest = _load_json(args.manifest)
    errors = validate_manifest(manifest, artifact_root=args.artifact_root)
    if errors:
        raise SystemExit("CANDIDATE_MANIFEST_FAIL\n" + "\n".join(errors))
    print("CANDIDATE_MANIFEST_PASS")


def _cmd_from_g1(args: argparse.Namespace) -> None:
    _assert_output_outside_artifact_root(args.output, args.artifact_root)
    manifest = build_probe_only_manifest_from_g1(
        args.g1_report,
        args.artifact_root,
        _load_json(args.bindings),
    )
    _write_json(args.output, manifest)
    print(manifest["manifest_sha256"])


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--spec", required=True)
    gen.add_argument("--artifact-root", required=True)
    gen.add_argument("--output", required=True)
    gen.set_defaults(func=_cmd_generate)

    val = sub.add_parser("validate")
    val.add_argument("--manifest", required=True)
    val.add_argument("--artifact-root")
    val.set_defaults(func=_cmd_validate)

    g1 = sub.add_parser("from-g1")
    g1.add_argument("--g1-report", required=True)
    g1.add_argument("--artifact-root", required=True)
    g1.add_argument("--bindings", required=True)
    g1.add_argument("--output", required=True)
    g1.set_defaults(func=_cmd_from_g1)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()