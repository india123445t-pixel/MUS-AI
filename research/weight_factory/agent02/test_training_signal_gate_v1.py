import copy
import json
import pathlib
import unittest

from training_signal_gate_v1 import (
    ADMIT,
    DENY,
    QUARANTINE,
    assess_record,
    build_protected_manifest,
    protected_overlap,
    sha256_text,
    validate_manifest,
)

ROOT = pathlib.Path(__file__).resolve().parent
POLICY = json.loads((ROOT / "training_signal_policy_v1.json").read_text(encoding="utf-8"))


def clean_record():
    return {
        "record_id": "train-001",
        "prompt": "Compute the exact integer result for 37 plus 58 and return only the number.",
        "answer": "95",
        "source": {
            "id": "synthetic-local-v1",
            "revision": "a1b2c3d4",
            "immutable_revision": True,
            "content_sha256": sha256_text("synthetic-local-v1/a1b2c3d4"),
            "admission": "candidate_allow",
            "license_status": "cleared",
            "provenance_status": "complete"
        },
        "protected_eval": False,
        "contamination": {"holdout_scan_completed": True, "protected_eval_hits": 0},
        "dedup": {"is_canonical": True, "semantic_duplicate_score": 0.20},
        "verifiers": [{
            "type": "numeric",
            "passed": True,
            "target_failure_modes": ["wrong_final_answer"],
            "fault_injection_passed": True,
            "independent_observation": True
        }],
        "baseline": {"attempts": 10, "successes": 4},
        "language_lane": "other",
        "synthetic": True
    }


class TrainingSignalGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest = build_protected_manifest([
            "Protected benchmark question with secret expected answer alpha beta gamma delta epsilon zeta eta theta iota."
        ], 8, "test-holdout-v1")

    def test_manifest_integrity(self):
        ok, reason = validate_manifest(self.manifest)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")
        bad = copy.deepcopy(self.manifest)
        bad["record_count"] += 1
        self.assertFalse(validate_manifest(bad)[0])

    def test_clean_record_admitted(self):
        d = assess_record(clean_record(), POLICY, self.manifest)
        self.assertEqual(d.decision, ADMIT)

    def test_missing_required_is_fail_closed(self):
        r = clean_record()
        del r["source"]["license_status"]
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, DENY)
        self.assertTrue(d.reasons[0].startswith("missing_required:"))

    def test_protected_flag_denied(self):
        r = clean_record()
        r["protected_eval"] = True
        self.assertEqual(assess_record(r, POLICY, self.manifest).decision, DENY)

    def test_protected_ngram_overlap_denied(self):
        r = clean_record()
        r["prompt"] = "Protected benchmark question with secret expected answer alpha beta gamma delta epsilon zeta eta theta iota."
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, DENY)
        self.assertIn("protected_manifest_overlap", d.reasons)

    def test_disallowed_license_denied(self):
        r = clean_record()
        r["source"]["license_status"] = "audit_required"
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, DENY)
        self.assertIn("license_not_cleared", d.reasons)

    def test_mutable_revision_denied(self):
        r = clean_record()
        r["source"]["immutable_revision"] = False
        self.assertEqual(assess_record(r, POLICY, self.manifest).decision, DENY)

    def test_semantic_only_verifier_is_insufficient(self):
        r = clean_record()
        r["verifiers"] = [{
            "type": "learned_semantic",
            "passed": True,
            "target_failure_modes": ["semantic_mismatch"],
            "fault_injection_passed": True,
            "independent_observation": True
        }]
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, QUARANTINE)
        self.assertIn("no_qualified_hard_verifier", d.reasons)

    def test_verifier_theatre_is_quarantined(self):
        r = clean_record()
        r["verifiers"][0]["fault_injection_passed"] = False
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, QUARANTINE)
        self.assertIn("verifier_0_not_fault_tested", d.reasons)

    def test_failed_verifier_is_quarantined(self):
        r = clean_record()
        r["verifiers"][0]["passed"] = False
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, QUARANTINE)
        self.assertIn("verifier_0_failed", d.reasons)

    def test_saturated_example_is_low_information(self):
        r = clean_record()
        r["baseline"] = {"attempts": 10, "successes": 10}
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, QUARANTINE)
        self.assertIn("already_mastered_low_information_gain", d.reasons)

    def test_too_hard_example_is_quarantined(self):
        r = clean_record()
        r["baseline"] = {"attempts": 10, "successes": 0}
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, QUARANTINE)
        self.assertIn("too_hard_or_unstable_for_current_stage", d.reasons)

    def test_darija_synthetic_requires_language_audit(self):
        r = clean_record()
        r["language_lane"] = "darija"
        d = assess_record(r, POLICY, self.manifest)
        self.assertEqual(d.decision, QUARANTINE)
        self.assertIn("language_quality_audit_required", d.reasons)
        r["language_quality_audit"] = {"passed": True, "auditor_class": "native_moroccan_review"}
        self.assertEqual(assess_record(r, POLICY, self.manifest).decision, ADMIT)

    def test_noncanonical_duplicate_quarantined(self):
        r = clean_record()
        r["dedup"]["is_canonical"] = False
        self.assertEqual(assess_record(r, POLICY, self.manifest).decision, QUARANTINE)

    def test_short_protected_record_uses_whole_text_hash(self):
        m = build_protected_manifest(["secret tiny item"], 8, "short-v1")
        overlap = protected_overlap("secret tiny item", m)
        self.assertTrue(overlap["matched"])


if __name__ == "__main__":
    unittest.main()
