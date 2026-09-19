#!/usr/bin/env python3
"""AQLEVON Worker-04 P4 Gene Package V1.

Packages one Manager-accepted promoted adapter without modifying the immutable base.
This module owns identity/preservation/runtime activation contracts only. It does not
originate evaluation truth, Manager promotion authority, training truth, or compute truth.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import numbers
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
from typing import Any, Callable, Mapping, Sequence

SCHEMA_VERSION = 1
PACKAGE_KIND = "AQLEVON_GENE_PACKAGE_V1"
PACKAGE_ID_PREFIX = "aqlevon-gene-package-v1:sha256:"
HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
RUNTIME_RECEIPT_KIND = "AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1"
EVAL_RECEIPT_KIND = "AQLEVON_EVALUATION_DECISION_RECEIPT_V1"
TRUTH_BOUNDARY = "PROMOTED_GENE_PACKAGE_REQUIRES_WORKER05_EVIDENCE_AND_MANAGER_ACCEPTANCE"
ROLLBACK_ACTION = "DETACH_ADAPTER_RESTORE_IMMUTABLE_BASE"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PACKAGE_ID_RE = re.compile(r"^aqlevon-gene-package-v1:sha256:[0-9a-f]{64}$")
QUANT_STATUSES = {"NOT_TESTED", "PASS", "FAIL"}


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def _normalize_string(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")


def _canon(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_string(value)
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, numbers.Number):
        raise ValueError("direct non-integral numeric forbidden; use canonical decimal strings or integer fixed-point units")
    if isinstance(value, list):
        return [_canon(v) for v in value]
    if isinstance(value, tuple):
        return [_canon(v) for v in value]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str) or not key or any(ord(ch) >= 128 for ch in key):
                raise ValueError("canonical object keys must be non-empty ASCII strings")
        return {key: _canon(value[key]) for key in sorted(value, key=lambda item: item.encode("ascii"))}
    raise ValueError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canon(value), ensure_ascii=False, separators=(",", ":"), sort_keys=False, allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def self_digest_ok(obj: Any, field: str) -> bool:
    if not isinstance(obj, dict) or obj.get("hash_profile") != HASH_PROFILE or not is_sha(obj.get(field)):
        return False
    try:
        return canonical_sha256({k: v for k, v in obj.items() if k != field}) == obj[field]
    except ValueError:
        return False


def _default_p2_validators() -> tuple[Callable[[Any], list[str]], Callable[[Any], list[str]]]:
    try:
        from p2_merge_receipt_gate import validate_candidate, validate_eval
    except ImportError as exc:  # pragma: no cover - full repository integration path
        raise RuntimeError("p2_merge_receipt_gate.py must be importable for authoritative Candidate/Evaluation validation") from exc
    return validate_candidate, validate_eval


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_candidate_artifact_tree(candidate_manifest: Mapping[str, Any], artifact_root: str | Path) -> list[str]:
    """Verify exact adapter bytes against Candidate Artifact Manifest file entries."""
    errors: list[str] = []
    root = Path(artifact_root).resolve()
    if not root.is_dir():
        return ["artifact_root must be an existing directory"]
    entries = candidate_manifest.get("artifact_files")
    if not isinstance(entries, list) or not entries:
        return ["candidate artifact_files missing"]

    expected_paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            errors.append(f"artifact_files[{index}] invalid")
            continue
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel or "\\" in rel:
            errors.append(f"artifact_files[{index}].path invalid")
            continue
        pure = PurePosixPath(rel)
        if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts) or pure.as_posix() != rel:
            errors.append(f"artifact_files[{index}].path unsafe")
            continue
        path = root.joinpath(*pure.parts)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            errors.append(f"artifact missing: {rel}")
            continue
        if root != resolved and root not in resolved.parents:
            errors.append(f"artifact escapes root: {rel}")
            continue
        st = resolved.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            errors.append(f"artifact must be a regular non-symlink file: {rel}")
            continue
        if type(entry.get("size")) is not int or entry["size"] < 0 or st.st_size != entry["size"]:
            errors.append(f"artifact size mismatch: {rel}")
        if not is_sha(entry.get("sha256")) or _sha256_file(resolved) != entry.get("sha256"):
            errors.append(f"artifact SHA-256 mismatch: {rel}")
        expected_paths.add(rel)

    actual_paths: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        directory = Path(dirpath)
        for name in dirnames:
            if (directory / name).is_symlink():
                errors.append(f"artifact tree contains symlink directory: {(directory / name).relative_to(root).as_posix()}")
        for name in filenames:
            path = directory / name
            if path.is_symlink():
                errors.append(f"artifact tree contains symlink file: {path.relative_to(root).as_posix()}")
            else:
                actual_paths.add(path.relative_to(root).as_posix())
    if expected_paths != actual_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        if missing:
            errors.append("artifact tree missing files: " + ",".join(missing))
        if extra:
            errors.append("artifact tree has unbound files: " + ",".join(extra))
    return errors


def _validate_compute_receipt(receipt: Any, candidate_sha: str) -> list[str]:
    """Strict cross-language minimum for accepted Worker-06 Runtime Attempt Receipt V1."""
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return ["compute receipt must be an object"]
    if receipt.get("schema_version") != 1:
        errors.append("compute receipt schema_version mismatch")
    if receipt.get("receipt_kind") != RUNTIME_RECEIPT_KIND:
        errors.append("compute receipt kind mismatch")
    if receipt.get("hash_profile") != HASH_PROFILE:
        errors.append("compute receipt hash_profile mismatch")
    if receipt.get("candidate_artifact_manifest_sha256") != candidate_sha:
        errors.append("compute receipt candidate binding mismatch")
    if not is_sha(receipt.get("receipt_sha256")):
        errors.append("compute receipt receipt_sha256 invalid")
    elif not self_digest_ok(receipt, "receipt_sha256"):
        errors.append("compute receipt self-digest mismatch")
    outcome = receipt.get("transport_outcome")
    if not isinstance(outcome, dict) or outcome.get("status") not in {"success", "failed"}:
        errors.append("compute receipt transport_outcome invalid")
    metrics = receipt.get("runtime_metrics")
    if not isinstance(metrics, dict) or metrics.get("schema") != "aqlevon-runtime-metrics-v1":
        errors.append("compute receipt runtime_metrics invalid")
    return errors


def _compute_set_sha(receipt_hashes: Sequence[str]) -> str:
    ordered = sorted(receipt_hashes)
    return canonical_sha256({
        "hash_profile": HASH_PROFILE,
        "receipt_kind": RUNTIME_RECEIPT_KIND,
        "receipt_sha256s": ordered,
    })


def _package_identity_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in package.items() if k not in {"package_id", "package_sha256"}}


def compute_package_id(package: Mapping[str, Any]) -> str:
    return PACKAGE_ID_PREFIX + canonical_sha256({"scheme": "AQLEVON_GENE_PACKAGE_IDENTITY_V1", "package": _package_identity_payload(package)})


def compute_package_sha256(package: Mapping[str, Any]) -> str:
    return canonical_sha256({k: v for k, v in package.items() if k != "package_sha256"})


def seal_gene_package(
    *,
    candidate_manifest: Mapping[str, Any],
    evaluation_receipt: Mapping[str, Any],
    target_capability: Mapping[str, Any],
    manager_acceptance_record_sha256: str,
    compute_receipts: Sequence[Mapping[str, Any]],
    training_shard_manifest_sha256: str,
    training_run_receipt_sha256: str,
    quantization_compatibility: Mapping[str, Any] | None = None,
    previous_gene_package_sha256: str | None = None,
    candidate_validator: Callable[[Any], list[str]] | None = None,
    evaluation_validator: Callable[[Any], list[str]] | None = None,
) -> dict[str, Any]:
    """Create Gene Package V1 only from upstream promotion evidence + Manager acceptance."""
    if candidate_validator is None or evaluation_validator is None:
        default_candidate, default_eval = _default_p2_validators()
        candidate_validator = candidate_validator or default_candidate
        evaluation_validator = evaluation_validator or default_eval
    c_errors = candidate_validator(candidate_manifest)
    e_errors = evaluation_validator(evaluation_receipt)
    if c_errors:
        raise ValueError("candidate manifest invalid: " + "; ".join(c_errors))
    if e_errors:
        raise ValueError("evaluation receipt invalid: " + "; ".join(e_errors))

    if candidate_manifest.get("artifact_type") != "adapter":
        raise ValueError("Gene Package V1 requires artifact_type=adapter")
    if candidate_manifest.get("artifact_stage") == "probe_only":
        raise ValueError("probe_only adapter cannot become a Gene Package")
    candidate_sha = candidate_manifest.get("manifest_sha256")
    adapter_sha = candidate_manifest.get("adapter_state_sha256")
    if not is_sha(candidate_sha) or not is_sha(adapter_sha):
        raise ValueError("candidate/adapter identity invalid")
    if evaluation_receipt.get("candidate_artifact_manifest_sha256") != candidate_sha:
        raise ValueError("evaluation receipt candidate binding mismatch")
    if evaluation_receipt.get("final_status") != "PROMOTION_ELIGIBLE":
        raise ValueError("Worker-05 final_status must be PROMOTION_ELIGIBLE")
    if not is_sha(manager_acceptance_record_sha256):
        raise ValueError("Manager acceptance record SHA-256 is required")

    candidate_training_shard_sha = candidate_manifest.get("training_shard_manifest_sha256")
    candidate_training_run_sha = candidate_manifest.get("training_run_receipt_sha256")
    if not is_sha(candidate_training_shard_sha) or not is_sha(candidate_training_run_sha):
        raise ValueError("promoted Gene Package requires bound training shard + training run receipts")
    if not is_sha(training_shard_manifest_sha256):
        raise ValueError("training_shard_manifest_sha256 must be a lowercase SHA-256")
    if not is_sha(training_run_receipt_sha256):
        raise ValueError("training_run_receipt_sha256 must be a lowercase SHA-256")
    if training_shard_manifest_sha256 != candidate_training_shard_sha:
        raise ValueError("training shard identity does not match Candidate Artifact binding")
    if training_run_receipt_sha256 != candidate_training_run_sha:
        raise ValueError("training run receipt identity does not match Candidate Artifact binding")

    if not isinstance(target_capability, Mapping):
        raise ValueError("target_capability must be an object")
    capability_id = target_capability.get("capability_id")
    capability_version = target_capability.get("capability_version")
    if not isinstance(capability_id, str) or not capability_id or any(ord(ch) >= 128 for ch in capability_id):
        raise ValueError("target_capability.capability_id must be non-empty ASCII")
    if type(capability_version) is not int or capability_version < 1:
        raise ValueError("target_capability.capability_version must be a positive integer")
    canonical_bytes(dict(target_capability))

    if not isinstance(compute_receipts, Sequence) or isinstance(compute_receipts, (str, bytes)) or not compute_receipts:
        raise ValueError("at least one compute/runtime receipt is required")
    compute_hashes: list[str] = []
    for index, receipt in enumerate(compute_receipts):
        errors = _validate_compute_receipt(receipt, candidate_sha)
        if errors:
            raise ValueError(f"compute_receipt[{index}] invalid: " + "; ".join(errors))
        receipt_sha = receipt["receipt_sha256"]
        if receipt_sha in compute_hashes:
            raise ValueError("duplicate compute receipt identity")
        compute_hashes.append(receipt_sha)
    compute_hashes.sort()

    quant = dict(quantization_compatibility or {"status": "NOT_TESTED", "quantized_candidate_manifest_sha256": None, "evaluation_decision_receipt_sha256": None})
    status = quant.get("status")
    if status not in QUANT_STATUSES:
        raise ValueError("quantization_compatibility.status invalid")
    q_candidate = quant.get("quantized_candidate_manifest_sha256")
    q_eval = quant.get("evaluation_decision_receipt_sha256")
    if status == "NOT_TESTED":
        if q_candidate is not None or q_eval is not None:
            raise ValueError("NOT_TESTED quantization compatibility cannot claim evidence identities")
    else:
        if not is_sha(q_candidate) or not is_sha(q_eval):
            raise ValueError("evaluated quantization compatibility requires candidate + evaluation SHA-256")

    if previous_gene_package_sha256 is not None and not is_sha(previous_gene_package_sha256):
        raise ValueError("previous_gene_package_sha256 must be null or SHA-256")

    base = candidate_manifest.get("base")
    if not isinstance(base, Mapping):
        raise ValueError("candidate base identity missing")
    for field in ("base_manifest_sha256",):
        if not is_sha(base.get(field)):
            raise ValueError(f"candidate base.{field} invalid")
    for field in ("tokenizer_sha256", "config_sha256", "parameter_layout_sha256", "artifact_file_tree_sha256"):
        if not is_sha(candidate_manifest.get(field)):
            raise ValueError(f"candidate {field} invalid")

    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "package_kind": PACKAGE_KIND,
        "package_id": "",
        "hash_profile": HASH_PROFILE,
        "truth_boundary": TRUTH_BOUNDARY,
        "target_capability": dict(target_capability),
        "base_identity": {
            "repo": base.get("repo"),
            "revision": base.get("revision"),
            "base_manifest_sha256": base.get("base_manifest_sha256"),
            "tokenizer_sha256": candidate_manifest.get("tokenizer_sha256"),
            "config_sha256": candidate_manifest.get("config_sha256"),
        },
        "adapter_identity": {
            "candidate_artifact_manifest_sha256": candidate_sha,
            "adapter_state_sha256": adapter_sha,
            "artifact_file_tree_sha256": candidate_manifest.get("artifact_file_tree_sha256"),
        },
        "promotion_binding": {
            "evaluation_decision_receipt_sha256": evaluation_receipt.get("receipt_sha256"),
            "worker05_status": "PROMOTION_ELIGIBLE",
            "manager_acceptance_record_sha256": manager_acceptance_record_sha256,
        },
        "training_binding": {
            "training_shard_manifest_sha256": candidate_training_shard_sha,
            "training_run_receipt_sha256": candidate_training_run_sha,
        },
        "compute_binding": {
            "runtime_receipt_kind": RUNTIME_RECEIPT_KIND,
            "runtime_attempt_receipt_sha256s": compute_hashes,
            "runtime_attempt_receipt_set_sha256": _compute_set_sha(compute_hashes),
        },
        "compatibility": {
            "topology_class": candidate_manifest.get("topology_class"),
            "parameter_layout_sha256": candidate_manifest.get("parameter_layout_sha256"),
            "quantization": quant,
        },
        "rollback": {
            "rollback_action": ROLLBACK_ACTION,
            "base_is_immutable": True,
            "adapter_detach_without_base_mutation": True,
            "previous_gene_package_sha256": previous_gene_package_sha256,
        },
        "integration_hook": {
            "eligible_for_future_gene_pair_check": True,
            "real_multi_gene_integration_authorized": False,
            "dormant_methods_until_two_manager_accepted_genes": ["ties", "dare", "della", "ctm", "hard_top1_router", "mopd"],
        },
    }
    package["package_id"] = compute_package_id(package)
    package["package_sha256"] = compute_package_sha256(package)
    errors = validate_gene_package(package)
    if errors:
        raise ValueError("sealed package invalid: " + "; ".join(errors))
    return package


def validate_gene_package(package: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(package, dict):
        return ["package must be an object"]
    if package.get("schema_version") != 1:
        errors.append("schema_version mismatch")
    if package.get("package_kind") != PACKAGE_KIND:
        errors.append("package_kind mismatch")
    if package.get("hash_profile") != HASH_PROFILE:
        errors.append("hash_profile mismatch")
    if package.get("truth_boundary") != TRUTH_BOUNDARY:
        errors.append("truth_boundary mismatch")
    if not isinstance(package.get("package_id"), str) or PACKAGE_ID_RE.fullmatch(package.get("package_id", "")) is None:
        errors.append("package_id invalid")
    else:
        try:
            if compute_package_id(package) != package["package_id"]:
                errors.append("package_id mismatch")
        except ValueError as exc:
            errors.append(f"package canonicalization invalid: {exc}")
    if not is_sha(package.get("package_sha256")):
        errors.append("package_sha256 invalid")
    else:
        try:
            if compute_package_sha256(package) != package["package_sha256"]:
                errors.append("package self-digest mismatch")
        except ValueError as exc:
            errors.append(f"package canonicalization invalid: {exc}")

    capability = package.get("target_capability")
    if not isinstance(capability, dict) or not isinstance(capability.get("capability_id"), str) or not capability.get("capability_id") or type(capability.get("capability_version")) is not int or capability.get("capability_version", 0) < 1:
        errors.append("target_capability invalid")

    base = package.get("base_identity")
    if not isinstance(base, dict) or not isinstance(base.get("repo"), str) or not base.get("repo") or not isinstance(base.get("revision"), str) or not base.get("revision"):
        errors.append("base_identity invalid")
    elif any(not is_sha(base.get(field)) for field in ("base_manifest_sha256", "tokenizer_sha256", "config_sha256")):
        errors.append("base_identity hashes invalid")

    adapter = package.get("adapter_identity")
    if not isinstance(adapter, dict) or any(not is_sha(adapter.get(field)) for field in ("candidate_artifact_manifest_sha256", "adapter_state_sha256", "artifact_file_tree_sha256")):
        errors.append("adapter_identity invalid")

    promotion = package.get("promotion_binding")
    if not isinstance(promotion, dict) or promotion.get("worker05_status") != "PROMOTION_ELIGIBLE" or any(not is_sha(promotion.get(field)) for field in ("evaluation_decision_receipt_sha256", "manager_acceptance_record_sha256")):
        errors.append("promotion_binding invalid")

    training = package.get("training_binding")
    if not isinstance(training, dict) or any(not is_sha(training.get(field)) for field in ("training_shard_manifest_sha256", "training_run_receipt_sha256")):
        errors.append("training_binding invalid")

    compute = package.get("compute_binding")
    if not isinstance(compute, dict) or compute.get("runtime_receipt_kind") != RUNTIME_RECEIPT_KIND:
        errors.append("compute_binding invalid")
    else:
        hashes = compute.get("runtime_attempt_receipt_sha256s")
        if not isinstance(hashes, list) or not hashes or any(not is_sha(x) for x in hashes) or hashes != sorted(hashes) or len(hashes) != len(set(hashes)):
            errors.append("compute_binding receipt identities invalid")
        elif compute.get("runtime_attempt_receipt_set_sha256") != _compute_set_sha(hashes):
            errors.append("compute_binding receipt set digest mismatch")

    compatibility = package.get("compatibility")
    if not isinstance(compatibility, dict) or not isinstance(compatibility.get("topology_class"), str) or not compatibility.get("topology_class") or not is_sha(compatibility.get("parameter_layout_sha256")):
        errors.append("compatibility invalid")
    else:
        quant = compatibility.get("quantization")
        if not isinstance(quant, dict) or quant.get("status") not in QUANT_STATUSES:
            errors.append("quantization compatibility invalid")
        elif quant.get("status") == "NOT_TESTED":
            if quant.get("quantized_candidate_manifest_sha256") is not None or quant.get("evaluation_decision_receipt_sha256") is not None:
                errors.append("NOT_TESTED quantization compatibility has evidence identities")
        elif not is_sha(quant.get("quantized_candidate_manifest_sha256")) or not is_sha(quant.get("evaluation_decision_receipt_sha256")):
            errors.append("evaluated quantization compatibility evidence invalid")

    rollback = package.get("rollback")
    if not isinstance(rollback, dict) or rollback.get("rollback_action") != ROLLBACK_ACTION or rollback.get("base_is_immutable") is not True or rollback.get("adapter_detach_without_base_mutation") is not True:
        errors.append("rollback metadata invalid")
    elif rollback.get("previous_gene_package_sha256") is not None and not is_sha(rollback.get("previous_gene_package_sha256")):
        errors.append("rollback previous_gene_package_sha256 invalid")

    hook = package.get("integration_hook")
    if not isinstance(hook, dict) or hook.get("eligible_for_future_gene_pair_check") is not True or hook.get("real_multi_gene_integration_authorized") is not False:
        errors.append("integration_hook invalid")
    return errors


@dataclass(frozen=True)
class RuntimeBaseIdentity:
    repo: str
    revision: str
    base_manifest_sha256: str
    tokenizer_sha256: str
    config_sha256: str
    parameter_layout_sha256: str
    topology_class: str


def prepare_single_gene_activation(
    package: Mapping[str, Any],
    runtime_identity: RuntimeBaseIdentity,
    *,
    artifact_root: str | Path | None = None,
    candidate_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare a reversible single-gene activation; never mutates model/base state."""
    errors = validate_gene_package(package)
    if errors:
        raise ValueError("invalid Gene Package: " + "; ".join(errors))
    base = package["base_identity"]
    expected = {
        "repo": base["repo"],
        "revision": base["revision"],
        "base_manifest_sha256": base["base_manifest_sha256"],
        "tokenizer_sha256": base["tokenizer_sha256"],
        "config_sha256": base["config_sha256"],
        "parameter_layout_sha256": package["compatibility"]["parameter_layout_sha256"],
        "topology_class": package["compatibility"]["topology_class"],
    }
    observed = asdict(runtime_identity)
    mismatches = [field for field in expected if observed[field] != expected[field]]
    if mismatches:
        raise ValueError("runtime/base identity mismatch: " + ",".join(mismatches))

    artifact_verified = False
    if artifact_root is not None:
        if candidate_manifest is None:
            raise ValueError("candidate_manifest is required when artifact_root is provided")
        if candidate_manifest.get("manifest_sha256") != package["adapter_identity"]["candidate_artifact_manifest_sha256"]:
            raise ValueError("candidate manifest does not match package adapter identity")
        artifact_errors = verify_candidate_artifact_tree(candidate_manifest, artifact_root)
        if artifact_errors:
            raise ValueError("adapter artifact verification failed: " + "; ".join(artifact_errors))
        artifact_verified = True

    request = {
        "schema_version": 1,
        "request_kind": "AQLEVON_SINGLE_GENE_ACTIVATION_REQUEST_V1",
        "hash_profile": HASH_PROFILE,
        "gene_package_sha256": package["package_sha256"],
        "candidate_artifact_manifest_sha256": package["adapter_identity"]["candidate_artifact_manifest_sha256"],
        "adapter_state_sha256": package["adapter_identity"]["adapter_state_sha256"],
        "runtime_base_identity": observed,
        "activation_mode": "SINGLE_ADAPTER_ATTACH_REVERSIBLE",
        "base_mutation_allowed": False,
        "rollback_action": ROLLBACK_ACTION,
        "artifact_bytes_verified": artifact_verified,
        "multi_gene_routing_authorized": False,
    }
    request["request_sha256"] = canonical_sha256(request)
    return request


def load_gene_package(path: str | Path) -> dict[str, Any]:
    """Load one Gene Package manifest from disk and fail closed on any identity error."""
    try:
        package = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Gene Package: {exc}") from exc
    errors = validate_gene_package(package)
    if errors:
        raise ValueError("invalid Gene Package: " + "; ".join(errors))
    return package


class SingleGeneRouter:
    """Single-gene-only runtime smoke router; multi-gene routing is intentionally impossible."""
    def __init__(self, package: Mapping[str, Any]):
        errors = validate_gene_package(package)
        if errors:
            raise ValueError("invalid Gene Package: " + "; ".join(errors))
        self._package = dict(package)

    @property
    def gene_package_sha256(self) -> str:
        return self._package["package_sha256"]

    def route(self, request_descriptor: Mapping[str, Any] | None = None) -> dict[str, Any]:
        descriptor = dict(request_descriptor or {})
        canonical_bytes(descriptor)
        out = {
            "schema_version": 1,
            "route_kind": "AQLEVON_SINGLE_GENE_ROUTE_V1",
            "hash_profile": HASH_PROFILE,
            "gene_package_sha256": self._package["package_sha256"],
            "candidate_artifact_manifest_sha256": self._package["adapter_identity"]["candidate_artifact_manifest_sha256"],
            "request_descriptor_sha256": canonical_sha256(descriptor),
            "route_mode": "ONLY_ACTIVE_GENE",
            "multi_gene_routing_authorized": False,
        }
        out["route_sha256"] = canonical_sha256(out)
        return out


def integration_descriptor(package: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_gene_package(package)
    if errors:
        raise ValueError("invalid Gene Package: " + "; ".join(errors))
    return {
        "gene_package_sha256": package["package_sha256"],
        "target_capability": package["target_capability"],
        "candidate_artifact_manifest_sha256": package["adapter_identity"]["candidate_artifact_manifest_sha256"],
        "evaluation_decision_receipt_sha256": package["promotion_binding"]["evaluation_decision_receipt_sha256"],
        "manager_acceptance_record_sha256": package["promotion_binding"]["manager_acceptance_record_sha256"],
        "adapter_state_sha256": package["adapter_identity"]["adapter_state_sha256"],
        "base_identity": package["base_identity"],
        "parameter_layout_sha256": package["compatibility"]["parameter_layout_sha256"],
        "topology_class": package["compatibility"]["topology_class"],
        "quantization_status": package["compatibility"]["quantization"]["status"],
    }


def prepare_gene_pair_integration_hook(packages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Identity-only Gene #2 hook. Explicitly does not authorize merge/routing execution."""
    if len(packages) < 2:
        raise ValueError("future integration hook requires at least two Manager-accepted Gene Packages")
    descriptors = [integration_descriptor(p) for p in packages]
    package_ids = [d["gene_package_sha256"] for d in descriptors]
    if len(package_ids) != len(set(package_ids)):
        raise ValueError("duplicate Gene Package identity")
    descriptors.sort(key=lambda d: d["gene_package_sha256"])
    first = descriptors[0]
    for other in descriptors[1:]:
        for field in ("base_identity", "parameter_layout_sha256", "topology_class"):
            if other[field] != first[field]:
                raise ValueError(f"Gene Package integration incompatibility: {field}")
    hook = {
        "schema_version": 1,
        "hook_kind": "AQLEVON_FUTURE_GENE_INTEGRATION_HOOK_V1",
        "hash_profile": HASH_PROFILE,
        "gene_package_sha256s": [d["gene_package_sha256"] for d in descriptors],
        "candidate_artifact_manifest_sha256s": [d["candidate_artifact_manifest_sha256"] for d in descriptors],
        "base_identity": first["base_identity"],
        "parameter_layout_sha256": first["parameter_layout_sha256"],
        "topology_class": first["topology_class"],
        "methods_dormant": ["ties", "dare", "della", "ctm", "hard_top1_router", "mopd"],
        "real_integration_authorized": False,
        "truth_boundary": "IDENTITY_COMPATIBILITY_ONLY_MANAGER_MUST_AUTHORIZE_FUTURE_INTEGRATION",
    }
    hook["hook_sha256"] = canonical_sha256(hook)
    return hook
