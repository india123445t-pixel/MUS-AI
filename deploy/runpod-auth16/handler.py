#!/usr/bin/env python3
import os, json, hashlib, time
import torch
import runpod
from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
from peft import PeftModel

BASE_DIR="/opt/aqlevon/base"
ADAPTER_DIR="/opt/aqlevon/adapter"
MODEL_NAME=os.getenv("AQLEVON_MODEL_NAME","AQLEVON-4B-Auth16")
EXPECTED_ADAPTER_SHA="2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a"

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

got=sha256(os.path.join(ADAPTER_DIR,"adapter_model.safetensors"))
if got!=EXPECTED_ADAPTER_SHA:
    raise RuntimeError(f"adapter_sha_mismatch:{got}")

print("AQLEVON_AUTH16_LOADING", flush=True)
tok=AutoTokenizer.from_pretrained(BASE_DIR,local_files_only=True,trust_remote_code=False)
base=Qwen3_5ForConditionalGeneration.from_pretrained(
    BASE_DIR,dtype=torch.bfloat16,device_map={"":0},
    low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
model=PeftModel.from_pretrained(base,ADAPTER_DIR,is_trainable=False)
model.eval(); model.config.use_cache=True
print("AQLEVON_AUTH16_READY",json.dumps({"model":MODEL_NAME,"adapter_sha256":got}),flush=True)

def handler(job):
    inp=(job or {}).get("input") or {}
    messages=inp.get("messages")
    if not isinstance(messages,list) or not messages:
        return {"error":"messages_required"}
    clean=[]; total=0
    for m in messages[-24:]:
        role=str((m or {}).get("role","user"))
        if role not in {"system","user","assistant"}: role="user"
        content=str((m or {}).get("content",""))
        total+=len(content)
        clean.append({"role":role,"content":content})
    if total>32000:
        return {"error":"prompt_too_long"}
    max_tokens=max(1,min(int(inp.get("max_tokens",512)),1024))
    temperature=max(0.0,min(float(inp.get("temperature",0.4)),1.2))
    top_p=max(0.05,min(float(inp.get("top_p",0.8)),1.0))
    top_k=max(1,min(int(inp.get("top_k",20)),100))
    prompt=tok.apply_chat_template(clean,tokenize=False,add_generation_prompt=True,enable_thinking=False)
    enc=tok(prompt,return_tensors="pt",add_special_tokens=False).to("cuda")
    kw={"max_new_tokens":max_tokens,"use_cache":True,"pad_token_id":tok.eos_token_id}
    if temperature>0:
        kw.update(do_sample=True,temperature=temperature,top_p=top_p,top_k=top_k)
    else:
        kw.update(do_sample=False)
    started=time.time()
    with torch.inference_mode():
        out=model.generate(**enc,**kw)[0]
    text=tok.decode(out[enc["input_ids"].shape[1]:],skip_special_tokens=True).strip()
    return {
        "id":"aqlevon-auth16",
        "object":"chat.completion",
        "model":MODEL_NAME,
        "adapter_sha256":got,
        "latency_ms":round((time.time()-started)*1000),
        "choices":[{"index":0,"message":{"role":"assistant","content":text},"finish_reason":"stop"}]
    }

runpod.serverless.start({"handler":handler})
