import copy
import hashlib
import importlib.util
import json
import unittest
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


p1 = load_module("eval_truth_gate", HERE / "eval_truth_gate.py")
p2 = load_module("evaluation_decision_receipt_v1", HERE / "evaluation_decision_receipt_v1.py")
POLICY = json.loads((HERE / "release_gate_policy_v1.json").read_text(encoding="utf-8"))
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64


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


def candidate_manifest(seed="1"):
    payload = {
        "schema_version": 1,
        "manifest_kind": p2.CANDIDATE_MANIFEST_KIND,
        "manifest_id": f"candidate-{seed}",
        "artifact_type": "adapter",
        "artifact_stage": "promotion_candidate",
        "base_repo": "Qwen/Qwen3.8-27B-FP8",
        "base_revision": "rev-fixed",
        "base_manifest_sha256": SHA_A,
        "tokenizer_sha256": SHA_B,
        "config_sha256": SHA_C,
        "training_shard_manifest_sha256": SHA_D,
        "training_run_receipt_sha256": SHA_E,
        "parameter_layout_sha256": SHA_F,
        "topology_class": "qwen3_8_hybrid",
        "artifact_files": [{"path": "adapter.safetensors", "size": 123, "sha256": hashlib.sha256(seed.encode()).hexdigest()}],
        "adapter_state_sha256": hashlib.sha256(("state" + seed).encode()).hexdigest(),
        "parent_candidate_artifact_manifest_sha256": [],
        "environment_toolchain_manifest_sha256": hashlib.sha256(("env" + seed).encode()).hexdigest(),
    }
    payload["manifest_sha256"] = p2.canonical_sha256(payload)
    return payload


def experiment_manifest():
    domains = {}
    for domain in POLICY["required_domains"]:
        domains[domain] = {
            "role": "target" if domain == "coding_repository" else "protected",
            "stochastic": False,
            "min_effect_pp": 5.0 if domain == "coding_repository" else None,
            "max_regression_pp": 2.0,
        }
    payload = {
        "schema_version": 1,
        "manifest_kind": p1.EXPERIMENT_KIND,
        "policy_id": POLICY["policy_id"],
        "policy_sha256": p1.canonical_sha256(POLICY),
        "harness_manifest_sha256": SHA_A,
        "provenance_manifest_sha256": SHA_B,
        "training_data_manifest_sha256": SHA_C,
        "source_registry_snapshot_sha256": SHA_D,
        "red_team_manifest_sha256": SHA_E,
        "domains": domains,
    }
    return p1.finalize_experiment_manifest(payload)


def provenance_receipt(exp):
    return p1.finalize_provenance_receipt({
        "schema_version": 1,
        "receipt_kind": p1.PROVENANCE_RECEIPT_KIND,
        "status": "PASS",
        "provenance_manifest_sha256": exp["provenance_manifest_sha256"],
        "training_data_manifest_sha256": exp["training_data_manifest_sha256"],
        "source_registry_snapshot_sha256": exp["source_registry_snapshot_sha256"],
        "license_evidence_bundle_sha256": SHA_F,
        "auditor_id": "manager-test",
    })


def scan_receipt():
    key = b"k" * 32
    protected = p1.build_fingerprint_pack([{"id": "p1", "field": "text", "text": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"}], key)
    candidate = p1.build_fingerprint_pack([{"id": "c1", "field": "text", "text": "completely different sample with enough words to avoid overlap zero one two alpha beta gamma delta epsilon zeta eta theta"}], key)
    receipt = p1.scan_fingerprint_packs(protected, candidate)
    assert receipt["status"] == "CLEAN"
    return receipt


def red_team():
    return {
        "manifest_sha256": SHA_E,
        "classes": {
            class_id: {"evaluated": True, "failure_count": 0, "evidence_sha256": hashlib.sha256(class_id.encode()).hexdigest()}
            for class_id in POLICY["red_team"]["catastrophic_classes"]
        },
    }


def report(exp, prov, scan):
    value = {
        "schema_version": 2,
        "policy_id": POLICY["policy_id"],
        "experiment_manifest_sha256": exp["manifest_sha256"],
        "runs": {
            "base": {"harness_manifest_sha256": exp["harness_manifest_sha256"], "run_trace_sha256": SHA_A, "raw_outputs_sha256": SHA_B},
            "candidate": {"harness_manifest_sha256": exp["harness_manifest_sha256"], "run_trace_sha256": SHA_C, "raw_outputs_sha256": SHA_D},
        },
        "provenance": {
            "base_checkpoint_sha256": SHA_A,
            "candidate_checkpoint_sha256": SHA_B,
            "tokenizer_sha256": SHA_C,
            "license_provenance_receipt_sha256": prov["receipt_sha256"],
            "license_provenance_receipt": prov,
        },
        "contamination": {"scan_receipt_sha256": scan["receipt_sha256"], "protected_answers_exported": False},
        "red_team": red_team(),
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
        else:
            b, c = outcomes(base_wins=45, improvements=0, regressions=0, n=60)
        value["domains"][domain] = {
            "baseline_outcomes": b,
            "candidate_outcomes": c,
            "baseline_repeat_rates": [sum(b) / len(b)],
        }
    return value


def anchor_pair(exp, cand):
    request = p2.build_anchor_request(
        experiment_manifest_sha256=exp["manifest_sha256"],
        evaluation_policy_sha256=p2.canonical_sha256(POLICY),
        candidate_artifact_manifest_sha256=cand["manifest_sha256"],
        requested_anchor_kind="git_commit",
    )
    verification = p2.finalize_anchor_verification({
        "schema_version": 1,
        "verification_kind": p2.ANCHOR_VERIFICATION_KIND,
        "verification_status": "VERIFIED",
        "anchor_kind": "git_commit",
        "anchor_request_sha256": request["request_sha256"],
        "experiment_manifest_sha256": request["experiment_manifest_sha256"],
        "evaluation_policy_sha256": request["evaluation_policy_sha256"],
        "candidate_artifact_manifest_sha256": request["candidate_artifact_manifest_sha256"],
        "immutable_reference": "github:owner/repo@0123456789abcdef0123456789abcdef01234567:anchors/exp.json",
        "external_evidence_sha256": hashlib.sha256(b"external-anchor-evidence").hexdigest(),
        "manager_authority_id": "AQLEVON_MANAGER",
        "manager_attestation_sha256": hashlib.sha256(b"manager-attestation-artifact").hexdigest(),
        "anchored_at_utc": "2026-09-19T00:40:00Z",
        "verified_at_utc": "2026-09-19T00:41:00Z",
    })
    return request, verification


def full_fixture():
    exp = experiment_manifest()
    prov = provenance_receipt(exp)
    scan = scan_receipt()
    rep = report(exp, prov, scan)
    gate = p1.evaluate_release(rep, POLICY, exp, scan)
    assert gate["status"] == "PROMOTION_ELIGIBLE", gate
    cand = candidate_manifest()
    req, ver = anchor_pair(exp, cand)
    receipt = p2.build_evaluation_decision_receipt(
        candidate_artifact_manifest=cand,
        experiment_manifest=exp,
        policy=POLICY,
        evaluation_code_sha256=p2.actual_evaluation_code_sha256(),
        anchor_request=req,
        anchor_verification=ver,
        report=rep,
        gate_result=gate,
        scan_receipt=scan,
    )
    return cand, exp, prov, scan, rep, gate, req, ver, receipt


class P2EvaluationDecisionReceiptTests(unittest.TestCase):
    def test_valid_receipt_builds_and_validates(self):
        cand, exp, _, _, _, _, req, ver, receipt = full_fixture()
        invalid = p2.validate_evaluation_decision_receipt(
            receipt, candidate_artifact_manifest=cand, experiment_manifest=exp,
            policy=POLICY, anchor_request=req, anchor_verification=ver,
        )
        self.assertEqual(invalid, [])
        self.assertEqual(receipt["final_status"], "PROMOTION_ELIGIBLE")

    def test_candidate_manifest_cross_lane_identity_is_kind_plus_hash_only(self):
        cand = candidate_manifest()
        # Worker 03 owns internal manifest validation. Worker 05 consumes only its
        # canonical kind + SHA identity and must not duplicate artifact-stage truth.
        cand["artifact_stage"] = "release_candidate"
        self.assertEqual(p2.validate_candidate_artifact_manifest(cand), [])
        cand["manifest_sha256"] = "not-a-sha"
        self.assertTrue(p2.validate_candidate_artifact_manifest(cand))

    def test_anchor_request_is_bound_to_candidate_artifact(self):
        exp = experiment_manifest()
        a = p2.build_anchor_request(
            experiment_manifest_sha256=exp["manifest_sha256"], evaluation_policy_sha256=p2.canonical_sha256(POLICY),
            candidate_artifact_manifest_sha256=candidate_manifest("1")["manifest_sha256"], requested_anchor_kind="git_commit")
        b = p2.build_anchor_request(
            experiment_manifest_sha256=exp["manifest_sha256"], evaluation_policy_sha256=p2.canonical_sha256(POLICY),
            candidate_artifact_manifest_sha256=candidate_manifest("2")["manifest_sha256"], requested_anchor_kind="git_commit")
        self.assertNotEqual(a["request_sha256"], b["request_sha256"])

    def test_self_hash_without_external_manager_evidence_is_not_verified(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["external_evidence_sha256"] = None
        ver["verification_record_sha256"] = p2.canonical_sha256({k: v for k, v in ver.items() if k != "verification_record_sha256"})
        invalid = p2.validate_anchor_verification(ver, req)
        self.assertTrue(any("external_evidence_sha256" in x for x in invalid))

    def test_missing_manager_attestation_is_invalid(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["manager_attestation_sha256"] = ""
        ver["verification_record_sha256"] = p2.canonical_sha256({k: v for k, v in ver.items() if k != "verification_record_sha256"})
        invalid = p2.validate_anchor_verification(ver, req)
        self.assertTrue(any("manager_attestation_sha256" in x for x in invalid))

    def test_anchor_wrong_experiment_binding_is_invalid(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["experiment_manifest_sha256"] = SHA_F
        ver["verification_record_sha256"] = p2.canonical_sha256({k: v for k, v in ver.items() if k != "verification_record_sha256"})
        self.assertTrue(any("experiment_manifest_sha256" in x for x in p2.validate_anchor_verification(ver, req)))

    def test_anchor_timestamp_order_is_fail_closed(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["verified_at_utc"] = "2026-09-18T23:59:00Z"
        ver["verification_record_sha256"] = p2.canonical_sha256({k: v for k, v in ver.items() if k != "verification_record_sha256"})
        invalid = p2.validate_anchor_verification(ver, req)
        self.assertTrue(any("precedes" in x for x in invalid))

    def test_anchor_timestamp_must_be_utc_rfc3339(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["anchored_at_utc"] = "2026-09-19 00:40:00"
        ver["verification_record_sha256"] = p2.canonical_sha256({k: v for k, v in ver.items() if k != "verification_record_sha256"})
        invalid = p2.validate_anchor_verification(ver, req)
        self.assertTrue(any("RFC3339" in x for x in invalid))

    def test_anchor_tamper_breaks_self_digest(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["immutable_reference"] += "-tampered"
        self.assertTrue(any("self-digest" in x for x in p2.validate_anchor_verification(ver, req)))

    def test_anchor_kind_mismatch_is_invalid(self):
        exp = experiment_manifest(); cand = candidate_manifest(); req, ver = anchor_pair(exp, cand)
        ver["anchor_kind"] = "immutable_object"
        ver["verification_record_sha256"] = p2.canonical_sha256({k: v for k, v in ver.items() if k != "verification_record_sha256"})
        self.assertTrue(any("kind does not match request" in x for x in p2.validate_anchor_verification(ver, req)))

    def test_receipt_self_digest_tamper_is_invalid(self):
        *_, receipt = full_fixture()
        receipt["final_status"] = "REJECTED"
        invalid = p2.validate_evaluation_decision_receipt(receipt)
        self.assertTrue(any("self-digest" in x for x in invalid))

    def test_receipt_candidate_binding_mismatch_is_invalid(self):
        _, exp, _, _, _, _, req, ver, receipt = full_fixture()
        other = candidate_manifest("other")
        invalid = p2.validate_evaluation_decision_receipt(
            receipt, candidate_artifact_manifest=other, experiment_manifest=exp,
            policy=POLICY, anchor_request=req, anchor_verification=ver)
        self.assertTrue(any("candidate artifact binding mismatch" in x for x in invalid))

    def test_build_rejects_report_experiment_mismatch(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        rep["experiment_manifest_sha256"] = SHA_F
        with self.assertRaisesRegex(ValueError, "report/experiment"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=p2.actual_evaluation_code_sha256(), anchor_request=req, anchor_verification=ver,
                report=rep, gate_result=gate, scan_receipt=scan)

    def test_build_rejects_harness_mismatch(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        rep["runs"]["candidate"]["harness_manifest_sha256"] = SHA_F
        gate = p1.evaluate_release(rep, POLICY, exp, scan)
        with self.assertRaisesRegex(ValueError, "candidate run harness"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=p2.actual_evaluation_code_sha256(), anchor_request=req, anchor_verification=ver,
                report=rep, gate_result=gate, scan_receipt=scan)

    def test_build_rejects_provenance_binding_mismatch(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        rep["provenance"]["license_provenance_receipt_sha256"] = SHA_F
        gate = p1.evaluate_release(rep, POLICY, exp, scan)
        with self.assertRaisesRegex(ValueError, "provenance receipt"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=p2.actual_evaluation_code_sha256(), anchor_request=req, anchor_verification=ver,
                report=rep, gate_result=gate, scan_receipt=scan)

    def test_build_rejects_scan_binding_mismatch(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        rep["contamination"]["scan_receipt_sha256"] = SHA_F
        gate = p1.evaluate_release(rep, POLICY, exp, scan)
        with self.assertRaisesRegex(ValueError, "contamination scan"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=p2.actual_evaluation_code_sha256(), anchor_request=req, anchor_verification=ver,
                report=rep, gate_result=gate, scan_receipt=scan)

    def test_build_rejects_incomplete_red_team_evidence(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        rep["red_team"]["classes"].pop(next(iter(rep["red_team"]["classes"])))
        gate = p1.evaluate_release(rep, POLICY, exp, scan)
        # Even with a freshly recomputed INVALID gate result, P2 refuses an incomplete evidence root.
        with self.assertRaisesRegex(ValueError, "red-team"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=p2.actual_evaluation_code_sha256(), anchor_request=req, anchor_verification=ver,
                report=rep, gate_result=gate, scan_receipt=scan)

    def test_fake_or_stale_gate_result_cannot_be_laundered_into_receipt(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        fake = copy.deepcopy(gate)
        fake["status"] = "REJECTED"
        fake["failures"] = ["fabricated downstream decision"]
        with self.assertRaisesRegex(ValueError, "fresh P1 evaluation recomputation"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=p2.actual_evaluation_code_sha256(),
                anchor_request=req, anchor_verification=ver, report=rep,
                gate_result=fake, scan_receipt=scan)

    def test_wrong_evaluation_code_hash_is_rejected(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        with self.assertRaisesRegex(ValueError, "does not identify"):
            p2.build_evaluation_decision_receipt(
                candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
                evaluation_code_sha256=SHA_F, anchor_request=req, anchor_verification=ver,
                report=rep, gate_result=gate, scan_receipt=scan)

    def test_receipt_exports_no_raw_outcomes_or_protected_plaintext(self):
        *_, receipt = full_fixture()
        encoded = json.dumps(receipt, sort_keys=True)
        self.assertNotIn("baseline_outcomes", encoded)
        self.assertNotIn("candidate_outcomes", encoded)
        self.assertNotIn('"prompt"', encoded)
        self.assertNotIn('"answer"', encoded)

    def test_reason_codes_export_hash_codes_not_raw_reasons(self):
        cand, exp, _, scan, rep, _, req, ver, _ = full_fixture()
        rep["efficiency"]["cost_per_verified_success"] = {"baseline": 0.0, "candidate": 0.01}
        gate = p1.evaluate_release(rep, POLICY, exp, scan)
        self.assertEqual(gate["status"], "REJECTED")
        raw_failure = gate["failures"][0]
        receipt = p2.build_evaluation_decision_receipt(
            candidate_artifact_manifest=cand, experiment_manifest=exp, policy=POLICY,
            evaluation_code_sha256=p2.actual_evaluation_code_sha256(), anchor_request=req, anchor_verification=ver,
            report=rep, gate_result=gate, scan_receipt=scan)
        encoded = json.dumps(receipt)
        self.assertNotIn(raw_failure, encoded)
        self.assertTrue(receipt["failure_reason_codes"][0].startswith("FAILURE_"))

    def test_forbidden_plaintext_key_in_receipt_is_invalid(self):
        *_, receipt = full_fixture()
        receipt["prompt"] = "private"
        receipt["receipt_sha256"] = p2.canonical_sha256({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        invalid = p2.validate_evaluation_decision_receipt(receipt)
        self.assertTrue(any("plaintext key forbidden" in x for x in invalid))

    def test_invalid_final_status_is_invalid(self):
        *_, receipt = full_fixture()
        receipt["final_status"] = "RELEASED"
        receipt["receipt_sha256"] = p2.canonical_sha256({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        invalid = p2.validate_evaluation_decision_receipt(receipt)
        self.assertTrue(any("final_status invalid" in x for x in invalid))

    def test_all_required_domains_are_summarized(self):
        *_, receipt = full_fixture()
        self.assertEqual(set(receipt["domain_metric_summary"]), set(POLICY["required_domains"]))
        self.assertEqual(receipt["domain_metric_summary"]["coding_repository"]["role"], "target")
        self.assertEqual(receipt["domain_metric_summary"]["moroccan_darija"]["role"], "protected")

    def test_efficiency_summary_contains_source_values_and_gate_ratio(self):
        *_, receipt = full_fixture()
        metric = receipt["efficiency_metric_summary"]["p95_latency_ms"]
        self.assertEqual(metric["baseline"], 1000)
        self.assertEqual(metric["candidate"], 1050)
        self.assertAlmostEqual(metric["ratio"], 1.05)

    def test_promotion_eligible_is_not_release_declaration(self):
        *_, receipt = full_fixture()
        self.assertEqual(receipt["truth_boundary"], "PROMOTION_ELIGIBLE_REQUIRES_MANAGER_REVIEW_AND_INDEPENDENT_RERUN")

    def test_receipt_validation_detects_policy_mismatch(self):
        cand, exp, _, _, _, _, req, ver, receipt = full_fixture()
        changed = copy.deepcopy(POLICY)
        changed["alpha"] = 0.01
        invalid = p2.validate_evaluation_decision_receipt(
            receipt, candidate_artifact_manifest=cand, experiment_manifest=exp,
            policy=changed, anchor_request=req, anchor_verification=ver)
        self.assertTrue(any("evaluation policy binding mismatch" in x for x in invalid))

    def test_cli_build_and_validate_receipt_end_to_end(self):
        cand, exp, _, scan, rep, gate, req, ver, _ = full_fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payloads = {
                "candidate.json": cand, "experiment.json": exp, "policy.json": POLICY,
                "request.json": req, "verification.json": ver, "report.json": rep,
                "gate.json": gate, "scan.json": scan,
            }
            for name, value in payloads.items():
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            out = root / "receipt.json"
            rc = p2.main([
                "build-receipt",
                "--candidate-artifact-manifest", str(root / "candidate.json"),
                "--experiment-manifest", str(root / "experiment.json"),
                "--policy", str(root / "policy.json"),
                "--evaluation-code", str(HERE / "eval_truth_gate.py"),
                "--anchor-request", str(root / "request.json"),
                "--anchor-verification", str(root / "verification.json"),
                "--report", str(root / "report.json"),
                "--gate-result", str(root / "gate.json"),
                "--scan-receipt", str(root / "scan.json"),
                "--output", str(out),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            rc = p2.main([
                "validate-receipt", "--receipt", str(out),
                "--candidate-artifact-manifest", str(root / "candidate.json"),
                "--experiment-manifest", str(root / "experiment.json"),
                "--policy", str(root / "policy.json"),
                "--anchor-request", str(root / "request.json"),
                "--anchor-verification", str(root / "verification.json"),
            ])
            self.assertEqual(rc, 0)

    def test_anchor_request_rejects_unsupported_kind(self):
        exp = experiment_manifest(); cand = candidate_manifest()
        with self.assertRaisesRegex(ValueError, "unsupported"):
            p2.build_anchor_request(
                experiment_manifest_sha256=exp["manifest_sha256"], evaluation_policy_sha256=p2.canonical_sha256(POLICY),
                candidate_artifact_manifest_sha256=cand["manifest_sha256"], requested_anchor_kind="self_hash")


if __name__ == "__main__":
    unittest.main()