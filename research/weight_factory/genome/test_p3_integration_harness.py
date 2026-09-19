#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import unittest

import p3_integration_harness as h


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def candidate(label: str, *, base_revision: str = "base-rev", layout: str | None = None) -> dict:
    return {
        "artifact_type": "adapter",
        "artifact_stage": "promotion_candidate",
        "manifest_sha256": sha("manifest:" + label),
        "adapter_state_sha256": sha("adapter:" + label),
        "parameter_layout_sha256": layout or sha("layout"),
        "topology_class": "FULL_HYBRID_TEXT",
        "base": {"repo": "Qwen/Qwen3.8-27B", "revision": base_revision, "base_manifest_sha256": sha("base-manifest")},
    }


def evaluation(c: dict, label: str, *, status: str = "PROMOTION_ELIGIBLE") -> dict:
    return {
        "candidate_artifact_manifest_sha256": c["manifest_sha256"],
        "receipt_sha256": sha("eval:" + label),
        "final_status": status,
    }


def ok(_): return []


def gene(label: str, **kwargs) -> h.GeneBinding:
    c = candidate(label, **kwargs)
    return h.bind_promoted_gene(c, evaluation(c, label), candidate_validator=ok, evaluation_validator=ok)


class IdentityTests(unittest.TestCase):
    def test_bind_requires_promotion_eligible(self):
        c = candidate("a")
        with self.assertRaisesRegex(ValueError, "PROMOTION_ELIGIBLE"):
            h.bind_promoted_gene(c, evaluation(c, "a", status="REJECTED"), candidate_validator=ok, evaluation_validator=ok)

    def test_bind_requires_eval_candidate_identity(self):
        c = candidate("a"); e = evaluation(c, "a"); e["candidate_artifact_manifest_sha256"] = sha("foreign")
        with self.assertRaisesRegex(ValueError, "not bound"):
            h.bind_promoted_gene(c, e, candidate_validator=ok, evaluation_validator=ok)

    def test_bank_is_source_order_invariant(self):
        a, b = gene("a"), gene("b")
        self.assertEqual(h.canonicalize_gene_bank([a, b]), h.canonicalize_gene_bank([b, a]))

    def test_bank_rejects_lineage_mismatch(self):
        with self.assertRaisesRegex(ValueError, "base_revision"):
            h.canonicalize_gene_bank([gene("a"), gene("b", base_revision="other")])

    def test_duplicate_gene_rejected(self):
        a = gene("a")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            h.canonicalize_gene_bank([a, a])


class MethodPlanTests(unittest.TestCase):
    def setUp(self):
        self.genes = [gene("b"), gene("a")]

    def test_all_static_controls_emit_dry_run_only_plan(self):
        for method in h.STATIC_METHODS:
            with self.subTest(method=method):
                plan = h.StaticMergeAdapter(method, {"density_ppm": 500000}).dry_run_plan(self.genes)
                self.assertFalse(plan["execution_authorized"])
                self.assertEqual(plan["truth_boundary"], h.TRUTH_BOUNDARY)
                self.assertEqual(plan["source_candidate_manifest_sha256"], sorted(plan["source_candidate_manifest_sha256"]))
                self.assertTrue(h.is_sha(plan["plan_sha256"]))

    def test_float_hyperparameter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "floating-point"):
            h.StaticMergeAdapter("ties", {"density": 0.5})

    def test_hard_router_top1_and_tie_break_are_deterministic(self):
        router = h.HardTop1Router(self.genes)
        a, b = router.ids
        self.assertEqual(router.route({a: 1, b: 2}), b)
        self.assertEqual(router.route({a: 7, b: 7}), min(a, b))

    def test_router_rejects_missing_gene_score(self):
        router = h.HardTop1Router(self.genes)
        with self.assertRaisesRegex(ValueError, "exactly one score"):
            router.route({router.ids[0]: 1})

    def test_oracle_route_ceiling(self):
        oracle = h.OracleRouteCeiling(self.genes)
        a, b = oracle.ids
        self.assertEqual(oracle.select({a: 100, b: 101}), b)

    def test_mopd_cost_accounting_is_exact_integer_sum(self):
        cost = h.CostAccounting(teacher_gpu_millis=11, student_gpu_millis=17, merge_gpu_millis=0, teacher_tokens=31, student_tokens=19)
        plan = h.MOPDExperimentStub({"teacher_selection": "all_promoted_genes"}).dry_run_plan(self.genes, cost)
        self.assertEqual(plan["cost_accounting"]["total_gpu_millis"], 28)
        self.assertEqual(plan["teacher_candidate_manifest_sha256"], sorted(plan["teacher_candidate_manifest_sha256"]))
        self.assertFalse(plan["execution_authorized"])

    def test_negative_cost_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            h.CostAccounting(teacher_gpu_millis=-1)


class ResultSchemaTests(unittest.TestCase):
    def base_payload(self):
        ids = sorted([gene("a").candidate_manifest_sha256, gene("b").candidate_manifest_sha256])
        cost = h.CostAccounting(teacher_gpu_millis=3, student_gpu_millis=5, merge_gpu_millis=7, cpu_millis=11, wall_millis=13, teacher_tokens=17, student_tokens=19, rollout_tokens=23, peak_train_vram_bytes=29, peak_serving_vram_bytes=31)
        return {
            "method_id": "ctm",
            "source_candidate_manifest_sha256": ids,
            "domain_retention": {
                "coding": {"specialist_score_microunits": 900000, "candidate_score_microunits": 880000, "retention_ppm": 977777},
                "tools": {"specialist_score_microunits": 850000, "candidate_score_microunits": 820000, "retention_ppm": 964705},
            },
            "weakest_domain": {"name": "tools", "retention_ppm": 964705},
            "interference": {"report_sha256": sha("interference"), "catastrophic_regression_count": 0},
            "serving": {"ttft_p50_micros": 100, "ttft_p95_micros": 120, "token_p50_micros": 10, "token_p95_micros": 12, "peak_vram_bytes": 1024},
            "quantization_survival": {"status": "NOT_TESTED", "evaluation_report_sha256": None},
            "cost": cost.receipt(),
        }

    def test_valid_result_seals_and_self_validates(self):
        result = h.seal_result(self.base_payload())
        self.assertEqual(h.validate_result(result), [])
        self.assertTrue(h.is_sha(result["result_sha256"]))

    def test_result_tamper_is_detected(self):
        result = h.seal_result(self.base_payload())
        result["weakest_domain"]["retention_ppm"] -= 1
        self.assertIn("result self-digest mismatch", h.validate_result(result))

    def test_quant_pass_requires_report_identity(self):
        payload = self.base_payload(); payload["quantization_survival"] = {"status": "PASS", "evaluation_report_sha256": None}
        with self.assertRaisesRegex(ValueError, "evaluation_report_sha256"):
            h.seal_result(payload)

    def test_cost_total_mismatch_is_rejected(self):
        payload = self.base_payload(); payload["cost"]["total_gpu_millis"] += 1
        with self.assertRaisesRegex(ValueError, "total_gpu_millis mismatch"):
            h.seal_result(payload)

    def test_float_result_is_rejected(self):
        payload = self.base_payload(); payload["serving"]["ttft_p50_micros"] = 1.5
        with self.assertRaisesRegex(ValueError, "ttft_p50_micros"):
            h.seal_result(payload)


class P21InteropTests(unittest.TestCase):
    def test_default_binding_accepts_real_p21_contract_when_available(self):
        try:
            from test_p2_merge_receipt_gate import seal_candidate, seal_eval
        except ImportError:
            self.skipTest("repository P2.1 test helpers are not present in standalone local test directory")
        c = seal_candidate("p3-interop", artifact_stage="promotion_candidate")
        e = seal_eval(c, "p3-interop")
        bound = h.bind_promoted_gene(c, e)
        self.assertEqual(bound.candidate_manifest_sha256, c["manifest_sha256"])
        self.assertEqual(bound.evaluation_receipt_sha256, e["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
