#!/usr/bin/env python3
"""AQLEVON Worker-04 P3 integration tournament dry-run harness.

This module prepares deterministic interfaces for future integration experiments while
explicitly forbidding real AQLEVON gene integration in P3-A04. It never loads model
weights, never merges adapters, never distills, and never claims capability gain.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
HASH_PROFILE = "AQLEVON_CANONICAL_JSON_SHA256_V1"
HARNESS_SCHEMA_VERSION = 1
HARNESS_KIND = "AQLEVON_P3_INTEGRATION_HARNESS_V1"
RESULT_KIND = "AQLEVON_INTEGRATION_TOURNAMENT_RESULT_V1"
TRUTH_BOUNDARY = "DRY_RUN_ONLY_NO_REAL_GENE_INTEGRATION_OR_CAPABILITY_CLAIM"
SUPPORTED_METHODS = ("ties", "dare", "della", "ctm", "hard_top1_router", "oracle_route_ceiling", "mopd")
STATIC_METHODS = ("ties", "dare", "della", "ctm")
QUANTIZATION_STATUSES = ("NOT_TESTED", "PASS", "FAIL", "INVALID")


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def canonical_json_bytes(value: Any) -> bytes:
    """Deterministic local harness encoding; floats are forbidden for auditability."""
    def walk(v: Any) -> Any:
        if v is None or type(v) in (bool, int, str):
            return v
        if isinstance(v, float):
            raise ValueError("floating-point values are forbidden; use integer fixed-point units")
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, tuple):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            if any(not isinstance(k, str) or not k or any(ord(c) >= 128 for c in k) for k in v):
                raise ValueError("object keys must be non-empty ASCII strings")
            return {k: walk(v[k]) for k in sorted(v, key=lambda s: s.encode("ascii"))}
        raise ValueError(f"unsupported canonical value type: {type(v).__name__}")
    return json.dumps(walk(value), ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _default_p2_validators() -> tuple[Callable[[Any], list[str]], Callable[[Any], list[str]]]:
    try:
        from p2_merge_receipt_gate import validate_candidate, validate_eval
    except ImportError as exc:  # pragma: no cover - exercised by repository integration environment
        raise RuntimeError("p2_merge_receipt_gate.py must be importable for authoritative identity validation") from exc
    return validate_candidate, validate_eval


@dataclass(frozen=True)
class GeneBinding:
    candidate_manifest_sha256: str
    evaluation_receipt_sha256: str
    adapter_state_sha256: str
    base_repo: str
    base_revision: str
    base_manifest_sha256: str
    parameter_layout_sha256: str
    topology_class: str

    def identity(self) -> dict[str, Any]:
        return asdict(self)


def bind_promoted_gene(
    candidate_manifest: Mapping[str, Any],
    evaluation_receipt: Mapping[str, Any],
    *,
    candidate_validator: Callable[[Any], list[str]] | None = None,
    evaluation_validator: Callable[[Any], list[str]] | None = None,
) -> GeneBinding:
    """Validate and bind one promoted adapter without loading any adapter bytes."""
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
        raise ValueError("integration harness source must be artifact_type=adapter")
    if candidate_manifest.get("artifact_stage") == "probe_only":
        raise ValueError("probe_only candidate is not an integration gene")
    candidate_sha = candidate_manifest.get("manifest_sha256")
    receipt_sha = evaluation_receipt.get("receipt_sha256")
    adapter_sha = candidate_manifest.get("adapter_state_sha256")
    if not is_sha(candidate_sha) or not is_sha(receipt_sha) or not is_sha(adapter_sha):
        raise ValueError("candidate/evaluation/adapter identity must be lowercase SHA-256")
    if evaluation_receipt.get("candidate_artifact_manifest_sha256") != candidate_sha:
        raise ValueError("evaluation receipt is not bound to candidate manifest")
    if evaluation_receipt.get("final_status") != "PROMOTION_ELIGIBLE":
        raise ValueError("source gene must have final_status=PROMOTION_ELIGIBLE")
    base = candidate_manifest.get("base")
    if not isinstance(base, Mapping):
        raise ValueError("candidate base lineage missing")

    return GeneBinding(
        candidate_manifest_sha256=candidate_sha,
        evaluation_receipt_sha256=receipt_sha,
        adapter_state_sha256=adapter_sha,
        base_repo=str(base.get("repo", "")),
        base_revision=str(base.get("revision", "")),
        base_manifest_sha256=str(base.get("base_manifest_sha256", "")),
        parameter_layout_sha256=str(candidate_manifest.get("parameter_layout_sha256", "")),
        topology_class=str(candidate_manifest.get("topology_class", "")),
    )


def canonicalize_gene_bank(genes: Sequence[GeneBinding]) -> tuple[GeneBinding, ...]:
    if len(genes) < 2:
        raise ValueError("integration tournament requires at least two promoted genes")
    ids = [g.candidate_manifest_sha256 for g in genes]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate manifest identity")
    ordered = tuple(sorted(genes, key=lambda g: g.candidate_manifest_sha256))
    first = ordered[0]
    lineage_fields = ("base_repo", "base_revision", "base_manifest_sha256", "parameter_layout_sha256", "topology_class")
    for gene in ordered[1:]:
        for field in lineage_fields:
            if getattr(gene, field) != getattr(first, field):
                raise ValueError(f"gene lineage mismatch: {field}")
    return ordered


@dataclass(frozen=True)
class CostAccounting:
    teacher_gpu_millis: int = 0
    student_gpu_millis: int = 0
    merge_gpu_millis: int = 0
    cpu_millis: int = 0
    wall_millis: int = 0
    teacher_tokens: int = 0
    student_tokens: int = 0
    rollout_tokens: int = 0
    peak_train_vram_bytes: int = 0
    peak_serving_vram_bytes: int = 0

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(f"cost.{name} must be a non-negative integer")

    @property
    def total_gpu_millis(self) -> int:
        return self.teacher_gpu_millis + self.student_gpu_millis + self.merge_gpu_millis

    def receipt(self) -> dict[str, int]:
        out = asdict(self)
        out["total_gpu_millis"] = self.total_gpu_millis
        return out


class IntegrationMethodAdapter:
    method_id: str
    requires_training: bool

    def __init__(self, method_id: str, *, requires_training: bool, config: Mapping[str, Any] | None = None):
        if method_id not in SUPPORTED_METHODS:
            raise ValueError(f"unsupported method: {method_id}")
        self.method_id = method_id
        self.requires_training = requires_training
        self.config = dict(config or {})
        canonical_json_bytes(self.config)  # fail early on floats/non-canonical types

    def dry_run_plan(self, genes: Sequence[GeneBinding]) -> dict[str, Any]:
        bank = canonicalize_gene_bank(genes)
        plan = {
            "schema_version": HARNESS_SCHEMA_VERSION,
            "harness_kind": HARNESS_KIND,
            "truth_boundary": TRUTH_BOUNDARY,
            "execution_authorized": False,
            "method_id": self.method_id,
            "requires_training": self.requires_training,
            "source_candidate_manifest_sha256": [g.candidate_manifest_sha256 for g in bank],
            "source_evaluation_receipt_sha256": [g.evaluation_receipt_sha256 for g in bank],
            "source_adapter_state_sha256": [g.adapter_state_sha256 for g in bank],
            "shared_lineage": {
                "base_repo": bank[0].base_repo,
                "base_revision": bank[0].base_revision,
                "base_manifest_sha256": bank[0].base_manifest_sha256,
                "parameter_layout_sha256": bank[0].parameter_layout_sha256,
                "topology_class": bank[0].topology_class,
            },
            "config": self.config,
        }
        plan["plan_sha256"] = canonical_sha256(plan)
        return plan


class StaticMergeAdapter(IntegrationMethodAdapter):
    """Dry-run interface for TIES/DARE/DELLA/CtM. No tensor mutation occurs here."""
    def __init__(self, method_id: str, config: Mapping[str, Any] | None = None):
        if method_id not in STATIC_METHODS:
            raise ValueError("StaticMergeAdapter supports ties/dare/della/ctm only")
        super().__init__(method_id, requires_training=False, config=config)


class HardTop1Router:
    """Deterministic top-1 route selection over precomputed integer route scores."""
    def __init__(self, genes: Sequence[GeneBinding]):
        self.genes = canonicalize_gene_bank(genes)
        self.ids = tuple(g.candidate_manifest_sha256 for g in self.genes)

    def route(self, route_scores: Mapping[str, int]) -> str:
        if set(route_scores) != set(self.ids):
            raise ValueError("route_scores must contain exactly one score per admitted gene")
        for gene_id, score in route_scores.items():
            if type(score) is not int:
                raise ValueError(f"route score for {gene_id} must be an integer")
        # Lexicographic identity is the deterministic tie-breaker.
        return min(self.ids, key=lambda gene_id: (-route_scores[gene_id], gene_id))


class OracleRouteCeiling:
    """Evaluation-only ceiling: picks the expert with the highest clean verified outcome."""
    def __init__(self, genes: Sequence[GeneBinding]):
        self.genes = canonicalize_gene_bank(genes)
        self.ids = tuple(g.candidate_manifest_sha256 for g in self.genes)

    def select(self, clean_verified_score_microunits: Mapping[str, int]) -> str:
        if set(clean_verified_score_microunits) != set(self.ids):
            raise ValueError("oracle scores must contain exactly one score per admitted gene")
        for value in clean_verified_score_microunits.values():
            if type(value) is not int:
                raise ValueError("oracle clean scores must use integer microunits")
        return min(self.ids, key=lambda gene_id: (-clean_verified_score_microunits[gene_id], gene_id))


class MOPDExperimentStub(IntegrationMethodAdapter):
    """No-training MOPD interface with explicit teacher/student cost-accounting hooks."""
    def __init__(self, config: Mapping[str, Any] | None = None):
        super().__init__("mopd", requires_training=True, config=config)

    def dry_run_plan(self, genes: Sequence[GeneBinding], cost: CostAccounting | None = None) -> dict[str, Any]:
        plan = super().dry_run_plan(genes)
        plan["teacher_candidate_manifest_sha256"] = list(plan["source_candidate_manifest_sha256"])
        plan["student_initialization"] = "shared_exact_base"
        plan["cost_accounting"] = (cost or CostAccounting()).receipt()
        plan["plan_sha256"] = canonical_sha256({k: v for k, v in plan.items() if k != "plan_sha256"})
        return plan


def validate_result(result: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, Mapping):
        return ["result must be an object"]
    if result.get("schema_version") != 1:
        errors.append("schema_version mismatch")
    if result.get("result_kind") != RESULT_KIND:
        errors.append("result_kind mismatch")
    if result.get("hash_profile") != HASH_PROFILE:
        errors.append("hash_profile mismatch")
    if result.get("truth_boundary") not in (TRUTH_BOUNDARY, "REAL_EXECUTION_REQUIRES_MANAGER_AUTHORIZED_EVIDENCE"):
        errors.append("truth_boundary invalid")
    if result.get("method_id") not in SUPPORTED_METHODS:
        errors.append("method_id invalid")

    sources = result.get("source_candidate_manifest_sha256")
    if not isinstance(sources, list) or len(sources) < 2 or any(not is_sha(x) for x in sources):
        errors.append("source candidate identities invalid")
    elif sources != sorted(sources) or len(sources) != len(set(sources)):
        errors.append("source candidate identities must be unique and lexicographically sorted")

    domains = result.get("domain_retention")
    if not isinstance(domains, dict) or not domains:
        errors.append("domain_retention missing")
    else:
        for domain, row in domains.items():
            if not isinstance(domain, str) or not domain or not isinstance(row, dict):
                errors.append("domain_retention entry invalid")
                continue
            for field in ("specialist_score_microunits", "candidate_score_microunits", "retention_ppm"):
                if type(row.get(field)) is not int or row[field] < 0:
                    errors.append(f"domain_retention.{domain}.{field} invalid")

    weakest = result.get("weakest_domain")
    if not isinstance(weakest, dict) or not isinstance(weakest.get("name"), str) or not weakest.get("name") or type(weakest.get("retention_ppm")) is not int:
        errors.append("weakest_domain invalid")

    interference = result.get("interference")
    if not isinstance(interference, dict) or not is_sha(interference.get("report_sha256")) or type(interference.get("catastrophic_regression_count")) is not int or interference.get("catastrophic_regression_count", -1) < 0:
        errors.append("interference invalid")

    serving = result.get("serving")
    if not isinstance(serving, dict):
        errors.append("serving missing")
    else:
        for field in ("ttft_p50_micros", "ttft_p95_micros", "token_p50_micros", "token_p95_micros", "peak_vram_bytes"):
            if type(serving.get(field)) is not int or serving[field] < 0:
                errors.append(f"serving.{field} invalid")

    quant = result.get("quantization_survival")
    if not isinstance(quant, dict) or quant.get("status") not in QUANTIZATION_STATUSES:
        errors.append("quantization_survival invalid")
    elif quant.get("status") in ("PASS", "FAIL") and not is_sha(quant.get("evaluation_report_sha256")):
        errors.append("quantization_survival evaluated status requires evaluation_report_sha256")

    cost = result.get("cost")
    if not isinstance(cost, dict):
        errors.append("cost missing")
    else:
        required_cost = ("teacher_gpu_millis", "student_gpu_millis", "merge_gpu_millis", "total_gpu_millis", "cpu_millis", "wall_millis", "teacher_tokens", "student_tokens", "rollout_tokens", "peak_train_vram_bytes", "peak_serving_vram_bytes")
        for field in required_cost:
            if type(cost.get(field)) is not int or cost[field] < 0:
                errors.append(f"cost.{field} invalid")
        if all(type(cost.get(f)) is int for f in ("teacher_gpu_millis", "student_gpu_millis", "merge_gpu_millis", "total_gpu_millis")):
            expected = cost["teacher_gpu_millis"] + cost["student_gpu_millis"] + cost["merge_gpu_millis"]
            if cost["total_gpu_millis"] != expected:
                errors.append("cost.total_gpu_millis mismatch")

    digest = result.get("result_sha256")
    if not is_sha(digest):
        errors.append("result_sha256 invalid")
    else:
        try:
            expected = canonical_sha256({k: v for k, v in result.items() if k != "result_sha256"})
            if digest != expected:
                errors.append("result self-digest mismatch")
        except ValueError as exc:
            errors.append(f"result canonicalization invalid: {exc}")
    return errors


def seal_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("schema_version", 1)
    out.setdefault("result_kind", RESULT_KIND)
    out.setdefault("hash_profile", HASH_PROFILE)
    out.setdefault("truth_boundary", TRUTH_BOUNDARY)

    # Validate structural/unit errors before canonical hashing so callers receive the
    # specific offending field instead of only a generic canonicalization failure.
    probe = dict(out)
    probe["result_sha256"] = "0" * 64
    pre_errors = [
        e for e in validate_result(probe)
        if e != "result self-digest mismatch" and not e.startswith("result canonicalization invalid:")
    ]
    if pre_errors:
        raise ValueError("cannot seal invalid integration result: " + "; ".join(pre_errors))

    out["result_sha256"] = canonical_sha256(out)
    errors = validate_result(out)
    if errors:
        raise ValueError("cannot seal invalid integration result: " + "; ".join(errors))
    return out


def method_adapter(method_id: str, config: Mapping[str, Any] | None = None) -> IntegrationMethodAdapter:
    if method_id in STATIC_METHODS:
        return StaticMergeAdapter(method_id, config)
    if method_id == "mopd":
        return MOPDExperimentStub(config)
    if method_id in ("hard_top1_router", "oracle_route_ceiling"):
        return IntegrationMethodAdapter(method_id, requires_training=False, config=config)
    raise ValueError(f"unsupported method: {method_id}")
