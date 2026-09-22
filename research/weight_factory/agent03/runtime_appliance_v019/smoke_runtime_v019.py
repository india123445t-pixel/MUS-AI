#!/usr/bin/env python3
import argparse
import importlib
import json
import subprocess

def build_check():
    import torch, vllm, ray, transformers, peft, accelerate, flash_attn, numpy as np
    assert vllm.__version__.split("+")[0] == "0.19.1", vllm.__version__
    assert transformers.__version__ == "5.17.0", transformers.__version__
    assert peft.__version__ == "0.21.0", peft.__version__
    assert accelerate.__version__ == "1.15.0", accelerate.__version__
    assert ray.__version__ == "2.53.0", ray.__version__
    assert flash_attn.__version__.split("+")[0] == "2.8.3", flash_attn.__version__
    assert np.__version__ == "2.2.6", np.__version__

    # Native Qwen3.5 implementation must exist; generic Transformers backend is forbidden.
    q=importlib.import_module("vllm.model_executor.models.qwen3_5")
    assert hasattr(q,"Qwen3_5ForConditionalGeneration")
    assert hasattr(q,"Qwen3_5ForCausalLM")

    # Pinned SDPO commit must import against this vLLM generation.
    import verl
    import verl.workers.fsdp_workers
    import verl.workers.rollout.vllm_rollout.vllm_rollout
    import verl.workers.rollout.vllm_rollout.vllm_async_server
    from verl.utils.groupwise import as_torch_index, group_mean_std
    idx=as_torch_index(np.array([10.0,10.0,20.0,20.0],dtype=np.float64),device="cpu")
    mean,std,count=group_mean_std(torch.tensor([1.0,3.0,2.0,4.0]),idx,device="cpu")
    assert idx.tolist()==[10,10,20,20] or idx.tolist()==[0,0,1,1]
    assert count.numel()>=2

    subprocess.run(["python3","-m","pip","check"],check=True)
    return {
      "torch":torch.__version__,
      "cuda":torch.version.cuda,
      "vllm":vllm.__version__,
      "ray":ray.__version__,
      "transformers":transformers.__version__,
      "peft":peft.__version__,
      "accelerate":accelerate.__version__,
      "flash_attn":flash_attn.__version__,
      "numpy":np.__version__,
      "sdpo_numpy2_runtime":"pass",
      "qwen35_backend":"native",
      "sdpo_imports":"pass",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--build-check",action="store_true")
    a=p.parse_args()
    assert a.build_check
    result=build_check()
    print("AQLEVON_V019_NATIVE_QWEN35_BUILD_CHECK_PASS")
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
