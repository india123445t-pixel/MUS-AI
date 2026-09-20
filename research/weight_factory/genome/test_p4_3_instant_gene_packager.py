#!/usr/bin/env python3
import hashlib,json,tempfile,unittest
from pathlib import Path
import p4_gene_package as g
import p4_3_instant_gene_packager as f
from test_p2_merge_receipt_gate import seal_candidate,seal_eval
from test_p4_1_gene_package_preflight import runtime_receipt

def h(x): return hashlib.sha256(x.encode()).hexdigest()

class InstantPackager(unittest.TestCase):
    def fixture(self,label="p43"):
        data=b"dummy-adapter"
        files=[{"path":"adapter_model.safetensors","size":len(data),"sha256":hashlib.sha256(data).hexdigest()}]
        c=seal_candidate(label,artifact_stage="promotion_candidate")
        c["artifact_files"]=files
        c["artifact_file_tree_sha256"]=h("tree:"+label)
        c["manifest_sha256"]=g.canonical_sha256({k:v for k,v in c.items() if k!="manifest_sha256"})
        e=seal_eval(c,"eval:"+label)
        r=runtime_receipt(c,"runtime:"+label)
        return data,c,e,r
    def test_one_function_finalizes_dummy_artifact(self):
        data,c,e,r=self.fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td,"artifact"); root.mkdir(); (root/"adapter_model.safetensors").write_bytes(data)
            result=f.finalize(candidate_manifest=c,evaluation_receipt=e,manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[r],artifact_root=root,output_dir=Path(td,"package"))
            self.assertTrue(Path(result["gene_package_path"]).is_file())
            self.assertTrue(Path(result["activation_request_path"]).is_file())
    def test_wrong_base_revision_rejected_by_activation_contract(self):
        data,c,e,r=self.fixture("wrongbase"); c["base"]["revision"]="wrong"
        c["manifest_sha256"]=g.canonical_sha256({k:v for k,v in c.items() if k!="manifest_sha256"})
        e=seal_eval(c,"eval:wrongbase"); r=runtime_receipt(c,"runtime:wrongbase")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td,"artifact"); root.mkdir(); (root/"adapter_model.safetensors").write_bytes(data)
            # A self-consistent foreign base is packageable only if upstream candidate semantics allowed it;
            # activation remains bound to that exact base. The existing suite tests runtime mismatch fail-closed.
            result=f.finalize(candidate_manifest=c,evaluation_receipt=e,manager_acceptance_record_sha256=h("manager"),
                compute_receipts=[r],artifact_root=root,output_dir=Path(td,"package"))
            p=g.load_gene_package(result["gene_package_path"])
            runtime=g.RuntimeBaseIdentity(repo=p["base_identity"]["repo"],revision="another",
              base_manifest_sha256=p["base_identity"]["base_manifest_sha256"],tokenizer_sha256=p["base_identity"]["tokenizer_sha256"],
              config_sha256=p["base_identity"]["config_sha256"],parameter_layout_sha256=p["compatibility"]["parameter_layout_sha256"],
              topology_class=p["compatibility"]["topology_class"])
            with self.assertRaisesRegex(ValueError,"revision"): g.prepare_single_gene_activation(p,runtime)
    def test_rejected_w05_never_packages(self):
        data,c,_,r=self.fixture("reject"); e=seal_eval(c,"eval:reject",status="REJECTED")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td,"artifact"); root.mkdir(); (root/"adapter_model.safetensors").write_bytes(data)
            with self.assertRaisesRegex(ValueError,"PROMOTION_ELIGIBLE"):
                f.finalize(candidate_manifest=c,evaluation_receipt=e,manager_acceptance_record_sha256=h("manager"),
                    compute_receipts=[r],artifact_root=root,output_dir=Path(td,"package"))
    def test_wrong_artifact_bytes_rejected(self):
        _,c,e,r=self.fixture("bytes")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td,"artifact"); root.mkdir(); (root/"adapter_model.safetensors").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"artifact tree invalid"):
                f.finalize(candidate_manifest=c,evaluation_receipt=e,manager_acceptance_record_sha256=h("manager"),
                    compute_receipts=[r],artifact_root=root,output_dir=Path(td,"package"))
if __name__=="__main__": unittest.main()
