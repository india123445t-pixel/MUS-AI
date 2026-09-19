from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

p3 = load_module("p3_g1_ready", ROOT / "p3_g1_ready.py")
sur = load_module("p3_surrogate_runner", ROOT / "p3_surrogate_runner.py")

H = {x: hashlib.sha256(x.encode()).hexdigest() for x in ("base","tok","cfg","shard","layout","state","tree","manifest")}

def official_config():
    return {
        "architectures": ["Qwen3_5ForConditionalGeneration"],
        "model_type": "qwen3_5",
        "text_config": {
            "dtype": "bfloat16",
            "hidden_size": 5120,
            "num_hidden_layers": 64,
            "layer_types": ["linear_attention","linear_attention","linear_attention","full_attention"] * 16,
        },
    }

class P3G1ReadyTests(unittest.TestCase):
    def test_pins_exact_27b_and_same_arch_surrogate(self):
        self.assertEqual(p3.MODEL_ID, "Qwen/Qwen3.8-27B")
        self.assertEqual(p3.MODEL_REVISION, "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")
        self.assertEqual(sur.MODEL_ID, "Qwen/Qwen3.5-4B-Base")
        self.assertEqual(sur.REVISION, "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5")

    def test_nvidia_smi_parser(self):
        rows = p3.parse_nvidia_smi_csv("0, NVIDIA H100 80GB HBM3, 81559\n1, RTX 6000 Ada, 49140\n")
        self.assertEqual(rows[0]["index"], 0)
        self.assertEqual(rows[0]["memory_total_mib"], 81559)
        self.assertEqual(rows[1]["name"], "RTX 6000 Ada")
        with self.assertRaises(ValueError):
            p3.parse_nvidia_smi_csv("")
        with self.assertRaises(ValueError):
            p3.parse_nvidia_smi_csv("broken")

    def test_hardware_profiles_fail_closed_no_fallback(self):
        self.assertEqual(p3.validate_hardware("1x80", [{"index":0,"name":"H100","memory_total_mib":81559}])["status"], "PASS")
        self.assertEqual(p3.validate_hardware("2x48", [
            {"index":0,"name":"A6000","memory_total_mib":49140},
            {"index":1,"name":"A6000","memory_total_mib":49140},
        ])["status"], "PASS")
        self.assertEqual(p3.validate_hardware("4x24", [
            {"index":i,"name":"4090","memory_total_mib":24564} for i in range(4)
        ])["status"], "PASS")
        with self.assertRaisesRegex(RuntimeError, "exactly 1"):
            p3.validate_hardware("1x80", [
                {"index":0,"name":"A6000","memory_total_mib":49140},
                {"index":1,"name":"A6000","memory_total_mib":49140},
            ])
        with self.assertRaisesRegex(RuntimeError, "too-small"):
            p3.validate_hardware("1x80", [{"index":0,"name":"A6000","memory_total_mib":49140}])
        with self.assertRaisesRegex(RuntimeError, "exactly 4"):
            p3.validate_hardware("4x24", [{"index":i,"name":"4090","memory_total_mib":24564} for i in range(3)])

    def test_official_layout_static_preflight(self):
        out = p3.validate_official_config(official_config())
        self.assertEqual(out["full_attention_layers"], 16)
        self.assertEqual(out["linear_attention_layers"], 48)
        bad = official_config()
        bad["text_config"]["layer_types"][0] = "full_attention"
        with self.assertRaisesRegex(RuntimeError, "16 full/48 linear"):
            p3.validate_official_config(bad)

    def test_commands_are_explicit_bf16_and_profile_specific(self):
        c1 = p3.command_for_profile("1x80", output_dir=Path("/tmp/out"), max_length=128, here=ROOT)
        self.assertIn("aqlevon_g1_delta_probe.py", " ".join(c1))
        self.assertIn("bf16", c1)
        self.assertNotIn("qlora-experimental", c1)
        c2 = p3.command_for_profile("2x48", output_dir=Path("/tmp/out"), max_length=128, here=ROOT)
        self.assertEqual(c2[0:2], ["accelerate","launch"])
        self.assertIn("accelerate_fsdp2_2x48.yaml", " ".join(c2))
        self.assertIn("p3_g1_fsdp2_probe.py", " ".join(c2))
        self.assertIn("2", c2)
        c4 = p3.command_for_profile("4x24", output_dir=Path("/tmp/out"), max_length=128, here=ROOT)
        self.assertIn("accelerate_fsdp2_4x24.yaml", " ".join(c4))
        self.assertIn("4", c4)

    def test_profiles_freeze_no_auto_qlora(self):
        data = json.loads((ROOT / "p3_g1_profiles.json").read_text())
        self.assertFalse(data["automatic_fallback"])
        self.assertEqual(data["hardware_order"], ["1x80","2x48","4x24"])
        self.assertEqual(data["qlora"]["status"], "EXPERIMENTAL_ONLY")
        self.assertFalse(data["qlora"]["automatic_replacement_of_bf16"])
        self.assertEqual(data["model"]["precision"], "bf16")
        self.assertEqual(data["model"]["quantization"], "none")

    def test_fsdp2_configs_are_bf16_v2_and_exact_world_sizes(self):
        y2 = (ROOT / "accelerate_fsdp2_2x48.yaml").read_text()
        y4 = (ROOT / "accelerate_fsdp2_4x24.yaml").read_text()
        for y in (y2,y4):
            self.assertIn("distributed_type: FSDP", y)
            self.assertIn("fsdp_version: 2", y)
            self.assertIn("mixed_precision: bf16", y)
            self.assertIn("fsdp_cpu_ram_efficient_loading: true", y)
            self.assertIn("fsdp_reshard_after_forward: true", y)
            self.assertNotIn("fp8", y.lower())
        self.assertIn("num_processes: 2", y2)
        self.assertIn("num_processes: 4", y4)

    def test_fsdp2_source_preserves_bf16_truth_contract(self):
        text = (ROOT / "p3_g1_fsdp2_probe.py").read_text()
        for token in (
            "Accelerator(mixed_precision=\"bf16\")",
            "fsdp_version",
            "expected_world_size",
            "_linear_attn_preflight",
            "changed_elements",
            "delta_l2",
            "gradient_l2",
            "save_pretrained",
            "PeftModel.from_pretrained",
            "reload_state_hash",
            "PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL",
        ):
            self.assertIn(token, text)
        self.assertNotIn("BitsAndBytesConfig(", text)
        self.assertNotIn("qlora-experimental", text.lower())

    def test_surrogate_plan_is_bf16_hybrid_integrity_only(self):
        plan = sur.plan(128)
        self.assertEqual(plan["precision"], "bf16")
        self.assertEqual(plan["quantization"], "none")
        self.assertEqual(plan["optimizer_steps"], 1)
        self.assertIn("hybrid_gated_deltanet", plan["architecture_family"])
        self.assertIn("NOT_27B_CAPABILITY_GAIN", plan["authority_boundary"])

    def _fixture(self, td: Path):
        artifact = td / "adapter"
        artifact.mkdir()
        (artifact/"adapter_model.safetensors").write_bytes(b"weights")
        report = {
            "status":"PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL",
            "plan":{
                "model":p3.MODEL_ID,
                "revision":p3.MODEL_REVISION,
                "mode":"bf16",
                "policy_state":{"canonical_preferred":True},
            },
            "parameter_delta":{"changed_elements":12,"delta_l2":0.2,"gradient_l2":0.4},
            "artifact":{
                "saved_adapter_state_sha256":H["state"],
                "reloaded_adapter_state_sha256":H["state"],
                "reload_hash_match":True,
            },
            "micro_diagnostics_not_quality_evidence":{
                "train_loss_before":2.0,
                "train_loss_after":1.9,
                "holdout_loss_before":2.1,
                "holdout_loss_after":2.05,
                "holdout_loss_after_reload":2.050001,
            },
        }
        rp=td/"g1_delta_report.json"
        rp.write_text(json.dumps(report))
        manifest={
            "artifact_type":"adapter",
            "artifact_stage":"probe_only",
            "base":{"repo":p3.MODEL_ID,"revision":p3.MODEL_REVISION},
            "training_run_receipt_sha256":p3._sha256_file(rp),
            "adapter_state_sha256":H["state"],
            "manifest_sha256":H["manifest"],
            "artifact_file_tree_sha256":H["tree"],
        }
        mp=td/"candidate.json"; mp.write_text(json.dumps(manifest))
        return artifact,rp,mp,report,manifest

    def test_frozen_smoke_eval_pass_is_integrity_only(self):
        with tempfile.TemporaryDirectory() as d:
            td=Path(d)
            artifact,rp,mp,report,manifest=self._fixture(td)
            fake=types.SimpleNamespace(validate_manifest=lambda m,artifact_root=None: [])
            old=sys.modules.get("candidate_artifact_manifest")
            sys.modules["candidate_artifact_manifest"]=fake
            try:
                out=p3.frozen_smoke_eval(rp,mp,artifact)
            finally:
                if old is None: sys.modules.pop("candidate_artifact_manifest",None)
                else: sys.modules["candidate_artifact_manifest"]=old
            self.assertEqual(out["status"],"PASS_INTEGRITY_ONLY_NO_CAPABILITY_CLAIM")
            self.assertIn("NOT_WORKER05_PROMOTION_NOT_CAPABILITY_GAIN",out["authority_boundary"])
            self.assertEqual(len(out["smoke_eval_sha256"]),64)

    def test_frozen_smoke_eval_rejects_zero_delta_or_nonprobe(self):
        with tempfile.TemporaryDirectory() as d:
            td=Path(d)
            artifact,rp,mp,report,manifest=self._fixture(td)
            report["parameter_delta"]["changed_elements"]=0
            rp.write_text(json.dumps(report))
            with self.assertRaisesRegex(RuntimeError,"changed_elements"):
                p3._validate_report(report)
            report["parameter_delta"]["changed_elements"]=12
            rp.write_text(json.dumps(report))
            manifest["training_run_receipt_sha256"]=p3._sha256_file(rp)
            manifest["artifact_stage"]="promotion_candidate"
            mp.write_text(json.dumps(manifest))
            fake=types.SimpleNamespace(validate_manifest=lambda m,artifact_root=None: [])
            old=sys.modules.get("candidate_artifact_manifest")
            sys.modules["candidate_artifact_manifest"]=fake
            try:
                with self.assertRaisesRegex(RuntimeError,"adapter \\+ probe_only"):
                    p3.frozen_smoke_eval(rp,mp,artifact)
            finally:
                if old is None: sys.modules.pop("candidate_artifact_manifest",None)
                else: sys.modules["candidate_artifact_manifest"]=old

    def test_frozen_smoke_eval_rejects_reload_loss_drift(self):
        with tempfile.TemporaryDirectory() as d:
            td=Path(d)
            artifact,rp,mp,report,manifest=self._fixture(td)
            report["micro_diagnostics_not_quality_evidence"]["holdout_loss_after_reload"]=2.5
            rp.write_text(json.dumps(report))
            manifest["training_run_receipt_sha256"]=p3._sha256_file(rp)
            mp.write_text(json.dumps(manifest))
            fake=types.SimpleNamespace(validate_manifest=lambda m,artifact_root=None: [])
            old=sys.modules.get("candidate_artifact_manifest")
            sys.modules["candidate_artifact_manifest"]=fake
            try:
                with self.assertRaisesRegex(RuntimeError,"save/reload"):
                    p3.frozen_smoke_eval(rp,mp,artifact)
            finally:
                if old is None: sys.modules.pop("candidate_artifact_manifest",None)
                else: sys.modules["candidate_artifact_manifest"]=old

    def test_print_commands_and_surrogate_plan_require_no_ml_stack(self):
        cp=subprocess.run([sys.executable,str(ROOT/"p3_g1_ready.py"),"print-command","--profile","1x80"],capture_output=True,text=True)
        self.assertEqual(cp.returncode,0,cp.stderr)
        out=json.loads(cp.stdout)
        self.assertFalse(out["automatic_fallback"])
        self.assertIn("bf16",out["command"])
        sp=subprocess.run([sys.executable,str(ROOT/"p3_surrogate_runner.py"),"--print-plan"],capture_output=True,text=True)
        self.assertEqual(sp.returncode,0,sp.stderr)
        self.assertEqual(json.loads(sp.stdout)["revision"],sur.REVISION)

if __name__ == "__main__":
    unittest.main()
