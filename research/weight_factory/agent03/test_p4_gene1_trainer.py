from __future__ import annotations
import copy, hashlib, json, tempfile, unittest
from pathlib import Path
import p4_gene1_trainer as p4
import p4_sft_surrogate as sft

H=lambda s: hashlib.sha256(s.encode()).hexdigest()

def method_spec():
    obj={
        "schema_version":1,"spec_kind":p4.METHOD_SPEC_KIND,"hash_profile":p4.HASH_PROFILE,
        "worker_id":"01","task_id":"P4-A01-METHOD-TOURNAMENT-DIRECTOR",
        "arms":[{
            "arm_id":"A0","method":"SFT_LORA_CONTROL","seed_policy":{"seeds":[1701]},
            "budget":{"optimizer_updates":24,"max_gpu_seconds":3600},
            "optimizer":{"name":"adamw","lr_decimal":"0.00001"},
            "stop_conditions":["nonfinite","compute_ceiling"],
            "runner_parameters":{"lora_rank":4,"target_modules":["q_proj","v_proj"]},
        }],
    }
    return p4.seal(obj,"spec_sha256")

def shard_fixture():
    row={"row_kind":"AQLEVON_TRAINING_SHARD_ROW_V1","record_id":"r1","prompt":"p","answer":"a","record_content_sha256":H("r1"),"source":{"id":"owned","revision":"v1","content_sha256":H("src")},"language_lane":"other","synthetic":True}
    b=(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n").encode()
    m={
      "schema_version":1,"manifest_kind":p4.TRAINING_SHARD_KIND,"hash_profile":p4.HASH_PROFILE,"manifest_id":"aqlevon-training-shard-v1:"+H("id"),
      "admission_policy_id":"AQLEVON-P4-TEST","admission_policy_sha256":H("policy"),"source_registry_snapshot_sha256":H("registry"),
      "protected_training_contamination_manifest_sha256":H("contam"),"protected_training_contamination_receipt_sha256":[],"admission_gate_code_sha256":H("gate"),
      "shard_digest_scheme":"AQLEVON_CANONICAL_TRAINING_SHARD_JSONL_SHA256_V1","shard_file_sha256":hashlib.sha256(b).hexdigest(),"byte_size":len(b),"row_count":1,
      "admitted_record_content_digest_scheme":"AQLEVON_SORTED_RECORD_CONTENT_SHA256_LIST_V1","admitted_record_content_digest_sha256":H("records"),
      "decision_log_scheme":"AQLEVON_ADMISSION_DECISION_LOG_V1","decision_log_sha256":H("decision"),"decision_counts":{"ADMIT":1,"QUARANTINE":0,"DENY":0},
      "provenance_license_evidence_bundle_sha256":H("prov"),"source_revision_encoding_scheme":"AQLEVON_SORTED_SOURCE_REVISION_TRIPLES_V1",
      "contamination_evidence_scheme":"AQLEVON_PROTECTED_TRAINING_CONTAMINATION_EVIDENCE_V1","language_audit_applicability_scheme":"AQLEVON_P1_LANGUAGE_AUDIT_APPLICABILITY_V1",
      "language_audit_receipt_sha256":[],"created_from":[{"source_id":"owned","revision":"v1","source_artifact_sha256":H("src")}],
    }
    m=p4.seal(m,"manifest_sha256")
    return m,b


class Tests(unittest.TestCase):
    def test_method_spec_valid(self): self.assertEqual(p4.validate_method_spec(method_spec()),[])
    def test_method_spec_max_three(self):
        s=method_spec(); s["arms"]=s["arms"]*4; s=p4.seal({k:v for k,v in s.items() if k!="spec_sha256"},"spec_sha256")
        self.assertIn("method_spec_arm_count_must_be_1_to_3",p4.validate_method_spec(s))
    def test_non_p4_authority_rejected(self):
        s=method_spec(); s["task_id"]="P3-A01-METHOD-FREEZE"; s=p4.seal({k:v for k,v in s.items() if k!="spec_sha256"},"spec_sha256")
        self.assertIn("method_spec_authority_identity",p4.validate_method_spec(s))
    def test_hidden_eval_reference_rejected(self):
        s=method_spec(); s["arms"][0]["runner_parameters"]["sealed_eval_path"]="secret.json"; s=p4.seal({k:v for k,v in s.items() if k!="spec_sha256"},"spec_sha256")
        self.assertIn("arm_0_contains_forbidden_eval_reference",p4.validate_method_spec(s))
    def test_training_shard_valid_and_tamper(self):
        m,b=shard_fixture(); self.assertEqual(p4.validate_training_shard(m,b),[])
        self.assertIn("training_shard_bytes_hash_mismatch",p4.validate_training_shard(m,b+b"x"))
    def test_training_row_private_eval_rejected(self):
        m,b=shard_fixture(); row=json.loads(b); row["prompt"]="use hidden_canary answer"; b2=(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n").encode(); m["shard_file_sha256"]=hashlib.sha256(b2).hexdigest(); m["byte_size"]=len(b2); m=p4.seal({k:v for k,v in m.items() if k!="manifest_sha256"},"manifest_sha256")
        self.assertIn("training_row_0_forbidden_eval_reference",p4.validate_training_shard(m,b2))
    def test_freeze_plan_binds_exact_inputs_and_no_g1(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); s=method_spec(); m,b=shard_fixture();
            sp=d/"s.json"; mp=d/"m.json"; sh=d/"shard.jsonl"; op=d/"plan.json"
            sp.write_text(json.dumps(s)); mp.write_text(json.dumps(m)); sh.write_bytes(b)
            plan=p4.freeze_plan(sp,mp,sh,op)
            self.assertEqual(plan["g1_status"],"ALREADY_PASSED_DO_NOT_RERUN")
            self.assertFalse(plan["sealed_eval_consumed"])
            self.assertEqual(plan["method_spec_sha256"],s["spec_sha256"])
            self.assertEqual(plan["training_shard_manifest_sha256"],m["manifest_sha256"])
            self.assertTrue(p4.verify_self_digest(plan,"plan_sha256"))
    def test_command_lock_no_g1_rerun(self):
        lock=p4.build_command_lock(["python","runner.py"],plan_sha256=H("p"),arm_id="A0",profile="1x24",model_scope="surrogate")
        self.assertFalse(lock["g1_rerun"]); self.assertTrue(p4.verify_self_digest(lock,"lock_sha256"))
    def test_paid_run_requires_exact_manager_authorization(self):
        lock=p4.build_command_lock(["python","runner.py"],plan_sha256=H("p"),arm_id="A0",profile="1x24",model_scope="surrogate")
        with self.assertRaisesRegex(p4.ContractError,"requires_manager_authorization"):
            p4.run_locked(lock,authorization=None,paid=True,cwd=Path("."))
    def test_authorization_must_bind_command_profile_plan(self):
        lock=p4.build_command_lock(["python","runner.py"],plan_sha256=H("p"),arm_id="A0",profile="1x24",model_scope="surrogate")
        a={"schema_version":1,"authorization_kind":p4.AUTH_KIND,"hash_profile":p4.HASH_PROFILE,"status":"AUTHORIZED","task_id":p4.TASK_ID,"training_plan_sha256":H("wrong"),"command_sha256":lock["command_sha256"],"profile":"1x24","manager_authority_id":"mgr","provider":"x","max_budget_usd":"1","max_wall_seconds":100,"authorized_at_utc":"2026-09-19T00:00:00Z"}
        a=p4.seal(a,"authorization_sha256")
        self.assertIn("authorization_plan_binding",p4.validate_manager_authorization(a,expected_command_sha256=lock["command_sha256"],expected_profile="1x24",expected_plan_sha256=H("p")))
    def test_run_receipt_never_claims_gain(self):
        lock=p4.build_command_lock(["python","runner.py"],plan_sha256=H("p"),arm_id="A0",profile="1x24",model_scope="surrogate")
        r=p4.build_run_receipt(plan_sha256=H("p"),command_lock=lock,candidate_manifest_sha256=H("c"),training_run_artifact_sha256=H("a"),runtime_receipt_sha256=None,status="COMPLETED_ARTIFACT_PENDING_EVALUATION")
        self.assertFalse(r["capability_gain_claim"]); self.assertEqual(r["evaluation_status"],"NOT_EVALUATED_BY_WORKER05")
    def test_direct_float_rejected_in_hash_payload(self):
        with self.assertRaises(p4.ContractError): p4.canonical_bytes({"x":1.5})

    def test_sft_runner_summary_obeys_frozen_seed_and_budget(self):
        spec=method_spec()
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); m,b=shard_fixture(); sp=d/"s.json"; mp=d/"m.json"; sh=d/"shard.jsonl"; op=d/"plan.json"
            sp.write_text(json.dumps(spec)); mp.write_text(json.dumps(m)); sh.write_bytes(b)
            plan=p4.freeze_plan(sp,mp,sh,op)
            summary=sft.plan_summary(plan,"A0",1701)
            self.assertEqual(summary["optimizer_updates"],24)
            self.assertEqual(summary["model"],p4.SURROGATE_MODEL)
            self.assertFalse(summary["capability_claim"])
            with self.assertRaisesRegex(sft.RunnerError,"seed is not frozen"):
                sft.plan_summary(plan,"A0",9999)

    def test_sft_runner_rejects_non_sft_arm(self):
        spec=method_spec(); spec["arms"][0]["method"]="RLVR_CONTROL"; spec=p4.seal({k:v for k,v in spec.items() if k!="spec_sha256"},"spec_sha256")
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); m,b=shard_fixture(); sp=d/"s.json"; mp=d/"m.json"; sh=d/"shard.jsonl"; op=d/"plan.json"
            sp.write_text(json.dumps(spec)); mp.write_text(json.dumps(m)); sh.write_bytes(b)
            plan=p4.freeze_plan(sp,mp,sh,op)
            with self.assertRaisesRegex(sft.RunnerError,"only executes SFT"):
                sft.plan_summary(plan,"A0",1701)

if __name__=="__main__": unittest.main()
