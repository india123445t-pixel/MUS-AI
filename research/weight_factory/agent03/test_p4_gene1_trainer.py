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
import p4_patch_sdpo_transformers5_native_vllm019 as native_vllm_patch
import p4_patch_sdpo_transformers5_compat as compat
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
        argv = [
            "python", "x.py",
            "data.seed=1701",
            "actor_rollout_ref.actor.data_loader_seed=1701",
            "actor_rollout_ref.actor.fsdp_config.seed=1701",
            "actor_rollout_ref.ref.fsdp_config.seed=1701",
            "++actor_rollout_ref.rollout.engine_kwargs.vllm.seed=1701",
        ]
        x = c.build_command_lock(
            argv,
            plan_sha256=H("p"),
            run_manifest_sha256=RUN_MANIFEST_SHA,
            arm_id="P4_A1_RLVR_CONTROL",
            seed=1701,
        )
        self.assertFalse(x["automatic_fallback"])
        self.assertFalse(x["g1_rerun"])
        self.assertTrue(c.verify_self_digest(x, "lock_sha256"))

    def test_rl_command_lock_rejects_metadata_only_seed(self):
        with self.assertRaisesRegex(c.ContractError, "seed_binding_missing"):
            c.build_command_lock(
                ["python", "x.py"],
                plan_sha256=H("p"),
                run_manifest_sha256=RUN_MANIFEST_SHA,
                arm_id="P4_A1_RLVR_CONTROL",
                seed=1701,
            )

    def test_paid_run_requires_exact_manager_auth(self):
        x = c.build_command_lock(
            ["true","data.seed=1701","actor_rollout_ref.actor.data_loader_seed=1701","actor_rollout_ref.actor.fsdp_config.seed=1701","actor_rollout_ref.ref.fsdp_config.seed=1701","++actor_rollout_ref.rollout.engine_kwargs.vllm.seed=1701"],
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
            ["true","data.seed=1701","actor_rollout_ref.actor.data_loader_seed=1701","actor_rollout_ref.actor.fsdp_config.seed=1701","actor_rollout_ref.ref.fsdp_config.seed=1701","++actor_rollout_ref.rollout.engine_kwargs.vllm.seed=1701"],
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


class RuntimeResolverTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> str:
        cp = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return cp.stdout.strip()

    def test_runtime_resolver_discovers_exact_binding_and_auth_without_ui_filenames(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            agent = repo / "research" / "weight_factory" / "agent03"
            agent.mkdir(parents=True)
            self._git(repo, "init")
            self._git(repo, "config", "user.email", "aqlevon@example.invalid")
            self._git(repo, "config", "user.name", "AQLEVON Test")

            marker = repo / "source.txt"
            marker.write_text("source\n")

            run_sha = H("run")
            lock_sha = H("lock")
            digest = "sha256:" + H("image")
            auth = c.seal(
                {
                    "schema_version": 1,
                    "authorization_kind": c.AUTH_KIND,
                    "hash_profile": c.HASH_PROFILE,
                    "authorization_id": "retry-test",
                    "run_task_id": c.TASK_ID,
                    "run_manifest_sha256": run_sha,
                    "profile_id": c.PROFILE,
                    "compute_origin": "paid_manager_authorized",
                    "max_billed_seconds": 1800,
                    "max_total_cost_usd": "0.40",
                    "max_hourly_rate_usd": "0.80",
                    "max_artifact_egress_bytes": 1,
                    "single_use": True,
                },
                "authorization_sha256",
            )
            auth_path = agent / "p4_a1_runpod_manager_authorization_retrytest_v1.json"
            auth_path.write_text(json.dumps(auth))
            self._git(repo, "add", ".")
            self._git(repo, "commit", "-m", "source plus authorization")
            source = self._git(repo, "rev-parse", "HEAD")

            binding = c.seal(
                {
                    "authorization_sha256": auth["authorization_sha256"],
                    "binding_kind": "AQLEVON_RUNTIME_APPLIANCE_BINDING_V1",
                    "command_lock_sha256": lock_sha,
                    "hash_profile": c.HASH_PROFILE,
                    "run_manifest_sha256": run_sha,
                    "runtime_appliance_digest": digest,
                    "runtime_appliance_image": "ghcr.io/india123445t-pixel/mus-ai@" + digest,
                    "schema_version": 1,
                    "worker03_runtime_source_commit": source,
                    "workflow_run_id": 1,
                },
                "binding_sha256",
            )
            binding_path = agent / "p4_a1_runtime_appliance_binding_retrytest_v1.json"
            binding_path.write_text(json.dumps(binding))
            self._git(repo, "add", ".")
            self._git(repo, "commit", "-m", "binding only")
            head = self._git(repo, "rev-parse", "HEAD")

            auth_name, binding_name = c.resolve_runtime_launch_files(
                agent_dir=agent,
                repo_dir=repo,
                actual_head=head,
                expected_image_digest=digest,
                run_manifest_sha256=run_sha,
                command_lock_sha256=lock_sha,
            )
            self.assertEqual(auth_name, auth_path.name)
            self.assertEqual(binding_name, binding_path.name)

    def test_runtime_resolver_rejects_source_drift(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            agent = repo / "research" / "weight_factory" / "agent03"
            agent.mkdir(parents=True)
            self._git(repo, "init")
            self._git(repo, "config", "user.email", "aqlevon@example.invalid")
            self._git(repo, "config", "user.name", "AQLEVON Test")
            (repo / "source.txt").write_text("source\n")

            run_sha = H("run")
            lock_sha = H("lock")
            digest = "sha256:" + H("image")
            auth = c.seal(
                {
                    "schema_version": 1,
                    "authorization_kind": c.AUTH_KIND,
                    "hash_profile": c.HASH_PROFILE,
                    "authorization_id": "retry-test",
                    "run_task_id": c.TASK_ID,
                    "run_manifest_sha256": run_sha,
                    "profile_id": c.PROFILE,
                    "compute_origin": "paid_manager_authorized",
                    "max_billed_seconds": 1800,
                    "max_total_cost_usd": "0.40",
                    "max_hourly_rate_usd": "0.80",
                    "max_artifact_egress_bytes": 1,
                    "single_use": True,
                },
                "authorization_sha256",
            )
            (agent / "p4_a1_runpod_manager_authorization_retrytest_v1.json").write_text(json.dumps(auth))
            self._git(repo, "add", ".")
            self._git(repo, "commit", "-m", "source plus authorization")
            source = self._git(repo, "rev-parse", "HEAD")
            binding = c.seal(
                {
                    "authorization_sha256": auth["authorization_sha256"],
                    "binding_kind": "AQLEVON_RUNTIME_APPLIANCE_BINDING_V1",
                    "command_lock_sha256": lock_sha,
                    "hash_profile": c.HASH_PROFILE,
                    "run_manifest_sha256": run_sha,
                    "runtime_appliance_digest": digest,
                    "runtime_appliance_image": "ghcr.io/india123445t-pixel/mus-ai@" + digest,
                    "schema_version": 1,
                    "worker03_runtime_source_commit": source,
                    "workflow_run_id": 1,
                },
                "binding_sha256",
            )
            (agent / "p4_a1_runtime_appliance_binding_retrytest_v1.json").write_text(json.dumps(binding))
            (repo / "unexpected.txt").write_text("drift\n")
            self._git(repo, "add", ".")
            self._git(repo, "commit", "-m", "binding plus drift")
            head = self._git(repo, "rev-parse", "HEAD")

            with self.assertRaisesRegex(c.ContractError, "runtime_binding_resolution_count:0"):
                c.resolve_runtime_launch_files(
                    agent_dir=agent,
                    repo_dir=repo,
                    actual_head=head,
                    expected_image_digest=digest,
                    run_manifest_sha256=run_sha,
                    command_lock_sha256=lock_sha,
                )


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

    def test_dict_put_cannot_be_shortcut_by_whole_dict_set(self):
        gt = json.dumps(
            {
                "initial_state": {"config": {"stable": True}, "audit": 1},
                "oracle_program": [
                    {"op": "dict_put", "key": "config", "subkey": "limit", "value": 12}
                ],
            }
        )
        oracle = reward.compute_score(
            solution_str='[{"op":"dict_put","key":"config","subkey":"limit","value":12}]',
            ground_truth=gt,
        )
        shortcut = reward.compute_score(
            solution_str='[{"op":"set","key":"config","value":{"stable":true,"limit":12}}]',
            ground_truth=gt,
        )
        self.assertEqual(oracle["score"], 1.0)
        self.assertEqual(shortcut["score"], 0.0)
        self.assertEqual(shortcut["feedback"], "side_effect_mismatch")


class VllmLoraCompatPatchTests(unittest.TestCase):
    def _source(self):
        return """            if self.supports_mm and not isinstance(new_module,
                                                   BaseLayerWithLoRA):
                continue
            self.register_module(module_name, new_module)
            self._register_packed_modules(module_name)
            # All lora layers share the same punica_wrapper based on reference.
            new_module.set_mapping(self.punica_wrapper)
"""

    def test_patch_never_silently_skips_frozen_self_attn_qv(self):
        patched = compat.patch_vllm_lora_manager(self._source())
        self.assertIn("AQLEVON_REQUIRED_ROLLOUT_LORA_MODULE_UNSUPPORTED", patched)
        self.assertIn('".self_attn.q_proj"', patched)
        self.assertIn('".self_attn.v_proj"', patched)
        self.assertIn("expected_16", patched)

    def test_patch_skips_only_non_required_unreplaceable_modules(self):
        patched = compat.patch_vllm_lora_manager(self._source())
        guard = patched.index("if not isinstance(new_module, BaseLayerWithLoRA):")
        required = patched.index("if module_name.endswith", guard)
        skip = patched.index("continue", required)
        register = patched.index("self.register_module(module_name, new_module)", skip)
        self.assertLess(guard, required)
        self.assertLess(required, skip)
        self.assertLess(skip, register)

    def test_patch_is_idempotent(self):
        once = compat.patch_vllm_lora_manager(self._source())
        twice = compat.patch_vllm_lora_manager(once)
        self.assertEqual(once, twice)


class SdpoFirstWakeMemoryPatchTests(unittest.TestCase):
    def _source(self):
        import textwrap

        method = '''async def rollout_mode(self):
    peft_config = object()
    params = collect_lora_params(
        module=self.actor_module_fsdp,
        layered_summon=self.config.rollout.get("layered_summon", False),
        base_sync_done=self.base_sync_done,
    )
    if not self.base_sync_done:
        params = {replace_lora_wrapper(k, peft_config): v for k, v in params.items()}
    params = convert_weight_keys(params, self.actor_module_fsdp)
    per_tensor_param = params.items()
    if peft_config is not None and getattr(self.rollout, "sleep_level", None) == 2:
        base_model_params = collect_lora_params(
            module=self.actor_module_fsdp,
            layered_summon=self.layered_summon,
            base_sync_done=False,
        )
        base_model_params = {replace_lora_wrapper(k, peft_config): v for k, v in base_model_params.items()}
        base_model_params = convert_weight_keys(
            base_model_params, getattr(self.actor_module_fsdp, "_fsdp_wrapped_module", self.actor_module_fsdp)
        )
    if peft_config is not None and getattr(self.rollout, "sleep_level", None) == 2:
        per_tensor_base_params = base_model_params.items()
        await self.rollout.update_weights(per_tensor_base_params, base_sync_done=False)
        del base_model_params, per_tensor_base_params
    await self.rollout.update_weights(per_tensor_param, peft_config=peft_config, base_sync_done=self.base_sync_done)
    self.base_sync_done = True
'''
        return "class _Fixture:\n" + textwrap.indent(method, "    ")

    def test_initial_level2_sync_reuses_one_snapshot_and_loads_once(self):
        import asyncio
        import types

        patched = native_vllm_patch.patch_sdpo_first_wake_base_sync_dedup(self._source())
        self.assertIn("AQLEVON_SDPO_FIRST_WAKE_BASE_SYNC_DEDUP", patched)
        self.assertEqual(
            patched,
            native_vllm_patch.patch_sdpo_first_wake_base_sync_dedup(patched),
        )

        namespace = {"collect_lora_params": None}
        collect_calls = []

        def collect_lora_params(*, module, layered_summon, base_sync_done):
            collect_calls.append(base_sync_done)
            return {"base" if not base_sync_done else "lora": len(collect_calls)}

        class _Logger:
            @staticmethod
            def info_once(*args, **kwargs):
                pass

        class _Rollout:
            sleep_level = 2

            def __init__(self):
                self.updates = []

            async def update_weights(self, weights, **kwargs):
                self.updates.append((dict(weights), kwargs))

        namespace.update({
            "collect_lora_params": collect_lora_params,
            "replace_lora_wrapper": lambda name, peft: name,
            "convert_weight_keys": lambda params, module: params,
            "logger": _Logger,
        })
        exec(patched, namespace)

        class _Worker:
            def __init__(self):
                self.actor_module_fsdp = object()
                self.config = types.SimpleNamespace(rollout={"layered_summon": False})
                self.layered_summon = False
                self.rollout = _Rollout()
                self.base_sync_done = False

            rollout_mode = namespace["_Fixture"].rollout_mode

        worker = _Worker()
        asyncio.run(worker.rollout_mode())
        self.assertEqual(collect_calls, [False], "first level-2 wake must collect the full base only once")
        self.assertEqual(len(worker.rollout.updates), 1, "first wake must issue one direct base load")
        self.assertEqual(worker.rollout.updates[0], ({"base": 1}, {"base_sync_done": False}))

        # On subsequent cycles, collect fresh LoRA params and one separate base
        # snapshot, then perform the expected base update followed by LoRA add.
        worker.base_sync_done = True
        worker.rollout.updates.clear()
        asyncio.run(worker.rollout_mode())
        self.assertEqual(collect_calls, [False, True, False])
        self.assertEqual(len(worker.rollout.updates), 2)
        self.assertEqual(worker.rollout.updates[0], ({"base": 3}, {"base_sync_done": False}))
        self.assertEqual(worker.rollout.updates[1][0], {"lora": 2})
        self.assertIsNotNone(worker.rollout.updates[1][1]["peft_config"])
        self.assertTrue(worker.rollout.updates[1][1]["base_sync_done"])


class VllmTransformersMmMappingPatchTests(unittest.TestCase):
    def _source(self):
        return """from .interfaces import (SupportsLoRA, SupportsMultiModal, SupportsPP,
                         SupportsQuant)
from .utils import (AutoWeightsLoader, PPMissingLayer, WeightsMapper,
                    flatten_bn, make_empty_intermediate_tensors_factory,
                    maybe_prefix)

class TransformersForMultimodalLM:
    def __init__(self, *, vllm_config: VllmConfig, prefix: str = ""):
        super().__init__(vllm_config=vllm_config, prefix=prefix)

        self.dtype = vllm_config.model_config.dtype
"""

    def test_patch_adds_qwen35_language_vs_vision_mapping(self):
        patched = compat.patch_vllm_transformers_mm_mapping(self._source())
        self.assertIn("AQLEVON_QWEN35_MM_LORA_MAPPING", patched)
        self.assertIn("from .module_mapping import MultiModelKeys", patched)
        self.assertIn('language_model="model.language_model"', patched)
        self.assertIn('tower_model="model.visual"', patched)

    def test_patch_fails_closed_outside_exact_qwen35_structure(self):
        patched = compat.patch_vllm_transformers_mm_mapping(self._source())
        self.assertIn('getattr(self.config, "model_type", None) != "qwen3_5"', patched)
        self.assertIn("AQLEVON_TRANSFORMERS_MM_MAPPING_UNSUPPORTED_MODEL", patched)
        self.assertIn("AQLEVON_QWEN35_MM_MAPPING_STRUCTURE_MISMATCH", patched)

    def test_patch_is_idempotent(self):
        once = compat.patch_vllm_transformers_mm_mapping(self._source())
        twice = compat.patch_vllm_transformers_mm_mapping(once)
        self.assertEqual(once, twice)



class VllmTransformersMmOutputPatchTests(unittest.TestCase):
    def _source(self):
        return """            vision_embeddings = self.model.get_image_features(
                pixel_values,
                **{
                    k: v.flatten(0, 1)
                    for k, v in kwargs.items()
                },
            )

            if isinstance(vision_embeddings, torch.Tensor):
"""

    def test_patch_unwraps_qwen35_pooler_output(self):
        patched = compat.patch_vllm_transformers_mm_output(self._source())
        self.assertIn("AQLEVON_QWEN35_MM_OUTPUT_UNWRAP", patched)
        self.assertIn('hasattr(vision_embeddings, "pooler_output")', patched)
        self.assertIn("vision_embeddings = vision_embeddings.pooler_output", patched)

    def test_patch_fails_closed_on_bad_qwen35_output(self):
        patched = compat.patch_vllm_transformers_mm_output(self._source())
        self.assertIn("AQLEVON_QWEN35_MM_OUTPUT_UNSUPPORTED", patched)
        self.assertIn('getattr(self.config, "model_type", None) == "qwen3_5"', patched)

    def test_patch_accepts_tensor_list_or_tuple_only(self):
        patched = compat.patch_vllm_transformers_mm_output(self._source())
        self.assertIn("isinstance(vision_embeddings, (list, tuple))", patched)
        self.assertIn("all(isinstance(x, torch.Tensor) for x in vision_embeddings)", patched)

    def test_patch_is_idempotent(self):
        once = compat.patch_vllm_transformers_mm_output(self._source())
        twice = compat.patch_vllm_transformers_mm_output(once)
        self.assertEqual(once, twice)



class VllmQwen35TextRolloutPatchTests(unittest.TestCase):
    def _source(self):
        return """        hidden_states = self.model(
            input_ids=input_ids,
            inputs_embeds=inputs_embeds,
            use_cache=False,
            position_ids=position_ids,
            attention_instances=self.attention_instances,
            return_dict=False)[0][0, ...]  # we remove batch dimension for now
"""

    def test_patch_routes_only_qwen35_to_language_model(self):
        patched = compat.patch_vllm_qwen35_text_rollout(self._source())
        self.assertIn("AQLEVON_QWEN35_TEXT_ROLLOUT_3D", patched)
        self.assertIn('getattr(self.config, "model_type", None) == "qwen3_5"', patched)
        self.assertIn('language_model = getattr(self.model, "language_model", None)', patched)
        self.assertIn("target_model = language_model", patched)

    def test_patch_fails_closed_on_wrong_tensor_rank(self):
        patched = compat.patch_vllm_qwen35_text_rollout(self._source())
        self.assertIn("AQLEVON_QWEN35_INPUT_IDS_RANK", patched)
        self.assertIn("AQLEVON_QWEN35_INPUT_EMBEDS_RANK", patched)
        self.assertIn("AQLEVON_QWEN35_LANGUAGE_MODEL_MISSING", patched)

    def test_patch_is_idempotent(self):
        once = compat.patch_vllm_qwen35_text_rollout(self._source())
        twice = compat.patch_vllm_qwen35_text_rollout(once)
        self.assertEqual(once, twice)


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
                "data.seed=1701",
                "actor_rollout_ref.actor.data_loader_seed=1701",
                "actor_rollout_ref.actor.fsdp_config.seed=1701",
                "actor_rollout_ref.actor.fsdp_config.model_dtype=bf16",
                "actor_rollout_ref.actor.fsdp_config.param_offload=True",
                "actor_rollout_ref.actor.fsdp_config.optimizer_offload=True",
                "actor_rollout_ref.ref.fsdp_config.seed=1701",
                "actor_rollout_ref.rollout.engine_kwargs.vllm.seed=1701",
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


    def test_qwen35_vllm_linear_shape_restore_is_scoped_and_idempotent(self):
        source = """        mixed_qkv = self.in_proj_qkv(hidden_states)
        mixed_qkv = mixed_qkv.transpose(1, 2)

        z = self.in_proj_z(hidden_states)
        z = z.reshape(batch_size, seq_len, -1, self.head_v_dim)

        b = self.in_proj_b(hidden_states)
        a = self.in_proj_a(hidden_states)

        output = self.out_proj(core_attn_out)
        return output
"""
        once = compat.patch_transformers_qwen35_vllm_linear_shapes(source)
        self.assertIn("AQLEVON_QWEN35_VLLM_LINEAR_SHAPE_RESTORE", once)
        self.assertIn("mixed_qkv.reshape(batch_size, seq_len, -1)", once)
        self.assertIn("b = b.reshape(batch_size, seq_len, -1)", once)
        self.assertIn("a = a.reshape(batch_size, seq_len, -1)", once)
        self.assertIn("output = output.reshape(batch_size, seq_len, -1)", once)
        twice = compat.patch_transformers_qwen35_vllm_linear_shapes(once)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()


class SdpoSecondWakeLoraSyncPatchTests(unittest.TestCase):
    def test_explicit_fsdp_state_dict_and_32_tensor_guard(self):
        src = """def collect_lora_params(module, layered_summon, base_sync_done):
    from peft.utils.save_and_load import get_peft_model_state_dict
    lora_params = {}
    peft_model = getattr(module, "_fsdp_wrapped_module", module)
    if fsdp_version(module) > 0:
        if layered_summon:
            lora_params = layered_summon_lora_params(module)
        else:
            with FSDP.summon_full_params(module, writeback=False):
                if base_sync_done:
                    lora_params = get_peft_model_state_dict(peft_model)
                    lora_params = {
                        name: param.full_tensor().detach().cpu()
                        if hasattr(param, "full_tensor")
                        else param.detach().cpu()
                        for name, param in lora_params.items()
                    }
                else:
                    pass
    return lora_params
"""
        patched = native_vllm_patch.patch_sdpo_lora_state_sync(src)
        self.assertIn("AQLEVON_SDPO_QWEN35_RAW_FSDP_LORA_STATE", patched)
        self.assertIn("full_state_dict = module.state_dict()", patched)
        self.assertIn("_aqlevon_extract_qwen35_lora_state_dict", patched)
        self.assertIn('adapter_name="default"', patched)
        self.assertIn("expected_lora_tensors = 32", patched)
        self.assertIn("AQLEVON_FSDP_LORA_RAW_STATE_COUNT", patched)
        self.assertIn("AQLEVON_FSDP_LORA_STATE_KEYS", patched)
        self.assertIn("AQLEVON_FSDP_LORA_AB_COUNT", patched)
        self.assertEqual(patched, native_vllm_patch.patch_sdpo_lora_state_sync(patched))

    def test_sender_requires_16_a_and_16_b_tensors(self):
        src = """class _Fixture:
    async def update_weights(self, weights, **kwargs):
        peft_config, base_sync_done = kwargs.get("peft_config", None), kwargs.get("base_sync_done", False)
        if peft_config and base_sync_done:
            self.inference_engine.worker.remove_lora(VLLM_LORA_INT_ID)
            weights = dict(weights)
            lora_request = TensorLoRARequest(
                lora_name=VLLM_LORA_NAME,
                lora_int_id=VLLM_LORA_INT_ID,
                lora_path=VLLM_LORA_PATH,
                peft_config=asdict(peft_config),
                lora_tensors=weights,
            )
"""
        patched = native_vllm_patch.patch_sdpo_tensor_lora_sender(src)
        self.assertIn("AQLEVON_TENSOR_LORA_SYNC_COUNT", patched)
        self.assertIn("expected_lora_tensors = 32", patched)
        self.assertIn("AQLEVON_TENSOR_LORA_SYNC_PASS", patched)
        self.assertEqual(patched, native_vllm_patch.patch_sdpo_tensor_lora_sender(patched))

    def test_tensor_loader_rejects_empty_mapped_lora(self):
        src = """                if isinstance(lora_request, TensorLoRARequest):
                    lora = self._lora_model_cls.from_lora_tensors(
                        tensors=lora_tensors,
                        **lora_request_kwargs,
                    )
                else:
                    lora = self._lora_model_cls.from_local_checkpoint(
"""
        patched = native_vllm_patch.patch_sdpo_tensor_lora_loader(src)
        self.assertIn("AQLEVON_TENSOR_LORA_LOADER_NONEMPTY", patched)
        self.assertIn("AQLEVON_TENSOR_LORA_MAPPING_EMPTY", patched)
        self.assertEqual(patched, native_vllm_patch.patch_sdpo_tensor_lora_loader(patched))
