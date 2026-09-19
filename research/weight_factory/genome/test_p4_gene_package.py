#!/usr/bin/env python3
from __future__ import annotations
import hashlib
from pathlib import Path
import tempfile
import unittest

import p4_gene_package as g


def h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def ok(_): return []


def candidate(label: str = "gene1", *, revision: str = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0", layout: str | None = None, artifact_files=None) -> dict:
    artifact_files = artifact_files or [{"path": "adapter_model.safetensors", "size": 4, "sha256": hashlib.sha256(b"gene").hexdigest()}]
    return {
        "artifact_type": "adapter",
        "artifact_stage": "promotion_candidate",
        "manifest_sha256": h("manifest:" + label),
        "adapter_state_sha256": h("adapter:" + label),
        "training_shard_manifest_sha256": h("shard:" + label),
        "training_run_receipt_sha256": h("training:" + label),
        "tokenizer_sha256": h("tokenizer"),
        "config_sha256": h("config"),
        "parameter_layout_sha256": layout or h("layout"),
        "topology_class": "FULL_HYBRID_TEXT",
        "artifact_files": artifact_files,
        "artifact_file_tree_sha256": h("tree:" + label),
        "base": {"repo": "Qwen/Qwen3.8-27B", "revision": revision, "base_manifest_sha256": h("base-manifest")},
    }


def evaluation(c: dict, label: str = "gene1", status: str = "PROMOTION_ELIGIBLE") -> dict:
    return {
        "receipt_kind": g.EVAL_RECEIPT_KIND,
        "candidate_artifact_manifest_sha256": c["manifest_sha256"],
        "receipt_sha256": h("eval:" + label),
        "final_status": status,
    }


def compute_receipt(c: dict, label: str = "attempt1", status: str = "success") -> dict:
    receipt = {
        "schema_version": 1,
        "receipt_kind": g.RUNTIME_RECEIPT_KIND,
        "hash_profile": g.HASH_PROFILE,
        "attempt_id": label,
        "task_id": "gene1-training",
        "candidate_artifact_manifest_sha256": c["manifest_sha256"],
        "request_identity": {"request_sha256": h("request:" + label), "harness_manifest_sha256": h("harness")},
        "transport_outcome": {"status": status, "failure_code": None if status == "success" else "OOM"},
        "runtime_metrics": {
            "schema": "aqlevon-runtime-metrics-v1",
            "elapsed_ms": "1200.5",
            "compute_device": "A100-SXM4-80GB",
            "gpu_count": 1,
            "allocated_gpu_seconds": "1.2005",
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "cached_prompt_tokens": 0,
            "reasoning_tokens": 0,
            "cached_prompt_ratio": "0",
            "completion_tokens_per_second": "16.66",
            "completion_tokens_per_gpu_second": "16.66",
            "configured_gpu_power_watts": 400,
            "configured_gpu_hourly_usd": "2.5",
            "estimated_energy_wh": "0.1333",
            "estimated_gpu_cost_usd": "0.00083368",
        },
        "measurement_provenance": {
            "elapsed_ms_source": "worker_monotonic_clock",
            "token_usage_source": "backend_usage",
            "gpu_allocation_source": "operator_configured_gpu_count",
            "energy_estimate_source": "configured_power_x_allocated_gpu_seconds",
            "cost_estimate_source": "configured_rate_x_allocated_gpu_seconds",
        },
        "raw_result_sha256": h("raw:" + label),
    }
    receipt["receipt_sha256"] = g.canonical_sha256(receipt)
    return receipt


def package(label: str = "gene1", **candidate_kwargs) -> tuple[dict, dict]:
    c = candidate(label, **candidate_kwargs)
    p = g.seal_gene_package(
        candidate_manifest=c,
        evaluation_receipt=evaluation(c, label),
        target_capability={"capability_id": "coding_tool_use", "capability_version": 1, "scope": "Gene #1"},
        manager_acceptance_record_sha256=h("manager-accept:" + label),
        compute_receipts=[compute_receipt(c, label + ":1")],
        candidate_validator=ok,
        evaluation_validator=ok,
    )
    return p, c


class PackageSealTests(unittest.TestCase):
    def test_valid_package_seals_and_validates(self):
        p, _ = package()
        self.assertEqual(g.validate_gene_package(p), [])
        self.assertTrue(g.is_sha(p["package_sha256"]))
        self.assertTrue(p["package_id"].startswith(g.PACKAGE_ID_PREFIX))
        self.assertEqual(p["promotion_binding"]["worker05_status"], "PROMOTION_ELIGIBLE")
        self.assertFalse(p["integration_hook"]["real_multi_gene_integration_authorized"])

    def test_worker05_rejection_cannot_be_packaged(self):
        c = candidate()
        with self.assertRaisesRegex(ValueError, "PROMOTION_ELIGIBLE"):
            g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c, status="REJECTED"), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("mgr"), compute_receipts=[compute_receipt(c)], candidate_validator=ok, evaluation_validator=ok)

    def test_manager_acceptance_record_is_required(self):
        c = candidate()
        with self.assertRaisesRegex(ValueError, "Manager acceptance"):
            g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256="not-a-sha", compute_receipts=[compute_receipt(c)], candidate_validator=ok, evaluation_validator=ok)

    def test_compute_receipt_must_bind_same_candidate(self):
        c = candidate(); other = candidate("other")
        with self.assertRaisesRegex(ValueError, "candidate binding mismatch"):
            g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("mgr"), compute_receipts=[compute_receipt(other)], candidate_validator=ok, evaluation_validator=ok)

    def test_compute_receipt_tamper_is_rejected(self):
        c = candidate(); r = compute_receipt(c); r["runtime_metrics"]["gpu_count"] = 2
        with self.assertRaisesRegex(ValueError, "self-digest mismatch"):
            g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("mgr"), compute_receipts=[r], candidate_validator=ok, evaluation_validator=ok)

    def test_training_receipts_are_required(self):
        c = candidate(); c["training_run_receipt_sha256"] = None
        with self.assertRaisesRegex(ValueError, "training shard"):
            g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("mgr"), compute_receipts=[compute_receipt(c)], candidate_validator=ok, evaluation_validator=ok)

    def test_package_tamper_is_detected(self):
        p, _ = package(); p["target_capability"]["scope"] = "tampered"
        errors = g.validate_gene_package(p)
        self.assertTrue("package_id mismatch" in errors or "package self-digest mismatch" in errors)

    def test_quantization_not_tested_cannot_claim_hashes(self):
        c = candidate()
        with self.assertRaisesRegex(ValueError, "NOT_TESTED"):
            g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("mgr"), compute_receipts=[compute_receipt(c)], quantization_compatibility={"status":"NOT_TESTED","quantized_candidate_manifest_sha256":h("q"),"evaluation_decision_receipt_sha256":None}, candidate_validator=ok, evaluation_validator=ok)

    def test_quantization_pass_requires_bound_evidence(self):
        c = candidate()
        p = g.seal_gene_package(candidate_manifest=c, evaluation_receipt=evaluation(c), target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("mgr"), compute_receipts=[compute_receipt(c)], quantization_compatibility={"status":"PASS","quantized_candidate_manifest_sha256":h("q-candidate"),"evaluation_decision_receipt_sha256":h("q-eval")}, candidate_validator=ok, evaluation_validator=ok)
        self.assertEqual(p["compatibility"]["quantization"]["status"], "PASS")


class ActivationTests(unittest.TestCase):
    def runtime(self, p: dict, **overrides) -> g.RuntimeBaseIdentity:
        base = p["base_identity"]
        values = dict(repo=base["repo"], revision=base["revision"], base_manifest_sha256=base["base_manifest_sha256"], tokenizer_sha256=base["tokenizer_sha256"], config_sha256=base["config_sha256"], parameter_layout_sha256=p["compatibility"]["parameter_layout_sha256"], topology_class=p["compatibility"]["topology_class"])
        values.update(overrides)
        return g.RuntimeBaseIdentity(**values)

    def test_single_gene_activation_is_reversible_and_base_immutable(self):
        p, _ = package(); req = g.prepare_single_gene_activation(p, self.runtime(p))
        self.assertFalse(req["base_mutation_allowed"])
        self.assertFalse(req["multi_gene_routing_authorized"])
        self.assertEqual(req["rollback_action"], g.ROLLBACK_ACTION)
        self.assertTrue(g.is_sha(req["request_sha256"]))

    def test_wrong_base_revision_is_rejected(self):
        p, _ = package()
        with self.assertRaisesRegex(ValueError, "revision"):
            g.prepare_single_gene_activation(p, self.runtime(p, revision="wrong"))

    def test_wrong_layout_is_rejected(self):
        p, _ = package()
        with self.assertRaisesRegex(ValueError, "parameter_layout_sha256"):
            g.prepare_single_gene_activation(p, self.runtime(p, parameter_layout_sha256=h("wrong-layout")))

    def test_wrong_base_manifest_is_rejected(self):
        p, _ = package()
        with self.assertRaisesRegex(ValueError, "base_manifest_sha256"):
            g.prepare_single_gene_activation(p, self.runtime(p, base_manifest_sha256=h("wrong-base")))

    def test_artifact_bytes_can_be_verified_before_activation(self):
        data = b"gene"
        files = [{"path":"adapter_model.safetensors","size":len(data),"sha256":hashlib.sha256(data).hexdigest()}]
        p, c = package(artifact_files=files)
        with tempfile.TemporaryDirectory() as td:
            Path(td, "adapter_model.safetensors").write_bytes(data)
            req = g.prepare_single_gene_activation(p, self.runtime(p), artifact_root=td, candidate_manifest=c)
            self.assertTrue(req["artifact_bytes_verified"])

    def test_artifact_extra_file_is_rejected(self):
        data = b"gene"; files = [{"path":"adapter_model.safetensors","size":len(data),"sha256":hashlib.sha256(data).hexdigest()}]
        p, c = package(artifact_files=files)
        with tempfile.TemporaryDirectory() as td:
            Path(td, "adapter_model.safetensors").write_bytes(data); Path(td, "extra.txt").write_text("x")
            with self.assertRaisesRegex(ValueError, "unbound files"):
                g.prepare_single_gene_activation(p, self.runtime(p), artifact_root=td, candidate_manifest=c)

    def test_loader_rejects_tampered_package_on_disk(self):
        p, _ = package()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td, "gene_package.json")
            import json
            path.write_text(json.dumps(p), encoding="utf-8")
            loaded = g.load_gene_package(path)
            self.assertEqual(loaded["package_sha256"], p["package_sha256"])
            p["target_capability"]["scope"] = "tampered"
            path.write_text(json.dumps(p), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "package"):
                g.load_gene_package(path)

    def test_single_gene_router_has_no_multi_gene_authority(self):
        p, _ = package()
        router = g.SingleGeneRouter(p)
        route = router.route({"task_family": "coding"})
        self.assertEqual(route["gene_package_sha256"], p["package_sha256"])
        self.assertFalse(route["multi_gene_routing_authorized"])
        self.assertTrue(g.is_sha(route["route_sha256"]))


class FutureIntegrationHookTests(unittest.TestCase):
    def test_one_gene_cannot_open_multi_gene_tournament(self):
        p, _ = package()
        with self.assertRaisesRegex(ValueError, "at least two"):
            g.prepare_gene_pair_integration_hook([p])

    def test_two_compatible_packages_only_emit_dormant_hook(self):
        p1, _ = package("gene1"); p2, _ = package("gene2")
        hook = g.prepare_gene_pair_integration_hook([p2, p1])
        self.assertFalse(hook["real_integration_authorized"])
        self.assertIn("ctm", hook["methods_dormant"])
        self.assertEqual(hook["gene_package_sha256s"], sorted(hook["gene_package_sha256s"]))
        self.assertTrue(g.is_sha(hook["hook_sha256"]))

    def test_gene_pair_layout_mismatch_is_rejected(self):
        p1, _ = package("gene1"); p2, _ = package("gene2", layout=h("different-layout"))
        with self.assertRaisesRegex(ValueError, "parameter_layout_sha256"):
            g.prepare_gene_pair_integration_hook([p1, p2])

    def test_gene_pair_revision_mismatch_is_rejected(self):
        p1, _ = package("gene1"); p2, _ = package("gene2", revision="different-revision")
        with self.assertRaisesRegex(ValueError, "base_identity"):
            g.prepare_gene_pair_integration_hook([p1, p2])


class P21InteropTests(unittest.TestCase):
    def test_real_p21_candidate_and_eval_contract_when_repository_helpers_exist(self):
        try:
            from test_p2_merge_receipt_gate import seal_candidate, seal_eval
        except ImportError:
            self.skipTest("repository P2.1 helper module absent in standalone local test directory")
        c = seal_candidate("p4-package-interop", artifact_stage="promotion_candidate")
        e = seal_eval(c, "p4-package-interop")
        r = compute_receipt(c, "p4-interop-attempt")
        p = g.seal_gene_package(candidate_manifest=c, evaluation_receipt=e, target_capability={"capability_id":"coding_tool_use","capability_version":1}, manager_acceptance_record_sha256=h("manager-accept-interop"), compute_receipts=[r])
        self.assertEqual(g.validate_gene_package(p), [])


if __name__ == "__main__":
    unittest.main()
