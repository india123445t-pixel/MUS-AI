from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research" / "weight_factory" / "agent03" / "aqlevon_27b_rerun_contract_v1.py"

spec = importlib.util.spec_from_file_location("aqlevon_27b_rerun_contract_v1", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AQLEVON27BRerunScientificContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = mod.load_contract()
        cls.w02 = mod.load_w02(cls.contract)
        cls.records = mod.build_task_records(cls.contract, cls.w02)
        cls.record_by_id = {r["task_id"]: r for r in cls.records}
        cls.pairs = mod.expected_pairs(cls.contract, cls.w02)

    def oracle_rows(self) -> list[dict]:
        rows = []
        for pair in self.pairs:
            oracle = self.record_by_id[pair["task_id"]]["_core"]["oracle_program"]
            rows.append({**pair, "output": json.dumps(oracle, ensure_ascii=False, separators=(",", ":"))})
        return rows

    def test_frozen_contract_matches_historical_recipe_and_blobs(self) -> None:
        report = mod.verify_contract()
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["training_recipe_match"])
        self.assertTrue(report["source_blobs_match"])
        self.assertTrue(report["same_seed_pairing"])
        self.assertEqual(report["contract_sha256"], "484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d")
        self.assertEqual(report["task_catalog_sha256"], "1ec78429ca5dc681361be281f94d945c0671f16328c983bd7494480ec4205388")
        self.assertEqual(report["pair_matrix_sha256"], "60e2653de2aaee2dae86414d5e69f5adf5dd2973a67056774ae7db3209f403a8")

    def test_base_and_candidate_have_identical_seed_sets_for_every_task(self) -> None:
        grouped: dict[tuple[str, str], dict[str, set[int]]] = {}
        for row in self.pairs:
            key = (row["split"], row["task_id"])
            grouped.setdefault(key, {}).setdefault(row["system"], set()).add(row["seed"])
        self.assertEqual(len(grouped), 56)
        for systems in grouped.values():
            self.assertEqual(set(systems), {"base", "candidate"})
            self.assertEqual(systems["base"], systems["candidate"])
            self.assertEqual(systems["base"], {1701, 271828})

    def test_no_task_or_seed_can_be_dropped_duplicated_or_substituted(self) -> None:
        rows = [{**pair, "output": "not-json"} for pair in self.pairs]
        self.assertEqual(len(mod.validate_result_rows(rows, self.contract)), 224)

        with self.assertRaisesRegex(mod.ContractError, "missing_pair"):
            mod.validate_result_rows(rows[1:], self.contract)

        with self.assertRaisesRegex(mod.ContractError, "duplicate_pair"):
            mod.validate_result_rows(rows + [dict(rows[0])], self.contract)

        wrong = [dict(r) for r in rows]
        wrong[0]["seed"] = 999999
        with self.assertRaisesRegex(mod.ContractError, "extra_or_wrong_pair"):
            mod.validate_result_rows(wrong, self.contract)

    def test_paired_score_is_deterministic_and_nonregression_threshold_is_enforced(self) -> None:
        rows = self.oracle_rows()
        score = mod.score_result_rows(rows, self.contract)
        self.assertEqual(score["metrics"]["base"], {"dev": 56, "shadow": 56, "total": 112})
        self.assertEqual(score["metrics"]["candidate"], {"dev": 56, "shadow": 56, "total": 112})
        self.assertEqual(score["delta"], {"dev": 0, "shadow": 0, "total": 0})
        self.assertTrue(score["paired_public_pass"])
        self.assertFalse(score["strict_gain_observed"])

        degraded = [dict(r) for r in rows]
        for row in degraded:
            if row["system"] == "candidate" and row["split"] == "dev":
                row["output"] = "[]"
                break
        failed = mod.score_result_rows(degraded, self.contract)
        self.assertEqual(failed["delta"]["dev"], -1)
        self.assertEqual(failed["delta"]["total"], -1)
        self.assertFalse(failed["paired_public_pass"])
        self.assertEqual(failed["status"], "PAIRED_PUBLIC_FAIL")

    def test_execution_plan_contains_only_public_source_derived_prompts(self) -> None:
        policy = self.contract["source_policy"]
        self.assertEqual(policy["private_or_sealed_source_count"], 0)
        self.assertFalse(policy["future_private_evaluation_authority"])
        self.assertEqual(len(policy["allowed_evaluation_sources"]), 1)
        locator = " ".join(
            str(policy["allowed_evaluation_sources"][0].get(k, ""))
            for k in ("path", "purpose", "visibility")
        ).lower()
        for forbidden in ("w05", "private", "sealed"):
            self.assertNotIn(forbidden, locator)

        plan = mod.build_execution_plan(self.contract)
        self.assertEqual(len(plan["rows"]), 224)
        self.assertNotIn("oracle_program", json.dumps(plan, ensure_ascii=False))
        self.assertEqual(plan["contract_sha256"], self.contract["contract_sha256"])
        self.assertEqual(plan["pair_matrix_sha256"], self.contract["paired_public_eval_v1"]["expected_pair_matrix_sha256"])


if __name__ == "__main__":
    unittest.main()
