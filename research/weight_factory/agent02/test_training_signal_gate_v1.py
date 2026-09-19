import copy, json, pathlib, subprocess, sys, tempfile, unittest
from training_signal_gate_v1 import (
    ADMIT,DENY,QUARANTINE,assess_record,build_protected_manifest,
    protected_overlap,record_content_sha256,sha256_text,source_registry_sha256,
    validate_manifest,validate_policy,validate_registry
)
ROOT=pathlib.Path(__file__).resolve().parent
POLICY=json.loads((ROOT/"training_signal_policy_v1.json").read_text(encoding="utf-8"))

def clean_registry():
    return {"schema_version":5,"policy":"default_deny","sources":[
        {"id":"synthetic-local-v1","kind":"synthetic_dataset","admission":"candidate_allow","license":"internal"},
        {"id":"agent0_recipe","kind":"code_recipe","admission":"recipe_allow","license":"Apache-2.0"},
        {"id":"fake_recipe_allow_dataset","kind":"dataset","admission":"recipe_allow","license":"Apache-2.0"},
        {"id":"code_recipe_allow","kind":"code_recipe","admission":"allow","license":"Apache-2.0"},
    ]}

def clean_record(registry=None):
    registry=registry or clean_registry()
    r={
      "record_id":"train-001",
      "prompt":"Compute the exact integer result for 37 plus 58 and return only the number.",
      "answer":"95",
      "source":{
        "id":"synthetic-local-v1","revision":"a1b2c3d4","immutable_revision":True,
        "content_sha256":sha256_text("artifact/synthetic-local-v1/a1b2c3d4"),
        "registry_sha256":source_registry_sha256(registry),
        "kind":"synthetic_dataset","admission":"candidate_allow",
        "license_status":"cleared","provenance_status":"complete"
      },
      "protected_eval":False,
      "contamination":{"holdout_scan_completed":True,"protected_eval_hits":0},
      "dedup":{"is_canonical":True,"semantic_duplicate_score":0.20},
      "verifiers":[{"type":"numeric","passed":True,"target_failure_modes":["wrong_final_answer"],
                    "fault_injection_passed":True,"independent_observation":True}],
      "baseline":{"attempts":10,"successes":4},
      "language_lane":"other","synthetic":True
    }
    r["record_content_sha256"]=record_content_sha256(r)
    return r

class GateTests(unittest.TestCase):
    def setUp(self):
        self.registry=clean_registry()
        self.manifest=build_protected_manifest(
          ["Protected benchmark question with secret expected answer alpha beta gamma delta epsilon zeta eta theta iota."],
          8,"test-holdout-v1")

    def assess(self,r,policy=None,manifest=None,registry=None):
        return assess_record(r,policy or POLICY,manifest or self.manifest,registry or self.registry)

    def test_clean_record_admitted(self):
        self.assertEqual(self.assess(clean_record(self.registry)).decision,ADMIT)

    # Manager blocker 1: recipe/source-kind separation + trusted registry binding.
    def test_recipe_allow_code_recipe_denied(self):
        r=clean_record(self.registry); r["source"].update(id="agent0_recipe",kind="code_recipe",admission="recipe_allow")
        r["record_content_sha256"]=record_content_sha256(r)
        d=self.assess(r)
        self.assertEqual(d.decision,DENY); self.assertIn("recipe_only_source_kind_not_trainable",d.reasons)

    def test_recipe_allow_even_dataset_kind_denied(self):
        r=clean_record(self.registry); r["source"].update(id="fake_recipe_allow_dataset",kind="dataset",admission="recipe_allow")
        r["record_content_sha256"]=record_content_sha256(r)
        d=self.assess(r)
        self.assertEqual(d.decision,DENY); self.assertIn("recipe_allow_not_trainable_data_admission",d.reasons)

    def test_recipe_kind_denied_even_if_admission_allow(self):
        r=clean_record(self.registry); r["source"].update(id="code_recipe_allow",kind="code_recipe",admission="allow")
        r["record_content_sha256"]=record_content_sha256(r)
        self.assertEqual(self.assess(r).decision,DENY)

    def test_unregistered_source_denied(self):
        r=clean_record(self.registry); r["source"]["id"]="invented"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("source_not_in_trusted_registry",self.assess(r).reasons)

    def test_source_kind_self_claim_must_match_registry(self):
        r=clean_record(self.registry); r["source"]["kind"]="dataset"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("source_kind_registry_mismatch",self.assess(r).reasons)

    def test_source_admission_self_claim_must_match_registry(self):
        r=clean_record(self.registry); r["source"]["admission"]="allow"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("source_admission_registry_mismatch",self.assess(r).reasons)

    def test_registry_digest_binding(self):
        r=clean_record(self.registry); r["source"]["registry_sha256"]="0"*64
        self.assertIn("source_registry_sha256_mismatch",self.assess(r).reasons)

    # Manager blocker 2: canonical row hash and tamper evidence.
    def test_prompt_tamper_denied(self):
        r=clean_record(self.registry); r["prompt"]+=" tampered"
        d=self.assess(r)
        self.assertEqual(d.decision,DENY); self.assertIn("record_content_sha256_mismatch",d.reasons)

    def test_answer_tamper_denied(self):
        r=clean_record(self.registry); r["answer"]="96"
        self.assertIn("record_content_sha256_mismatch",self.assess(r).reasons)

    def test_invalid_row_hash_format_denied(self):
        r=clean_record(self.registry); r["record_content_sha256"]="not-a-sha"
        self.assertIn("invalid_record_content_sha256",self.assess(r).reasons)

    def test_newline_normalization_is_stable(self):
        r=clean_record(self.registry); r["prompt"]="line1\r\nline2"; r["record_content_sha256"]=record_content_sha256(r)
        r["prompt"]="line1\nline2"
        self.assertEqual(record_content_sha256(r),r["record_content_sha256"])

    # Manager blocker 3: manifest digest/type hardening.
    def test_manifest_integrity(self):
        self.assertEqual(validate_manifest(self.manifest),(True,"ok"))
        bad=copy.deepcopy(self.manifest); bad["record_count"]+=1
        self.assertIn("digest_mismatch",validate_manifest(bad)[1])

    def test_manifest_zero_ngram_denied(self):
        bad=copy.deepcopy(self.manifest); bad["ngram_size"]=0
        self.assertIn("invalid_ngram_size",self.assess(clean_record(self.registry),manifest=bad).reasons[0])

    def test_manifest_string_ngram_denied(self):
        bad=copy.deepcopy(self.manifest); bad["ngram_size"]="8"
        self.assertIn("invalid_ngram_size",self.assess(clean_record(self.registry),manifest=bad).reasons[0])

    def test_manifest_bad_hash_entry_denied(self):
        bad=copy.deepcopy(self.manifest); bad["ngram_hashes"]=["xyz"]
        self.assertIn("protected_manifest_invalid_ngram_hashes_digest",self.assess(clean_record(self.registry),manifest=bad).reasons)

    def test_manifest_bad_manifest_digest_format_denied(self):
        bad=copy.deepcopy(self.manifest); bad["manifest_sha256"]="z"*64
        self.assertIn("invalid_manifest_sha256",self.assess(clean_record(self.registry),manifest=bad).reasons[0])

    def test_manifest_policy_ngram_mismatch_denied(self):
        m=build_protected_manifest(["abc def ghi jkl mno pqr stu vwx yz"],7,"other")
        self.assertIn("protected_manifest_policy_ngram_mismatch",self.assess(clean_record(self.registry),manifest=m).reasons)

    def test_build_manifest_rejects_nonpositive_ngram(self):
        with self.assertRaises(ValueError): build_protected_manifest(["x"],0,"id")

    # Manager non-blocking hardening: schema/type failures are controlled DENY.
    def test_policy_bad_type_returns_deny(self):
        p=copy.deepcopy(POLICY); p["learnability"]["min_attempts"]="four"
        d=self.assess(clean_record(self.registry),policy=p)
        self.assertEqual(d.decision,DENY); self.assertIn("policy_invalid_min_attempts",d.reasons)

    def test_policy_cannot_reenable_recipe_allow(self):
        p=copy.deepcopy(POLICY); p["trainable_source_admissions"].append("recipe_allow")
        self.assertIn("policy_recipe_allow_cannot_train_rows",self.assess(clean_record(self.registry),policy=p).reasons)

    def test_invalid_protected_hit_type_denied(self):
        r=clean_record(self.registry); r["contamination"]["protected_eval_hits"]="0"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("invalid_protected_eval_hits",self.assess(r).reasons)

    def test_invalid_baseline_type_denied(self):
        r=clean_record(self.registry); r["baseline"]["attempts"]="10"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("invalid_baseline_count_types",self.assess(r).reasons)

    def test_invalid_semantic_duplicate_type_denied(self):
        r=clean_record(self.registry); r["dedup"]["semantic_duplicate_score"]="0.2"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("invalid_semantic_duplicate_score",self.assess(r).reasons)

    def test_malformed_registry_denied(self):
        bad={"schema_version":5,"policy":"default_deny","sources":"not-list"}
        d=assess_record(clean_record(self.registry),POLICY,self.manifest,bad)
        self.assertEqual(d.decision,DENY); self.assertIn("source_registry_sources_not_list",d.reasons)

    # Preserve original control-plane gates.
    def test_missing_required_denied(self):
        r=clean_record(self.registry); del r["source"]["license_status"]
        self.assertTrue(self.assess(r).reasons[0].startswith("missing_required:"))

    def test_protected_flag_denied(self):
        r=clean_record(self.registry); r["protected_eval"]=True; r["record_content_sha256"]=record_content_sha256(r)
        self.assertEqual(self.assess(r).decision,DENY)

    def test_protected_overlap_denied(self):
        r=clean_record(self.registry); r["prompt"]="Protected benchmark question with secret expected answer alpha beta gamma delta epsilon zeta eta theta iota."
        r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("protected_manifest_overlap",self.assess(r).reasons)

    def test_uncleared_license_denied(self):
        r=clean_record(self.registry); r["source"]["license_status"]="audit_required"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("license_not_cleared",self.assess(r).reasons)

    def test_mutable_revision_denied(self):
        r=clean_record(self.registry); r["source"]["immutable_revision"]=False; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("source_revision_not_immutable",self.assess(r).reasons)

    def test_semantic_only_verifier_quarantined(self):
        r=clean_record(self.registry); r["verifiers"]=[{"type":"learned_semantic","passed":True,"target_failure_modes":["semantic"],"fault_injection_passed":True,"independent_observation":True}]
        r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("no_qualified_hard_verifier",self.assess(r).reasons)

    def test_verifier_theatre_quarantined(self):
        r=clean_record(self.registry); r["verifiers"][0]["fault_injection_passed"]=False; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("verifier_0_not_fault_tested",self.assess(r).reasons)

    def test_saturated_is_quarantined(self):
        r=clean_record(self.registry); r["baseline"]={"attempts":10,"successes":10}; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("already_mastered_low_information_gain",self.assess(r).reasons)

    def test_too_hard_is_quarantined(self):
        r=clean_record(self.registry); r["baseline"]={"attempts":10,"successes":0}; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("too_hard_or_unstable_for_current_stage",self.assess(r).reasons)

    def test_darija_requires_audit(self):
        r=clean_record(self.registry); r["language_lane"]="darija"; r["record_content_sha256"]=record_content_sha256(r)
        self.assertIn("language_quality_audit_required",self.assess(r).reasons)
        r["language_quality_audit"]={"passed":True,"auditor_class":"native_moroccan_review"}
        self.assertEqual(self.assess(r).decision,ADMIT)

    def test_noncanonical_duplicate_quarantined(self):
        r=clean_record(self.registry); r["dedup"]["is_canonical"]=False; r["record_content_sha256"]=record_content_sha256(r)
        self.assertEqual(self.assess(r).decision,QUARANTINE)

    def test_short_protected_record_hash(self):
        m=build_protected_manifest(["secret tiny item"],8,"short-v1")
        self.assertTrue(protected_overlap("secret tiny item",m)["matched"])

    def test_cli_malformed_policy_fails_closed_and_writes_deny(self):
        with tempfile.TemporaryDirectory() as td:
            td=pathlib.Path(td)
            (td/"bad.json").write_text("{bad",encoding="utf-8")
            (td/"manifest.json").write_text(json.dumps(self.manifest),encoding="utf-8")
            (td/"registry.json").write_text(json.dumps(self.registry),encoding="utf-8")
            r=clean_record(self.registry)
            (td/"input.jsonl").write_text(json.dumps(r)+"\n",encoding="utf-8")
            cmd=[sys.executable,str(ROOT/"training_signal_gate_v1.py"),"gate","--policy",str(td/"bad.json"),
                 "--protected-manifest",str(td/"manifest.json"),"--source-registry",str(td/"registry.json"),
                 "--input",str(td/"input.jsonl"),"--admitted",str(td/"a.jsonl"),"--quarantine",str(td/"q.jsonl"),"--denied",str(td/"d.jsonl")]
            cp=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(cp.returncode,2)
            denied=[json.loads(x) for x in (td/"d.jsonl").read_text().splitlines()]
            self.assertEqual(len(denied),1)
            self.assertEqual(denied[0]["training_signal_decision"]["decision"],DENY)
            self.assertIn("config_parse_error",denied[0]["training_signal_decision"]["reasons"][0])

if __name__=="__main__": unittest.main()
