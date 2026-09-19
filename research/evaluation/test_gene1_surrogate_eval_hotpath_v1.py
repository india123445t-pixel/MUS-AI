import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import gene1_reality_tournament_v1 as p4
import gene1_surrogate_eval_hotpath_v1 as hp
from evaluation_decision_receipt_v1 import canonical_p2_sha256, verify_p2_self_digest
from test_gene1_reality_tournament_v1 import binding_fixture, score_card

H = lambda c: c * 64


def seal(obj, field):
    out = dict(obj)
    out[field] = canonical_p2_sha256(out)
    return out


def law_binding():
    law = p4.frozen_gene1_evaluation_law()
    binding = binding_fixture(law, matched_budget_sha256=H("8"))
    return law, binding


def synthetic_run_manifest(command_sha=None):
    d = {
        "schema_version":1,"manifest_kind":hp.W03_RUN_MANIFEST_KIND,"hash_profile":hp.HASH_PROFILE,
        "task_id":hp.W03_TASK_ID,"arm_id":hp.A1_ARM_ID,"seed":hp.A1_SEED,"profile_id":hp.A1_PROFILE,
        "training_plan_sha256":hp.A1_PLAN_SHA256,"command_sha256":command_sha or H("c"),
        "student_model":{"repo":hp.SURROGATE_REPO,"revision":hp.SURROGATE_REVISION,"precision":"bf16","quantization":"none"},
        "method_reference":{"repo":"lasgroup/SDPO","commit":"7c457fc1b1f636ae794eb0362ba37d4743b06fbc","config":"baseline_grpo"},
        "worker01_method_spec_canonical_sha256":p4.W01_METHOD_TOURNAMENT_SPEC_SHA256,
        "worker02_training_manifest_sha256":p4.W02_TRAINING_SHARD_MANIFEST_SHA256,
        "worker02_training_shard_sha256":p4.W02_TRAINING_SHARD_FILE_SHA256,
        "worker02_training_visible_pack_sha256":p4.W02_TRAINING_VISIBLE_PACK_SHA256,
        "worker02_split_sha256":p4.W02_SPLIT_COMMITMENT_SHA256,
        "worker02_sealed_eval_commitment_sha256":p4.W02_SEALED_EVAL_COMMITMENT_SHA256,
        "worker05_evaluation_law_sha256":p4.frozen_gene1_evaluation_law()["law_sha256"],
        "worker05_sampling_profile_sha256":p4.frozen_gene1_evaluation_law()["sampling_profile_sha256"],
        "worker06_compute_profile":hp.A1_PROFILE,
        "worker06_reference_commit":H("6")[:40],
        "worker03_sources":{"trainer_git_blob_sha1":H("1")[:40]},
        "runtime_compatibility":{"ray_preflight_pass":True},
        "budget":{"optimizer_updates":12,"prompts_per_update":4,"rollouts_per_prompt":4,"student_rollout_ceiling":192,"student_response_token_ceiling":393216},
        "data_preparation":{"format":"parquet","pyarrow_version":"22.0.0","source":"exact_worker02_public_training_shard_and_training_visible_pack","generated_on_execution_host":True,"sealed_eval_consumed":False},
        "sealed_eval_consumed":False,"g1_rerun":False,"automatic_fallback":False,
        "paid_compute_requires_manager_authorization":True,"capability_gain_claim":False,
    }
    return seal(d, "manifest_sha256")


def synthetic_command_lock(run_manifest, argv=None):
    argv = argv or ["python", "train.py", "--exact"]
    cmd = canonical_p2_sha256(argv)
    d = {
        "schema_version":1,"record_kind":hp.W03_COMMAND_LOCK_KIND,"hash_profile":hp.HASH_PROFILE,
        "task_id":hp.W03_TASK_ID,"training_plan_sha256":hp.A1_PLAN_SHA256,
        "run_manifest_sha256":run_manifest["manifest_sha256"],"arm_id":hp.A1_ARM_ID,"seed":hp.A1_SEED,
        "profile":hp.A1_PROFILE,"model_scope":"surrogate","argv":argv,"command_sha256":cmd,
        "automatic_fallback":False,"g1_rerun":False,
    }
    return seal(d, "lock_sha256")


def training_receipt(adapter_state=H("a"), **overrides):
    obj = {
        "receipt_kind":"AQLEVON_P4_SURROGATE_TRAINING_RECEIPT_V1",
        "run_manifest_sha256":"RUN_SHA",
        "training_plan_sha256":hp.A1_PLAN_SHA256,
        "arm_id":hp.A1_ARM_ID,
        "seed":hp.A1_SEED,
        "sealed_eval_consumed":False,
        "capability_gain_claim":False,
        "training":{"optimizer_updates":12,"changed_elements":100},
        "artifact":{"saved_adapter_state_sha256":adapter_state,"reloaded_adapter_state_sha256":adapter_state,"reload_hash_match":True},
    }
    for k,v in overrides.items():
        obj[k]=v
    return obj


def receipt_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode()


def candidate_for_receipt(raw, adapter_state=H("a")):
    files=[{"path":"adapter_model.safetensors","size":123,"sha256":H("b")}]
    c={
        "schema_version":1,"manifest_kind":"AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_V1","manifest_id":"",
        "hash_profile":hp.HASH_PROFILE,"artifact_type":"adapter","artifact_stage":"reproducible_gene",
        "base":{"repo":hp.SURROGATE_REPO,"revision":hp.SURROGATE_REVISION,"base_manifest_sha256":H("c")},
        "tokenizer_sha256":H("d"),"config_sha256":H("e"),
        "training_shard_manifest_sha256":p4.W02_TRAINING_SHARD_MANIFEST_SHA256,
        "training_run_receipt_sha256":hashlib.sha256(raw).hexdigest(),"merge_recipe_sha256":None,
        "parameter_layout_sha256":H("f"),"topology_class":"CUSTOM_EXPERIMENTAL",
        "artifact_files":files,"artifact_file_tree_sha256":hp._canonical_legacy_sha(files),
        "adapter_state_sha256":adapter_state,"checkpoint_state_sha256":None,
        "parent_candidate_artifact_manifest_sha256":[],"environment_toolchain_manifest_sha256":H("1"),
        "manifest_sha256":"",
    }
    c["manifest_id"]=hp._candidate_manifest_id(c)
    c["manifest_sha256"]=canonical_p2_sha256({k:v for k,v in c.items() if k!="manifest_sha256"})
    return c


def freeze_fixture(law,binding,registration, anchored="2026-09-19T10:00:00Z", unsealed="2026-09-19T10:01:00Z"):
    return hp.finalize_a1_freeze_verification({
        "law_sha256":law["law_sha256"],"stage_binding_sha256":binding["stage_binding_sha256"],
        "registration_sha256":registration["registration_sha256"],"anchor_kind":"git_commit",
        "immutable_reference":"github:owner/repo@0123456789012345678901234567890123456789:p41/a1.json",
        "external_evidence_sha256":H("2"),"manager_authority_id":"AQLEVON_MANAGER",
        "manager_attestation_sha256":H("3"),"anchored_at_utc":anchored,"scores_unsealed_at_utc":unsealed,
        "chronology_statement":"MANAGER_VERIFIED_A1_REGISTRATION_EXISTED_IN_IMMUTABLE_SYSTEM_BEFORE_A1_SCORE_INSPECTION",
    })


class TestHotPath(unittest.TestCase):
    def setUp(self):
        self.law,self.binding=law_binding()
        argv=["python","train.py","--exact"]
        self.run=synthetic_run_manifest(canonical_p2_sha256(argv))
        self.lock=synthetic_command_lock(self.run,argv)
        # Make the synthetic run receipt bind the synthetic run-manifest hash.
        self.tr=training_receipt()
        self.tr["run_manifest_sha256"]=self.run["manifest_sha256"]
        self.raw=receipt_bytes(self.tr)
        self.candidate=candidate_for_receipt(self.raw)

    def patches(self):
        return patch.multiple(hp,
            A1_RUN_MANIFEST_SHA256=self.run["manifest_sha256"],
            A1_COMMAND_SHA256=self.lock["command_sha256"],
            A1_COMMAND_LOCK_SHA256=self.lock["lock_sha256"],
        )

    def ingest(self):
        with self.patches():
            return hp.build_a1_ingest_receipt(
                law=self.law,stage_binding=self.binding,run_manifest=self.run,command_lock=self.lock,
                candidate=self.candidate,training_receipt_bytes=self.raw,recipe_spec_sha256=H("4"),
                compute_receipt_sha256=H("5"),training_budget_manifest_sha256=self.binding["matched_training_budget_manifest_sha256"])

    def test_frozen_constants_match_p41_manager_snapshot(self):
        self.assertEqual(hp.W03_TESTED_SOURCE_COMMIT,"4c56b8f738c51d57de981e9ae9a8a1a5f4e887ab")
        self.assertEqual(hp.A1_RUN_MANIFEST_SHA256,"7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45")
        self.assertEqual(hp.A1_COMMAND_SHA256,"3ad2fd2cd5303e1eb4ea71f3e25edf07d38269df1b5b3c8b6e98c8553e017400")
        self.assertEqual(hp.A1_COMMAND_LOCK_SHA256,"f1d05b53d0e00b07f7f4d60c90a6bf489f4cd2bd118b2b6a6b38c66026cee44e")

    def test_no_tuning_frozen_law_identity(self):
        self.assertEqual(self.law["law_sha256"],"70581a21c26605317afcb314d990fa2f78b621bf44af1747d8caac6168385ec0")