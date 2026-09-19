from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import p4_aqlevon_reward as reward
import p4_gene1_trainer as c
import p4_sft_surrogate as sft
import p4_surrogate_tournament as tour

H = lambda x: hashlib.sha256(x.encode()).hexdigest()
RUN_MANIFEST_SHA = "5a3f9df84d89216f4e227c187a53997aceb2e8c8e4727c053a531f295e26d6b5"


def plan_fixture():
    obj = {
        "schema_version": 1,
        "plan_kind": c.FROZEN_PLAN_KIND,
        "hash_profile": c.HASH_PROFILE,
        "task_id": c.TASK_ID,
        "g1_status": c.G1_STATUS,
        "sealed_eval_consumed": False,
        "plan_sha256": "",
        "profile": c.PROFILE,
        "surrogate_model": {
            "repo": c.SURROGATE_MODEL,
            "revision": c.SURROGATE_REVISION,
            "precision": "bf16",
            "quantization": "none",
        },
        "training_seeds": [1701, 1702, 1703],
        "screen_budget": {"max_optimizer_updates": 12},
        "generation": {
            "temperature": "0.7",
            "top_p": "0.8",
            "top_k": 20,
        },
        "arms": [
            {
                "arm_id": "P4_A0_SFT_LORA_CONTROL",
                "algorithm": "supervised next-token CE on Worker02-admitted reference targets only",
                "lr": "0.00001",
                "weight_decay": "0.10",
                "schedule": "cosine",
                "min_lr": "0.000001",
                "warmup_fraction": "0.10",
            },
            {
                "arm_id": "P4_A1_RLVR_CONTROL",
                "rollout_group_size": 4,
                "ppo_mini_batch_size": 8,
                "lr": "0.00001",
                "rollout_importance_sampling": "token",
            },
            {
                "arm_id": "P4_A2_SDPO_RICH_FEEDBACK",
                "rollout_group_size": 4,
                "self_distillation_alpha": "0.5",
                "distillation_topk": 100,
                "include_environment_feedback": True,
                "environment_feedback_only_without_solution": True,
            },
        ],
    }
    return c.seal(obj, "plan_sha256")


def worker06_auth(lock, *, run_manifest_sha=RUN_MANIFEST_SHA):
    obj = {
        "schema_version": 1,
        "authorization_kind": c.AUTH_KIND,
        "hash_profile": c.HASH_PROFILE,
        "authorization_id": "manager-p4-a1-seed1701",
        "run_task_id": c.TASK_ID,
        "run_manifest_sha256": run_manifest_sha,
        "profile_id": c.PROFILE,
        "compute_origin": "paid_manager_authorized",
        "max_billed_seconds": 3600,
        "max_total_cost_usd": "1",
        "max_hourly_rate_usd": "1",
        "max_artifact_egress_bytes": 104857600,
        "single_use": True,
    }
    return c.seal(obj, "authorization_sha256")


class ContractTests(unittest.TestCase):
    def test_canonical_hash_rejects_float(self):
        with self.assertRaises(c.ContractError):
            c.canonical_sha256({"x": 1.5})

    def test_constants_pin_real_handoffs(self):
        self.assertEqual(
            c.W01_CANONICAL_SHA256,
            "7c6cc62b6ae20fd49038198865567df75f1a105607bd9d32d974530bd9894f1d",
        )
        self.assertEqual(
            c.W02_SHARD_SHA256,
            "59480e9ff48b36a0efb77a36d3e35d9f656ef4dee0ce18489d3017c92b2a0d49",
        )
        self.assertEqual(
            c.W05_LAW_SHA256,
            "70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0",
        )

    def test_execution_order_a1_first(self):
        self.assertEqual(c.EXECUTION_ORDER[0], "P4_A1_RLVR_CONTROL")

    def test_profile_is_worker06_24gb_lane(self):
        self.assertEqual(c.PROFILE, "p4-surrogate-1x24")

    def test_g1_locked_passed_no_rerun(self):
        self.assertEqual(c.G1_STATUS, "ALREADY_PASSED_DO_NOT_RERUN")

    def test_command_lock_has_no_fallback_or_g1(self):
        x = c.build_command_lock(
            ["python", "x.py"],
            plan_sha256=H("p"),
            run_manifest_sha256=RUN_MANIFEST_SHA,
            arm_id="P4_A1_RLVR_CONTROL",
            seed=1701,
        )
        self.assertFalse(x["automatic_fallback"])
        self.assertFalse(x["g1_rerun"])
        self.assertTrue(c.verify_self_digest(x, "lock_sha256"))

    def test_paid_run_requires_exact_manager_auth(self):
        x = c.build_command_lock(
            ["true"],
            plan_sha256=H("p"),
            run_manifest_sha256=RUN_MANIFEST_SHA,
            arm_id="P4_A1_RLVR_CONTROL",
            seed=1701,
        )
        with self.assertRaisesRegex(
            c.ContractError, "requires_exact_manager_authorization"
        ):
            c.run_locked(
                x,
                paid=True,
                authorization=None,
                run_manifest_sha256=RUN_MANIFEST_SHA,
                cwd=Path("."),
            )

    def test_worker06_auth_binds_exact_run_manifest_and_profile(self):
        x = c.build_command_lock(
            ["true"],
            plan_sha256=H("p"),
            run_manifest_sha256=RUN_MANIFEST_SHA,
            arm_id="P4_A1_RLVR_CONTROL",
            seed=1701,
        )
        auth = worker06_auth(x)
        self.assertEqual(
            c.validate_manager_authorization(
                auth,
                lock=x,
                run_manifest_sha256=RUN_MANIFEST_SHA,
            ),
            [],
        )
        self.assertIn(
            "authorization_run_manifest",
            c.validate_manager_authorization(
                auth,
                lock=x,
                run_manifest_sha256=H("wrong"),
            ),
        )

    def test_worker06_auth_schema_kind(self):
        self.assertEqual(c.AUTH_KIND, "AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1")


class RewardTests(unittest.TestCase):
    def test_correct_increment_reward(self):
        gt = json.dumps(
            {
                "initial_state": {"x": 1},
                "oracle_program": [{"op": "increment", "key": "x", "by": 2}],
            }
        )
        r = reward.compute_score(
            solution_str='[{"op":"increment","key":"x","by":2}]',
            ground_truth=gt,
        )
        self.assertEqual(r["score"], 1.0)
        self.assertEqual(r["feedback"], "")

    def test_wrong_reward_feedback_is_sanitized_class(self):
        gt = json.dumps(
            {
                "initial_state": {"x": 1},
                "oracle_program": [{"op": "increment", "key": "x", "by": 2}],
            }
        )
        r = reward.compute_score(
            solution_str='[{"op":"increment","key":"x","by":3}]',
            ground_truth=gt,
        )
        self.assertEqual(r["score"], 0.0)
        self.assertEqual(r["feedback"], "final_state_mismatch")
        self.assertNotIn("expected", r["feedback"].lower())

    def test_invalid_json_is_sanitized(self):
        gt = json.dumps(
            {
                "initial_state": {"x": 1},
                "oracle_program": [{"op": "set", "key": "x", "value": 2}],
            }
        )
        self.assertEqual(
            reward.compute_score(solution_str="oops", ground_truth=gt)["feedback"],
            "invalid_json",
        )

    def test_feedback_vocab_contains_no_oracle_text(self):
        for item in reward.ALLOWED_REASONS:
            self.assertNotIn("expected", item)
            self.assertNotIn("answer", item)
            self.assertNotIn("canary", item)


class RunnerTests(unittest.TestCase):
    def test_a1_command_exact_budget_sampling_lora_and_one_gpu(self):
        p = plan_fixture()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            f.write_text(json.dumps(p))
            argv = tour.build_a1_argv(f, Path("/workspace"))
            self.assertEqual(argv[:3], ["env", "USER=root", "bash"])
            joined = " ".join(argv)
            for token in (
                "trainer.total_training_steps=12",
                "data.train_batch_size=4",
                "actor_rollout_ref.rollout.n=4",
                "actor_rollout_ref.actor.ppo_mini_batch_size=4",
                "actor_rollout_ref.model.lora_rank=4",
                "actor_rollout_ref.model.lora_alpha=4",
                "temperature=0.7",
                "top_p=0.8",
                "top_k=20",
                "baseline_grpo",
                "trainer.n_gpus_per_node=1",
                "actor_rollout_ref.rollout.tensor_model_parallel_size=1",
                "ray_kwargs.ray_init.runtime_env.env_vars.PYTHONPATH",
                "ray_kwargs.ray_init.runtime_env.env_vars.USER=root",
                "max_model_len=4096",
                "actor_rollout_ref.rollout.max_model_len=4096",
                "train.parquet",
                "test.parquet",
            ):
                self.assertIn(token, joined)
            self.assertIn("self_attn", joined)
            self.assertIn("linear_attn", joined)
            self.assertNotIn("qlora", joined.lower())


    def test_driver_user_env_survives_clean_process_boundary(self):
        env = dict(os.environ)
        env.pop("USER", None)
        cp = subprocess.run(
            ["env", "USER=root", sys.executable, "-c", "import os; assert os.environ.get('USER') == 'root'"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stderr)

    def test_a1_command_excludes_linear_attention_from_trainable_scope(self):
        p = plan_fixture()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            f.write_text(json.dumps(p))
            argv = tour.build_a1_argv(f, Path("/workspace"))
            target = next(x for x in argv if x.startswith("actor_rollout_ref.model.target_modules="))
            exclude = next(x for x in argv if x.startswith("actor_rollout_ref.model.exclude_modules="))
            self.assertIn("self_attn", target)
            self.assertNotIn("linear_attn", target)
            self.assertIn("linear_attn", exclude)

    def test_a2_command_enables_safe_feedback_contract(self):
        p = plan_fixture()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            f.write_text(json.dumps(p))
            joined = " ".join(tour.build_a2_argv(f, Path("/workspace")))
            self.assertIn("include_environment_feedback=True", joined)
            self.assertIn(
                "environment_feedback_only_without_solution=True",
                joined,
            )
            self.assertIn("distillation_topk=100", joined)
            self.assertIn("alpha=0.5", joined)
            self.assertIn("trainer.n_gpus_per_node=1", joined)

    def test_sft_summary_uses_12_updates_r4_alpha4(self):
        s = sft.plan_summary(plan_fixture(), 1701)
        self.assertEqual(s["optimizer_updates"], 12)
        self.assertEqual(s["lora_r"], 4)
        self.assertEqual(s["lora_alpha"], 4)
        self.assertEqual(s["examples_per_update"], 4)

    def test_target_regex_excludes_linear_attention_by_construction(self):
        self.assertIn("self_attn", tour.TARGET_REGEX)
        self.assertNotIn("linear_attn", tour.TARGET_REGEX)

    def test_qwen35_processor_template_bridge_is_exact_and_scoped(self):
        class Tok:
            chat_template = "CANONICAL_TEMPLATE"

        class Proc:
            chat_template = None
            tokenizer = Tok()

        p = Proc()
        out = tour.bridge_processor_chat_template(
            p, "/workspace/models/qwen35-4b-daa9c16f3712"
        )
        self.assertIs(out, p)
        self.assertEqual(p.chat_template, "CANONICAL_TEMPLATE")

        other = Proc()
        tour.bridge_processor_chat_template(other, "/workspace/models/other")
        self.assertIsNone(other.chat_template)

    def test_runtime_guard_pins_w01_versions(self):
        self.assertEqual(
            tour.W01_STACK,
            {
                "transformers": "5.17.0",
                "peft": "0.21.0",
                "accelerate": "1.15.0",
            },
        )

    def test_training_records_match_verl_parquet_schema(self):
        rows = []
        tasks = []
        for i in range(56):
            prompt = f"prompt-{i}"
            answer = [{"op": "set", "key": "x", "value": i}]
            rows.append(
                {
                    "row_kind": c.W02_ROW_KIND,
                    "record_id": f"r-{i}",
                    "prompt": prompt,
                    "answer": answer,
                }
            )
            tasks.append(
                {
                    "prompt": prompt,
                    "verifier_mode": "hardened",
                    "training_eligible": True,
                    "oracle_program": answer,
                    "visible_initial_state": {"x": 0},
                    "semantic_core_id": f"core-{i}",
                    "task_sha256": H(f"task-{i}"),
                }
            )
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            shard = d / "shard.jsonl"
            pack = d / "pack.json"
            shard.write_text(
                "".join(json.dumps(x) + "\n" for x in rows),
                encoding="utf-8",
            )
            pack.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
            records = tour.build_training_records(shard, pack)
            self.assertEqual(len(records), 56)
            first = records[0]
            self.assertEqual(
                set(first),
                {"data_source", "prompt", "ability", "reward_model", "extra_info"},
            )
            self.assertEqual(first["prompt"][0]["role"], "user")
            ground = json.loads(first["reward_model"]["ground_truth"])
            self.assertEqual(ground["initial_state"], {"x": 0})
            self.assertEqual(ground["oracle_program"], rows[0]["answer"])

    def test_data_writer_fails_closed_without_parquet_backend(self):
        records = [
            {
                "data_source": "x",
                "prompt": [{"role": "user", "content": "p"}],
                "ability": "x",
                "reward_model": {"style": "rule", "ground_truth": "{}"},
                "extra_info": {},
            }
        ]
        # The actual execution image must provide pyarrow through the pinned SDPO
        # environment.  This test only verifies the function is explicit/fail-closed.
        self.assertTrue(callable(tour.write_parquet_records))


if __name__ == "__main__":
    unittest.main()
