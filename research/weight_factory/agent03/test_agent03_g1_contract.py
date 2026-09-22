from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "aqlevon_g1_delta_probe.py"
MANIFEST = HERE / "g1_run_manifest.template.json"


def load_probe():
    spec = importlib.util.spec_from_file_location("aqlevon_g1_delta_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def literal_constant(name: str):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"missing literal constant {name}")


class FakeWeight:
    def __init__(self, *, dtype="torch.bfloat16", shape=(8, 8), quant_state=None):
        self.dtype = dtype
        self.shape = shape
        self.quant_state = quant_state


class FakeLinear:
    def __init__(self, *, dtype="torch.bfloat16", shape=(8, 8), quant_state=None):
        self.weight = FakeWeight(dtype=dtype, shape=shape, quant_state=quant_state)
        self.out_features = shape[0] if len(shape) == 2 else 8
        self.in_features = shape[1] if len(shape) == 2 else 8


class Linear4bit(FakeLinear):
    pass


class FakeModel:
    def __init__(self, modules):
        self._modules = list(modules)

    def named_modules(self):
        return iter(self._modules)


def valid_linear_attn_model(probe):
    modules = []
    # 48 DeltaNet layers x 5 projection suffixes = 240.
    for layer in range(probe.EXPECTED_LINEAR_ATTN_LAYERS):
        for suffix in probe.LINEAR_ATTN_PROJECTION_SUFFIXES:
            name = f"model.language_model.layers.{layer}.linear_attn.{suffix}"
            modules.append((name, FakeLinear()))
    return FakeModel(modules)


class G1RepairContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe()
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_canonical_identity_is_hard_pinned(self):
        self.assertEqual(self.probe.MODEL_ID, "Qwen/Qwen3.8-27B")
        self.assertEqual(
            self.probe.REVISION,
            "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
        )

    def test_canonical_policy_defaults_to_bf16(self):
        p = self.probe.plan(128, self.probe.CANONICAL_PREFERRED_MODE)
        self.assertEqual(self.probe.CANONICAL_PREFERRED_MODE, "bf16")
        self.assertTrue(p["policy_state"]["canonical_preferred"])
        self.assertFalse(p["policy_state"]["experimental"])
        self.assertIn("BF16", p["quantization"])

    def test_qlora_is_explicit_experimental_challenger(self):
        p = self.probe.plan(128, self.probe.EXPERIMENTAL_MODE)
        self.assertEqual(self.probe.EXPERIMENTAL_MODE, "qlora-experimental")
        self.assertTrue(p["policy_state"]["experimental"])
        self.assertFalse(p["policy_state"]["canonical_preferred"])
        self.assertTrue(p["policy_state"]["quantization_regression_required_for_promotion"])
        with self.assertRaisesRegex(RuntimeError, "QLoRA is experimental"):
            self.probe._validate_mode_authorization(self.probe.EXPERIMENTAL_MODE, False)
        self.probe._validate_mode_authorization(self.probe.EXPERIMENTAL_MODE, True)

    def test_manifest_preserves_canonical_policy_truth_boundary(self):
        policy = self.manifest["canonical_policy"]
        self.assertEqual(policy["preferred_training"], "bf16_lora")
        self.assertEqual(policy["default_cli_mode"], "bf16")
        self.assertEqual(policy["qlora_4bit"], "experimental_challenger")
        self.assertIn("quantization_regression_pass", policy["experimental_requires_for_promotion"])
        self.assertFalse(self.manifest["promotion_allowed"])
        self.assertFalse(self.manifest["quality_claim_allowed"])

    def test_package_profile_is_exact_and_declared_unvalidated_on_gpu(self):
        expected = {
            "transformers": "5.17.0",
            "peft": "0.21.0",
            "bitsandbytes": "0.50.2",
            "accelerate": "1.15.0",
        }
        self.assertEqual(self.probe.PINNED_PACKAGE_VERSIONS, expected)
        profile = self.manifest["compatibility_profile"]
        self.assertEqual(profile["status"], "PINNED_FIRST_RUN_PROFILE_NOT_YET_GPU_VALIDATED")
        for k, v in expected.items():
            self.assertEqual(profile[k], v)

    def test_stack_mismatch_fails_closed(self):
        actual = dict(self.probe.PINNED_PACKAGE_VERSIONS)
        actual["transformers"] = "5.16.1"
        errors = self.probe._stack_errors(actual, "bf16")
        self.assertTrue(any("transformers must equal 5.17.0" in x for x in errors))
        actual = dict(self.probe.PINNED_PACKAGE_VERSIONS)
        actual["bitsandbytes"] = None
        self.assertEqual(self.probe._stack_errors(actual, "bf16"), [])
        q_errors = self.probe._stack_errors(actual, self.probe.EXPERIMENTAL_MODE)
        self.assertTrue(any("bitsandbytes must equal 0.50.2" in x for x in q_errors))

    def test_determinism_is_strict_not_warn_only(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("torch.use_deterministic_algorithms(True)", text)
        self.assertNotIn("warn_only=True", text)
        det = self.manifest["determinism"]
        self.assertTrue(det["torch_use_deterministic_algorithms"])
        self.assertFalse(det["warn_only"])

    def test_linear_attn_skip_list_is_explicit_and_complete(self):
        skips = self.probe.QLORA_SKIP_MODULES
        self.assertEqual(len(skips), 65)
        self.assertEqual(skips[0], "lm_head")
        for i in range(64):
            self.assertIn(f"model.language_model.layers.{i}.linear_attn", skips)
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("llm_int8_skip_modules=list(QLORA_SKIP_MODULES)", text)

    def test_valid_linear_attn_preflight_passes_all_240_projections(self):
        result = self.probe._linear_attn_preflight(
            valid_linear_attn_model(self.probe),
            self.probe.EXPERIMENTAL_MODE,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["observed_projection_count"], 240)
        self.assertEqual(result["required_dtype"], "bfloat16")
        self.assertEqual(result["required_quant_state"], "absent")

    def test_linear_attn_wrong_dtype_fails_closed(self):
        model = valid_linear_attn_model(self.probe)
        name, _ = model._modules[0]
        model._modules[0] = (name, FakeLinear(dtype="torch.uint8"))
        with self.assertRaisesRegex(RuntimeError, "expected BF16"):
            self.probe._linear_attn_preflight(model, self.probe.EXPERIMENTAL_MODE)

    def test_linear_attn_bad_shape_fails_closed(self):
        model = valid_linear_attn_model(self.probe)
        name, _ = model._modules[1]
        model._modules[1] = (name, FakeLinear(shape=(64,)))
        with self.assertRaisesRegex(RuntimeError, "expected 2-D"):
            self.probe._linear_attn_preflight(model, self.probe.EXPERIMENTAL_MODE)

    def test_linear_attn_quant_state_presence_fails_closed(self):
        model = valid_linear_attn_model(self.probe)
        name, _ = model._modules[2]
        model._modules[2] = (name, FakeLinear(quant_state=object()))
        with self.assertRaisesRegex(RuntimeError, "quant_state is present"):
            self.probe._linear_attn_preflight(model, self.probe.EXPERIMENTAL_MODE)

    def test_linear_attn_4bit_class_fails_closed(self):
        model = valid_linear_attn_model(self.probe)
        name, _ = model._modules[3]
        model._modules[3] = (name, Linear4bit())
        with self.assertRaisesRegex(RuntimeError, "unexpectedly converted"):
            self.probe._linear_attn_preflight(model, self.probe.EXPERIMENTAL_MODE)

    def test_missing_linear_attn_projection_fails_closed(self):
        model = valid_linear_attn_model(self.probe)
        model._modules.pop()
        with self.assertRaisesRegex(RuntimeError, "projection count mismatch"):
            self.probe._linear_attn_preflight(model, "bf16")

    def test_qlora_target_missing_quant_state_fails_closed(self):
        names = [
            "model.language_model.layers.3.self_attn.q_proj",
            "model.language_model.layers.3.self_attn.v_proj",
        ]
        model = FakeModel([(n, FakeLinear(quant_state=None)) for n in names])
        with self.assertRaisesRegex(RuntimeError, "missing quant_state"):
            self.probe._qlora_target_preflight(model, names)

    def test_delta_save_reload_hash_contract_remains_present(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "get_peft_model_state_dict",
            "changed_elements",
            "save_pretrained",
            "PeftModel.from_pretrained",
            "reload_state_hash",
            "_sha256_tree",
            "torch.cuda.max_memory_allocated",
            "reload_linear_attn_preflight",
        ):
            self.assertIn(required, text)

    def test_print_plan_defaults_to_bf16_without_ml_stack(self):
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--print-plan"],
            check=True,
            text=True,
            capture_output=True,
        )
        out = json.loads(p.stdout)
        self.assertEqual(out["mode"], "bf16")
        self.assertTrue(out["policy_state"]["canonical_preferred"])
        self.assertEqual(out["optimizer_steps"], 1)
        self.assertFalse(out["automatic_fallback"])

    def test_print_plan_can_describe_qlora_without_authorizing_execution(self):
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--mode", "qlora-experimental", "--print-plan"],
            check=True,
            text=True,
            capture_output=True,
        )
        out = json.loads(p.stdout)
        self.assertTrue(out["policy_state"]["experimental"])
        self.assertIn("linear_attn explicitly skipped", out["quantization"])


if __name__ == "__main__":
    unittest.main()
