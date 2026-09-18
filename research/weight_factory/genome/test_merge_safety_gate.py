import unittest
from copy import deepcopy
from pathlib import Path
from merge_safety_gate import load_json, validate_candidate

ROOT = Path(__file__).resolve().parent
POLICY = load_json(ROOT / "merge_safety_policy_v2.json")


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
        "evidence": {
            "reload_pass": True,
            "nonzero_delta_pass": True,
            "delta_identity_pass": True,
            "base_hash_match": True,
            "artifact_hash": "a" * 64,
            "license_pass": True,
            "provenance_pass": True,
            "contamination_pass": True,
            "target_gain": True,
            "global_regression_pass": True
        }
    }


class MergeSafetyTests(unittest.TestCase):
    def test_good_candidate_passes(self):
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


if __name__ == "__main__":
    unittest.main()