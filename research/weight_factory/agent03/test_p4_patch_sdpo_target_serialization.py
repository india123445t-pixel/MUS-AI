import unittest

from p4_patch_sdpo_transformers5_native_vllm019 import (
    _aqlevon_extract_qwen35_lora_state_dict,
    patch_sdpo_lora_state_sync,
    patch_sdpo_lora_target_modules_save,
)


class TestTargetSerialization(unittest.TestCase):
    SOURCE = '                peft_config["target_modules"] = list(peft_config["target_modules"])\n'
    REGEX = r".*\.self_attn\.(q_proj|v_proj)$"

    def test_regex_survives_and_patch_is_idempotent(self):
        patched = patch_sdpo_lora_target_modules_save(self.SOURCE)
        scope = {"peft_config": {"target_modules": self.REGEX}}
        exec("def save_target():\n" + patched, scope)
        scope["save_target"]()
        self.assertEqual(scope["peft_config"]["target_modules"], self.REGEX)
        self.assertEqual(patch_sdpo_lora_target_modules_save(patched), patched)

    def test_sequences_are_sorted(self):
        patched = patch_sdpo_lora_target_modules_save(self.SOURCE)
        scope = {"peft_config": {"target_modules": {"v_proj", "q_proj"}}}
        exec("def save_target():\n" + patched, scope)
        scope["save_target"]()
        self.assertEqual(scope["peft_config"]["target_modules"], ["q_proj", "v_proj"])

    def test_changed_upstream_anchor_fails_closed(self):
        with self.assertRaisesRegex(SystemExit, "expected_once"):
            patch_sdpo_lora_target_modules_save("other source\n")


class TestFSDPLoRAStateExtraction(unittest.TestCase):
    LAYERS = (3, 7, 11, 15, 19, 23, 27, 31)

    def raw_state(self):
        state = {
            "base_model.model.model.language_model.layers.3.self_attn.q_proj.base_layer.weight": "base"
        }
        for layer in self.LAYERS:
            for projection in ("q_proj", "v_proj"):
                for kind in ("A", "B"):
                    key = (
                        f"base_model.model.model.language_model.layers.{layer}.self_attn."
                        f"{projection}.lora_{kind}.default.weight"
                    )
                    state[key] = f"{layer}:{projection}:{kind}"
        return state

    def test_normalizes_default_adapter_and_returns_only_exact_32_targets(self):
        raw = self.raw_state()
        extracted = _aqlevon_extract_qwen35_lora_state_dict(raw)
        self.assertEqual(len(extracted), 32)
        self.assertEqual(sum(".lora_A." in key for key in extracted), 16)
        self.assertEqual(sum(".lora_B." in key for key in extracted), 16)
        self.assertFalse(any(".default." in key for key in extracted))
        self.assertNotIn("base_model.model.model.language_model.layers.3.self_attn.q_proj.base_layer.weight", extracted)
        self.assertEqual(
            extracted["base_model.model.model.language_model.layers.3.self_attn.q_proj.lora_A.weight"],
            "3:q_proj:A",
        )

    def test_missing_or_extra_targets_fail_closed(self):
        missing = self.raw_state()
        missing.pop(
            "base_model.model.model.language_model.layers.31.self_attn.v_proj.lora_B.default.weight"
        )
        with self.assertRaisesRegex(RuntimeError, "AQLEVON_FSDP_LORA_STATE_KEYS"):
            _aqlevon_extract_qwen35_lora_state_dict(missing)

        extra = self.raw_state()
        extra["base_model.model.model.language_model.layers.2.self_attn.k_proj.lora_A.default.weight"] = "extra"
        with self.assertRaisesRegex(RuntimeError, "AQLEVON_FSDP_LORA_STATE_KEYS"):
            _aqlevon_extract_qwen35_lora_state_dict(extra)

    def test_sdpo_patch_uses_raw_state_extractor_and_is_idempotent(self):
        upstream = (
            "                if base_sync_done:\n"
            "                    lora_params = get_peft_model_state_dict(peft_model)\n"
            "                    lora_params = {\n"
            "                        name: param.full_tensor().detach().cpu()\n"
            "                        if hasattr(param, \"full_tensor\")\n"
            "                        else param.detach().cpu()\n"
            "                        for name, param in lora_params.items()\n"
            "                    }\n"
            "def collect_lora_params(module):\n"
            "    pass\n"
        )
        patched = patch_sdpo_lora_state_sync(upstream)
        self.assertIn("def _aqlevon_extract_qwen35_lora_state_dict(", patched)
        self.assertIn("_aqlevon_extract_qwen35_lora_state_dict(", patched)
        self.assertIn("AQLEVON_SDPO_QWEN35_RAW_FSDP_LORA_STATE", patched)
        self.assertEqual(patch_sdpo_lora_state_sync(patched), patched)


if __name__ == "__main__":
    unittest.main()
