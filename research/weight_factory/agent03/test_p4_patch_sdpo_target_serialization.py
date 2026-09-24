import unittest
from p4_patch_sdpo_transformers5_native_vllm019 import patch_sdpo_lora_target_modules_save

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

if __name__ == "__main__":
    unittest.main()
