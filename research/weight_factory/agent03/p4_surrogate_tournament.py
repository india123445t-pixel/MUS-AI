#!/usr/bin/env python3
"""Prepare and execute the frozen P4 surrogate tournament without sealed eval.

A1/A2 use the pinned SDPO/veRL code semantics; A0 uses Worker03's SFT runner.
Paid execution itself remains externally Manager-authorized.
"""
from __future__ import annotations
import argparse, importlib.metadata as md, json, subprocess, sys
from pathlib import Path
from typing import Any
import p4_gene1_trainer as c

W01_STACK={"transformers":"5.17.0","peft":"0.21.0","accelerate":"1.15.0"}
TARGET_REGEX=r".*\.self_attn\.(q_proj|v_proj)$"

def sha(p:Path)->str: return c.sha256_file(p)

def _arm(plan:dict[str,Any],arm_id:str)->dict[str,Any]:
    m=[x for x in plan["arms"] if x.get("arm_id")==arm_id]
    if len(m)!=1: raise c.ContractError("arm_missing_or_duplicate")
    return m[0]

def _check_plan(plan:dict[str,Any]):
    if not c.verify_self_digest(plan,"plan_sha256") or plan.get("plan_kind")!=c.FROZEN_PLAN_KIND: raise c.ContractError("invalid_frozen_plan")
    if plan.get("g1_status")!=c.G1_STATUS or plan.get("sealed_eval_consumed") is not False: raise c.ContractError("truth_boundary_violation")

def build_training_json(shard_path:Path,pack_path:Path,out_dir:Path)->dict[str,str]:
    rows=[json.loads(x) for x in shard_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    pack=json.loads(pack_path.read_text(encoding="utf-8")); hard={t["prompt"]:t for t in pack["tasks"] if t.get("verifier_mode")=="hardened" and t.get("training_eligible") is True}
    data=[]
    for i,row in enumerate(rows):
        t=hard.get(row["prompt"])
        if not t: raise c.ContractError(f"training_row_not_bound_to_hardened_task:{i}")
        if row["answer"]!=t.get("oracle_program"): raise c.ContractError(f"sft_oracle_binding_mismatch:{i}")
        ground={"initial_state":t["visible_initial_state"],"oracle_program":row["answer"]}
        data.append({"prompt":row["prompt"],"answer":json.dumps(ground,ensure_ascii=False,sort_keys=True,separators=(",",":")),"idx":row["record_id"],"tests":[],"description":"AQLEVON Gene1 objective DSL state transition","kind":"aqlevon_gene1","dataset":"aqlevon_gene1","elo":0})
    out_dir.mkdir(parents=True,exist_ok=True)
    for name in ("train.json","test.json"):
        (out_dir/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"rows":str(len(data)),"train_json_sha256":sha(out_dir/"train.json"),"test_json_sha256":sha(out_dir/"test.json")}

def _base_rl_args(plan:dict[str,Any],data_dir:Path,model_dir:Path,out_dir:Path,reward_path:Path)->list[str]:
    g=plan["generation"]
    return [
      f"data.train_files={data_dir/'train.parquet'}",f"data.val_files={data_dir/'test.parquet'}","data.train_batch_size=4","data.max_prompt_length=2048","data.max_response_length=2048","data.filter_overlong_prompts=True","data.truncation=error",
      f"actor_rollout_ref.model.path={model_dir}","actor_rollout_ref.model.lora_rank=4","actor_rollout_ref.model.lora_alpha=4",f"actor_rollout_ref.model.target_modules={TARGET_REGEX}","actor_rollout_ref.model.exclude_modules=.*(visual|vision|lm_head|embed|mtp|norm).*",
      "actor_rollout_ref.actor.optim.lr=1e-5","actor_rollout_ref.actor.optim.lr_warmup_steps=10","actor_rollout_ref.actor.ppo_mini_batch_size=8",
      "actor_rollout_ref.rollout.n=4",f"actor_rollout_ref.rollout.temperature={g['temperature']}",f"actor_rollout_ref.rollout.top_p={g['top_p']}",f"actor_rollout_ref.rollout.top_k={g['top_k']}","actor_rollout_ref.rollout.calculate_log_probs=True",
      "algorithm.rollout_correction.rollout_is=token",f"custom_reward_function.path={reward_path}","custom_reward_function.name=compute_score",
      "trainer.total_training_steps=12","trainer.save_freq=12","trainer.test_freq=-1","trainer.val_before_train=False","trainer.logger=console",f"trainer.default_local_dir={out_dir/'checkpoints'}","trainer.max_actor_ckpt_to_keep=1",
    ]

def build_a1_argv(plan_path:Path,workspace:Path)->list[str]:
    plan=json.loads(plan_path.read_text()); _check_plan(plan); arm=_arm(plan,"P4_A1_RLVR_CONTROL")
    if arm.get("rollout_group_size")!=4 or arm.get("ppo_mini_batch_size")!=8 or arm.get("lr")!="0.00001": raise c.ContractError("A1_contract_mismatch")
    repo=workspace/"SDPO"; data=workspace/"aqlevon_p4/data"; model=workspace/("models/qwen35-4b-"+c.SURROGATE_REVISION[:12]); out=workspace/"aqlevon_p4/runs/P4_A1_RLVR_CONTROL_seed1701"; reward=workspace/"MUS-AI/research/weight_factory/agent03/p4_aqlevon_reward.py"
    return ["bash",str(repo/"training/verl_training.sh"),"AQLEVON-P4-A1-seed1701","baseline_grpo",str(data)]+_base_rl_args(plan,data,model,out,reward)

def build_a2_argv(plan_path:Path,workspace:Path)->list[str]:
    plan=json.loads(plan_path.read_text()); _check_plan(plan); arm=_arm(plan,"P4_A2_SDPO_RICH_FEEDBACK")
    if arm.get("rollout_group_size")!=4 or arm.get("self_distillation_alpha")!="0.5" or arm.get("distillation_topk")!=100: raise c.ContractError("A2_contract_mismatch")
    repo=workspace/"SDPO"; data=workspace/"aqlevon_p4/data"; model=workspace/("models/qwen35-4b-"+c.SURROGATE_REVISION[:12]); out=workspace/"aqlevon_p4/runs/P4_A2_SDPO_RICH_FEEDBACK_seed1701"; reward=workspace/"MUS-AI/research/weight_factory/agent03/p4_aqlevon_reward.py"
    args=_base_rl_args(plan,data,model,out,reward)+["actor_rollout_ref.actor.ppo_mini_batch_size=8","actor_rollout_ref.actor.self_distillation.distillation_topk=100","actor_rollout_ref.actor.self_distillation.dont_reprompt_on_self_success=True","actor_rollout_ref.actor.self_distillation.alpha=0.5","actor_rollout_ref.actor.self_distillation.include_environment_feedback=True","actor_rollout_ref.actor.self_distillation.environment_feedback_only_without_solution=True"]
    return ["bash",str(repo/"training/verl_training.sh"),"AQLEVON-P4-A2-seed1701","sdpo",str(data)]+args

def build_a0_argv(plan_path:Path,workspace:Path)->list[str]:
    return [sys.executable,str(workspace/"MUS-AI/research/weight_factory/agent03/p4_sft_surrogate.py"),"--training-plan",str(plan_path),"--training-shard-manifest",str(workspace/"aqlevon_p4/inputs/gene1_training_shard_manifest_v1.json"),"--training-shard",str(workspace/"aqlevon_p4/inputs/gene1_training_shard_v1.jsonl"),"--arm-id","P4_A0_SFT_LORA_CONTROL","--seed","1701","--output-dir",str(workspace/"aqlevon_p4/runs/P4_A0_SFT_LORA_CONTROL_seed1701")]

def check_runtime(sdpo_root:Path)->dict[str,Any]:
    cp=subprocess.run(["git","-C",str(sdpo_root),"rev-parse","HEAD"],capture_output=True,text=True)
    if cp.returncode or cp.stdout.strip()!=c.SDPO_COMMIT: raise c.ContractError("sdpo_commit_mismatch")
    got={k:md.version(k) for k in W01_STACK}; bad={k:(got[k],v) for k,v in W01_STACK.items() if got[k]!=v}
    if bad: raise c.ContractError("w01_stack_version_mismatch:"+json.dumps(bad,sort_keys=True))
    return {"sdpo_commit":c.SDPO_COMMIT,"packages":got}

def main()->int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("prepare-data"); p.add_argument("--training-shard",type=Path,required=True); p.add_argument("--training-pack",type=Path,required=True); p.add_argument("--output-dir",type=Path,required=True)
    q=sub.add_parser("print-command"); q.add_argument("--training-plan",type=Path,required=True); q.add_argument("--arm-id",choices=list(c.ARMS),required=True); q.add_argument("--workspace",type=Path,default=Path("/workspace"))
    r=sub.add_parser("check-runtime"); r.add_argument("--sdpo-root",type=Path,required=True)
    a=ap.parse_args()
    try:
        if a.cmd=="prepare-data": out=build_training_json(a.training_shard,a.training_pack,a.output_dir)
        elif a.cmd=="check-runtime": out=check_runtime(a.sdpo_root)
        else:
            fn={"P4_A1_RLVR_CONTROL":build_a1_argv,"P4_A0_SFT_LORA_CONTROL":build_a0_argv,"P4_A2_SDPO_RICH_FEEDBACK":build_a2_argv}[a.arm_id]; argv=fn(a.training_plan,a.workspace); out={"arm_id":a.arm_id,"profile":c.PROFILE,"argv":argv,"command_sha256":c.canonical_sha256(argv),"g1_rerun":False}
        print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)); return 0
    except Exception as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":f"{type(exc).__name__}: {exc}"}),file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
