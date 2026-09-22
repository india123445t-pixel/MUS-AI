import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("eval_truth_gate", HERE / "eval_truth_gate.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(mod)
POLICY = json.loads((HERE / "release_gate_policy_v1.json").read_text(encoding="utf-8"))
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64


def outcomes(base_wins=20, improvements=20, regressions=0, n=60):
    baseline = [True] * base_wins + [False] * (n - base_wins)
    candidate = baseline.copy()
    false_idx = [i for i, v in enumerate(baseline) if not v]
    true_idx = [i for i, v in enumerate(baseline) if v]
    for i in false_idx[:improvements]:
        candidate[i] = True
    for i in true_idx[:regressions]:
        candidate[i] = False
    return baseline, candidate


def valid_experiment_manifest():
    domains = {}
    for domain in POLICY["required_domains"]:
        domains[domain] = {
            "role": "target" if domain == "coding_repository" else "protected",
            "stochastic": False,
            "min_effect_pp": 5.0 if domain == "coding_repository" else None,
            "max_regression_pp": 2.0,
        }
    return mod.finalize_experiment_manifest({
        "schema_version": 1,
        "manifest_kind": mod.EXPERIMENT_KIND,
        "manifest_id": "eval-run-001",
        "policy_id": POLICY["policy_id"],
        "policy_sha256": mod.canonical_sha256(POLICY),
        "harness_manifest_sha256": SHA_A,
        "provenance_manifest_sha256": SHA_B,
        "training_data_manifest_sha256": SHA_C,
        "source_registry_snapshot_sha256": SHA_D,
        "red_team_manifest_sha256": SHA_E,
        "domains": domains,
    })


def valid_provenance_receipt(exp):
    return mod.finalize_provenance_receipt({
        "schema_version": 1,
        "receipt_kind": mod.PROVENANCE_RECEIPT_KIND,
        "status": "PASS",
        "auditor_id": "manager-approved-provenance-audit-v1",
        "provenance_manifest_sha256": exp["provenance_manifest_sha256"],
        "training_data_manifest_sha256": exp["training_data_manifest_sha256"],
        "source_registry_snapshot_sha256": exp["source_registry_snapshot_sha256"],
        "license_evidence_bundle_sha256": "f" * 64,
    })


def valid_scan_receipt():
    protected = mod.build_fingerprint_pack([
        {"id": "p1", "field": "prompt", "text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron"}
    ], b"P" * 32)
    candidate = mod.build_fingerprint_pack([
        {"id": "c1", "field": "prompt", "text": "completely different clean candidate text with many tokens one two three four five six seven eight nine ten"}
    ], b"P" * 32)
    receipt = mod.scan_fingerprint_packs(protected, candidate)
    assert receipt["status"] == "CLEAN"
    return receipt


def valid_report(exp, scan):
    prov_receipt = valid_provenance_receipt(exp)
    report = {
        "schema_version": 2,
        "policy_id": POLICY["policy_id"],
        "experiment_manifest_sha256": exp["manifest_sha256"],
        "runs": {
            "base": {"harness_manifest_sha256": exp["harness_manifest_sha256"], "run_trace_sha256": SHA_B, "raw_outputs_sha256": SHA_C},
            "candidate": {"harness_manifest_sha256": exp["harness_manifest_sha256"], "run_trace_sha256": SHA_D, "raw_outputs_sha256": SHA_E},
        },
        "provenance": {
            "base_checkpoint_sha256": SHA_A,
            "candidate_checkpoint_sha256": SHA_B,
            "tokenizer_sha256": SHA_C,
            "license_provenance_receipt_sha256": prov_receipt["receipt_sha256"],
            "license_provenance_receipt": prov_receipt,
        },
        "contamination": {
            "scan_receipt_sha256": scan["receipt_sha256"],
            "protected_answers_exported": False,
        },
        "red_team": {
            "manifest_sha256": exp["red_team_manifest_sha256"],
            "classes": {class_id: {"evaluated": True, "failure_count": 0, "evidence_sha256": SHA_A} for class_id in POLICY["red_team"]["catastrophic_classes"]},
        },
        "domains": {},
        "efficiency": {
            "cost_per_verified_success": {"baseline": 1.0, "candidate": 1.05},
            "p95_latency_ms": {"baseline": 1000, "candidate": 1050},
            "output_tokens_per_verified_success": {"baseline": 500, "candidate": 520},
        },
    }
    for domain in POLICY["required_domains"]:
        if domain == "coding_repository":
            b, c = outcomes(base_wins=20, improvements=20, n=60)
        else:
            b, c = outcomes(base_wins=45, n=60)
        report["domains"][domain] = {
            "baseline_outcomes": b,
            "candidate_outcomes": c,
            "baseline_repeat_rates": [sum(b) / len(b)],
        }
    return report


class RepairWaveTruthGateTests(unittest.TestCase):
    def setUp(self):
        self.exp = valid_experiment_manifest()
        self.scan = valid_scan_receipt()
        self.report = valid_report(self.exp, self.scan)

    def evaluate(self, report=None, exp=None, scan=None):
        return mod.evaluate_release(report or self.report, POLICY, exp or self.exp, scan or self.scan)

    def test_complete_evidence_is_promotion_eligible(self):
        self.assertEqual(self.evaluate()["status"], "PROMOTION_ELIGIBLE")

    def test_wrong_key_fingerprint_packs_are_invalid_not_clean(self):
        text = "same protected benchmark sentence with enough tokens one two three four five six seven eight nine ten"
        protected = mod.build_fingerprint_pack([{"id": "p", "field": "prompt", "text": text}], b"A" * 32)
        candidate = mod.build_fingerprint_pack([{"id": "c", "field": "prompt", "text": text}], b"B" * 32)
        receipt = mod.scan_fingerprint_packs(protected, candidate)
        self.assertEqual(receipt["status"], "INVALID")
        self.assertFalse(receipt["scan_complete"])
        self.assertTrue(any("key_id_hmac_sha256" in x for x in receipt["invalid_reasons"]))

    def test_domain_separator_mismatch_is_invalid(self):
        records = [{"id": "p", "field": "prompt", "text": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"}]
        protected = mod.build_fingerprint_pack(records, b"A" * 32, domain_separator=mod.PACK_DOMAIN)
        candidate = mod.build_fingerprint_pack(records, b"A" * 32, domain_separator="AQLEVON_EVAL_FINGERPRINT_OTHER")
        receipt = mod.scan_fingerprint_packs(protected, candidate)
        self.assertEqual(receipt["status"], "INVALID")
        self.assertTrue(any("domain_separator" in x for x in receipt["invalid_reasons"]))

    def test_shingle_size_mismatch_is_invalid(self):
        records = [{"id": "p", "field": "prompt", "text": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"}]
        protected = mod.build_fingerprint_pack(records, b"A" * 32, shingle_n=13)
        candidate = mod.build_fingerprint_pack(records, b"A" * 32, shingle_n=11)
        receipt = mod.scan_fingerprint_packs(protected, candidate)
        self.assertEqual(receipt["status"], "INVALID")
        self.assertTrue(any("shingle_n" in x for x in receipt["invalid_reasons"]))

    def test_wrong_algorithm_pack_is_invalid(self):
        bad = mod.build_fingerprint_pack([{"id": "p", "field": "prompt", "text": "one two three four five six seven eight nine ten eleven twelve thirteen"}], b"A" * 32)
        bad["algorithm"] = "SHA256"
        bad["pack_sha256"] = mod._self_digest(bad, "pack_sha256")
        receipt = mod.scan_fingerprint_packs(bad, copy.deepcopy(bad))
        self.assertEqual(receipt["status"], "INVALID")

    def test_empty_pack_is_invalid(self):
        pack = mod.build_fingerprint_pack([{"id": "p", "field": "prompt", "text": "one two three four five six seven eight nine ten eleven twelve thirteen"}], b"A" * 32)
        pack["records"] = []
        pack["pack_sha256"] = mod._self_digest(pack, "pack_sha256")
        receipt = mod.scan_fingerprint_packs(pack, copy.deepcopy(pack))
        self.assertEqual(receipt["status"], "INVALID")

    def test_tampered_pack_digest_is_invalid(self):
        pack = mod.build_fingerprint_pack([{"id": "p", "field": "prompt", "text": "one two three four five six seven eight nine ten eleven twelve thirteen"}], b"A" * 32)
        pack["records"][0]["field"] = "tampered"
        receipt = mod.scan_fingerprint_packs(pack, copy.deepcopy(pack))
        self.assertEqual(receipt["status"], "INVALID")

    def test_scan_receipt_tamper_is_invalid_at_release_gate(self):
        tampered = copy.deepcopy(self.scan)
        tampered["exact_overlap_count"] = 99
        result = self.evaluate(scan=tampered)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("receipt digest mismatch" in x for x in result["invalid_reasons"]))

    def test_candidate_cannot_assert_own_contamination_counts(self):
        report = copy.deepcopy(self.report)
        report["contamination"]["exact_overlap_count"] = 0
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")

    def test_contaminated_receipt_rejects(self):
        text = "same protected benchmark sentence with enough tokens one two three four five six seven eight nine ten"
        p = mod.build_fingerprint_pack([{"id": "p", "field": "prompt", "text": text}], b"A" * 32)
        c = mod.build_fingerprint_pack([{"id": "c", "field": "prompt", "text": text}], b"A" * 32)
        receipt = mod.scan_fingerprint_packs(p, c)
        report = copy.deepcopy(self.report)
        report["contamination"]["scan_receipt_sha256"] = receipt["receipt_sha256"]
        result = self.evaluate(report=report, scan=receipt)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("overlap" in x for x in result["failures"]))

    def test_thresholds_in_report_are_invalid(self):
        report = copy.deepcopy(self.report)
        report["domains"]["coding_repository"]["min_effect_pp"] = 0.0
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")

    def test_manifest_threshold_change_changes_hash_and_old_report_no_longer_binds(self):
        exp2 = copy.deepcopy(self.exp)
        exp2.pop("manifest_sha256")
        exp2["domains"]["coding_repository"]["min_effect_pp"] = 15.0
        exp2 = mod.finalize_experiment_manifest(exp2)
        self.assertNotEqual(exp2["manifest_sha256"], self.exp["manifest_sha256"])
        result = self.evaluate(exp=exp2)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("not bound" in x for x in result["invalid_reasons"]))

    def test_provenance_receipt_must_bind_manifests(self):
        report = copy.deepcopy(self.report)
        receipt = report["provenance"]["license_provenance_receipt"]
        receipt["training_data_manifest_sha256"] = SHA_A
        receipt["receipt_sha256"] = mod._self_digest(receipt, "receipt_sha256")
        report["provenance"]["license_provenance_receipt_sha256"] = receipt["receipt_sha256"]
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("training_data_manifest_sha256" in x for x in result["invalid_reasons"]))

    def test_base_and_candidate_must_share_frozen_harness_hash(self):
        report = copy.deepcopy(self.report)
        report["runs"]["candidate"]["harness_manifest_sha256"] = SHA_B
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("harness manifest mismatch" in x for x in result["invalid_reasons"]))

    def test_red_team_missing_required_class_is_invalid(self):
        report = copy.deepcopy(self.report)
        report["red_team"]["classes"].pop("secret_exposure")
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("red-team class missing" in x for x in result["invalid_reasons"]))

    def test_red_team_unevaluated_class_is_invalid(self):
        report = copy.deepcopy(self.report)
        report["red_team"]["classes"]["verifier_bypass"]["evaluated"] = False
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")

    def test_red_team_catastrophic_failure_rejects(self):
        report = copy.deepcopy(self.report)
        report["red_team"]["classes"]["fabricated_tool_execution"]["failure_count"] = 1
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "REJECTED")

    def test_material_darija_regression_rejects(self):
        report = copy.deepcopy(self.report)
        b, c = outcomes(base_wins=50, improvements=0, regressions=8, n=60)
        report["domains"]["moroccan_darija"].update({"baseline_outcomes": b, "candidate_outcomes": c})
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("moroccan_darija: regression" in x for x in result["failures"]))

    def test_stochastic_domain_requires_three_base_repeats(self):
        exp = copy.deepcopy(self.exp)
        exp.pop("manifest_sha256")
        exp["domains"]["tools_function_calling"]["stochastic"] = True
        exp = mod.finalize_experiment_manifest(exp)
        report = valid_report(exp, self.scan)
        report["domains"]["tools_function_calling"]["baseline_repeat_rates"] = [0.75, 0.76]
        result = mod.evaluate_release(report, POLICY, exp, self.scan)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("at least 3" in x for x in result["invalid_reasons"]))

    def test_string_false_cannot_masquerade_as_boolean(self):
        report = copy.deepcopy(self.report)
        report["domains"]["coding_repository"]["baseline_outcomes"][0] = "false"
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")

    def test_zero_cost_baseline_allows_zero_cost_candidate(self):
        report = copy.deepcopy(self.report)
        report["efficiency"]["cost_per_verified_success"] = {"baseline": 0.0, "candidate": 0.0}
        self.assertEqual(self.evaluate(report=report)["status"], "PROMOTION_ELIGIBLE")

    def test_zero_cost_baseline_rejects_new_positive_cost(self):
        report = copy.deepcopy(self.report)
        report["efficiency"]["cost_per_verified_success"] = {"baseline": 0.0, "candidate": 0.01}
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "REJECTED")

    def test_missing_required_domain_invalid_even_if_smoke_output_exists(self):
        report = copy.deepcopy(self.report)
        report["domains"].pop("research_citation")
        result = self.evaluate(report=report)
        self.assertEqual(result["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()