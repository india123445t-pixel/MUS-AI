from __future__ import annotations

import copy
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

import numpy as np

from research.weight_factory.agent07 import cli as cli_module

from research.weight_factory.agent07.core import (
    B07Error,
    DeltaBundle,
    LowRankModule,
    SCHEMA_RESULTS,
    baseline_coefficients,
    build_geometry,
    decide_acc,
    families_from_config,
    fit_compiler,
    generate_family_partitions,
    load_capsule_features,
    load_json,
    make_apa_followup_spec,
    prepare_artifacts,
    scale_coeffs_to_norm,
    sha256_json,
    validate_config,
    verify_behavioral_results,
)


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "b07_e0_config.json"


def load_config():
    return load_json(CONFIG_PATH)


def synthetic_bundle(family_id: str, scalar: float, base_revision: str) -> DeltaBundle:
    # One exact rank-1 operator. Varying factor gauge should not affect geometry.
    a = np.asarray([[1.0, -0.5, 0.25]], dtype=np.float64)
    b = np.asarray([[scalar], [2.0 * scalar]], dtype=np.float64)
    return DeltaBundle(
        family_id=family_id,
        base_model_repo="Qwen/Qwen3.5-0.8B-Base",
        base_model_revision=base_revision,
        modules={"model.layers.0.self_attn.q_proj": LowRankModule(
            name="model.layers.0.self_attn.q_proj", a=a, b=b, scale=1.0
        )},
        adapter_sha256=("%064x" % (abs(hash(family_id)) % (1 << 256)))[:64],
    )


def result_fixture(config, compiled_hidden=0.46, strongest_override=None, direct=0.82):
    records = []
    controls = ["zero_update", "random_same_norm", "nearest_adapter", "mean_delta", "basis_pc1_same_norm"]
    for family in families_from_config(config):
        if family.split != "compiler_holdout":
            continue
        candidates = {
            "base": {"hidden": 0.10, "semantic_hidden": 0.10},
            "direct_lora": {"hidden": direct, "semantic_hidden": max(0.0, direct - 0.05)},
            "compiled": {"hidden": compiled_hidden, "semantic_hidden": max(0.0, compiled_hidden - 0.03)},
            "zero_update": {"hidden": 0.10, "semantic_hidden": 0.10},
            "random_same_norm": {"hidden": 0.16, "semantic_hidden": 0.14},
            "nearest_adapter": {"hidden": 0.19, "semantic_hidden": 0.17},
            "mean_delta": {"hidden": 0.18, "semantic_hidden": 0.16},
            "basis_pc1_same_norm": {"hidden": 0.17, "semantic_hidden": 0.15},
        }
        if strongest_override:
            candidates[strongest_override]["hidden"] = 0.50
        records.append({"family_id": family.id, "candidates": candidates})
    out = {
        "schema_version": SCHEMA_RESULTS,
        "experiment_id": config["experiment_id"],
        "task_id": config["task_id"],
        "config_sha256": sha256_json(config),
        "holdout_families": records,
    }
    out["results_sha256"] = sha256_json(out)
    return out


class ConfigAndDataTests(unittest.TestCase):
    def test_config_is_exactly_8_train_4_holdout_and_controls_complete(self):
        config = load_config()
        validate_config(config)
        families = families_from_config(config)
        self.assertEqual(8, sum(f.split == "compiler_train" for f in families))
        self.assertEqual(4, sum(f.split == "compiler_holdout" for f in families))
        self.assertEqual(
            {"zero_update", "random_same_norm", "nearest_adapter", "mean_delta", "basis_pc1_same_norm"},
            set(config["decision"]["mandatory_controls"]),
        )

    def test_model_pin_is_exact_and_permissive(self):
        config = load_config()
        self.assertEqual("Qwen/Qwen3.5-0.8B-Base", config["base_model"]["repo_id"])
        self.assertEqual("dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68", config["base_model"]["revision"])
        self.assertEqual("apache-2.0", config["base_model"]["license"])

    def test_data_policy_forbids_protected_and_closed_outputs(self):
        config = load_config()
        self.assertFalse(config["data_policy"]["protected_benchmarks_allowed"])
        self.assertFalse(config["data_policy"]["closed_model_outputs_allowed"])
        self.assertFalse(config["data_policy"]["worker02_assets_imported"])

    def test_family_partitions_are_disjoint_and_prompts_hide_identity_and_rule(self):
        config = load_config()
        family = families_from_config(config)[0]
        parts = generate_family_partitions(family, config["dataset"])
        capsule_pairs = {(x["x"], x["y"]) for x in parts["capsule"]}
        train_pairs = {(x["x"], x["y"]) for x in parts["train"]}
        hidden_pairs = {(x["x"], x["y"]) for x in parts["hidden"]}
        self.assertFalse(capsule_pairs & train_pairs)
        self.assertFalse(capsule_pairs & hidden_pairs)
        self.assertFalse(train_pairs & hidden_pairs)
        for row in parts["train"] + parts["hidden"] + parts["semantic_hidden"]:
            prompt = row["prompt"]
            self.assertNotIn(family.id, prompt)
            self.assertNotIn(f"a={family.a}", prompt)
            self.assertNotIn(f"b={family.b}", prompt)
            self.assertNotIn(f"c={family.c}", prompt)

    def test_prepare_is_deterministic(self):
        config = load_config()
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            m1 = prepare_artifacts(config, d1)
            m2 = prepare_artifacts(config, d2)
            self.assertEqual(m1["manifest_sha256"], m2["manifest_sha256"])
            self.assertEqual(m1["families"], m2["families"])

    def test_bad_split_fails_closed(self):
        config = load_config()
        broken = copy.deepcopy(config)
        broken["families"][0]["split"] = "compiler_holdout"
        with self.assertRaises(B07Error):
            validate_config(broken)


class DeltaGeometryTests(unittest.TestCase):
    def test_inner_product_is_invariant_to_lora_factor_rescaling(self):
        rev = load_config()["base_model"]["revision"]
        a = np.asarray([[1.0, 2.0]], dtype=np.float64)
        b = np.asarray([[3.0], [-1.0]], dtype=np.float64)
        d1 = DeltaBundle("a", "Qwen/Qwen3.5-0.8B-Base", rev, {
            "m": LowRankModule("m", a=a, b=b, scale=0.5)
        }, "a" * 64)
        d2 = DeltaBundle("b", "Qwen/Qwen3.5-0.8B-Base", rev, {
            "m": LowRankModule("m", a=a * 7.0, b=b / 7.0, scale=0.5)
        }, "b" * 64)
        self.assertAlmostEqual(d1.inner(d1), d1.inner(d2), places=10)
        self.assertAlmostEqual(d1.norm(), d2.norm(), places=10)

    def test_geometry_is_psd_and_symmetric(self):
        config = load_config()
        rev = config["base_model"]["revision"]
        bundles = [synthetic_bundle(f"x{i}", float(i + 1), rev) for i in range(4)]
        g = build_geometry(bundles)
        self.assertTrue(np.allclose(g.gram, g.gram.T))
        self.assertGreaterEqual(float(np.min(np.linalg.eigvalsh(g.gram))), -1e-8)

    def test_random_control_is_same_operator_norm(self):
        config = load_config()
        rev = config["base_model"]["revision"]
        bundles = [synthetic_bundle(f"x{i}", float(i + 1), rev) for i in range(4)]
        g = build_geometry(bundles)
        raw = np.asarray([0.2, -0.5, 0.3, 0.7], dtype=np.float64)
        target = 3.25
        scaled = scale_coeffs_to_norm(raw, target, g)
        self.assertAlmostEqual(target, g.mixture_norm(scaled), places=8)

    def test_layout_mismatch_fails_closed(self):
        config = load_config()
        rev = config["base_model"]["revision"]
        one = synthetic_bundle("one", 1.0, rev)
        bad = DeltaBundle("bad", "Qwen/Qwen3.5-0.8B-Base", rev, {
            "different": LowRankModule("different", np.ones((1, 3)), np.ones((2, 1)), 1.0)
        }, "c" * 64)
        with self.assertRaises(B07Error):
            one.inner(bad)


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manifest = prepare_artifacts(self.config, self.temp.name)
        self.all_features = load_capsule_features(self.config, self.temp.name)
        rev = self.config["base_model"]["revision"]
        train_families = [f for f in families_from_config(self.config) if f.split == "compiler_train"]
        self.features = {f.id: self.all_features[f.id] for f in train_families}
        # Deterministic nonzero scalar derived from the capsule itself to create a learnable toy manifold.
        self.bundles = [
            synthetic_bundle(f.id, 1.0 + float(np.mean(self.features[f.id])), rev)
            for f in train_families
        ]

    def test_fit_consumes_only_train_families(self):
        model, geometry, diagnostics = fit_compiler(
            self.config, self.manifest, self.features, self.bundles
        )
        self.assertEqual([f.id for f in families_from_config(self.config) if f.split == "compiler_train"], model.training_family_ids)
        self.assertGreaterEqual(diagnostics["components_retained"], 1)
        self.assertEqual((8, 8), geometry.gram.shape)

    def test_holdout_adapter_in_fit_fails_closed(self):
        rev = self.config["base_model"]["revision"]
        bad = list(self.bundles)
        bad[-1] = synthetic_bundle("cap_08", 1.0, rev)
        with self.assertRaises(B07Error):
            fit_compiler(self.config, self.manifest, self.features, bad)

    def test_holdout_feature_presence_in_fit_fails_closed(self):
        leaked = dict(self.features)
        leaked["cap_08"] = self.all_features["cap_08"]
        with self.assertRaises(B07Error):
            fit_compiler(self.config, self.manifest, leaked, self.bundles)

    def test_manifest_tamper_fails_closed(self):
        tampered = copy.deepcopy(self.manifest)
        tampered["families"][0]["feature_sha256"] = "0" * 64
        with self.assertRaises(B07Error):
            fit_compiler(self.config, tampered, self.features, self.bundles)

    def test_capsule_feature_tamper_fails_closed(self):
        tampered = {k: v.copy() for k, v in self.features.items()}
        tampered["cap_00"][0] += 1.0 / float(self.config["dataset"]["modulus"])
        with self.assertRaises(B07Error):
            fit_compiler(self.config, self.manifest, tampered, self.bundles)

    def test_compiler_predicts_source_coefficients_and_all_controls(self):
        model, geometry, _ = fit_compiler(self.config, self.manifest, self.features, self.bundles)
        train_x = np.vstack([self.features[fid] for fid in model.training_family_ids])
        controls = baseline_coefficients(
            model, geometry, self.all_features["cap_08"], train_x, random_seed=123
        )
        self.assertEqual(
            {"compiled", "zero_update", "random_same_norm", "nearest_adapter", "mean_delta", "basis_pc1_same_norm"},
            set(controls),
        )
        self.assertEqual((8,), controls["compiled"].shape)
        self.assertAlmostEqual(
            geometry.mixture_norm(controls["compiled"]),
            geometry.mixture_norm(controls["random_same_norm"]),
            places=8,
        )


class RunAllIsolationTests(unittest.TestCase):
    def test_run_all_freezes_compiler_before_holdout_adapter_training(self):
        calls = []
        args = SimpleNamespace(runner="hf_peft", family_set="all")

        def mark(name):
            def _inner(a):
                calls.append(f"{name}:{getattr(a, 'family_set', '-')}")
            return _inner

        with mock.patch.object(cli_module, "cmd_prepare", side_effect=mark("prepare")), \
             mock.patch.object(cli_module, "cmd_train", side_effect=mark("train")), \
             mock.patch.object(cli_module, "cmd_fit", side_effect=mark("fit")), \
             mock.patch.object(cli_module, "cmd_evaluate", side_effect=mark("evaluate")), \
             mock.patch.object(cli_module, "cmd_decide", side_effect=mark("decide")):
            cli_module.cmd_run_all(args)

        self.assertEqual(
            [
                "prepare:all",
                "train:train",
                "fit:train",
                "train:holdout",
                "evaluate:holdout",
                "decide:holdout",
            ],
            calls,
        )


class DecisionTests(unittest.TestCase):
    def test_behavioral_result_tamper_fails_closed(self):
        config = load_config()
        results = result_fixture(config)
        verify_behavioral_results(config, results)
        results["holdout_families"][0]["candidates"]["compiled"]["hidden"] = 0.99
        with self.assertRaises(B07Error):
            verify_behavioral_results(config, results)

    def test_go_requires_unseen_family_behavior_not_reconstruction(self):
        config = load_config()
        decision = decide_acc(config, result_fixture(config))
        self.assertEqual("GO_QWEN3_5_4B_REPLICATION", decision["status"])
        self.assertFalse(decision["acc_killed"])
        self.assertGreaterEqual(decision["families_beating_all_controls"], 3)

    def test_mean_control_can_kill_acc(self):
        config = load_config()
        decision = decide_acc(config, result_fixture(config, strongest_override="mean_delta"))
        self.assertEqual("KILL_ACC_PREPARE_APA", decision["status"])
        self.assertTrue(decision["acc_killed"])
        apa = make_apa_followup_spec(config, decision)
        self.assertEqual("aqlevon.b07e0.apa_followup.v1", apa["schema_version"])
        self.assertFalse(apa["complexity_escalation_allowed"])

    def test_basis_control_can_kill_acc(self):
        config = load_config()
        decision = decide_acc(config, result_fixture(config, strongest_override="basis_pc1_same_norm"))
        self.assertEqual("KILL_ACC_PREPARE_APA", decision["status"])

    def test_bad_direct_teacher_is_inconclusive_not_acc_rescue(self):
        config = load_config()
        decision = decide_acc(config, result_fixture(config, direct=0.18))
        self.assertEqual("INCONCLUSIVE_DIRECT_LORA_PRECONDITION", decision["status"])
        self.assertFalse(decision["acc_killed"])
        self.assertFalse(decision["go_to_exact_family_4b_replication"])

    def test_wrong_holdout_set_fails_closed(self):
        config = load_config()
        results = result_fixture(config)
        results["holdout_families"][0]["family_id"] = "cap_07"
        with self.assertRaises(B07Error):
            decide_acc(config, results)

    def test_missing_mandatory_control_fails_closed(self):
        config = load_config()
        results = result_fixture(config)
        del results["holdout_families"][0]["candidates"]["nearest_adapter"]
        with self.assertRaises(B07Error):
            decide_acc(config, results)


if __name__ == "__main__":
    unittest.main()
