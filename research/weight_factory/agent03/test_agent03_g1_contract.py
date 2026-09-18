from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "aqlevon_g1_delta_probe.py"
MANIFEST = HERE / "g1_run_manifest.template.json"


def literal_constant(name: str):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"missing constant {name}")


class G1ContractTests(unittest.TestCase):
    def test_canonical_identity_is_hard_pinned(self):
        self.assertEqual(literal_constant("MODEL_ID"), "Qwen/Qwen3.8-27B")
        self.assertEqual(literal_constant("REVISION"), "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")

    def test_minimal_target_profile(self):
        self.assertEqual(tuple(literal_constant("TARGET_SUFFIXES")), ("q_proj", "v_proj"))
        self.assertEqual(literal_constant("LORA_R"), 4)
        self.assertEqual(literal_constant("EXPECTED_TARGET_MODULES"), 32)
        self.assertEqual(literal_constant("EXPECTED_TRAINABLE_PARAMS_R4"), 1_507_328)
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('target_modules="all-linear"', text)
        self.assertIn('".self_attn."', text)

    def test_delta_save_reload_hash_contract_present(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "get_peft_model_state_dict",
            "changed_elements",
            "save_pretrained",
            "PeftModel.from_pretrained",
            "reload_state_hash",
            "_sha256_tree",
            "torch.cuda.max_memory_allocated",
        ):
            self.assertIn(required, text)

    def test_qlora_is_nf4_on_exact_base_not_mirror(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('bnb_4bit_quant_type="nf4"', text)
        self.assertIn("bnb_4bit_use_double_quant=True", text)
        self.assertNotIn("Qwen3.8-27B-unsloth-bnb-4bit", text)

    def test_manifest_matches_probe(self):
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        recipe = m["preferred_cheapest_recipe"]
        self.assertEqual(m["base_model"], literal_constant("MODEL_ID"))
        self.assertEqual(m["base_revision"], literal_constant("REVISION"))
        self.assertEqual(recipe["lora_rank"], literal_constant("LORA_R"))
        self.assertEqual(recipe["expected_trainable_parameters"], literal_constant("EXPECTED_TRAINABLE_PARAMS_R4"))
        self.assertFalse(m["quality_claim_allowed"])
        self.assertFalse(m["compute_authorization"]["paid_compute_authorized"])

    def test_print_plan_runs_without_ml_stack(self):
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--print-plan"],
            check=True,
            text=True,
            capture_output=True,
        )
        out = json.loads(p.stdout)
        self.assertEqual(out["model"], "Qwen/Qwen3.8-27B")
        self.assertEqual(out["optimizer_steps"], 1)
        self.assertFalse(out["automatic_fallback"])


if __name__ == "__main__":
    unittest.main()
