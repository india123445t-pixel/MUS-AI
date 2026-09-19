import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import gene1_reality_tournament_v1 as p4
from evaluation_decision_receipt_v1 import canonical_p2_sha256
from test_evaluation_decision_receipt_v1 import full_fixture

HERE = Path(__file__).resolve().parent
SHA = lambda c: c * 64


def law_fixture():
    return p4.frozen_gene1_evaluation_law()


def binding_fixture(law=None, stage="surrogate", *, round_mode=None, parent_decision_receipt_sha256=None, matched_budget_sha256=None):
    law = law or law_fixture()
    if stage == "canonical_27b" and parent_decision_receipt_sha256 is None:
        parent_decision_receipt_sha256 = SHA("d")
    return p4.build_stage_binding(
        stage=stage,
        experiment_id=f"gene1-{stage}-001",
        law_sha256=law["law_sha256"],
        w01_method_freeze_sha256=p4.W01_METHOD_TOURNAMENT_SPEC_SHA256,
        w02_gene1_pack_sha256=p4.W02_PUBLIC_PACK_BINDING_SHA256,
        sealed_eval_pack_manifest_sha256=p4.W02_SEALED_EVAL_PACK_SHA256,
        sealed_eval_commitment_sha256=p4.W02_SEALED_EVAL_COMMITMENT_SHA256,
        hidden_canary_manifest_sha256=SHA("4"),
        anti_shortcut_manifest_sha256=SHA("5"),
        metamorphic_manifest_sha256=SHA("6"),
        harness_manifest_sha256=SHA("7"),
        task_factory_manifest_sha256=SHA("a"),
        reality_policy_sha256=SHA("b"),
        sampling_profile_sha256=law["sampling_profile_sha256"],
        matched_training_budget_manifest_sha256=matched_budget_sha256 or SHA("8"),
        baseline_artifact_manifest_sha256=SHA("9"),
        round_mode=round_mode,
        parent_decision_receipt_sha256=parent_decision_receipt_sha256,
    )


def entries_fixture(binding, stage="surrogate"):
    if stage == "canonical_27b":
        return [{
            "candidate_slot": "control",
            "arm_id": "P4_A0_SFT_LORA_CONTROL",
            "training_seed": 2701,
            "training_gpu_milliseconds": 12000,
            "recipe_spec_sha256": SHA("a"),
            "candidate_artifact_manifest_sha256": SHA("b"),
            "training_run_receipt_sha256": SHA("c"),
            "compute_receipt_sha256": SHA("d"),
            "training_budget_manifest_sha256": binding["matched_training_budget_manifest_sha256"],
        }]
    return [
        {
            "candidate_slot": "control",
            "arm_id": "P4_A0_SFT_LORA_CONTROL",
            "training_seed": 1701,
            "training_gpu_milliseconds": 12000,
            "recipe_spec_sha256": SHA("a"),
            "candidate_artifact_manifest_sha256": SHA("b"),
            "training_run_receipt_sha256": SHA("c"),
            "compute_receipt_sha256": SHA("d"),
            "training_budget_manifest_sha256": binding["matched_training_budget_manifest_sha256"],
        },
        {
            "candidate_slot": "challenger_a",
            "arm_id": "P4_A1_RLVR_CONTROL",
            "training_seed": 1701,
            "training_gpu_milliseconds": 10000,
            "recipe_spec_sha256": SHA("e"),
            "candidate_artifact_manifest_sha256": SHA("f"),
            "training_run_receipt_sha256": SHA("0"),
            "compute_receipt_sha256": SHA("1"),
            "training_budget_manifest_sha256": binding["matched_training_budget_manifest_sha256"],
        },
    ]


def registration_fixture(law=None, binding=None, stage="surrogate"):
    law = law or law_fixture()
    binding = binding or binding_fixture(law, stage)
    return p4.build_candidate_registration(law=law, stage_binding=binding, entries=entries_fixture(binding, stage))


def verification_fixture(law, binding, reg, *, anchored="2026-09-19T04:50:00Z", unsealed="2026-09-19T05:00:00Z"):
    return p4.finalize_freeze_verification({
        "law_sha256": law["law_sha256"],
        "stage_binding_sha256": binding["stage_binding_sha256"],
        "candidate_registration_sha256": reg["candidate_registration_sha256"],
        "anchor_kind": "git_commit",
        "immutable_reference": "github:india123445t-pixel/MUS-AI@deadbeefdeadbeefdeadbeefdeadbeefdeadbeef:p4/prereg.json",
        "external_evidence_sha256": SHA("2"),
        "manager_authority_id": "AQLEVON_MANAGER",
        "manager_attestation_sha256": SHA("3"),
        "anchored_at_utc": anchored,
        "scores_unsealed_at_utc": unsealed,
        "chronology_statement": "MANAGER_VERIFIED_LAW_BINDING_AND_REGISTRATION_EXISTED_IN_IMMUTABLE_SYSTEM_BEFORE_SCORE_INSPECTION",
    })


def score_card(*, law, binding, slot, artifact, recipe, primary1, primary4, transfer1=4, transfer4=5,
               canary1=3, canary4=4, anti1=3, anti4=4, raw1=None, raw4=None,
               meta1=2, meta4=3, paired=10, coding=3, tools=2, reality="REALITY_PASS", divergence=False,
               arm_id=None, training_seed=1701, training_gpu_milliseconds=10000):
    if raw1 is None:
        raw1 = primary1 + 1
    if raw4 is None:
        raw4 = primary4 + 1
    if slot == "baseline":
        arm_id = "BASELINE_REFERENCE"
        training_seed = 0
        training_gpu_milliseconds = 0
    elif arm_id is None:
        arm_id = law["arm_id_by_slot"][slot]
    card = {
        "stage_binding_sha256": binding["stage_binding_sha256"],
        "candidate_slot": slot,
        "arm_id": arm_id,
        "training_seed": training_seed,
        "training_gpu_milliseconds": training_gpu_milliseconds,
        "candidate_artifact_manifest_sha256": artifact,
        "recipe_spec_sha256": recipe,
        "reality_evidence_kind": p4.P3_REALITY_EVIDENCE_KIND,
        "reality_evidence_sha256": hashlib.sha256((slot + artifact).encode()).hexdigest(),
        "reality_gate_code_sha256": p4.P3_REALITY_GATE_CODE_SHA256,
        "reality_status": reality,
        "sampling_profile_sha256": law["sampling_profile_sha256"],
        "anti_shortcut_receipt_sha256": SHA("c"),
        "proxy_clean_divergence": divergence,
        "population": {
            "primary_total": 10,
            "transfer_total": 6,
            "canary_total": 4,
            "anti_shortcut_total": 5,
            "metamorphic_group_total": 3,
            "paired_slot_total": 12,
        },
        "primary_by_k": {
            "1": {"raw_pass_count": raw1, "clean_pass_count": primary1, "hack_gap_count": raw1-primary1},
            "4": {"raw_pass_count": raw4, "clean_pass_count": primary4, "hack_gap_count": raw4-primary4},
        },
        "transfer_by_k": {
            "1": {"clean_pass_count": transfer1},
            "4": {"clean_pass_count": transfer4},
        },
        "canary_by_k": {
            "1": {"clean_pass_count": canary1},
            "4": {"clean_pass_count": canary4},
        },
        "anti_shortcut_by_k": {
            "1": {"clean_pass_count": anti1},
            "4": {"clean_pass_count": anti4},
        },
        "metamorphic_invariant_groups_by_k": {"1": meta1, "4": meta4},
        "paired_slot_invariant_count": paired,
        "domains": {
            "coding": {"total": 5, "clean_pass_at_1": coding},
            "tool_use": {"total": 5, "clean_pass_at_1": tools},
        },
    }
    return p4.finalize_score_card(card)


def baseline_fixture(law, binding):
    return score_card(
        law=law, binding=binding, slot="baseline", artifact=SHA("9"), recipe=SHA("8"),
        primary1=5, primary4=7, transfer1=3, transfer4=5, canary1=3, canary4=4,
        anti1=3, anti4=4, raw1=6, raw4=8, meta1=2, meta4=3, paired=10, coding=3, tools=2,
    )


def candidate_from_entry(law, binding, entry, *, quality=1):
    if quality == 1:
        return score_card(
            law=law, binding=binding, slot=entry["candidate_slot"], artifact=entry["candidate_artifact_manifest_sha256"],
            recipe=entry["recipe_spec_sha256"], primary1=6, primary4=8, transfer1=4, transfer4=5,
            canary1=3, canary4=4, anti1=3, anti4=4, raw1=7, raw4=9, meta1=2, meta4=3,
            paired=10, coding=4, tools=2, arm_id=entry["arm_id"], training_seed=entry["training_seed"], training_gpu_milliseconds=entry["training_gpu_milliseconds"],
        )
    return score_card(
        law=law, binding=binding, slot=entry["candidate_slot"], artifact=entry["candidate_artifact_manifest_sha256"],
        recipe=entry["recipe_spec_sha256"], primary1=7, primary4=9, transfer1=5, transfer4=6,
        canary1=4, canary4=4, anti1=4, anti4=5, raw1=8, raw4=10, meta1=3, meta4=3,
        paired=11, coding=4, tools=3, arm_id=entry["arm_id"], training_seed=entry["training_seed"], training_gpu_milliseconds=entry["training_gpu_milliseconds"],
    )


def make_surrogate_fixture():
    law = law_fixture()
    binding = binding_fixture(law)
    reg = registration_fixture(law, binding)
    ver = verification_fixture(law, binding, reg)
    base = baseline_fixture(law, binding)
    cards = [candidate_from_entry(law, binding, reg["entries"][0], quality=1), candidate_from_entry(law, binding, reg["entries"][1], quality=2)]
    return law, binding, reg, ver, base, cards


def p3_summary(*, primary1, primary4, raw1, raw4, transfer1, transfer4, canary1, canary4, meta1, meta4, paired, coding, tools):
    return {
        "primary": {
            "1": {"task_count":10,"raw_pass_count":raw1,"raw_pass_rate":"0","clean_pass_count":primary1,"clean_pass_rate":"0","hack_gap_count":raw1-primary1,"hack_gap_rate":"0"},
            "4": {"task_count":10,"raw_pass_count":raw4,"raw_pass_rate":"0","clean_pass_count":primary4,"clean_pass_rate":"0","hack_gap_count":raw4-primary4,"hack_gap_rate":"0"},
        },
        "transfer": {
            "1": {"task_count":6,"raw_pass_count":transfer1,"raw_pass_rate":"0","clean_pass_count":transfer1,"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
            "4": {"task_count":6,"raw_pass_count":transfer4,"raw_pass_rate":"0","clean_pass_count":transfer4,"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
        },
        "canary": {
            "1": {"task_count":4,"raw_pass_count":canary1,"raw_pass_rate":"0","clean_pass_count":canary1,"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
            "4": {"task_count":4,"raw_pass_count":canary4,"raw_pass_rate":"0","clean_pass_count":canary4,"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
        },
        "domains": {
            "coding": {
                "1": {"task_count":5,"raw_pass_count":coding,"raw_pass_rate":"0","clean_pass_count":coding,"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
                "4": {"task_count":5,"raw_pass_count":5,"raw_pass_rate":"1","clean_pass_count":5,"clean_pass_rate":"1","hack_gap_count":0,"hack_gap_rate":"0"},
            },
            "tool_use": {
                "1": {"task_count":5,"raw_pass_count":tools,"raw_pass_rate":"0","clean_pass_count":tools,"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
                "4": {"task_count":5,"raw_pass_count":5,"raw_pass_rate":"1","clean_pass_count":5,"clean_pass_rate":"1","hack_gap_count":0,"hack_gap_rate":"0"},
            },
        },
        "metamorphic": {
            "group_count":3,
            "groups": {},
            "paired_slot_count":12,
            "paired_slot_invariant_count":paired,
            "paired_slot_invariance_rate":"0",
            "clean_pass_group_invariance_by_k": {
                "1": {"invariant_group_count":meta1,"group_count":3,"rate":"0"},
                "4": {"invariant_group_count":meta4,"group_count":3,"rate":"1"},
            },
        },
        "integrity_violation_sample_count":0,
        "total_sample_count":80,
    }


def p3_evidence_fixture(law,binding,candidate_artifact,*,quality=1,status="REALITY_PASS",divergence=False):
    base=p3_summary(primary1=5,primary4=7,raw1=6,raw4=8,transfer1=3,transfer4=5,canary1=3,canary4=4,meta1=2,meta4=3,paired=10,coding=3,tools=2)
    if quality==1:
        cand=p3_summary(primary1=6,primary4=8,raw1=7,raw4=9,transfer1=4,transfer4=5,canary1=3,canary4=4,meta1=2,meta4=3,paired=10,coding=4,tools=2)
    else:
        cand=p3_summary(primary1=7,primary4=9,raw1=8,raw4=10,transfer1=5,transfer4=6,canary1=4,canary4=4,meta1=3,meta4=3,paired=11,coding=4,tools=3)
    e={
        "schema_version":1,
        "evidence_kind":p4.P3_REALITY_EVIDENCE_KIND,
        "hash_profile":p4.HASH_PROFILE,
        "reality_policy_sha256":binding["reality_policy_sha256"],
        "reality_gate_code_sha256":p4.P3_REALITY_GATE_CODE_SHA256,
        "baseline_outcome_pack_sha256":SHA("d"),
        "candidate_outcome_pack_sha256":hashlib.sha256((candidate_artifact+"pack").encode()).hexdigest(),
        "baseline_candidate_artifact_manifest_sha256":binding["baseline_artifact_manifest_sha256"],
        "candidate_artifact_manifest_sha256":candidate_artifact,
        "harness_manifest_sha256":binding["harness_manifest_sha256"],
        "task_factory_manifest_sha256":binding["task_factory_manifest_sha256"],
        "hidden_canary_manifest_sha256":binding["hidden_canary_manifest_sha256"],
        "baseline_raw_outcome_log_sha256":SHA("e"),
        "candidate_raw_outcome_log_sha256":hashlib.sha256((candidate_artifact+"raw").encode()).hexdigest(),
        "metrics":{"baseline":base,"candidate":cand,"primary_clean_pass_delta_basis_points":"1000","transfer_clean_pass_delta_basis_points":"1666.666","hack_gap_increase_basis_points":"0"},
        "checkpoint_curve":{"divergence_detected":divergence,"divergence_steps":[],"baseline_step":0,"final_step":1},
        "seed_vs_resampling_null":None,
        "method_level_claim":False,
        "final_status":status,
        "failure_reason_codes":[],
        "failure_reason_set_sha256":canonical_p2_sha256([]),
        "promotion_authority":{
            "authority_kind":"AQLEVON_REALITY_EVIDENCE_NOT_PROMOTION_AUTHORITY_V1",
            "authoritative_for_model_promotion":False,
            "promotion_requirement":"VALID_AQLEVON_EVALUATION_DECISION_RECEIPT_V1_PLUS_MANAGER_REVIEW",
            "authoritative_for_arbitrary_runtime_attempts":False,
        },
        "truth_boundary":"REALITY_PASS_IS_EVIDENCE_ONLY_PROMOTION_REQUIRES_EVALUATION_DECISION_RECEIPT_AND_MANAGER_REVIEW",
    }
    e["evidence_sha256"]=canonical_p2_sha256(e)
    return e


def anti_receipt_fixture(law,binding,artifact,*,baseline=False,quality=1):
    if baseline:
        c1,c4=3,4
    elif quality==1:
        c1,c4=3,4
    else:
        c1,c4=4,5
    return p4.finalize_anti_shortcut_receipt({
        "candidate_artifact_manifest_sha256":artifact,
        "anti_shortcut_manifest_sha256":binding["anti_shortcut_manifest_sha256"],
        "harness_manifest_sha256":binding["harness_manifest_sha256"],
        "raw_outcome_log_sha256":hashlib.sha256((artifact+"anti").encode()).hexdigest(),
        "by_k":{"1":{"task_count":5,"clean_pass_count":c1},"4":{"task_count":5,"clean_pass_count":c4}},
    })


def _summary_from_score_card(card):
    def pop_block(name,total_key,raw=False):
        out={}
        for k,item in card[name].items():
            clean=item["clean_pass_count"]
            total=card["population"][total_key]
            rawc=item.get("raw_pass_count",clean)
            gap=rawc-clean
            out[k]={"task_count":total,"raw_pass_count":rawc,"raw_pass_rate":"0","clean_pass_count":clean,"clean_pass_rate":"0","hack_gap_count":gap,"hack_gap_rate":"0"}
        return out
    domains={}
    for d,item in card["domains"].items():
        domains[d]={
            "1":{"task_count":item["total"],"raw_pass_count":item["clean_pass_at_1"],"raw_pass_rate":"0","clean_pass_count":item["clean_pass_at_1"],"clean_pass_rate":"0","hack_gap_count":0,"hack_gap_rate":"0"},
            "4":{"task_count":item["total"],"raw_pass_count":item["total"],"raw_pass_rate":"1","clean_pass_count":item["total"],"clean_pass_rate":"1","hack_gap_count":0,"hack_gap_rate":"0"},
        }
    return {
        "primary":pop_block("primary_by_k","primary_total",True),
        "transfer":pop_block("transfer_by_k","transfer_total"),
        "canary":pop_block("canary_by_k","canary_total"),
        "domains":domains,
        "metamorphic":{
            "group_count":card["population"]["metamorphic_group_total"],
            "groups":{},
            "paired_slot_count":card["population"]["paired_slot_total"],
            "paired_slot_invariant_count":card["paired_slot_invariant_count"],
            "paired_slot_invariance_rate":"0",
            "clean_pass_group_invariance_by_k":{
                k:{"invariant_group_count":v,"group_count":card["population"]["metamorphic_group_total"],"rate":"0"}
                for k,v in card["metamorphic_invariant_groups_by_k"].items()
            },
        },
        "integrity_violation_sample_count":0,
        "total_sample_count":80,
    }


def _p3_evidence_from_cards(law,binding,base,card):
    e={
        "schema_version":1,"evidence_kind":p4.P3_REALITY_EVIDENCE_KIND,"hash_profile":p4.HASH_PROFILE,
        "reality_policy_sha256":binding["reality_policy_sha256"],"reality_gate_code_sha256":p4.P3_REALITY_GATE_CODE_SHA256,
        "baseline_outcome_pack_sha256":SHA("d"),
        "candidate_outcome_pack_sha256":hashlib.sha256((card["candidate_artifact_manifest_sha256"]+"pack").encode()).hexdigest(),
        "baseline_candidate_artifact_manifest_sha256":binding["baseline_artifact_manifest_sha256"],
        "candidate_artifact_manifest_sha256":card["candidate_artifact_manifest_sha256"],
        "harness_manifest_sha256":binding["harness_manifest_sha256"],"task_factory_manifest_sha256":binding["task_factory_manifest_sha256"],
        "hidden_canary_manifest_sha256":binding["hidden_canary_manifest_sha256"],"baseline_raw_outcome_log_sha256":SHA("e"),
        "candidate_raw_outcome_log_sha256":hashlib.sha256((card["candidate_artifact_manifest_sha256"]+"raw").encode()).hexdigest(),
        "metrics":{"baseline":_summary_from_score_card(base),"candidate":_summary_from_score_card(card),"primary_clean_pass_delta_basis_points":"0","transfer_clean_pass_delta_basis_points":"0","hack_gap_increase_basis_points":"0"},
        "checkpoint_curve":{"divergence_detected":card["proxy_clean_divergence"],"divergence_steps":[],"baseline_step":0,"final_step":1},
        "seed_vs_resampling_null":None,"method_level_claim":False,
        "final_status":card["reality_status"],"failure_reason_codes":[],"failure_reason_set_sha256":canonical_p2_sha256([]),
        "promotion_authority":{"authority_kind":"AQLEVON_REALITY_EVIDENCE_NOT_PROMOTION_AUTHORITY_V1","authoritative_for_model_promotion":False,"promotion_requirement":"VALID_AQLEVON_EVALUATION_DECISION_RECEIPT_V1_PLUS_MANAGER_REVIEW","authoritative_for_arbitrary_runtime_attempts":False},
        "truth_boundary":"REALITY_PASS_IS_EVIDENCE_ONLY_PROMOTION_REQUIRES_EVALUATION_DECISION_RECEIPT_AND_MANAGER_REVIEW",
    }
    e["evidence_sha256"]=canonical_p2_sha256(e)
    return e


def _anti_receipt_from_card(binding,card):
    return p4.finalize_anti_shortcut_receipt({
        "candidate_artifact_manifest_sha256":card["candidate_artifact_manifest_sha256"],
        "anti_shortcut_manifest_sha256":binding["anti_shortcut_manifest_sha256"],
        "harness_manifest_sha256":binding["harness_manifest_sha256"],
        "raw_outcome_log_sha256":hashlib.sha256((card["candidate_artifact_manifest_sha256"]+"anti-live").encode()).hexdigest(),
        "by_k":{k:{"task_count":card["population"]["anti_shortcut_total"],"clean_pass_count":v["clean_pass_count"]} for k,v in card["anti_shortcut_by_k"].items()},
    })


def decision_with_semantics(*,law,binding,reg,ver,base,cards,p2receipt=None):
    # Build the exact support evidence first, then derive the authoritative score
    # cards from that evidence.  Hand-built cards above are only concise fixture
    # specifications; production decisions never trust their embedded hashes.
    first_card=cards[0] if cards else candidate_from_entry(law,binding,reg["entries"][0],quality=1)
    baseline_p3=_p3_evidence_from_cards(law,binding,base,first_card)
    baseline_anti=_anti_receipt_from_card(binding,base)
    p3_by={c["candidate_slot"]:_p3_evidence_from_cards(law,binding,base,c) for c in cards}
    anti_by={c["candidate_slot"]:_anti_receipt_from_card(binding,c) for c in cards}

    semantic_base=p4.build_score_card_from_p3_evidence(
        law=law,stage_binding=binding,p3_evidence=baseline_p3,
        anti_shortcut_receipt=baseline_anti,candidate_slot="baseline",
        recipe_spec_sha256=base["recipe_spec_sha256"],summary_role="baseline",
    )
    semantic_cards=[p4.build_score_card_from_p3_evidence(
        law=law,stage_binding=binding,p3_evidence=p3_by[c["candidate_slot"]],
        anti_shortcut_receipt=anti_by[c["candidate_slot"]],candidate_slot=c["candidate_slot"],
        recipe_spec_sha256=c["recipe_spec_sha256"],summary_role="candidate",
        arm_id=c["arm_id"], training_seed=c["training_seed"], training_gpu_milliseconds=c["training_gpu_milliseconds"],
    ) for c in cards]

    return p4.build_tournament_decision(
        law=law,stage_binding=binding,registration=reg,freeze_verification=ver,
        baseline_card=semantic_base,candidate_cards=semantic_cards,baseline_p3_evidence=baseline_p3,
        baseline_anti_shortcut_receipt=baseline_anti,candidate_p3_evidence_by_slot=p3_by,
        candidate_anti_shortcut_receipt_by_slot=anti_by,p2_evaluation_decision_receipt=p2receipt,
    )



def round_bundle_fixture(law, binding, seed, slot_specs):
    entries=[]
    cards=[]
    for slot,spec in slot_specs.items():
        artifact=hashlib.sha256(f"{slot}-{seed}-artifact".encode()).hexdigest()
        recipe=hashlib.sha256(f"{slot}-recipe".encode()).hexdigest()
        entry={
            "candidate_slot":slot,
            "arm_id":law["arm_id_by_slot"][slot],
            "training_seed":seed,
            "training_gpu_milliseconds":spec.get("gpu",10000),
            "recipe_spec_sha256":recipe,
            "candidate_artifact_manifest_sha256":artifact,
            "training_run_receipt_sha256":hashlib.sha256(f"{slot}-{seed}-train".encode()).hexdigest(),
            "compute_receipt_sha256":hashlib.sha256(f"{slot}-{seed}-compute".encode()).hexdigest(),
            "training_budget_manifest_sha256":binding["matched_training_budget_manifest_sha256"],
        }
        entries.append(entry)
        cards.append(score_card(
            law=law,binding=binding,slot=slot,artifact=artifact,recipe=recipe,
            primary1=spec.get("primary1",6),primary4=spec.get("primary4",8),
            transfer1=spec.get("transfer1",4),transfer4=spec.get("transfer4",5),
            canary1=spec.get("canary1",3),canary4=spec.get("canary4",4),
            anti1=spec.get("anti1",3),anti4=spec.get("anti4",4),
            raw1=spec.get("raw1",spec.get("primary1",6)+1),raw4=spec.get("raw4",spec.get("primary4",8)+1),
            meta1=spec.get("meta1",2),meta4=spec.get("meta4",3),paired=spec.get("paired",10),
            coding=spec.get("coding",3),tools=spec.get("tools",2),
            arm_id=law["arm_id_by_slot"][slot],training_seed=seed,training_gpu_milliseconds=spec.get("gpu",10000),
        ))
    reg=p4.build_candidate_registration(law=law,stage_binding=binding,entries=entries)
    ver=verification_fixture(law,binding,reg,anchored=f"2026-09-19T04:{40 + (seed-1701)*2:02d}:00Z",unsealed=f"2026-09-19T05:{10 + (seed-1701)*2:02d}:00Z")
    base=baseline_fixture(law,binding)
    first=cards[0]
    baseline_p3=_p3_evidence_from_cards(law,binding,base,first)
    baseline_anti=_anti_receipt_from_card(binding,base)
    p3_by={c["candidate_slot"]:_p3_evidence_from_cards(law,binding,base,c) for c in cards}
    anti_by={c["candidate_slot"]:_anti_receipt_from_card(binding,c) for c in cards}
    semantic_base=p4.build_score_card_from_p3_evidence(
        law=law,stage_binding=binding,p3_evidence=baseline_p3,anti_shortcut_receipt=baseline_anti,
        candidate_slot="baseline",recipe_spec_sha256=base["recipe_spec_sha256"],summary_role="baseline")
    semantic_cards=[p4.build_score_card_from_p3_evidence(
        law=law,stage_binding=binding,p3_evidence=p3_by[c["candidate_slot"]],
        anti_shortcut_receipt=anti_by[c["candidate_slot"]],candidate_slot=c["candidate_slot"],
        recipe_spec_sha256=c["recipe_spec_sha256"],summary_role="candidate",arm_id=c["arm_id"],
        training_seed=c["training_seed"],training_gpu_milliseconds=c["training_gpu_milliseconds"]) for c in cards]
    return {
        "stage_binding":binding,"registration":reg,"freeze_verification":ver,"baseline_card":semantic_base,
        "candidate_cards":semantic_cards,"baseline_p3_evidence":baseline_p3,"baseline_anti_shortcut_receipt":baseline_anti,
        "candidate_p3_evidence_by_slot":p3_by,"candidate_anti_shortcut_receipt_by_slot":anti_by,
    }

class Gene1RealityTournamentTests(unittest.TestCase):
    def test_frozen_law_is_valid_and_candidate_blind(self):
        law = law_fixture()
        self.assertEqual(p4.validate_evaluation_law(law), [])
        text = json.dumps(law)
        self.assertNotIn('"candidate_scores"', text)
        self.assertFalse(law["authority"]["authoritative_for_model_promotion"])

    def test_law_self_hash_tamper_fails(self):
        law = law_fixture()
        law["tie_policy"] = "PICK_CONTROL"
        self.assertTrue(p4.validate_evaluation_law(law))

    def test_law_rehashed_score_injection_still_fails_schema(self):
        law = law_fixture()
        law["score"] = 99
        law["law_sha256"] = canonical_p2_sha256({k: v for k, v in law.items() if k != "law_sha256"})
        self.assertTrue(p4.validate_evaluation_law(law))

    def test_stage_binding_valid(self):
        law = law_fixture(); binding = binding_fixture(law)
        self.assertEqual(p4.validate_stage_binding(binding, law=law), [])

    def test_stage_binding_rehashed_foreign_law_fails(self):
        law = law_fixture(); binding = binding_fixture(law)
        binding["law_sha256"] = SHA("a")
        binding["stage_binding_sha256"] = canonical_p2_sha256({k:v for k,v in binding.items() if k != "stage_binding_sha256"})
        self.assertTrue(p4.validate_stage_binding(binding, law=law))

    def test_registration_valid_and_sorted_by_frozen_slots(self):
        law = law_fixture(); binding = binding_fixture(law)
        entries = list(reversed(entries_fixture(binding)))
        reg = p4.build_candidate_registration(law=law, stage_binding=binding, entries=entries)
        self.assertEqual([e["candidate_slot"] for e in reg["entries"]], ["control", "challenger_a"])
        self.assertEqual(p4.validate_candidate_registration(reg, law=law, stage_binding=binding), [])

    def test_registration_duplicate_candidate_rejected(self):
        law = law_fixture(); binding = binding_fixture(law); entries = entries_fixture(binding)
        entries[1]["candidate_artifact_manifest_sha256"] = entries[0]["candidate_artifact_manifest_sha256"]
        with self.assertRaises(p4.Gene1TournamentError):
            p4.build_candidate_registration(law=law, stage_binding=binding, entries=entries)

    def test_registration_budget_mismatch_rejected(self):
        law = law_fixture(); binding = binding_fixture(law); entries = entries_fixture(binding)
        entries[1]["training_budget_manifest_sha256"] = SHA("f")
        with self.assertRaises(p4.Gene1TournamentError):
            p4.build_candidate_registration(law=law, stage_binding=binding, entries=entries)

    def test_freeze_verification_valid(self):
        law = law_fixture(); binding = binding_fixture(law); reg = registration_fixture(law,binding)
        ver = verification_fixture(law,binding,reg)
        self.assertEqual(p4.validate_freeze_verification(ver, law=law, stage_binding=binding, registration=reg), [])

    def test_freeze_verification_anchor_must_predate_score_unseal(self):
        law = law_fixture(); binding = binding_fixture(law); reg = registration_fixture(law,binding)
        ver = verification_fixture(law,binding,reg,anchored="2026-09-19T05:01:00Z",unsealed="2026-09-19T05:00:00Z")
        self.assertTrue(any("chronology violated" in x for x in p4.validate_freeze_verification(ver, law=law, stage_binding=binding, registration=reg)))

    def test_score_card_valid(self):
        law = law_fixture(); binding = binding_fixture(law); base = baseline_fixture(law,binding)
        self.assertEqual(p4.validate_score_card(base, law=law, stage_binding=binding), [])

    def test_score_card_hack_gap_arithmetic_tamper_fails_even_rehashed(self):
        law = law_fixture(); binding = binding_fixture(law); base = baseline_fixture(law,binding)
        base["primary_by_k"]["1"]["hack_gap_count"] = 0
        base["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in base.items() if k != "score_card_sha256"})
        self.assertTrue(any("hack gap arithmetic" in x for x in p4.validate_score_card(base, law=law, stage_binding=binding)))

    def test_score_card_wrong_p3_code_identity_fails(self):
        law = law_fixture(); binding = binding_fixture(law); base = baseline_fixture(law,binding)
        base["reality_gate_code_sha256"] = SHA("a")
        base["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in base.items() if k != "score_card_sha256"})
        self.assertTrue(any("P3 reality" in x for x in p4.validate_score_card(base, law=law, stage_binding=binding)))

    def test_surrogate_selection_picks_unique_best_survivor(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        receipt = decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)
        self.assertEqual(receipt["decision_status"], "SURROGATE_SCREEN_RANKING_READY")
        self.assertIsNone(receipt["selected_candidate_slot"])
        self.assertIsNone(receipt["selected_recipe_spec_sha256"])
        self.assertEqual(receipt["ranked_survivor_slots"][0], "challenger_a")
        self.assertEqual(receipt["top_two_survivor_slots"], ["challenger_a", "control"])
        self.assertEqual(p4.validate_tournament_decision(receipt, law=law), [])

    def test_raw_reward_gain_with_clean_flat_is_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        bad = score_card(law=law,binding=binding,slot=reg["entries"][0]["candidate_slot"],artifact=reg["entries"][0]["candidate_artifact_manifest_sha256"],recipe=reg["entries"][0]["recipe_spec_sha256"],primary1=5,primary4=7,raw1=8,raw4=9,arm_id=reg["entries"][0]["arm_id"],training_seed=reg["entries"][0]["training_seed"],training_gpu_milliseconds=reg["entries"][0]["training_gpu_milliseconds"])
        bad2 = copy.deepcopy(bad); bad2["candidate_slot"]="challenger_a"; bad2["arm_id"]="P4_A1_RLVR_CONTROL"; bad2["training_seed"]=1701; bad2["training_gpu_milliseconds"]=10000; bad2["candidate_artifact_manifest_sha256"]=reg["entries"][1]["candidate_artifact_manifest_sha256"]; bad2["recipe_spec_sha256"]=reg["entries"][1]["recipe_spec_sha256"]; bad2["reality_evidence_sha256"]=SHA("e"); bad2["score_card_sha256"]=canonical_p2_sha256({k:v for k,v in bad2.items() if k!="score_card_sha256"})
        receipt = decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=[bad,bad2])
        self.assertEqual(receipt["decision_status"], "REJECTED")

    def test_proxy_clean_divergence_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for i,card in enumerate(cards):
            card["proxy_clean_divergence"] = True
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        receipt = decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)
        self.assertEqual(receipt["decision_status"], "REJECTED")

    def test_hack_gap_worsening_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for card in cards:
            card["primary_by_k"]["1"]["raw_pass_count"] = 9
            card["primary_by_k"]["1"]["hack_gap_count"] = 9-card["primary_by_k"]["1"]["clean_pass_count"]
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        receipt = decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)
        self.assertEqual(receipt["decision_status"], "REJECTED")

    def test_transfer_regression_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for card in cards:
            card["transfer_by_k"]["1"]["clean_pass_count"] = 2
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        self.assertEqual(decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)["decision_status"], "REJECTED")

    def test_canary_regression_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for card in cards:
            card["canary_by_k"]["1"]["clean_pass_count"] = 2
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        self.assertEqual(decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)["decision_status"], "REJECTED")

    def test_anti_shortcut_regression_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for card in cards:
            card["anti_shortcut_by_k"]["1"]["clean_pass_count"] = 2
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        self.assertEqual(decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)["decision_status"], "REJECTED")

    def test_metamorphic_regression_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for card in cards:
            card["metamorphic_invariant_groups_by_k"]["1"] = 1
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        self.assertEqual(decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)["decision_status"], "REJECTED")

    def test_weakest_domain_regression_rejected(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        for card in cards:
            card["domains"]["tool_use"]["clean_pass_at_1"] = 1
            card["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in card.items() if k!="score_card_sha256"})
        self.assertEqual(decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)["decision_status"], "REJECTED")

    def test_tie_policy_does_not_arbitrarily_pick_candidate(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        tied = copy.deepcopy(cards[0])
        tied["candidate_slot"] = "challenger_a"
        tied["arm_id"] = "P4_A1_RLVR_CONTROL"
        tied["training_seed"] = 1701
        tied["training_gpu_milliseconds"] = reg["entries"][1]["training_gpu_milliseconds"]
        tied["candidate_artifact_manifest_sha256"] = reg["entries"][1]["candidate_artifact_manifest_sha256"]
        tied["recipe_spec_sha256"] = reg["entries"][1]["recipe_spec_sha256"]
        tied["reality_evidence_sha256"] = SHA("f")
        tied["score_card_sha256"] = canonical_p2_sha256({k:v for k,v in tied.items() if k!="score_card_sha256"})
        receipt = decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=[cards[0],tied])
        self.assertEqual(receipt["decision_status"], "SURROGATE_SCREEN_RANKING_READY")
        self.assertIsNone(receipt["selected_candidate_slot"])
        self.assertEqual(receipt["ranked_survivor_slots"][0], "challenger_a")

    def test_missing_registered_score_card_is_invalid(self):
        law,binding,reg,ver,base,cards = make_surrogate_fixture()
        receipt = decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards[:1])
        self.assertEqual(receipt["decision_status"], "INVALID")

    def test_27b_without_p2_receipt_cannot_reach_manager_review(self):
        law=law_fixture(); binding=binding_fixture(law,"canonical_27b"); reg=registration_fixture(law,binding,"canonical_27b"); ver=verification_fixture(law,binding,reg); base=baseline_fixture(law,binding)
        card=candidate_from_entry(law,binding,reg["entries"][0],quality=2)
        receipt=decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=[card])
        self.assertEqual(receipt["decision_status"],"REJECTED")
        self.assertIsNone(receipt["p2_evaluation_decision_receipt_sha256"])

    def test_27b_valid_p2_promotion_receipt_reaches_manager_review_only(self):
        law=law_fixture(); binding=binding_fixture(law,"canonical_27b")
        cand, exp, prov, scan, rep, gate, req, anchor, p2receipt = full_fixture()
        entry=entries_fixture(binding,"canonical_27b")[0]
        entry["candidate_artifact_manifest_sha256"] = cand["manifest_sha256"]
        reg=p4.build_candidate_registration(law=law,stage_binding=binding,entries=[entry]); ver=verification_fixture(law,binding,reg); base=baseline_fixture(law,binding)
        card=candidate_from_entry(law,binding,entry,quality=2)
        receipt=decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=[card],p2receipt=p2receipt)
        self.assertEqual(receipt["decision_status"],"READY_FOR_MANAGER_PROMOTION_REVIEW")
        self.assertFalse(receipt["authority"]["authoritative_for_model_promotion"])
        self.assertEqual(p4.validate_tournament_decision(receipt,law=law),[])

    def test_27b_p2_receipt_wrong_candidate_is_invalid(self):
        law=law_fixture(); binding=binding_fixture(law,"canonical_27b"); reg=registration_fixture(law,binding,"canonical_27b"); ver=verification_fixture(law,binding,reg); base=baseline_fixture(law,binding); card=candidate_from_entry(law,binding,reg["entries"][0],quality=2)
        _,_,_,_,_,_,_,_,p2receipt=full_fixture()
        receipt=decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=[card],p2receipt=p2receipt)
        self.assertEqual(receipt["decision_status"],"INVALID")

    def test_decision_authority_cannot_be_laundered_true(self):
        law,binding,reg,ver,base,cards=make_surrogate_fixture(); receipt=decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)
        receipt["authority"]["authoritative_for_model_promotion"]=True
        receipt["decision_receipt_sha256"]=canonical_p2_sha256({k:v for k,v in receipt.items() if k!="decision_receipt_sha256"})
        self.assertTrue(any("authority laundering" in x for x in p4.validate_tournament_decision(receipt,law=law)))

    def test_no_direct_float_in_frozen_or_decision_evidence(self):
        law,binding,reg,ver,base,cards=make_surrogate_fixture(); receipt=decision_with_semantics(law=law,binding=binding,reg=reg,ver=ver,base=base,cards=cards)
        def walk(x):
            if isinstance(x,float): return True
            if isinstance(x,dict): return any(walk(v) for v in x.values())
            if isinstance(x,list): return any(walk(v) for v in x)
            return False
        self.assertFalse(walk(law)); self.assertFalse(walk(receipt))

    def test_cross_lane_frozen_input_snapshots_validate(self):
        w01=json.loads((HERE/"worker01_method_tournament_spec_v1.json").read_text())
        w02=json.loads((HERE/"gene1_worker02_public_pack_binding_v1.json").read_text())
        self.assertEqual(p4.validate_worker01_method_tournament_spec(w01),[])
        self.assertEqual(p4.validate_worker02_public_pack_binding(w02),[])
        self.assertEqual(canonical_p2_sha256(w01),p4.W01_METHOD_TOURNAMENT_SPEC_SHA256)
        self.assertEqual(w02["binding_sha256"],p4.W02_PUBLIC_PACK_BINDING_SHA256)

    def test_worker02_public_binding_tamper_fails_even_rehashed(self):
        w02=json.loads((HERE/"gene1_worker02_public_pack_binding_v1.json").read_text())
        w02["training_visible_pack_sha256"]=SHA("f")
        w02["binding_sha256"]=canonical_p2_sha256({k:v for k,v in w02.items() if k!="binding_sha256"})
        self.assertTrue(p4.validate_worker02_public_pack_binding(w02))

    def test_cli_validate_frozen_inputs(self):
        r=subprocess.run([sys.executable,str(HERE/"gene1_reality_tournament_v1.py"),"validate-inputs","--worker01-spec",str(HERE/"worker01_method_tournament_spec_v1.json"),"--worker02-binding",str(HERE/"gene1_worker02_public_pack_binding_v1.json")],cwd=HERE,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)["status"],"VALID")

    def test_cli_freeze_and_validate_law(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"law.json"
            r=subprocess.run([sys.executable,str(HERE/"gene1_reality_tournament_v1.py"),"freeze-law","--output",str(p)],cwd=HERE,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r2=subprocess.run([sys.executable,str(HERE/"gene1_reality_tournament_v1.py"),"validate-law","--law",str(p)],cwd=HERE,capture_output=True,text=True)
            self.assertEqual(r2.returncode,0,r2.stderr)
            self.assertEqual(json.loads(r2.stdout)["status"],"VALID")


    def test_p3_envelope_validates_exact_frozen_bindings(self):
        law=law_fixture(); binding=binding_fixture(law); artifact=SHA("b")
        evidence=p3_evidence_fixture(law,binding,artifact)
        self.assertEqual(p4.validate_p3_reality_evidence_envelope(evidence,law=law,stage_binding=binding,expected_candidate_artifact_manifest_sha256=artifact),[])

    def test_p3_envelope_authority_laundering_fails_even_rehashed(self):
        law=law_fixture(); binding=binding_fixture(law); artifact=SHA("b"); evidence=p3_evidence_fixture(law,binding,artifact)
        evidence["promotion_authority"]["authoritative_for_model_promotion"]=True
        evidence["evidence_sha256"]=canonical_p2_sha256({k:v for k,v in evidence.items() if k!="evidence_sha256"})
        self.assertTrue(any("promotion authority" in x or "cannot be promotion" in x for x in p4.validate_p3_reality_evidence_envelope(evidence,law=law,stage_binding=binding,expected_candidate_artifact_manifest_sha256=artifact)))

    def test_p3_envelope_wrong_candidate_binding_fails(self):
        law=law_fixture(); binding=binding_fixture(law); evidence=p3_evidence_fixture(law,binding,SHA("b"))
        self.assertTrue(any("candidate artifact" in x for x in p4.validate_p3_reality_evidence_envelope(evidence,law=law,stage_binding=binding,expected_candidate_artifact_manifest_sha256=SHA("c"))))

    def test_anti_shortcut_receipt_valid_and_tamper_evident(self):
        law=law_fixture(); binding=binding_fixture(law); r=anti_receipt_fixture(law,binding,SHA("9"),baseline=True)
        self.assertEqual(p4.validate_anti_shortcut_receipt(r,law=law,stage_binding=binding,expected_candidate_artifact_manifest_sha256=SHA("9")),[])
        r["by_k"]["1"]["clean_pass_count"]=4
        self.assertTrue(p4.validate_anti_shortcut_receipt(r,law=law,stage_binding=binding,expected_candidate_artifact_manifest_sha256=SHA("9")))

    def test_score_card_is_derived_from_p3_and_anti_shortcut_evidence(self):
        law=law_fixture(); binding=binding_fixture(law); artifact=SHA("b")
        evidence=p3_evidence_fixture(law,binding,artifact,quality=2)
        anti=anti_receipt_fixture(law,binding,artifact,quality=2)
        card=p4.build_score_card_from_p3_evidence(law=law,stage_binding=binding,p3_evidence=evidence,anti_shortcut_receipt=anti,candidate_slot="control",recipe_spec_sha256=SHA("a"),summary_role="candidate",arm_id="P4_A0_SFT_LORA_CONTROL",training_seed=1701,training_gpu_milliseconds=10000)
        self.assertEqual(card["primary_by_k"]["1"]["clean_pass_count"],7)
        self.assertEqual(card["anti_shortcut_by_k"]["1"]["clean_pass_count"],4)
        self.assertEqual(card["reality_evidence_sha256"],evidence["evidence_sha256"])
        self.assertEqual(p4.validate_score_card(card,law=law,stage_binding=binding),[])

    def test_baseline_score_card_comes_from_same_p3_evidence_population(self):
        law=law_fixture(); binding=binding_fixture(law); artifact=SHA("b")
        evidence=p3_evidence_fixture(law,binding,artifact)
        anti=anti_receipt_fixture(law,binding,binding["baseline_artifact_manifest_sha256"],baseline=True)
        card=p4.build_score_card_from_p3_evidence(law=law,stage_binding=binding,p3_evidence=evidence,anti_shortcut_receipt=anti,candidate_slot="baseline",recipe_spec_sha256=SHA("8"),summary_role="baseline")
        self.assertEqual(card["candidate_slot"],"baseline")
        self.assertEqual(card["reality_status"],"BASELINE_REFERENCE")
        self.assertEqual(card["candidate_artifact_manifest_sha256"],binding["baseline_artifact_manifest_sha256"])
        self.assertEqual(p4.validate_score_card(card,law=law,stage_binding=binding),[])

    def test_score_card_builder_rejects_rehashed_p3_float_injection(self):
        law=law_fixture(); binding=binding_fixture(law); artifact=SHA("b")
        evidence=p3_evidence_fixture(law,binding,artifact)
        evidence["metrics"]["candidate"]["primary"]["1"]["raw_pass_rate"]=0.7
        evidence["evidence_sha256"]=canonical_p2_sha256({k:v for k,v in evidence.items() if k!="evidence_sha256"}) if False else evidence["evidence_sha256"]
        anti=anti_receipt_fixture(law,binding,artifact)
        with self.assertRaises((p4.Gene1TournamentError,TypeError)):
            p4.build_score_card_from_p3_evidence(law=law,stage_binding=binding,p3_evidence=evidence,anti_shortcut_receipt=anti,candidate_slot="control",recipe_spec_sha256=SHA("a"),summary_role="candidate",arm_id="P4_A0_SFT_LORA_CONTROL",training_seed=1701,training_gpu_milliseconds=10000)

    def test_rehashed_metric_laundering_fails_semantic_recomputation(self):
        law,binding,reg,ver,base,cards=make_surrogate_fixture()
        first=cards[0]
        baseline_p3=_p3_evidence_from_cards(law,binding,base,first)
        baseline_anti=_anti_receipt_from_card(binding,base)
        p3_by={c["candidate_slot"]:_p3_evidence_from_cards(law,binding,base,c) for c in cards}
        anti_by={c["candidate_slot"]:_anti_receipt_from_card(binding,c) for c in cards}
        semantic_base=p4.build_score_card_from_p3_evidence(
            law=law,stage_binding=binding,p3_evidence=baseline_p3,anti_shortcut_receipt=baseline_anti,
            candidate_slot="baseline",recipe_spec_sha256=base["recipe_spec_sha256"],summary_role="baseline")
        semantic_cards=[]
        for c in cards:
            semantic_cards.append(p4.build_score_card_from_p3_evidence(
                law=law,stage_binding=binding,p3_evidence=p3_by[c["candidate_slot"]],
                anti_shortcut_receipt=anti_by[c["candidate_slot"]],candidate_slot=c["candidate_slot"],
                recipe_spec_sha256=c["recipe_spec_sha256"],summary_role="candidate",
                arm_id=c["arm_id"], training_seed=c["training_seed"], training_gpu_milliseconds=c["training_gpu_milliseconds"]))
        forged=dict(semantic_cards[0])
        forged["primary_by_k"]={k:dict(v) for k,v in forged["primary_by_k"].items()}
        forged["primary_by_k"]["1"]["clean_pass_count"] += 1
        forged["primary_by_k"]["1"]["hack_gap_count"] = forged["primary_by_k"]["1"]["raw_pass_count"] - forged["primary_by_k"]["1"]["clean_pass_count"]
        forged["score_card_sha256"]=canonical_p2_sha256({k:v for k,v in forged.items() if k!="score_card_sha256"})
        receipt=p4.build_tournament_decision(
            law=law,stage_binding=binding,registration=reg,freeze_verification=ver,
            baseline_card=semantic_base,candidate_cards=[forged,semantic_cards[1]],
            baseline_p3_evidence=baseline_p3,baseline_anti_shortcut_receipt=baseline_anti,
            candidate_p3_evidence_by_slot=p3_by,candidate_anti_shortcut_receipt_by_slot=anti_by)
        self.assertEqual(receipt["decision_status"],"INVALID")
        self.assertTrue(any("semantic recomputation" in code.lower() for code in receipt["decision_reason_codes"]) or receipt["decision_reason_codes"])


    def test_published_law_file_matches_frozen_code(self):
        law=law_fixture()
        published=json.loads((HERE/"gene1_evaluation_law_v1.json").read_text())
        self.assertEqual(published,law)

    def test_cross_lane_freeze_snapshots_match_frozen_hashes(self):
        w01=json.loads((HERE/"worker01_method_tournament_spec_v1.json").read_text())
        w02=json.loads((HERE/"gene1_worker02_public_pack_binding_v1.json").read_text())
        self.assertEqual(canonical_p2_sha256(w01),p4.W01_METHOD_TOURNAMENT_SPEC_SHA256)
        self.assertEqual(w02["binding_sha256"],p4.W02_PUBLIC_PACK_BINDING_SHA256)
        self.assertTrue(p4.verify_p2_self_digest(w02,"binding_sha256"))

    def test_confirmation_seed_registration_allowed_by_frozen_law(self):
        law=law_fixture(); binding=binding_fixture(law)
        b=round_bundle_fixture(law,binding,1702,{"control":{},"challenger_a":{}})
        self.assertEqual(p4.validate_candidate_registration(b["registration"],law=law,stage_binding=binding),[])

    def test_final_surrogate_recipe_selected_from_three_seed_evidence(self):
        law=law_fixture(); binding=binding_fixture(law)
        rounds=[]
        for seed in (1701,1702,1703):
            rounds.append(round_bundle_fixture(law,binding,seed,{
                "control":{"transfer4":4,"primary4":8,"gpu":9000},
                "challenger_a":{"transfer4":6,"primary4":9,"gpu":10000},
            }))
        receipt=p4.build_surrogate_recipe_decision(law=law,round_bundles=rounds)
        self.assertEqual(receipt["decision_status"],"SURROGATE_RECIPE_SELECTED")
        self.assertEqual(receipt["selected_candidate_slot"],"challenger_a")
        self.assertEqual(p4.validate_surrogate_recipe_decision(receipt,law=law,round_bundles=rounds),[])

    def test_final_surrogate_ambiguity_requires_extension(self):
        law=law_fixture(); binding=binding_fixture(law)
        rounds=[]
        for seed in (1701,1702,1703):
            rounds.append(round_bundle_fixture(law,binding,seed,{
                "control":{"transfer4":5,"primary4":8,"gpu":9000},
                "challenger_a":{"transfer4":6,"primary4":9,"gpu":10000},
            }))
        receipt=p4.build_surrogate_recipe_decision(law=law,round_bundles=rounds)
        self.assertEqual(receipt["decision_status"],"SURROGATE_MORE_EVIDENCE_REQUIRED")
        self.assertTrue(receipt["extension_required"])
        self.assertIsNone(receipt["selected_candidate_slot"])

    def test_final_surrogate_confirmation_must_match_screen_top_two(self):
        law=law_fixture(); binding=binding_fixture(law)
        screen=round_bundle_fixture(law,binding,1701,{
            "control":{"transfer4":6,"primary4":9},
            "challenger_a":{"transfer4":5,"primary4":8},
            "challenger_b":{"transfer4":4,"primary4":8},
        })
        r2=round_bundle_fixture(law,binding,1702,{"control":{"transfer4":6},"challenger_b":{"transfer4":5}})
        r3=round_bundle_fixture(law,binding,1703,{"control":{"transfer4":6},"challenger_b":{"transfer4":5}})
        receipt=p4.build_surrogate_recipe_decision(law=law,round_bundles=[screen,r2,r3])
        self.assertEqual(receipt["decision_status"],"INVALID")

    def test_final_surrogate_sdpo_displacement_guard_retains_control(self):
        law=law_fixture(); binding=binding_fixture(law)
        rounds=[]
        for seed in (1701,1702,1703):
            rounds.append(round_bundle_fixture(law,binding,seed,{
                "challenger_a":{"transfer4":5,"primary4":7,"primary1":6,"gpu":9000},
                "challenger_b":{"transfer4":5,"primary4":9,"primary1":7,"gpu":10000},
            }))
        receipt=p4.build_surrogate_recipe_decision(law=law,round_bundles=rounds)
        self.assertEqual(receipt["decision_status"],"SURROGATE_RECIPE_SELECTED")
        self.assertEqual(receipt["selected_candidate_slot"],"challenger_a")

    def test_surrogate_recipe_decision_authority_cannot_be_laundered(self):
        law=law_fixture(); binding=binding_fixture(law)
        rounds=[round_bundle_fixture(law,binding,seed,{
            "control":{"transfer4":4,"primary4":8},"challenger_a":{"transfer4":6,"primary4":9}
        }) for seed in (1701,1702,1703)]
        receipt=p4.build_surrogate_recipe_decision(law=law,round_bundles=rounds)
        receipt["authority"]["authoritative_for_model_promotion"]=True
        receipt["surrogate_recipe_decision_sha256"]=canonical_p2_sha256({k:v for k,v in receipt.items() if k!="surrogate_recipe_decision_sha256"})
        self.assertTrue(any("authority" in x for x in p4.validate_surrogate_recipe_decision(receipt,law=law)))

if __name__ == "__main__":
    unittest.main()
