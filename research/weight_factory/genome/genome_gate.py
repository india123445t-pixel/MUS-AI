#!/usr/bin/env python3
"""Fail-closed admission checks for AQLEVON Capability Genome metadata."""
from __future__ import annotations
import json
from pathlib import Path

ALLOW_ADMISSIONS = {"allow", "allow_local_open_weight", "allow_with_conditions"}
DENY_ADMISSIONS = {"deny_training_harvest", "research_only_for_current_commercial_plan", "default_quarantine", "quarantine_until_license_and_contamination_audit", "quarantine_until_source_license_and_benchmark_audit", "quarantine_hosted_generation_terms"}
REQUIRED_PROMOTION = {"artifact_hash","exact_lineage","license_pass","provenance_pass","contamination_pass","target_gain","global_regression_pass","reload_pass"}


def load_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def source_training_allowed(entry: dict) -> bool:
    admission = entry.get("admission")
    return admission in ALLOW_ADMISSIONS and admission not in DENY_ADMISSIONS


def validate_registry(reg: dict) -> list[str]:
    errors=[]
    if reg.get("policy") != "default_deny": errors.append("registry must be default_deny")
    seen=set()
    for src in reg.get("sources",[]):
        sid=src.get("id")
        if not sid or sid in seen: errors.append(f"invalid/duplicate source id: {sid}")
        seen.add(sid)
        if not src.get("license"): errors.append(f"source {sid} missing license")
        if not src.get("admission"): errors.append(f"source {sid} missing admission")
    return errors


def validate_genome(genome: dict) -> list[str]:
    errors=[]
    base=genome.get("base",{})
    if base.get("repo") != "Qwen/Qwen3.8-27B": errors.append("unexpected canonical base")
    if not base.get("revision"): errors.append("base revision must be pinned")
    forbidden=set(genome.get("default_forbidden_scopes",[]))
    if not {"model.visual","lm_head","embed_tokens","mtp"}.issubset(forbidden): errors.append("required forbidden scopes missing")
    if set(genome.get("promotion_requirements",[])) != REQUIRED_PROMOTION: errors.append("promotion requirements changed")
    ids=[g.get("id") for g in genome.get("genes",[])]
    if len(ids)!=len(set(ids)): errors.append("duplicate gene ids")
    for g in genome.get("genes",[]):
        if not g.get("verifiers"): errors.append(f"gene {g.get('id')} has no verifier")
    return errors


def can_promote_gene(metadata: dict) -> tuple[bool,list[str]]:
    missing=[]
    for key in REQUIRED_PROMOTION:
        val=metadata.get(key)
        if val not in (True,) and not (key in {"artifact_hash","exact_lineage"} and isinstance(val,str) and val.strip()):
            missing.append(key)
    return (not missing, sorted(missing))


def main():
    root=Path(__file__).resolve().parent
    reg=load_json(root/"source_registry_v2.json")
    genome=load_json(root/"genome_manifest_v1.json")
    errs=validate_registry(reg)+validate_genome(genome)
    if errs:
        raise SystemExit("GENOME_GATE_FAIL\n"+"\n".join(errs))
    print(f"GENOME_GATE_PASS sources={len(reg['sources'])} genes={len(genome['genes'])}")

if __name__ == "__main__":
    main()