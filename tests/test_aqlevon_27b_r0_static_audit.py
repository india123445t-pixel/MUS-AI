from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "research" / "weight_factory" / "agent03" / "aqlevon_27b_r0_static_audit_v1.py"

spec = importlib.util.spec_from_file_location("aqlevon_27b_r0_static_audit_v1", AUDIT_PATH)
assert spec is not None and spec.loader is not None
audit_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_mod)


class AQLEVON27BR0StaticAuditTests(unittest.TestCase):
    def test_helpers(self) -> None:
        constants = audit_mod.literal_constants('A=1\nB="x"\nC={"k": 2}\n')
        self.assertEqual(constants["A"], 1)
        self.assertEqual(constants["B"], "x")
        self.assertEqual(constants["C"], {"k": 2})
        self.assertTrue(audit_mod.top_level_yaml_key("name: x\nconcurrency:\n  group: y\n", "concurrency"))
        self.assertFalse(audit_mod.top_level_yaml_key("jobs:\n  concurrency: nested\n", "concurrency"))

    def test_exact_historical_path_and_receipt(self) -> None:
        report = audit_mod.audit()
        self.assertTrue(report["all_invariants_pass"], report)
        self.assertTrue(report["all_receipt_checks_pass"], report)
        self.assertTrue(all(report["findings"].values()), report)

        self.assertTrue(report["findings"]["baseline_final_sampling_is_not_pairwise"])
        self.assertTrue(report["findings"]["workflow_has_no_concurrency_guard"])
        self.assertTrue(report["findings"]["adapter_bytes_not_durably_exported_by_historical_path"])
        self.assertTrue(report["findings"]["runtime_dependency_versions_not_in_durable_receipt"])


if __name__ == "__main__":
    unittest.main()
