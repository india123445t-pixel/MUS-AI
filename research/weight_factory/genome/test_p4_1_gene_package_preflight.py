#!/usr/bin/env python3
"""P4.1 zero-wait Gene Package preflight using authoritative P2.1 fixtures only."""
from __future__ import annotations

import copy
import hashlib
import unittest

import p4_gene_package as g
from test_p2_merge_receipt_gate import seal_candidate, seal_eval


def h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def runtime_receipt(candidate: dict, label: str) -> dict:
    """Exact Worker-06 Runtime Attempt Receipt V1 field shape, sealed with P2 hash law."""
    receipt = {
        "schema_version": 1,
        "receipt_kind": g.RUNTIME_RECEIPT_KIND,
        "hash_profile": g.HASH_PROFILE,
        "attempt_id": label,
        "task_id": "P4.1-A04-GENE-PACKAGE-PREFLIGHT",
        "candidate_artifact_manifest_sha256": candidate["manifest_sha256"],
        "request_identity": {
            "request_sha256": h("request:" + label),
            "harness_manifest_sha256": h("harness:" + label),
        },
        "transport_outcome": {"status": "success", "failure_code": None},
        "runtime_metrics": {
            "schema": "aqlevon-runtime-metrics-v1",
            "elapsed_ms": "1200.5",
            "compute_device": "synthetic-preflight",
            "gpu_count": 0,
            "allocated_gpu_seconds": 0,
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "total_tokens": 15,
            "cached_prompt_tokens": 0,
            "reasoning_tokens": 0,
            "cached_prompt_ratio": 0,
            "completion_tokens_per_second": "2.5",
            "completion_tokens_per_gpu_second": None,
            "configured_gpu_power_watts": None,
            "configured_gpu_hourly_usd": None,
            "estimated_energy_wh": None,
            "estimated_gpu_cost_usd": None,
        },
        "measurement_provenance": {
            "elapsed_ms_source": "worker_monotonic_clock",
            "token_usage_source": "openai_compatible_backend_usage",
            "gpu_allocation_source": "operator_configured_gpu_count",
            "energy_estimate_source": "unavailable",
            "cost_estimate_source": "unavailable",
        },
        "raw_result_sha256": h("raw:" + label),
    }
    receipt["receipt_sha256"] = g.canonical_sha256(receipt)
    return receipt


def valid_candidate(label: str = "gene1") -> dict:
    return seal_candidate(label, artifact_stage="promotion_candidate")


def valid_package(label: str = "gene1") -> tuple[dict, dict, dict, dict]:
    candidate = valid_candidate(label)
    evaluation = seal_eval(candidate, "eval:" + label)
    compute = runtime_receipt(candidate, "runtime:" + label)
    package = g.seal_gene_package(
        candidate_manifest=candidate,
        evaluation_receipt=evaluation,
        target_capability={
            "capability_id": "coding_tool_use",
            "capability_version": 1,
            "scope": "synthetic P4.1 preflight only",
        },
        manager_acceptance_record_sha256=h("manager-accept:" + label),
        compute_receipts=[compute],
        training_shard_manifest_sha256=candidate["training_shard_manifest_sha256"],
        training_run_receipt_sha256=candidate["training_run_receipt_sha256"],
    )
    return package, candidate, evaluation, compute


def runtime_identity(package: dict, **overrides) -> g.RuntimeBaseIdentity:
    values = {
        "repo": package["base_identity"]["repo"],
        "revision": package["base_identity"]["revision"],
        "base_manifest_sha256": package["base_identity"]["base_manifest_sha256"],
        "tokenizer_sha256": package["base_identity"]["tokenizer_sha256"],
        "config_sha256": package["base_identity"]["config_sha256"],
        "parameter_layout_sha256": package["compatibility"]["parameter_layout_sha256"],
        "topology_class": package["compatibility"]["topology_class"],
    }
    values.update(overrides)
    return g.RuntimeBaseIdentity(**values)


def reseal(package: dict) -> dict:
    out = copy.deepcopy(package)
    out["package_id"] = g.compute_package_id(out)
    out["package_sha256"] = g.compute_package_sha256(out)
    return out


class AuthoritativeFixturePreflight(unittest.TestCase):
    def test_valid_adapter_gene_fixture_matches_authoritative_candidate_and_eval_contracts(self):
        package, candidate, evaluation, compute = valid_package()
        self.assertEqual(g.validate_gene_package(package), [])
        self.assertEqual(package["adapter_identity"]["candidate_artifact_manifest_sha256"], candidate["manifest_sha256"])
        self.assertEqual(package["promotion_binding"]["evaluation_decision_receipt_sha256"], evaluation["receipt_sha256"])
        self.assertEqual(package["compute_binding"]["runtime_attempt_receipt_sha256s"], [compute["receipt_sha256"]])

    def test_wrong_base_revision_cannot_activate(self):
        package, _, _, _ = valid_package()
        with self.assertRaisesRegex(ValueError, "revision"):
            g.prepare_single_gene_activation(package, runtime_identity(package, revision="stale-or-wrong-revision"))

    def test_wrong_parameter_layout_cannot_activate(self):
        package, _, _, _ = valid_package()
        with self.assertRaisesRegex(ValueError, "parameter_layout_sha256"):
            g.prepare_single_gene_activation(
                package,
                runtime_identity(package, parameter_layout_sha256=h("wrong-layout")),
            )

    def test_stale_but_valid_evaluation_receipt_from_other_candidate_is_rejected(self):
        candidate = valid_candidate("current")
        old_candidate = valid_candidate("old")
        stale_eval = seal_eval(old_candidate, "old-eval")
        compute = runtime_receipt(candidate, "runtime-current")
        with self.assertRaisesRegex(ValueError, "evaluation receipt candidate binding mismatch"):
            g.seal_gene_package(
                candidate_manifest=candidate,
                evaluation_receipt=stale_eval,
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager-current"),
                compute_receipts=[compute],
                training_shard_manifest_sha256=candidate["training_shard_manifest_sha256"],
                training_run_receipt_sha256=candidate["training_run_receipt_sha256"],
            )

    def test_mismatched_training_run_receipt_identity_is_rejected(self):
        candidate = valid_candidate()
        evaluation = seal_eval(candidate, "eval")
        compute = runtime_receipt(candidate, "runtime")
        with self.assertRaisesRegex(ValueError, "training run receipt identity"):
            g.seal_gene_package(
                candidate_manifest=candidate,
                evaluation_receipt=evaluation,
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[compute],
                training_shard_manifest_sha256=candidate["training_shard_manifest_sha256"],
                training_run_receipt_sha256=h("foreign-training-run"),
            )

    def test_mismatched_training_shard_identity_is_rejected(self):
        candidate = valid_candidate()
        evaluation = seal_eval(candidate, "eval")
        compute = runtime_receipt(candidate, "runtime")
        with self.assertRaisesRegex(ValueError, "training shard identity"):
            g.seal_gene_package(
                candidate_manifest=candidate,
                evaluation_receipt=evaluation,
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[compute],
                training_shard_manifest_sha256=h("foreign-training-shard"),
                training_run_receipt_sha256=candidate["training_run_receipt_sha256"],
            )

    def test_mismatched_compute_receipt_from_other_candidate_is_rejected(self):
        candidate = valid_candidate("current")
        other = valid_candidate("other")
        evaluation = seal_eval(candidate, "eval-current")
        foreign_compute = runtime_receipt(other, "runtime-other")
        with self.assertRaisesRegex(ValueError, "compute receipt candidate binding mismatch"):
            g.seal_gene_package(
                candidate_manifest=candidate,
                evaluation_receipt=evaluation,
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager-current"),
                compute_receipts=[foreign_compute],
                training_shard_manifest_sha256=candidate["training_shard_manifest_sha256"],
                training_run_receipt_sha256=candidate["training_run_receipt_sha256"],
            )

    def test_invalid_rollback_metadata_rejected_even_after_resealing(self):
        package, _, _, _ = valid_package()
        package["rollback"]["base_is_immutable"] = False
        package = reseal(package)
        self.assertIn("rollback metadata invalid", g.validate_gene_package(package))
        with self.assertRaisesRegex(ValueError, "rollback metadata invalid"):
            g.SingleGeneRouter(package)

    def test_wrong_quantization_declaration_is_rejected(self):
        candidate = valid_candidate()
        evaluation = seal_eval(candidate, "eval")
        compute = runtime_receipt(candidate, "runtime")
        with self.assertRaisesRegex(ValueError, "NOT_TESTED"):
            g.seal_gene_package(
                candidate_manifest=candidate,
                evaluation_receipt=evaluation,
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[compute],
                training_shard_manifest_sha256=candidate["training_shard_manifest_sha256"],
                training_run_receipt_sha256=candidate["training_run_receipt_sha256"],
                quantization_compatibility={
                    "status": "NOT_TESTED",
                    "quantized_candidate_manifest_sha256": h("fake-quant-candidate"),
                    "evaluation_decision_receipt_sha256": h("fake-quant-eval"),
                },
            )

    def test_single_gene_router_never_activates_multi_gene_path(self):
        package, _, _, _ = valid_package()
        router = g.SingleGeneRouter(package)
        route = router.route({"task_family": "coding_tool_use"})
        self.assertFalse(route["multi_gene_routing_authorized"])
        with self.assertRaisesRegex(ValueError, "at least two"):
            g.prepare_gene_pair_integration_hook([package])

    def test_valid_activation_is_explicitly_base_immutable(self):
        package, _, _, _ = valid_package()
        request = g.prepare_single_gene_activation(package, runtime_identity(package))
        self.assertFalse(request["base_mutation_allowed"])
        self.assertFalse(request["multi_gene_routing_authorized"])
        self.assertEqual(request["rollback_action"], g.ROLLBACK_ACTION)


class FalseSuccessAttacks(unittest.TestCase):
    def test_attack_quality_receipt_swap_is_closed(self):
        current = valid_candidate("quality-current")
        old = valid_candidate("quality-old")
        stale_eval = seal_eval(old, "stale")
        compute = runtime_receipt(current, "runtime")
        with self.assertRaises(ValueError):
            g.seal_gene_package(
                candidate_manifest=current,
                evaluation_receipt=stale_eval,
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[compute],
                training_shard_manifest_sha256=current["training_shard_manifest_sha256"],
                training_run_receipt_sha256=current["training_run_receipt_sha256"],
            )

    def test_attack_execution_cost_receipt_swap_is_closed(self):
        current = valid_candidate("cost-current")
        other = valid_candidate("cost-other")
        with self.assertRaises(ValueError):
            g.seal_gene_package(
                candidate_manifest=current,
                evaluation_receipt=seal_eval(current, "eval"),
                target_capability={"capability_id": "coding_tool_use", "capability_version": 1},
                manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[runtime_receipt(other, "foreign-runtime")],
                training_shard_manifest_sha256=current["training_shard_manifest_sha256"],
                training_run_receipt_sha256=current["training_run_receipt_sha256"],
            )

    def test_attack_wrong_base_activation_is_closed(self):
        package, _, _, _ = valid_package("base-attack")
        with self.assertRaises(ValueError):
            g.prepare_single_gene_activation(package, runtime_identity(package, revision="wrong"))


if __name__ == "__main__":
    unittest.main()
