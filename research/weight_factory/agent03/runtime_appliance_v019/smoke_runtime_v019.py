#!/usr/bin/env python3
import argparse
import asyncio
import cloudpickle
import importlib
import inspect
import json
import os
import subprocess
import shutil
import sys
import threading
import time
import types
from dataclasses import dataclass, fields


def _real_zmq_control_path_check(torch):
    """Exercise pinned SDPO's real ZMQ serialization/dispatch path without GPU."""
    import zmq
    import zmq.asyncio
    from verl.workers.rollout.vllm_rollout.vllm_async_server import ExternalZeroMQDistributedExecutor
    from verl.workers.rollout.vllm_rollout.vllm_rollout import vLLMAsyncRollout

    class _FakeModel:
        def compute_logits(self, *args, **kwargs):
            return torch.zeros((1, 1, 8), dtype=torch.float32)

    class _FakeWorker:
        def __init__(self):
            self.model_runner=types.SimpleNamespace(model=_FakeModel())
            self.events=[]
        def remove_lora(self, lora_id):
            self.events.append(("remove_lora", lora_id))
            return False
        def add_lora(self, request):
            self.events.append(("add_lora", request))
            return True

    class _FakeInferenceEngine:
        def __init__(self):
            self.worker=_FakeWorker()
            self.events=[]
        def ping(self, x):
            return x + 1
        def init_device(self):
            self.events.append(("init_device",))
            return "init_device_ok"
        def determine_available_memory(self):
            self.events.append(("determine_available_memory",))
            return 123456789
        def get_kv_cache_spec(self):
            self.events.append(("get_kv_cache_spec",))
            return {"fake":"kv"}
        def initialize_from_config(self, configs):
            self.events.append(("initialize_from_config", configs))
            return None
        def compile_or_warm_up_model(self):
            self.events.append(("compile_or_warm_up_model",))
            return 0.125
        def load_model(self, *args, **kwargs):
            self.events.append(("load_model", args, kwargs))
            return None
        def sleep(self, level=2):
            self.events.append(("sleep", level))
            return None
        def wake_up(self, tags=None):
            self.events.append(("wake_up", tuple(tags or ())))
            return None
        def reset_mm_cache(self):
            self.events.append(("reset_mm_cache",))
            return None
        def execute_model(self, scheduler_output):
            self.events.append(("execute_model", scheduler_output))
            return {"fake":"model_runner_output"}
        def sample_tokens(self, grammar_output):
            self.events.append(("sample_tokens", grammar_output))
            return {"fake":"sample_output"}
        def list_loras(self):
            self.events.append(("list_loras",))
            return {1}

    probe=object.__new__(vLLMAsyncRollout)
    probe.inference_engine=_FakeInferenceEngine()
    probe.tokenizer=list(range(8))

    endpoint=f"ipc:///tmp/aqlevon_v019_zmq_{os.getpid()}.ipc"
    ready=threading.Event()
    state={}

    def _server():
        loop=asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        context=zmq.asyncio.Context()
        sock=context.socket(zmq.REP)
        sock.bind(endpoint)
        probe.socket=sock
        state["loop"]=loop
        state["context"]=context
        state["socket"]=sock
        ready.set()
        task=loop.create_task(probe._loop_forever())
        state["task"]=task
        try:
            loop.run_forever()
        finally:
            task.cancel()
            try:
                loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
            except Exception:
                pass
            sock.close(0)
            context.term()
            loop.close()

    thread=threading.Thread(target=_server, daemon=True)
    thread.start()
    assert ready.wait(5), "zmq_server_not_ready"

    context=zmq.Context()
    req=context.socket(zmq.REQ)
    req.setsockopt(zmq.RCVTIMEO, 5000)
    req.setsockopt(zmq.SNDTIMEO, 5000)
    req.connect(endpoint)
    rpc_self=types.SimpleNamespace(sockets=[req])

    def rpc(method, *args, **kwargs):
        return ExternalZeroMQDistributedExecutor.collective_rpc(
            rpc_self, method, args=args, kwargs=kwargs
        )[0]

    try:
        assert rpc("init_device") == "init_device_ok"
        assert rpc("determine_available_memory") == 123456789
        assert rpc("get_kv_cache_spec") == {"fake":"kv"}
        assert rpc("initialize_from_config", [{"fake":"config"}]) is None
        assert rpc("compile_or_warm_up_model") == 0.125
        assert rpc("load_model") is None
        assert rpc("reset_mm_cache") is None
        assert rpc("execute_model", {"fake":"scheduler"}) == {"fake":"model_runner_output"}
        assert rpc("sample_tokens", {"fake":"grammar"}) == {"fake":"sample_output"}
        assert rpc("list_loras") == {1}
        assert rpc("sleep", level=2) is None
        assert rpc("wake_up", tags=["weights","kv_cache"]) is None
        assert rpc("ping", 41) == 42

        def _callable_probe(worker, x):
            return worker.ping(x)
        assert rpc(_callable_probe, 41) == 42
    finally:
        req.close(0)
        context.term()
        loop=state.get("loop")
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)

    # Exercise SDPO's actual direct sleep/wake and tensor-LoRA replacement path.
    probe.config=types.SimpleNamespace(free_cache_engine=True)
    probe.sleep_level=2
    asyncio.run(probe.release())
    asyncio.run(probe.resume(["weights","kv_cache"]))

    @dataclass
    class _PeftProbe:
        r: int = 4
        lora_alpha: int = 4
        target_modules: tuple = ("q_proj","v_proj")

    first_weights=iter([("model.layers.3.self_attn.q_proj.lora_A.default.weight", torch.ones(1))])
    second_weights=iter([("model.layers.3.self_attn.q_proj.lora_A.default.weight", torch.full((1,),2.0))])
    asyncio.run(probe.update_weights(first_weights, peft_config=_PeftProbe(), base_sync_done=True))
    asyncio.run(probe.update_weights(second_weights, peft_config=_PeftProbe(), base_sync_done=True))
    worker_events=[e[0] for e in probe.inference_engine.worker.events]
    assert worker_events==["remove_lora","add_lora","remove_lora","add_lora"], worker_events

    names=[e[0] for e in probe.inference_engine.events]
    required=[
        "init_device","determine_available_memory","get_kv_cache_spec",
        "initialize_from_config","compile_or_warm_up_model","load_model",
        "reset_mm_cache","execute_model","sample_tokens","list_loras","sleep","wake_up",
    ]
    for name in required:
        assert name in names, (name,names)
    print("AQLEVON_V019_REAL_ZMQ_CONTROL_PATH_PASS")
    return True


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
    import verl.workers.rollout.vllm_rollout.vllm_async_server as vllm_async_server
    async_src=inspect.getsource(vllm_async_server.vLLMHttpServer.__init__)
    assert "AQLEVON_VLLM019_PRESERVE_MAX_MODEL_LEN" in async_src
    assert "if self.config.max_model_len is None:" in async_src
    assert "self.config.max_model_len = get_max_position_embeddings(self.model_config.hf_config)" not in async_src
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

    # Gate exact vLLM 0.19.1 APIs used after init_device by pinned SDPO.
    from vllm.v1.worker.gpu_worker import Worker as GPUWorker
    load_params=inspect.signature(GPUWorker.load_model).parameters
    assert "load_dummy_weights" in load_params
    assert load_params["load_dummy_weights"].default is False
    for name in ("determine_available_memory","get_kv_cache_spec","initialize_from_config","compile_or_warm_up_model","load_model"):
        assert hasattr(WorkerWrapperBase, name), name
    from vllm.v1.engine.async_llm import AsyncLLM
    generate_params=inspect.signature(AsyncLLM.generate).parameters
    for name in ("prompt","sampling_params","request_id","lora_request","priority"):
        assert name in generate_params, (name,generate_params)
    from vllm.entrypoints.openai.api_server import build_app, init_app_state
    assert "args" in inspect.signature(build_app).parameters
    init_app_params=inspect.signature(init_app_state).parameters
    for name in ("engine_client","state","args"):
        assert name in init_app_params, (name,init_app_params)
    # vLLM 0.19 removed WorkerWrapperBase.execute_method. Verify AQLEVON's
    # SDPO bridge dispatches strings and serialized callables through the same
    # vllm.v1.serial_utils.run_method primitive used by UniProcExecutor.
    from vllm.v1.worker.worker_base import WorkerWrapperBase
    from verl.workers.rollout.vllm_rollout.vllm_rollout import vLLMAsyncRollout
    assert not hasattr(WorkerWrapperBase, "execute_method")
    class _DispatchProbe:
        def ping(self, x):
            return x + 1
    probe=object.__new__(vLLMAsyncRollout)
    probe.inference_engine=_DispatchProbe()
    assert asyncio.run(probe._execute_method("ping", 41)) == 42
    def _callable_probe(worker, x):
        return worker.ping(x)
    payload=cloudpickle.dumps(_callable_probe)
    assert asyncio.run(probe._execute_method(payload, 41)) == 42

    assert _real_zmq_control_path_check(torch) is True

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
      "sdpo_vllm019_worker_dispatch":"pass",
      "sdpo_preserves_explicit_max_model_len":"pass",
      "sdpo_real_zmq_control_path":"pass",
      "vllm019_post_init_api_signatures":"pass",
      "sdpo_tensor_lora_replace_path":"pass",
      "sdpo_sleep_wake_path":"pass",
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
