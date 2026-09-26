#!/usr/bin/env python3
import json, os, threading, time
import runpod
import torch
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
from peft import PeftModel

MODEL_REPO="Qwen/Qwen3.5-4B-Base"
MODEL_REV="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
MODEL_DIR=os.environ.get("AQLEVON_BASE_DIR","/models/qwen35-4b")
ADAPTER_DIR="/app/adapter"
MODEL_NAME="AQLEVON-4B-Auth16"
LOCK=threading.Lock()

def load_runtime():
    snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REV,
        local_dir=MODEL_DIR,
    )
    tok=AutoTokenizer.from_pretrained(
        MODEL_DIR, local_files_only=True, trust_remote_code=False
    )
    base=Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_DIR,
        dtype=torch.bfloat16,
        device_map={"":0},
        low_cpu_mem_usage=True,
        local_files_only=True,
        trust_remote_code=False,
    )
    model=PeftModel.from_pretrained(base,ADAPTER_DIR,is_trainable=False)
    model.eval()
    model.config.use_cache=True
    return tok,model

TOKENIZER,MODEL=load_runtime()

def normalize_messages(items):
    clean=[]
    for m in (items or [])[-24:]:
        if not isinstance(m,dict):
            continue
        role=str(m.get("role","user"))
        if role not in {"system","user","assistant"}:
            role="user"
        content=str(m.get("content",""))
        clean.append({"role":role,"content":content})
    if not clean:
        raise ValueError("messages_required")
    return clean

def handler(job):
    req=job.get("input") or {}
    messages=normalize_messages(req.get("messages"))
    temperature=float(req.get("temperature",0.25))
    temperature=max(0.0,min(1.2,temperature))
    max_tokens=int(req.get("max_tokens",512))
    max_tokens=max(1,min(768,max_tokens))
    top_p=float(req.get("top_p",0.8))
    top_p=max(0.1,min(1.0,top_p))
    top_k=int(req.get("top_k",20))
    top_k=max(1,min(100,top_k))

    prompt=TOKENIZER.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    enc=TOKENIZER(
        prompt,
        return_tensors="pt",
        add_special_tokens=False,
        truncation=True,
        max_length=4096,
    ).to("cuda")

    kwargs=dict(
        max_new_tokens=max_tokens,
        use_cache=True,
        pad_token_id=TOKENIZER.eos_token_id,
    )
    if temperature>0:
        kwargs.update(
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
        )
    else:
        kwargs.update(do_sample=False)

    with LOCK, torch.inference_mode():
        out=MODEL.generate(**enc,**kwargs)[0]
    text=TOKENIZER.decode(
        out[enc["input_ids"].shape[1]:],
        skip_special_tokens=True,
    ).strip()

    return {
        "id":"aqlevon-auth16",
        "object":"chat.completion",
        "created":int(time.time()),
        "model":MODEL_NAME,
        "choices":[
            {
                "index":0,
                "message":{"role":"assistant","content":text},
                "finish_reason":"stop",
            }
        ],
        "aqlevon":{
            "candidate":"Auth16",
            "base_revision":MODEL_REV,
            "adapter_sha256":"2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a",
        },
    }

runpod.serverless.start({"handler":handler})
