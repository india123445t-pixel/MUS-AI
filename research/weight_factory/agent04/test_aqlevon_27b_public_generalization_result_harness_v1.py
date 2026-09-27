#!/usr/bin/env python3
from __future__ import annotations
import copy,importlib.util,json,pathlib,unittest
from fractions import Fraction

HERE=pathlib.Path(__file__).resolve().parent
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod); return mod
h=load(HERE/"aqlevon_27b_public_generalization_result_harness_v1.py","h")
gxc=load(HERE/"aqlevon_27b_public_generalization_challenge_v1.py","g")
TEMPLATE=HERE/"aqlevon_27b_public_generalization_execution_manifest_template_v1.json"

class HarnessTests(unittest.TestCase):
    def template(self):
        return json.loads(TEMPLATE.read_text(encoding="utf-8"))
    def manifest(self):
        return h.finalize_manifest(
            self.template(),adapter_sha256="a"*64,
            adapter_state_sha256="b"*64,candidate_manifest_sha256="c"*64)
    def filled(self,base_oracle=False,candidate_oracle=True):
        m=self.manifest(); rows=h.build_result_skeleton(m); oracles=gxc.reference_oracles()
        for r in rows:
            use=base_oracle if r["system"]=="canonical_base" else candidate_oracle
            r["raw_output"]=json.dumps(oracles[r["task_id"]] if use else [],separators=(",",":"))
        return m,rows

    def test_template_and_exact_128_pairs(self):
        h.validate_template(self.template())
        m=self.manifest(); rows=h.build_result_skeleton(m)
        self.assertEqual(len(rows),128)
        self.assertEqual(len({(r["system"],r["task_id"],r["seed"]) for r in rows}),128)
        self.assertEqual({r["seed"] for r in rows},set(h.SEEDS))
        self.assertEqual({r["system"] for r in rows},set(h.SYSTEMS))

    def test_frozen_metrics_perfect_candidate(self):
        m,rows=self.filled(False,True); r=h.score_results(m,rows)
        self.assertEqual(r["successes"]["canonical_base"],0)
        self.assertEqual(r["successes"]["candidate_adapter_on_same_base"],64)
        self.assertEqual(r["primary_delta_candidate_minus_base"],64)
        self.assertEqual(r["discordant_pairs"],{"candidate_wins":64,"base_wins":0,"total":64})
        self.assertEqual(r["paired_one_sided_exact_sign_binomial_p"]["fraction"],"1/18446744073709551616")
        self.assertEqual(r["robust_tasks"]["canonical_base"]["count"],0)
        self.assertEqual(r["robust_tasks"]["candidate_adapter_on_same_base"]["count"],16)
        self.assertTrue(r["support_observed"])

    def test_missing_pair_rejected(self):
        m,rows=self.filled(); rows.pop()
        with self.assertRaisesRegex(h.HarnessError,"missing_pair"): h.score_results(m,rows)

    def test_duplicate_pair_rejected(self):
        m,rows=self.filled(); rows.append(copy.deepcopy(rows[0]))
        with self.assertRaisesRegex(h.HarnessError,"duplicate_pair"): h.score_results(m,rows)

    def test_extra_pair_rejected(self):
        m,rows=self.filled(); rows[0]["task_id"]="gxc-v1-extra"
        with self.assertRaisesRegex(h.HarnessError,"extra_pair"): h.score_results(m,rows)

    def test_wrong_model_identity_rejected(self):
        m,rows=self.filled(); rows[0]["model_identity_sha256"]="0"*64
        with self.assertRaisesRegex(h.HarnessError,"model_identity_mismatch"): h.score_results(m,rows)

    def test_wrong_challenge_and_freeze_hash_rejected(self):
        for field,msg in (("challenge_pack_sha256","challenge_hash_mismatch"),("freeze_manifest_sha256","freeze_hash_mismatch")):
            m,rows=self.filled(); rows[0][field]="0"*64
            with self.subTest(field=field):
                with self.assertRaisesRegex(h.HarnessError,msg): h.score_results(m,rows)

    def test_malformed_envelope_type_rejected(self):
        m,rows=self.filled(); rows[0]["raw_output"]=7
        with self.assertRaisesRegex(h.HarnessError,"malformed_output_type"): h.score_results(m,rows)

    def test_malformed_model_text_is_failed_without_retry(self):
        m,rows=self.filled(True,True)
        target=next(r for r in rows if r["system"]=="canonical_base")
        target["raw_output"]="not-json"
        r=h.score_results(m,rows)
        self.assertEqual(r["malformed_outputs_scored_failed_no_retry"]["canonical_base"],1)
        self.assertEqual(r["successes"]["canonical_base"],63)
        self.assertEqual(r["successes"]["candidate_adapter_on_same_base"],64)
        self.assertEqual(r["primary_delta_candidate_minus_base"],1)
        self.assertFalse(r["support_observed"])

    def test_manifest_tamper_and_wrong_candidate_base_rejected(self):
        t=self.template(); t["generation"]["common_generation_seeds"]=[1,2,3,4]
        with self.assertRaisesRegex(h.HarnessError,"template_frozen_field_mismatch:generation"):
            h.finalize_manifest(t,adapter_sha256="a"*64,adapter_state_sha256="b"*64,candidate_manifest_sha256="c"*64)
        t=self.template(); t["candidate_identity"]["base_revision"]="wrong"
        with self.assertRaisesRegex(h.HarnessError,"template_candidate_base_mismatch"):
            h.finalize_manifest(t,adapter_sha256="a"*64,adapter_state_sha256="b"*64,candidate_manifest_sha256="c"*64)

    def test_exact_binomial_edge_math(self):
        self.assertEqual(h.exact_one_sided_sign_p(3,1),Fraction(5,16))
        self.assertEqual(h.exact_one_sided_sign_p(5,0),Fraction(1,32))
        self.assertEqual(h.exact_one_sided_sign_p(0,0),Fraction(1,1))

if __name__=="__main__":
    unittest.main()
