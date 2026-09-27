#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, pathlib, unittest

HERE=pathlib.Path(__file__).resolve().parent
GEN=HERE/"aqlevon_27b_public_generalization_challenge_v1.py"
spec=importlib.util.spec_from_file_location("gxc",GEN)
gxc=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(gxc)

class ChallengeTests(unittest.TestCase):
    def test_generated_pack_self_hash(self):
        built=gxc.build_pack()
        claimed=built["pack_sha256"]
        body={k:v for k,v in built.items() if k!="pack_sha256"}
        self.assertEqual(claimed,gxc.sha256_obj(body))
        self.assertEqual(claimed,"10e049fa86fb034023bfa7e93a9dc0cfa58b3cff35718ef32b26533a18ff2b3b")

    def test_structure_is_not_atomic_training_template(self):
        pack=gxc.build_pack()
        self.assertEqual(pack["task_count"],16)
        self.assertTrue(all(t["exact_steps"]>=2 for t in pack["tasks"]))
        self.assertTrue(any(t["exact_steps"]==3 for t in pack["tasks"]))
        for t in pack["tasks"]:
            self.assertNotIn("Apply exactly this state transformation:",t["prompt"])
            self.assertNotIn("Initial state:",t["prompt"])
            self.assertNotRegex(t["task_id"],r"train-|eval-|tr\d\d")
        self.assertGreaterEqual(len({t["scenario"] for t in pack["tasks"]}),8)

    def test_all_reference_oracles_pass(self):
        for task_id,program in gxc.reference_oracles().items():
            self.assertTrue(gxc.verify_program(task_id,program)["passed"],task_id)

    def test_shortcuts_and_step_drops_fail(self):
        for task_id,program in gxc.reference_oracles().items():
            self.assertFalse(gxc.verify_program(task_id,program[:-1])["passed"],task_id)
            bad=[dict(x) for x in program]
            bad[0]={"op":"replace_state","state":{}}
            self.assertFalse(gxc.verify_program(task_id,bad)["passed"],task_id)

    def test_public_pack_exposes_no_oracle(self):
        raw=json.dumps(gxc.build_pack(),sort_keys=True,separators=(",",":"))
        self.assertNotIn('"oracle_program"',raw)
        self.assertFalse(gxc.build_pack()["protected_or_sealed_material_used"])

if __name__=="__main__":
    unittest.main()
