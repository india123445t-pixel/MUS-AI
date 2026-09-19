import json
import unittest
from pathlib import Path
import torch
from interference_atlas import tensor_metrics
from merge_safety_gate import default_policy_path

ROOT = Path(__file__).resolve().parent

class MergeArchitectureV2Tests(unittest.TestCase):
    def test_v4_is_the_default_merge_policy(self):
        self.assertEqual(default_policy_path().name, "merge_safety_policy_v4.json")

    def test_v4_requires_behavior_quantization_and_artifact_proofs(self):
        p = json.loads((ROOT / "merge_safety_policy_v4.json").read_text(encoding="utf-8"))
        self.assertIn("pairwise_behavior_eval_pass", p["required_merge_promotion_evidence"])
        self.assertIn("quantization_survival_pass", p["required_merge_promotion_evidence"])
        self.assertIn("interference_report_hash", p["required_merge_artifacts"])

    def test_tiny_sign_disagreement_has_low_mass_risk(self):
        m = tensor_metrics(torch.tensor([10.0, 1e-4]), torch.tensor([10.0, -1e-4]), 1e-8)
        self.assertEqual(m["sign_conflict"], 0.5)
        self.assertLess(m["conflict_mass"], 0.001)
        self.assertLess(m["magnitude_conflict_risk"], 0.001)

    def test_tournament_is_pareto_and_quantization_gated(self):
        p = json.loads((ROOT / "merge_tournament_policy_v2.json").read_text(encoding="utf-8"))
        self.assertIn("pareto", p["selection_law"])
        self.assertTrue(p["quantization"]["required_for_release_promotion"])
        self.assertEqual(p["metric_contract"]["missing_margin"], "hard_reject")

    def test_architecture_escalation_remains_evidence_gated(self):
        p = json.loads((ROOT / "merge_tournament_policy_v2.json").read_text(encoding="utf-8"))
        self.assertIn("at_least_two_distinct_merge_families_fail_behavioral_noninferiority", p["architecture_escalation"]["dense_merge_exhaustion_requires"])
        self.assertEqual(p["architecture_escalation"]["direct_cross_architecture_tensor_grafting"], "forbidden")

if __name__ == "__main__":
    unittest.main()
