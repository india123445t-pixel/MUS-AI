from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import candidate_artifact_manifest as cam

H = {
    name: hashlib.sha256(name.encode("utf-8")).hexdigest()
    for name in (
        "base", "tokenizer", "config", "shard", "run", "layout", "env",
        "adapter", "checkpoint", "parent1", "parent2", "merge", "other",
    )
}


def write_artifact(root: Path, rel: str, data: bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def adapter_spec() -> dict:
    return {
        "artifact_type": "adapter",
        "artifact_stage": "reproducible_gene",
        "base": {
            "repo": "Qwen/Qwen3.8-27B",
            "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
            "base_manifest_sha256": H["base"],
        },
        "tokenizer_sha256": H["tokenizer"],
        "config_sha256": H["config"],
        "training_shard_manifest_sha256": H["shard"],
        "training_run_receipt_sha256": H["run"],
        "merge_recipe_sha256": None,
        "parameter_layout_sha256": H["layout"],
        "topology_class": "CUSTOM_EXPERIMENTAL",
        "adapter_state_sha256": H["adapter"],
        "checkpoint_state_sha256": None,
        "parent_candidate_artifact_manifest_sha256": [],
        "environment_toolchain_manifest_sha256": H["env"],
    }


def full_checkpoint_spec() -> dict:
    s = adapter_spec()
    s.update({
        "artifact_type": "full_checkpoint",
        "adapter_state_sha256": None,
        "checkpoint_state_sha256": H["checkpoint"],
        "topology_class": "FULL_HYBRID_TEXT",
    })
    return s


class CandidateArtifactManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "artifact"
        self.root.mkdir()
        write_artifact(self.root, "z-last.bin", b"z")
        write_artifact(self.root, "nested/a-first.json", b"{}")

    def tearDown(self):
        self.tmp.cleanup()

    def test_adapter_manifest_is_deterministic_self_hashed_and_ordered(self):
        m1 = cam.build_manifest(adapter_spec(), self.root)
        m2 = cam.build_manifest(adapter_spec(), self.root)
        self.assertEqual(m1, m2)
        self.assertEqual(m1["manifest_kind"], cam.MANIFEST_KIND)
        self.assertEqual(m1["hash_profile"], cam.HASH_PROFILE)
        self.assertEqual(m1["manifest_id"], cam.compute_manifest_id(m1))
        self.assertEqual(m1["manifest_sha256"], cam.compute_manifest_sha256(m1))
        self.assertNotEqual(m1["manifest_id"].split(":")[-1], m1["manifest_sha256"])
        paths = [x["path"] for x in m1["artifact_files"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(cam.validate_manifest(m1, self.root), [])


    def test_p21_hash_profile_required_and_unknown_rejected(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        missing = copy.deepcopy(m)
        del missing["hash_profile"]
        errors = cam.validate_manifest(missing)
        self.assertTrue(any("missing top-level fields: hash_profile" in x for x in errors))
        self.assertTrue(any("hash_profile must equal" in x for x in errors))

        unknown = copy.deepcopy(m)
        unknown["hash_profile"] = "UNKNOWN_PROFILE"
        errors = cam.validate_manifest(unknown)
        self.assertTrue(any("hash_profile must equal" in x for x in errors))

    def test_p21_interop_vector_nfkc_newlines_ascii_order_and_digest(self):
        payload = {
            "z": "Ａ\r\nCafe\u0301",
            "a": [1, True, None, {"line": "x\ry"}],
            "hash_profile": cam.HASH_PROFILE,
        }
        expected = (
            b'{"a":[1,true,null,{"line":"x\\ny"}],'
            b'"hash_profile":"AQLEVON_CANONICAL_JSON_SHA256_V1",'
            b'"z":"A\\nCaf\xc3\xa9"}'
        )
        actual = cam.canonical_p2_json_bytes(payload)
        self.assertEqual(actual, expected)
        self.assertEqual(
            cam.sha256_bytes(actual),
            "57a289efd889602d76395057bae6f06602308c273fe8b27dbefe78ec65b4ebce",
        )
        # NFKC-equivalent/LF-normalized input must interoperate to the same bytes.
        equivalent = {
            "hash_profile": cam.HASH_PROFILE,
            "a": [1, True, None, {"line": "x\ny"}],
            "z": "A\nCafé",
        }
        self.assertEqual(cam.canonical_p2_json_bytes(equivalent), expected)

    def test_p21_ascii_authoritative_keys_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "ASCII"):
            cam.canonical_p2_json_bytes({"é": "value"})
        with self.assertRaisesRegex(ValueError, "ASCII"):
            cam.canonical_p2_json_bytes({"": "value"})

    def test_p21_non_integral_numeric_objects_fail_closed(self):
        for value in (1.25, float("nan"), float("inf"), Decimal("1.25")):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ValueError, "non-integral numeric"):
                    cam.canonical_p2_json_bytes({"x": value})
        self.assertEqual(cam.canonical_p2_json_bytes({"i": -12, "b": True}), b'{"b":true,"i":-12}')

    def test_p21_canonical_decimal_string_vectors(self):
        vectors = {
            "0": "0",
            "-0": "0",
            "-0.000": "0",
            "001.2300": "1.23",
            "-001.200": "-1.2",
            "10.000": "10",
        }
        for raw, expected in vectors.items():
            self.assertEqual(cam.canonical_decimal_string(raw), expected)
        for bad in ("+1.2", "1e3", "NaN", "Infinity", "1.", ".5"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "invalid decimal string"):
                    cam.canonical_decimal_string(bad)

    def test_p21_exact_self_digest_excludes_only_manifest_sha256(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        payload = copy.deepcopy(m)
        payload.pop("manifest_sha256")
        self.assertEqual(cam.canonical_p2_json_sha256(payload), m["manifest_sha256"])
        without_id = copy.deepcopy(payload)
        without_id.pop("manifest_id")
        self.assertNotEqual(cam.canonical_p2_json_sha256(without_id), m["manifest_sha256"])
        self.assertEqual(m["manifest_id"], cam.compute_manifest_id(m))

    def test_p21_uppercase_sha256_rejected(self):
        s = adapter_spec()
        s["tokenizer_sha256"] = H["tokenizer"].upper()
        with self.assertRaisesRegex(ValueError, "lowercase"):
            cam.build_manifest(s, self.root)

    def test_artifact_stage_remains_workflow_metadata_not_truth(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        m["artifact_stage"] = "release_candidate"
        m = cam.seal_manifest(m)
        self.assertEqual(cam.validate_manifest(m, self.root), [])
        for forbidden in cam.FORBIDDEN_TRUTH_FIELDS:
            self.assertNotIn(forbidden, m)

    def test_artifact_byte_tamper_fails_closed(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        write_artifact(self.root, "z-last.bin", b"tampered")
        errors = cam.validate_manifest(m, self.root)
        self.assertTrue(any("do not match current artifact_root bytes" in x for x in errors))

    def test_manifest_metadata_tamper_breaks_self_hash(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        m["artifact_stage"] = "promotion_candidate"
        errors = cam.validate_manifest(m)
        self.assertIn("manifest_sha256 self-digest mismatch", errors)
        self.assertIn("manifest_id identity digest mismatch", errors)

    def test_unknown_or_evaluation_truth_fields_fail_closed(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        m["verified"] = True
        errors = cam.validate_manifest(m)
        self.assertTrue(any("cannot originate evaluation/release truth" in x for x in errors))
        self.assertTrue(any("unknown top-level fields" in x for x in errors))

    def test_bad_sha256_fails_closed(self):
        s = adapter_spec()
        s["tokenizer_sha256"] = "not-a-hash"
        with self.assertRaisesRegex(ValueError, "tokenizer_sha256"):
            cam.build_manifest(s, self.root)

    def test_unknown_spec_field_fails_closed_instead_of_being_silently_dropped(self):
        s = adapter_spec()
        s["promotion_eligible"] = True
        with self.assertRaisesRegex(ValueError, "cannot originate evaluation/release truth"):
            cam.build_manifest(s, self.root)
        s = adapter_spec()
        s["invented_future_field"] = H["other"]
        with self.assertRaisesRegex(ValueError, "unknown spec fields"):
            cam.build_manifest(s, self.root)

    def test_manifest_output_cannot_live_inside_artifact_root(self):
        with self.assertRaisesRegex(ValueError, "outside artifact_root"):
            cam._assert_output_outside_artifact_root(self.root / "manifest.json", self.root)
        outside = Path(self.tmp.name) / "manifest.json"
        cam._assert_output_outside_artifact_root(outside, self.root)

    def test_adapter_cannot_be_mislabeled_as_checkpoint(self):
        s = full_checkpoint_spec()
        s["adapter_state_sha256"] = H["adapter"]
        with self.assertRaisesRegex(ValueError, "full_checkpoint must not claim adapter_state_sha256"):
            cam.build_manifest(s, self.root)

    def test_adapter_training_bindings_are_atomic_but_may_both_be_null(self):
        s = adapter_spec()
        s["training_shard_manifest_sha256"] = None
        with self.assertRaisesRegex(ValueError, "training bindings are atomic"):
            cam.build_manifest(s, self.root)
        imported = adapter_spec()
        imported["training_shard_manifest_sha256"] = None
        imported["training_run_receipt_sha256"] = None
        m = cam.build_manifest(imported, self.root)
        self.assertIsNone(m["training_shard_manifest_sha256"])
        self.assertIsNone(m["training_run_receipt_sha256"])

    def test_full_checkpoint_requires_checkpoint_state_and_atomic_training_bindings(self):
        s = full_checkpoint_spec()
        s["checkpoint_state_sha256"] = None
        with self.assertRaisesRegex(ValueError, "full_checkpoint requires checkpoint_state_sha256"):
            cam.build_manifest(s, self.root)
        imported = full_checkpoint_spec()
        imported["training_shard_manifest_sha256"] = None
        imported["training_run_receipt_sha256"] = None
        self.assertEqual(cam.validate_manifest(cam.build_manifest(imported, self.root), self.root), [])

    def test_merge_requires_two_parents_recipe_and_exactly_one_state_identity(self):
        s = adapter_spec()
        s.update({
            "artifact_type": "merge",
            "artifact_stage": "merge_candidate",
            "training_shard_manifest_sha256": None,
            "training_run_receipt_sha256": None,
            "merge_recipe_sha256": H["merge"],
            "parent_candidate_artifact_manifest_sha256": [H["parent2"], H["parent1"]],
        })
        m = cam.build_manifest(s, self.root)
        self.assertEqual(m["parent_candidate_artifact_manifest_sha256"], sorted([H["parent1"], H["parent2"]]))
        bad = copy.deepcopy(s)
        bad["parent_candidate_artifact_manifest_sha256"] = [H["parent1"]]
        with self.assertRaisesRegex(ValueError, "at least two parent"):
            cam.build_manifest(bad, self.root)

    def test_quantized_artifact_requires_single_parent_and_checkpoint_state(self):
        s = full_checkpoint_spec()
        s.update({
            "artifact_type": "quantized_serving_artifact",
            "artifact_stage": "release_candidate",
            "training_shard_manifest_sha256": None,
            "training_run_receipt_sha256": None,
            "parent_candidate_artifact_manifest_sha256": [H["parent1"]],
        })
        m = cam.build_manifest(s, self.root)
        self.assertEqual(m["artifact_type"], "quantized_serving_artifact")
        bad = copy.deepcopy(s)
        bad["parent_candidate_artifact_manifest_sha256"] = []
        with self.assertRaisesRegex(ValueError, "requires exactly one parent"):
            cam.build_manifest(bad, self.root)

    def test_duplicate_parent_hashes_fail_closed(self):
        s = adapter_spec()
        s["parent_candidate_artifact_manifest_sha256"] = [H["parent1"], H["parent1"]]
        with self.assertRaisesRegex(ValueError, "must be unique"):
            cam.build_manifest(s, self.root)

    def test_path_traversal_and_noncanonical_paths_fail_closed(self):
        m = cam.build_manifest(adapter_spec(), self.root)
        m["artifact_files"][0]["path"] = "../escape"
        errors = cam.validate_manifest(m)
        self.assertTrue(any("unsafe artifact path" in x for x in errors))

    def test_symlink_in_artifact_tree_fails_closed(self):
        target = self.root / "real.bin"
        target.write_bytes(b"real")
        link = self.root / "link.bin"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported")
        with self.assertRaisesRegex(ValueError, "symlink file"):
            cam.build_artifact_file_tree(self.root)

    def _make_g1_fixture(self):
        g1_root = Path(self.tmp.name) / "g1_adapter"
        g1_root.mkdir()
        write_artifact(g1_root, "adapter_model.safetensors", b"weights")
        write_artifact(g1_root, "adapter_config.json", b"{}")
        file_tree = cam.build_artifact_file_tree(g1_root)
        file_map = {x["path"]: x["sha256"] for x in file_tree}
        report = {
            "status": "PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL",
            "plan": {
                "model": "Qwen/Qwen3.8-27B",
                "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
                "mode": "bf16",
                "policy_state": {"canonical_preferred": True},
            },
            "artifact": {
                "file_sha256": file_map,
                "saved_adapter_state_sha256": H["adapter"],
                "reloaded_adapter_state_sha256": H["adapter"],
                "reload_hash_match": True,
            },
            "environment": {
                "transformers": "5.17.0",
                "peft": "0.21.0",
                "accelerate": "1.15.0",
                "gpu_name": "fixture-only",
            },
        }
        report_path = Path(self.tmp.name) / "g1_report.json"
        report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        bindings = {
            "base_manifest_sha256": H["base"],
            "tokenizer_sha256": H["tokenizer"],
            "config_sha256": H["config"],
            "training_shard_manifest_sha256": H["shard"],
            "parameter_layout_sha256": H["layout"],
        }
        return g1_root, report_path, report, bindings

    def test_g1_integration_is_forced_adapter_probe_only(self):
        root, report_path, report, bindings = self._make_g1_fixture()
        m = cam.build_probe_only_manifest_from_g1(report_path, root, bindings)
        self.assertEqual(m["artifact_type"], "adapter")
        self.assertEqual(m["artifact_stage"], "probe_only")
        self.assertEqual(m["hash_profile"], cam.HASH_PROFILE)
        self.assertEqual(m["topology_class"], "CUSTOM_EXPERIMENTAL")
        self.assertEqual(m["training_run_receipt_sha256"], cam.sha256_file(report_path))
        self.assertEqual(
            m["environment_toolchain_manifest_sha256"],
            cam.canonical_json_sha256(report["environment"]),
        )
        self.assertEqual(cam.validate_manifest(m, root), [])

    def test_g1_integration_rejects_experimental_qlora_status(self):
        root, report_path, report, bindings = self._make_g1_fixture()
        report["status"] = "PASS_EXPERIMENTAL_QLORA_DELTA_SMOKE_NOT_CANONICAL_G1"
        report["plan"]["mode"] = "qlora-experimental"
        report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "canonical BF16"):
            cam.build_probe_only_manifest_from_g1(report_path, root, bindings)

    def test_g1_integration_rejects_artifact_map_tamper(self):
        root, report_path, report, bindings = self._make_g1_fixture()
        report["artifact"]["file_sha256"]["adapter_model.safetensors"] = H["other"]
        report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match artifact_root"):
            cam.build_probe_only_manifest_from_g1(report_path, root, bindings)

    def test_g1_integration_requires_training_shard_binding(self):
        root, report_path, _report, bindings = self._make_g1_fixture()
        bindings.pop("training_shard_manifest_sha256")
        with self.assertRaisesRegex(ValueError, "bindings.training_shard_manifest_sha256"):
            cam.build_probe_only_manifest_from_g1(report_path, root, bindings)

    def test_g1_integration_rejects_reload_hash_mismatch(self):
        root, report_path, report, bindings = self._make_g1_fixture()
        report["artifact"]["reloaded_adapter_state_sha256"] = H["other"]
        report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "saved/reloaded"):
            cam.build_probe_only_manifest_from_g1(report_path, root, bindings)


if __name__ == "__main__":
    unittest.main()