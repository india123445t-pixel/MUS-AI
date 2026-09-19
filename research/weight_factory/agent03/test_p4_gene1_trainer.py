from __future__ import annotations
import hashlib, json, tempfile, unittest
from pathlib import Path
import p4_gene1_trainer as c
import p4_aqlevon_reward as reward
import p4_surrogate_tournament as tour
import p4_sft_surrogate as sft

H=lambda x:hashlib.sha256(x.encode()).hexdigest()

def plan_fixture():
    obj={"schema_version":1,"plan_kind":c.FROZEN_PLAN_KIND,"hash_profile":c.HASH_PROFILE,"task_id":c.TASK_ID,"g1_status":c.G1_STATUS,"sealed_eval_consumed":False,"plan_sha256":"","profile":c.PROFILE,"surrogate_model":{"repo":c.SURROGATE_MODEL,"revision":c.SURROGATE_REVISION,"precision":"bf16","quantization":"none"},"training_seeds":[1701,1702,1703],"screen_budget":{"max_optimizer_updates":12},"generation":{"temperature":"0.7","top_p":"0.8","top_k":20},"arms":[
      {"arm_id":"P4_A0_SFT_LORA_CONTROL","algorithm":"supervised next-token CE on Worker02-admitted reference targets only","lr":"0.00001","weight_decay":"0.10","schedule":"cosine","min_lr":"0.000001","warmup_fraction":"0.10"},
      {"arm_id":"P4_A1_RLVR_CONTROL","rollout_group_size":4,"ppo_mini_batch_size":8,"lr":"0.00001","rollout_importance_sampling":"token"},
      {"arm_id":"P4_A2_SDPO_RICH_FEEDBACK","rollout_group_size":4,"self_distillation_alpha":"0.5","distillation_topk":100,"include_environment_feedback":True,"environment_feedback_only_without_solution":True}],
    }
    return c.seal(obj,"plan_sha256")

class ContractTests(unittest.TestCase):
    def test_canonical_hash_rejects_float(self):
        with self.assertRaises(c.ContractError): c.canonical_sha256({"x":1.5})
    def test_constants_pin_real_handoffs(self):
        self.assertEqual(c.W01_CANONICAL_SHA256,"7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d")
        self.assertEqual(c.W02_SHARD_SHA256,"59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49")
        self.assertEqual(c.W05_LAW_SHA256,"70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0")
    def test_execution_order_a1_first(self): self.assertEqual(c.EXECUTION_ORDER[0],"P4_A1_RLVR_CONTROL")
    def test_profile_is_worker06_24gb_lane(self): self.assertEqual(c.PROFILE,"p4-surrogate-1x24")
    def test_g1_locked_passed_no_rerun(self): self.assertEqual(c.G1_STATUS,"ALREADY_PASSED_DO_NOT_RERUN")
    def test_command_lock_has_no_fallback_or_g1(self):
        x=c.build_command_lock(["python","x.py"],plan_sha256=H("p"),arm_id="P4_A1_RLVR_CONTROL",seed=1701)
        self.assertFalse(x["automatic_fallback"]); self.assertFalse(x["g1_rerun"]); self.assertTrue(c.verify_self_digest(x,"lock_sha256"))
    def test_paid_run_requires_auth(self):
        x=c.build_command_lock(["true"],plan_sha256=H("p"),arm_id="P4_A1_RLVR_CONTROL",seed=1701)
        with self.assertRaisesRegex(c.ContractError,"requires_exact_manager_authorization"): c.run_locked(x,paid=True,authorization=None,cwd=Path("."))
    def test_auth_binds_exact_command_profile_plan(self):
        x=c.build_command_lock(["true"],plan_sha256=H("p"),arm_id="P4_A1_RLVR_CONTROL",seed=1701)
        a={"schema_version":1,"authorization_kind":c.AUTH_KIND,"hash_profile":c.HASH_PROFILE,"authorization_id":"mgr-p4-a1-1701","run_task_id":c.TASK_ID,"run_manifest_sha256":H("wrong"),"profile_id":c.PROFILE,"compute_origin":"paid_manager_authorized","max_billed_seconds":7200,"max_total_cost_usd":"1","max_hourly_rate_usd":"1","max_artifact_egress_bytes":104857600,"single_use":True}; a=c.seal(a,"authorization_sha256")
        self.assertIn("authorization_plan",c.validate_manager_authorization(a,lock=x))

class RewardTests(unittest.TestCase):
    def test_correct_increment_reward(self):
        gt=json.dumps({"initial_state":{"x":1},"oracle_program":[{"op":"increment","key":"x","by":2}]})
        r=reward.compute_score(solution_str='[{"op":"increment","key":"x","by":2}]',ground_truth=gt); self.assertEqual(r["score"],1.0); self.assertEqual(r["feedback"],"")
    def test_wrong_reward_feedback_is_sanitized_class(self):
        gt=json.dumps({"initial_state":{"x":1},"oracle_program":[{"op":"increment","key":"x","by":2}]})
        r=reward.compute_score(solution_str='[{"op":"increment","key":"x","by":3}]',ground_truth=gt); self.assertEqual(r["score"],0.0); self.assertEqual(r["feedback"],"final_state_mismatch"); self.assertNotIn("expected",r["feedback"].lower())
    def test_invalid_json_is_sanitized(self):
        gt=json.dumps({"initial_state":{"x":1},"oracle_program":[{"op":"set","key":"x","value":2}]}); self.assertEqual(reward.compute_score(solution_str="oops",ground_truth=gt)["feedback"],"invalid_json")
    def test_feedback_vocab_contains_no_oracle_text(self):
        for x in reward.ALLOWED_REASONS: self.assertNotIn("expected",x); self.assertNotIn("answer",x); self.assertNotIn("canary",x)

class RunnerTests(unittest.TestCase):
    def test_a1_command_exact_budget_sampling_lora(self):
        p=plan_fixture()
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"p.json"; f.write_text(json.dumps(p)); argv=tour.build_a1_argv(f,Path("/workspace")); joined=" ".join(argv)
            for tok in ("trainer.total_training_steps=12","data.train_batch_size=4","actor_rollout_ref.rollout.n=4","actor_rollout_ref.model.lora_rank=4","actor_rollout_ref.model.lora_alpha=4","temperature=0.7","top_p=0.8","top_k=20","baseline_grpo","trainer.n_gpus_per_node=1","actor_rollout_ref.rollout.tensor_model_parallel_size=1","max_model_len=4096","actor_rollout_ref.rollout.max_model_len=4096","train.parquet","test.parquet"): self.assertIn(tok,joined)
            self.assertIn("self_attn",joined); self.assertNotIn("qlora",joined.lower())
    def test_a2_command_enables_safe_feedback_contract(self):
        p=plan_fixture()
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"p.json"; f.write_text(json.dumps(p)); joined=" ".join(tour.build_a2_argv(f,Path("/workspace")))
            self.assertIn("include_environment_feedback=True",joined); self.assertIn("environment_feedback_only_without_solution=True",joined); self.assertIn("distillation_topk=100",joined); self.assertIn("alpha=0.5",joined)
    def test_sft_summary_uses_12_updates_r4_alpha4(self):
        s=sft.plan_summary(plan_fixture(),1701); self.assertEqual(s["optimizer_updates"],12); self.assertEqual(s["lora_r"],4); self.assertEqual(s["lora_alpha"],4); self.assertEqual(s["examples_per_update"],4)
    def test_target_regex_excludes_linear_attention_by_construction(self):
        self.assertIn("self_attn",tour.TARGET_REGEX); self.assertNotIn("linear_attn",tour.TARGET_REGEX)
    def test_runtime_guard_pins_w01_versions(self): self.assertEqual(tour.W01_STACK,{"transformers":"5.17.0","peft":"0.21.0","accelerate":"1.15.0"})
    def test_worker06_authorization_kind(self): self.assertEqual(c.AUTH_KIND,"AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1")
    def test_a1_single_gpu_has_no_tp2_or_four_gpu_default(self):
        p=plan_fixture()
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"p.json"; f.write_text(json.dumps(p)); joined=" ".join(tour.build_a1_argv(f,Path("/workspace")))
            self.assertIn("trainer.n_gpus_per_node=1",joined)
            self.assertIn("actor_rollout_ref.rollout.tensor_model_parallel_size=1",joined)
            self.assertNotIn("trainer.n_gpus_per_node=4",joined)
    def test_public_data_record_schema(self):
        row={"row_kind":c.W02_ROW_KIND,"record_id":"r1","prompt":"Do x","answer":[{"op":"increment","key":"x","by":1}]}
        task={"prompt":"Do x","verifier_mode":"hardened","training_eligible":True,"oracle_program":row["answer"],"visible_initial_state":{"x":0},"semantic_core_id":"core1","task_sha256":H("task")}
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); shard=d/"shard.jsonl"; pack=d/"pack.json"
            shard.write_text("\n".join(json.dumps({**row,"record_id":f"r{i}","prompt":f"Do x {i}"}) for i in range(56))+"\n")
            tasks=[{**task,"prompt":f"Do x {i}","task_sha256":H(f"task{i}")} for i in range(56)]
            pack.write_text(json.dumps({"tasks":tasks}))
            recs=tour.build_training_records(shard,pack)
            self.assertEqual(len(recs),56)
            self.assertEqual(recs[0]["data_source"],"aqlevon_gene1")
            self.assertEqual(recs[0]["prompt"][0]["role"],"user")
            self.assertIn("ground_truth",recs[0]["reward_model"])

if __name__=="__main__": unittest.main()
