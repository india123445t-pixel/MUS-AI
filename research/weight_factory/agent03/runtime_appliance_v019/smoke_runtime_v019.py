#!/usr/bin/env python3
import argparse
import importlib
import inspect
import json
import subprocess
import shutil
import sys
from dataclasses import fields

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
    from vllm.engine.arg_utils import EngineArgs
    engine_fields={f.name for f in fields(EngineArgs)}
    assert "language_model_only" in engine_fields
    assert "lora_target_modules" in engine_fields
    q=importlib.import_module("vllm.model_executor.models.qwen3_5")
    assert hasattr(q,"Qwen3_5ForConditionalGeneration")
    assert hasattr(q,"Qwen3_5ForCausalLM")
    packed=q.Qwen3_5ForCausalLMBase.packed_modules_mapping
    assert packed.get("qkv_proj")==["q_proj","k_proj","v_proj"], packed.get("qkv_proj")

    # Pinned SDPO commit must import against this vLLM generation.
    import verl
    import verl.workers.fsdp_workers
    import verl.workers.rollout.vllm_rollout.vllm_rollout
    import verl.workers.rollout.vllm_rollout.vllm_async_server
    from vllm.lora.lora_model import LoRAModel
    from vllm.lora.worker_manager import LRUCacheWorkerLoRAManager
    from verl.utils.vllm import TensorLoRARequest, VLLMHijack
    tensor_loader_params=set(inspect.signature(LoRAModel.from_lora_tensors).parameters)
    required_tensor_loader={"lora_model_id","tensors","peft_helper","device","dtype","model_vocab_size","weights_mapper"}
    assert required_tensor_loader.issubset(tensor_loader_params), sorted(required_tensor_loader-tensor_loader_params)
    assert hasattr(LRUCacheWorkerLoRAManager,"_load_adapter")
    VLLMHijack.hijack()
    patched_loader=LRUCacheWorkerLoRAManager._load_adapter
    assert patched_loader.__name__=="hijack__load_adapter", patched_loader.__name__
    assert issubclass(TensorLoRARequest, __import__("vllm.lora.request",fromlist=["LoRARequest"]).LoRARequest)
    from verl.utils.groupwise import as_torch_index, group_mean_std
    idx=as_torch_index(np.array([10.0,10.0,20.0,20.0],dtype=np.float64),device="cpu")
    mean,std,count=group_mean_std(torch.tensor([1.0,3.0,2.0,4.0]),idx,device="cpu")
    assert idx.tolist()==[10,10,20,20] or idx.tolist()==[0,0,1,1]
    assert count.numel()>=2

    assert shutil.which("python"), "python_launcher_missing"
    subprocess.run(["python","-c","import sys; assert sys.version_info[:2] == (3, 12); print('AQLEVON_PYTHON_LAUNCHER_PASS', sys.executable)"],check=True)
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
      "qwen35_packed_qkv_lora":"pass",
      "vllm_language_model_only_arg":"pass",
      "vllm_lora_target_modules_arg":"pass",
      "sdpo_imports":"pass",
      "sdpo_tensor_lora_v019_contract":"pass",
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
