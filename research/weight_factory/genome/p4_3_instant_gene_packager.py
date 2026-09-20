#!/usr/bin/env python3
"""P4.3 Worker-04 instant Gene Package finalizer.

Packaging-only: cannot manufacture Worker-05 or Manager authority.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import p4_gene_package as g

EXPECTED_CAPABILITY={"capability_id":"coding_tool_use","capability_version":1,"scope":"Gene #1"}

def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))

def finalize(*,candidate_manifest,evaluation_receipt,manager_acceptance_record_sha256,
             compute_receipts,artifact_root,output_dir):
    cval,evalval=g._default_p2_validators()
    errors=cval(candidate_manifest)
    if errors: raise ValueError("candidate manifest invalid: "+"; ".join(errors))
    errors=evalval(evaluation_receipt)
    if errors: raise ValueError("evaluation receipt invalid: "+"; ".join(errors))
    if evaluation_receipt.get("final_status")!="PROMOTION_ELIGIBLE":
        raise ValueError("Worker-05 final_status must be PROMOTION_ELIGIBLE")
    errors=g.verify_candidate_artifact_tree(candidate_manifest,artifact_root)
    if errors: raise ValueError("candidate artifact tree invalid: "+"; ".join(errors))
    package=g.seal_gene_package(
        candidate_manifest=candidate_manifest,evaluation_receipt=evaluation_receipt,
        target_capability=EXPECTED_CAPABILITY,
        manager_acceptance_record_sha256=manager_acceptance_record_sha256,
        compute_receipts=compute_receipts,
        training_shard_manifest_sha256=candidate_manifest.get("training_shard_manifest_sha256"),
        training_run_receipt_sha256=candidate_manifest.get("training_run_receipt_sha256"))
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    package_path=out/"gene_package_v1.json"
    package_path.write_text(json.dumps(package,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    loaded=g.load_gene_package(package_path)
    b=loaded["base_identity"]
    runtime=g.RuntimeBaseIdentity(repo=b["repo"],revision=b["revision"],
        base_manifest_sha256=b["base_manifest_sha256"],tokenizer_sha256=b["tokenizer_sha256"],
        config_sha256=b["config_sha256"],
        parameter_layout_sha256=loaded["compatibility"]["parameter_layout_sha256"],
        topology_class=loaded["compatibility"]["topology_class"])
    activation=g.prepare_single_gene_activation(loaded,runtime,artifact_root=artifact_root,candidate_manifest=candidate_manifest)
    activation_path=out/"single_gene_activation_request.json"
    activation_path.write_text(json.dumps(activation,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"gene_package_path":str(package_path),"package_sha256":loaded["package_sha256"],
            "activation_request_path":str(activation_path),"activation_request_sha256":activation["request_sha256"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--candidate",required=True); ap.add_argument("--evaluation",required=True)
    ap.add_argument("--manager-acceptance-sha256",required=True)
    ap.add_argument("--compute-receipt",action="append",required=True)
    ap.add_argument("--artifact-root",required=True); ap.add_argument("--output-dir",required=True)
    a=ap.parse_args()
    print(json.dumps(finalize(candidate_manifest=load(a.candidate),evaluation_receipt=load(a.evaluation),
        manager_acceptance_record_sha256=a.manager_acceptance_sha256,
        compute_receipts=[load(x) for x in a.compute_receipt],artifact_root=a.artifact_root,output_dir=a.output_dir),sort_keys=True))
if __name__=="__main__": main()
