import hashlib
import unittest

import p2_merge_receipt_gate as gate


def h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def seal_candidate(
    label: str,
    *,
    artifact_type: str = "adapter",
    artifact_stage: str = "reproducible_gene",
    base_revision: str = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
    parameter_layout_sha256: str | None = None,
    topology_class: str = "FULL_HYBRID_TEXT",
    parents=None,
    merge_recipe_sha256=None,
):
    parameter_layout_sha256 = parameter_layout_sha256 or h("layout")
    parents = [] if parents is None else list(parents)
    manifest = {
        "schema_version": 1,
        "manifest_kind": gate.CANDIDATE_MANIFEST_KIND,
        "manifest_id": "aqlevon-candidate-artifact-v1:sha256:" + h("id:" + label),
        "hash_profile": gate.HASH_PROFILE,
        "artifact_type": artifact_type,
        "artifact_stage": artifact_stage,
        "base": {
            "repo": "Qwen/Qwen3.8-27B",
            "revision": base_revision,
            "base_manifest_sha256": h("base-manifest"),
        },
        "tokenizer_sha256": h("tokenizer"),
        "config_sha256": h("config"),
        "training_shard_manifest_sha256": h("training-shard:" + label),
        "training_run_receipt_sha256": h("training-run:" + label),
        "merge_recipe_sha256": merge_recipe_sha256,
        "parameter_layout_sha256": parameter_layout_sha256,
        "topology_class": topology_class,
        "artifact_files": [
            {"path": "adapter_model.safetensors", "size": 123, "sha256": h("file:" + label)}
        ],
        "artifact_file_tree_sha256": h("tree:" + label),
        "adapter_state_sha256": h("adapter-state:" + label) if artifact_type == "adapter" else None,
        "checkpoint_state_sha256": h("checkpoint:" + label) if artifact_type in {"full_checkpoint", "merge", "quantized_serving_artifact"} else None,
        "parent_candidate_artifact_manifest_sha256": parents,
        "environment_toolchain_manifest_sha256": h("environment"),
    }
    manifest["manifest_sha256"] = gate.canonical_p2_sha256(manifest)
    return manifest


def seal_eval(candidate, label: str, status: str = "PROMOTION_ELIGIBLE"):
    receipt = {
        "schema_version": 1,
        "receipt_kind": gate.EVALUATION_RECEIPT_KIND,
        "hash_profile": gate.HASH_PROFILE,
        "candidate_artifact_manifest_sha256": candidate["manifest_sha256"],
        "experiment_manifest_sha256": h("experiment:" + label),
        "preregistration_anchor": {
            "anchor_request_sha256": h("anchor-request:" + label),
            "anchor_kind": "git_commit",
            "immutable_reference": "commit:" + h("anchor-ref:" + label)[:40],
            "external_evidence_sha256": h("external-evidence:" + label),
            "manager_authority_id": "AQLEVON_MANAGER_V1",
            "manager_attestation_sha256": h("manager-attestation:" + label),
            "anchored_at_utc": "2026-09-19T00:00:00Z",
            "verification_record_sha256": h("anchor-verification:" + label),
        },
        "evaluation_policy_sha256": h("eval-policy"),
        "evaluation_code_sha256": h("eval-code"),
        "harness_manifest_sha256": h("harness"),
        "provenance_receipt_sha256": h("provenance:" + label),
        "contamination_scan_receipt_sha256": h("contamination:" + label),
        "red_team_evidence_root_sha256": h("red-team:" + label),
        "base_run": {
            "raw_outputs_sha256": h("base-raw:" + label),
            "run_trace_sha256": h("base-trace:" + label),
        },
        "candidate_run": {
            "raw_outputs_sha256": h("candidate-raw:" + label),
            "run_trace_sha256": h("candidate-trace:" + label),
        },
        "domain_metric_summary": {
            "coding": {
                "n": 10,
                "baseline_rate": "0.5",
                "candidate_rate": "0.6",
                "delta_pp": "10.0",
            }
        },
        "efficiency_scope": {
            "hash_profile": gate.HASH_PROFILE,
            "efficiency_scope_kind": "AQLEVON_EVALUATION_HARNESS_EFFICIENCY_SCOPE_V1",
            "runtime_evidence_consumed": False,
            "runtime_attempt_set_sha256": None,
        },
        "efficiency_metric_summary": {"p95_latency_ms": {"baseline": 10, "candidate": 9, "limit": 20, "ratio": "0.9"}},
        "runtime_attempt_authority": {
            "authority_kind": "AQLEVON_CANDIDATE_LEVEL_EVAL_NOT_ATTEMPT_AUTHORITY_V1",
            "authoritative_for_arbitrary_runtime_attempts": False,
            "attempt_set_root_sha256": None,
            "attempt_level_truth_requirement": "MANAGER_APPROVED_PER_ATTEMPT_OBJECTIVE_VERIFIER_OR_FUTURE_APPROVED_ATTEMPT_SET_EXTENSION",
        },
        "final_status": status,
        "invalid_reason_codes": [],
        "invalid_reason_set_sha256": h("invalid-set:" + label),
        "failure_reason_codes": [],
        "failure_reason_set_sha256": h("failure-set:" + label),
        "truth_boundary": "PROMOTION_ELIGIBLE_REQUIRES_MANAGER_REVIEW_AND_INDEPENDENT_RERUN",
    }
    receipt["receipt_sha256"] = gate.canonical_p2_sha256(receipt)
    return receipt


def policy():
    return {
        "schema_version": 4,
        "base": {
            "repo": "Qwen/Qwen3.8-27B",
            "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
            "family": "qwen3_5",
        },
    }


def source_fixture():
    left = seal_candidate("left")
    right = seal_candidate("right")
    left_eval = seal_eval(left, "left")
    right_eval = seal_eval(right, "right")
    return [left, right], [left_eval, right_eval]


class P2CanonicalInteropTests(unittest.TestCase):
    def test_worker03_frozen_canonical_vector(self):
        value = {
            "z": "Ａ\rCafe\u0301",
            "hash_profile": gate.HASH_PROFILE,
            "a": [1, True, None, {"line": "x\r\ny"}],
        }
        self.assertEqual(
            gate.canonical_p2_sha256(value),
            "57a289efd889602d76395057bae6f06602308c273fe8b27dbefe78ec65b4ebce",
        )

    def test_worker05_worker06_frozen_canonical_vector(self):
        value = {"2": "two", "10": "ten", "text": "e\u0301\r\nline", "tiny": "0.0000001"}
        self.assertEqual(
            gate.canonical_p2_sha256(value),
            "1b1580a59f4ae1efdf8ed0fc7a86ffbcf1ee32d9f6d3294840afecd8a55f8b19",
        )

    def test_direct_float_in_authoritative_hash_fails_closed(self):
        with self.assertRaises(ValueError):
            gate.canonical_p2_sha256({"x": 0.5})


class PreMergeAdmissionTests(unittest.TestCase):
    def test_pre_merge_admission_passes_without_merged_candidate_or_receipt(self):
        manifests, receipts = source_fixture()
        out = gate.pre_merge_source_admission(
            source_manifests=manifests,
            source_evaluation_receipts=receipts,
            merge_policy=policy(),
            merge_policy_sha256=h("merge-policy-file"),
        )
        self.assertEqual(out["decision"], "ADMIT_FOR_MERGE_CONSTRUCTION")
        self.assertEqual(gate.validate_source_admission_receipt(out), [])
        self.assertFalse(out["legacy_p1_booleans_authoritative"])

    def test_legacy_p1_booleans_cannot_replace_evaluation_receipts(self):
        manifests, _ = source_fixture()
        with self.assertRaisesRegex(ValueError, "one evaluation receipt per source candidate"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=[],
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
                legacy_p1_evidence={
                    "target_gain": True,
                    "global_regression_pass": True,
                    "pairwise_behavior_eval_pass": True,
                    "quantization_survival_pass": True,
                    "license_pass": True,
                    "provenance_pass": True,
                    "contamination_pass": True,
                },
            )

    def test_probe_only_source_is_rejected_even_with_promotion_receipt(self):
        manifests, receipts = source_fixture()
        manifests[0]["artifact_stage"] = "probe_only"
        manifests[0]["manifest_sha256"] = gate.canonical_p2_sha256({k:v for k,v in manifests[0].items() if k != "manifest_sha256"})
        receipts[0] = seal_eval(manifests[0], "left-probe")
        with self.assertRaisesRegex(ValueError, "probe_only"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_rejected_source_evaluation_is_rejected(self):
        manifests, receipts = source_fixture()
        receipts[1] = seal_eval(manifests[1], "right-rejected", status="REJECTED")
        with self.assertRaisesRegex(ValueError, "not PROMOTION_ELIGIBLE"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_evaluation_receipt_candidate_binding_mismatch_fails(self):
        manifests, receipts = source_fixture()
        receipts[0]["candidate_artifact_manifest_sha256"] = manifests[1]["manifest_sha256"]
        receipts[0]["receipt_sha256"] = gate.canonical_p2_sha256({k:v for k,v in receipts[0].items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "candidate binding mismatch"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_layout_mismatch_fails_closed(self):
        manifests, receipts = source_fixture()
        manifests[1] = seal_candidate("right-layout", parameter_layout_sha256=h("other-layout"))
        receipts[1] = seal_eval(manifests[1], "right-layout")
        with self.assertRaisesRegex(ValueError, "lineage/layout/topology mismatch"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_wrong_hash_profile_fails_closed(self):
        manifests, receipts = source_fixture()
        manifests[0]["hash_profile"] = "UNKNOWN_PROFILE"
        manifests[0]["manifest_sha256"] = gate.canonical_p2_sha256({k:v for k,v in manifests[0].items() if k != "manifest_sha256"})
        with self.assertRaisesRegex(ValueError, "hash_profile"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_bad_candidate_manifest_id_fails_closed_even_when_resealed(self):
        manifests, receipts = source_fixture()
        manifests[0]["manifest_id"] = "not-a-canonical-manifest-id"
        manifests[0]["manifest_sha256"] = gate.canonical_p2_sha256({k:v for k,v in manifests[0].items() if k != "manifest_sha256"})
        receipts[0] = seal_eval(manifests[0], "bad-id")
        with self.assertRaisesRegex(ValueError, "manifest_id"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_evaluation_unknown_hash_profile_fails_closed_even_when_resealed(self):
        manifests, receipts = source_fixture()
        receipts[0]["hash_profile"] = "UNKNOWN_PROFILE"
        receipts[0]["receipt_sha256"] = gate.canonical_p2_sha256({k:v for k,v in receipts[0].items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "hash_profile"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )

    def test_tampered_source_manifest_self_digest_fails_closed(self):
        manifests, receipts = source_fixture()
        manifests[0]["config_sha256"] = h("tampered")
        with self.assertRaisesRegex(ValueError, "self-digest"):
            gate.pre_merge_source_admission(
                source_manifests=manifests,
                source_evaluation_receipts=receipts,
                merge_policy=policy(),
                merge_policy_sha256=h("merge-policy-file"),
            )


class PostEvaluationPromotionTests(unittest.TestCase):
    def setUp(self):
        self.manifests, self.receipts = source_fixture()
        self.policy = policy()
        self.policy_sha = h("merge-policy-file")
        self.admission = gate.pre_merge_source_admission(
            source_manifests=self.manifests,
            source_evaluation_receipts=self.receipts,
            merge_policy=self.policy,
            merge_policy_sha256=self.policy_sha,
        )
        parents = [m["manifest_sha256"] for m in self.manifests]
        self.merged = seal_candidate(
            "merged",
            artifact_type="merge",
            artifact_stage="merge_candidate",
            parents=parents,
            merge_recipe_sha256=h("merge-recipe"),
        )
        self.merged_eval = seal_eval(self.merged, "merged")

    def promote(self, **extra):
        kwargs = dict(
            source_admission_receipt=self.admission,
            source_manifests=self.manifests,
            source_evaluation_receipts=self.receipts,
            merged_candidate_manifest=self.merged,
            merged_evaluation_receipt=self.merged_eval,
            merge_policy=self.policy,
            merge_policy_sha256=self.policy_sha,
            interference_report_sha256=h("interference"),
            merge_roundtrip_receipt_sha256=h("roundtrip"),
        )
        kwargs.update(extra)
        return gate.post_evaluation_merge_promotion(**kwargs)

    def test_valid_merged_candidate_promotes_only_for_manager_review(self):
        out = self.promote()
        self.assertEqual(out["decision"], "MERGE_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW")
        self.assertEqual(out["release_authority"], "MANAGER_ONLY")
        self.assertFalse(out["legacy_p1_booleans_authoritative"])
        self.assertEqual(gate.validate_promotion_receipt(out), [])

    def test_merged_receipt_is_required_post_construction(self):
        with self.assertRaisesRegex(ValueError, "merged candidate/evaluation invalid"):
            self.promote(merged_evaluation_receipt={})

    def test_merged_evaluation_must_be_promotion_eligible(self):
        rejected = seal_eval(self.merged, "merged-rejected", status="REJECTED")
        with self.assertRaisesRegex(ValueError, "not PROMOTION_ELIGIBLE"):
            self.promote(merged_evaluation_receipt=rejected)

    def test_merged_evaluation_candidate_binding_mismatch_fails(self):
        wrong = seal_eval(self.manifests[0], "wrong-merged-binding")
        with self.assertRaisesRegex(ValueError, "merged evaluation receipt candidate binding mismatch"):
            self.promote(merged_evaluation_receipt=wrong)

    def test_merged_parent_chain_must_match_admitted_sources(self):
        bad = seal_candidate(
            "bad-parents",
            artifact_type="merge",
            artifact_stage="merge_candidate",
            parents=[self.manifests[0]["manifest_sha256"]],
            merge_recipe_sha256=h("merge-recipe"),
        )
        bad_eval = seal_eval(bad, "bad-parents")
        with self.assertRaisesRegex(ValueError, "parent manifest list"):
            self.promote(merged_candidate_manifest=bad, merged_evaluation_receipt=bad_eval)

    def test_source_admission_tamper_fails_even_if_legacy_booleans_true(self):
        tampered = dict(self.admission)
        tampered["decision"] = "ADMIT_FOR_MERGE_CONSTRUCTION_TAMPERED"
        with self.assertRaisesRegex(ValueError, "invalid source admission receipt"):
            self.promote(
                source_admission_receipt=tampered,
                legacy_p1_evidence={
                    "target_gain": True,
                    "global_regression_pass": True,
                    "pairwise_behavior_eval_pass": True,
                    "quantization_survival_pass": True,
                },
            )

    def test_quantized_release_requires_quantized_manifest_and_eval_receipt(self):
        with self.assertRaisesRegex(ValueError, "requires quantized candidate manifest and evaluation receipt"):
            self.promote(request_quantized_release=True)

    def test_quantized_release_requires_separate_promotion_eligible_receipt(self):
        quantized = seal_candidate(
            "quantized",
            artifact_type="quantized_serving_artifact",
            artifact_stage="release_candidate",
            parents=[self.merged["manifest_sha256"]],
            merge_recipe_sha256=None,
        )
        rejected = seal_eval(quantized, "quantized", status="REJECTED")
        with self.assertRaisesRegex(ValueError, "quantized survival evaluation is not PROMOTION_ELIGIBLE"):
            self.promote(
                request_quantized_release=True,
                quantized_candidate_manifest=quantized,
                quantized_evaluation_receipt=rejected,
            )

    def test_quantized_parent_must_be_exact_merged_candidate(self):
        quantized = seal_candidate(
            "quantized-wrong-parent",
            artifact_type="quantized_serving_artifact",
            artifact_stage="release_candidate",
            parents=[self.manifests[0]["manifest_sha256"]],
            merge_recipe_sha256=None,
        )
        q_eval = seal_eval(quantized, "quantized-wrong-parent")
        with self.assertRaisesRegex(ValueError, "sole parent"):
            self.promote(
                request_quantized_release=True,
                quantized_candidate_manifest=quantized,
                quantized_evaluation_receipt=q_eval,
            )

    def test_valid_quantized_survival_path_is_bound_but_not_release_approved(self):
        quantized = seal_candidate(
            "quantized-pass",
            artifact_type="quantized_serving_artifact",
            artifact_stage="release_candidate",
            parents=[self.merged["manifest_sha256"]],
            merge_recipe_sha256=None,
        )
        q_eval = seal_eval(quantized, "quantized-pass")
        out = self.promote(
            request_quantized_release=True,
            quantized_candidate_manifest=quantized,
            quantized_evaluation_receipt=q_eval,
        )
        self.assertEqual(out["decision"], "MERGE_AND_QUANTIZED_SURVIVAL_PROMOTION_ELIGIBLE_FOR_MANAGER_REVIEW")
        self.assertEqual(out["release_authority"], "MANAGER_ONLY")
        self.assertEqual(out["quantized_survival_binding"]["candidate_artifact_manifest_sha256"], quantized["manifest_sha256"])
        self.assertEqual(gate.validate_promotion_receipt(out), [])

    def test_promotion_receipt_tamper_is_detected(self):
        out = self.promote()
        out["interference_report_sha256"] = h("tampered-interference")
        errors = gate.validate_promotion_receipt(out)
        self.assertIn("promotion receipt self-digest mismatch", errors)


if __name__ == "__main__":
    unittest.main()
