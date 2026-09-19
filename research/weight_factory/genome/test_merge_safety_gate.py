import hashlib
import unittest
from copy import deepcopy
from pathlib import Path
from merge_safety_gate import load_json, validate_candidate

ROOT = Path(__file__).resolve().parent
POLICY = load_json(ROOT / "merge_safety_policy_v4.json")


def sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def good_candidate():
    return {
        "base": deepcopy(POLICY["base"]),
        "topology_class": "FULL_HYBRID_TEXT",
        "target_suffixes": list(POLICY["full_hybrid_required_suffixes"]),
        "target_scopes": ["model.language_model.layers"],
        "training_method": "bf16_lora",
        "rank_pattern": {},
        "merge": {"backend": "peft_native", "combination_type": "svd"},
        "promotion_requested": True,
        "merge_promotion_requested": True,
        "interference_input_representation": "effective_parameter_delta",
        "parameter_layout": {
            "algorithm": "sha256",
            "compatible": True,
            "base_layout_sha256": sha("canonical-layout"),
            "candidate_layout_sha256": sha("canonical-layout"),
        },
        "hard_rejection_counts": {
            threshold_key[:-4]: 0
            for threshold_key in POLICY["hard_rejection_thresholds"]
        },
        "evidence": {
            "reload_pass": True,
            "nonzero_delta_pass": True,
            "delta_identity_pass": True,
            "base_hash_match": True,
            "artifact_hash": sha("artifact"),
            "license_pass": True,
            "provenance_pass": True,
            "contamination_pass": True,
            "target_gain": True,
            "global_regression_pass": True,
            "interference_atlas_pass": True,
            "pairwise_behavior_eval_pass": True,
            "merge_roundtrip_pass": True,
            "quantization_survival_pass": True,
        },
        "artifacts": {
            key: sha(key) for key in POLICY["required_merge_artifacts"]
        },
    }


class MergeSafetyTests(unittest.TestCase):
    def test_complete_v4_candidate_passes(self):
        self.assertEqual(validate_candidate(good_candidate(), POLICY), [])

    def test_base_revision_mismatch_fails(self):
        c = good_candidate(); c["base"]["revision"] = "wrong"
        self.assertIn("base.revision mismatch", validate_candidate(c, POLICY))

    def test_full_hybrid_requires_deltanet_targets(self):
        c = good_candidate(); c["target_suffixes"] = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        errs = validate_candidate(c, POLICY)
        self.assertTrue(any("full hybrid coverage missing" in e for e in errs))

    def test_rank_pattern_blocks_ties(self):
        c = good_candidate(); c["merge"]["combination_type"] = "ties"; c["rank_pattern"] = {"q_proj": 8}
        self.assertIn("rank_pattern forbidden for ties", validate_candidate(c, POLICY))

    def test_mergekit_qwen35_is_blocked(self):
        c = good_candidate(); c["merge"]["backend"] = "mergekit_qwen3_5"
        self.assertIn("merge backend blocked: mergekit_qwen3_5", validate_candidate(c, POLICY))

    def test_qlora_requires_regression_proof(self):
        c = good_candidate(); c["training_method"] = "qlora_4bit"
        self.assertIn("qlora_4bit requires quantization_regression_pass", validate_candidate(c, POLICY))

    def test_integrity_proof_is_fail_closed(self):
        c = good_candidate(); c["evidence"]["delta_identity_pass"] = False
        self.assertIn("missing evidence.delta_identity_pass", validate_candidate(c, POLICY))

    def test_forbidden_scope_fails(self):
        c = good_candidate(); c["target_scopes"].append("model.visual.blocks.0")
        self.assertTrue(any("forbidden target scope" in e for e in validate_candidate(c, POLICY)))

    def test_missing_layout_proof_fails_closed(self):
        c = good_candidate(); c.pop("parameter_layout")
        self.assertIn("merge promotion missing parameter_layout proof", validate_candidate(c, POLICY))

    def test_mismatched_layout_fingerprint_fails_closed(self):
        c = good_candidate(); c["parameter_layout"]["candidate_layout_sha256"] = sha("different-layout")
        self.assertIn("parameter layout fingerprint mismatch", validate_candidate(c, POLICY))

    def test_fake_long_hash_is_not_sha256(self):
        c = good_candidate(); c["evidence"]["artifact_hash"] = "this-is-longer-than-sixteen-but-not-a-sha256"
        self.assertIn("missing/invalid SHA-256 evidence.artifact_hash", validate_candidate(c, POLICY))

    def test_missing_merge_artifact_fails_closed(self):
        c = good_candidate(); c["artifacts"].pop("merge_recipe_hash")
        self.assertIn("merge promotion missing/invalid SHA-256 artifacts.merge_recipe_hash", validate_candidate(c, POLICY))

    def test_missing_quantization_survival_fails_closed(self):
        c = good_candidate(); c["evidence"]["quantization_survival_pass"] = False
        self.assertIn("merge promotion missing evidence.quantization_survival_pass", validate_candidate(c, POLICY))

    def test_wrong_interference_representation_fails_closed(self):
        c = good_candidate(); c["interference_input_representation"] = "raw_lora_factors"
        self.assertIn(
            "merge promotion requires interference_input_representation=effective_parameter_delta",
            validate_candidate(c, POLICY),
        )

    def test_merge_promotion_without_general_promotion_fails_closed(self):
        c = good_candidate(); c["promotion_requested"] = False
        self.assertIn("merge promotion requires promotion_requested", validate_candidate(c, POLICY))

    def test_missing_hard_rejection_counts_fails_closed(self):
        c = good_candidate(); c.pop("hard_rejection_counts")
        self.assertIn("merge promotion missing hard_rejection_counts", validate_candidate(c, POLICY))

    def test_hard_rejection_threshold_exceeded_fails_closed(self):
        c = good_candidate(); c["hard_rejection_counts"]["parameter_layout_mismatch_count"] = 1
        self.assertIn(
            "hard rejection threshold exceeded: parameter_layout_mismatch_count=1 > 0",
            validate_candidate(c, POLICY),
        )


if __name__ == "__main__":
    unittest.main()
