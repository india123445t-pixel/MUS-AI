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


def valid_report():
    sha = "a" * 64
    report = {
        "schema_version": 1,
        "policy_id": POLICY["policy_id"],
        "provenance": {
            "license_clean": True,
            "same_harness_for_base_and_candidate": True,
            **{field: sha for field in POLICY["required_hash_fields"]},
        },
        "contamination": {
            "scan_complete": True,
            "keyed_fingerprints": True,
            "protected_answers_exported": False,
            "exact_overlap_count": 0,
            "fuzzy_overlap_count": 0,
            "protected_pack_sha256": "b" * 64,
            "candidate_pack_sha256": "c" * 64,
        },
        "red_team": {"catastrophic_failures": 0},
        "domains": {},
        "efficiency": {
            "cost_per_verified_success": {"baseline": 1.0, "candidate": 1.05},
            "p95_latency_ms": {"baseline": 1000, "candidate": 1050},
            "output_tokens_per_verified_success": {"baseline": 500, "candidate": 520},
        },
    }
    for domain in POLICY["required_domains"]:
        if domain == "coding_repository":
            b, c = outcomes(base_wins=20, improvements=20, regressions=0, n=60)
            role = "target"
            min_effect = 5.0
        else:
            b, c = outcomes(base_wins=45, improvements=0, regressions=0, n=60)
            role = "protected"
            min_effect = None
        report["domains"][domain] = {
            "role": role,
            "stochastic": False,
            "baseline_outcomes": b,
            "candidate_outcomes": c,
            "baseline_repeat_rates": [sum(b) / len(b)],
            "min_effect_pp": min_effect,
            "max_regression_pp": 2.0,
        }
    return report


class TruthGateTests(unittest.TestCase):
    def test_promotion_eligible_when_all_gates_pass(self):
        result = mod.evaluate_release(valid_report(), POLICY)
        self.assertEqual(result["status"], "PROMOTION_ELIGIBLE", result)

    def test_exact_contamination_rejects(self):
        report = valid_report()
        report["contamination"]["exact_overlap_count"] = 1
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("exact protected-eval overlap" in x for x in result["failures"]))

    def test_material_regression_rejects(self):
        report = valid_report()
        b, c = outcomes(base_wins=50, improvements=0, regressions=8, n=60)
        report["domains"]["moroccan_darija"].update({"baseline_outcomes": b, "candidate_outcomes": c, "max_regression_pp": 2.0})
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("moroccan_darija: regression" in x for x in result["failures"]))

    def test_missing_predeclared_threshold_is_invalid(self):
        report = valid_report()
        report["domains"]["coding_repository"]["min_effect_pp"] = None
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "INVALID")

    def test_stochastic_domain_requires_three_base_repeats(self):
        report = valid_report()
        report["domains"]["tools_function_calling"].update({"stochastic": True, "baseline_repeat_rates": [0.75, 0.76]})
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("at least 3" in x for x in result["invalid_reasons"]))

    def test_fingerprints_detect_exact_and_fuzzy_without_plaintext(self):
        key = b"unit-test-key-never-production"
        protected_rows = [{"id": "p1", "prompt": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"}]
        candidate_rows = [
            {"id": "c1", "text": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"},
            {"id": "c2", "text": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen changed"},
        ]
        protected = mod.build_fingerprint_pack(protected_rows, key, ["prompt"], shingle_n=5)
        candidate = mod.build_fingerprint_pack(candidate_rows, key, ["text"], shingle_n=5)
        encoded = json.dumps(protected)
        self.assertNotIn("one two three", encoded)
        result = mod.scan_fingerprint_packs(protected, candidate, fuzzy_threshold=0.70)
        self.assertGreaterEqual(result["exact_overlap_count"], 1)
        self.assertGreaterEqual(result["fuzzy_overlap_count"], 1)

    def test_wrong_fingerprint_key_does_not_match(self):
        rows = [{"id": "x", "text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi"}]
        a = mod.build_fingerprint_pack(rows, b"key-a", ["text"], shingle_n=5)
        b = mod.build_fingerprint_pack(rows, b"key-b", ["text"], shingle_n=5)
        result = mod.scan_fingerprint_packs(a, b, fuzzy_threshold=0.5)
        self.assertEqual(result["exact_overlap_count"], 0)
        self.assertEqual(result["fuzzy_overlap_count"], 0)

    def test_smoke_nonempty_output_is_not_enough(self):
        report = valid_report()
        report["domains"].pop("research_citation")
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("required domain missing" in x for x in result["invalid_reasons"]))

    def test_string_false_cannot_masquerade_as_boolean(self):
        report = valid_report()
        report["domains"]["coding_repository"]["baseline_outcomes"][0] = "false"
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("must be boolean" in x for x in result["invalid_reasons"]))

    def test_zero_cost_baseline_allows_zero_cost_candidate(self):
        report = valid_report()
        report["efficiency"]["cost_per_verified_success"] = {"baseline": 0.0, "candidate": 0.0}
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "PROMOTION_ELIGIBLE", result)

    def test_zero_cost_baseline_rejects_new_positive_cost(self):
        report = valid_report()
        report["efficiency"]["cost_per_verified_success"] = {"baseline": 0.0, "candidate": 0.01}
        result = mod.evaluate_release(report, POLICY)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any("introduced positive cost" in x for x in result["failures"]))


if __name__ == "__main__":
    unittest.main()
