import os, json, hashlib, time
import torch
import runpod
from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
from peft import PeftModel

MODEL_DIR=os.environ.get("AQLEVON_BASE_DIR","/models/qwen35-4b")
ADAPTER_DIR=os.environ.get("AQLEVON_ADAPTER_DIR","/models/auth16")
MODEL_NAME=os.environ.get("AQLEVON_MODEL_NAME","AQLEVON-4B-Auth16")
EXPECTED_ADAPTER_SHA="2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a"

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

adapter_path=os.path.join(ADAPTER_DIR,"adapter_model.safetensors")
actual=sha256(adapter_path)
if actual!=EXPECTED_ADAPTER_SHA:
    raise RuntimeError(f"AUTH16_ADAPTER_SHA_MISMATCH:{actual}")

tokenizer=AutoTokenizer.from_pretrained(MODEL_DIR,local_files_only=True,trust_remote_code=False)
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

def clean_messages(raw):
    if not isinstance(raw,list) or not raw:
        raise ValueError("messages_required")
    out=[]; total=0
    for m in raw[-16:]:
        if not isinstance(m,dict):
            continue
        role=str(m.get("role","user"))
        if role not in {"system","user","assistant"}:
            role="user"
        content=str(m.get("content",""))
        total+=len(content)
        if total>24000:
            raise ValueError("prompt_too_long")
        out.append({"role":role,"content":content})
    if not out:
        raise ValueError("messages_required")
    return out

def handler(job):
    inp=job.get("input") or {}
    started=time.time()
    try:
        messages=clean_messages(inp.get("messages"))
        max_tokens=max(1,min(int(inp.get("max_tokens",512)),768))
        temperature=max(0.0,min(float(inp.get("temperature",0.2)),1.2))
        prompt=tokenizer.apply_chat_template(
            messages,tokenize=False,add_generation_prompt=True,enable_thinking=False
        )
        enc=tokenizer(prompt,return_tensors="pt",add_special_tokens=False).to("cuda")
        kwargs={
            "max_new_tokens":max_tokens,
            "use_cache":True,
            "pad_token_id":tokenizer.eos_token_id,
        }
        if temperature>0:
            kwargs.update(do_sample=True,temperature=temperature,top_p=0.8,top_k=20)
        else:
            kwargs.update(do_sample=False)
        with torch.inference_mode():
            output=model.generate(**enc,**kwargs)[0]
        text=tokenizer.decode(output[enc["input_ids"].shape[1]:],skip_special_tokens=True).strip()
        return {
            "id":"aqlevon-auth16",
            "object":"chat.completion",
            "model":MODEL_NAME,
            "adapter_sha256":EXPECTED_ADAPTER_SHA,
            "latency_ms":round((time.time()-started)*1000),
            "choices":[{
                "index":0,
                "message":{"role":"assistant","content":text},
                "finish_reason":"stop"
            }]
        }
    except Exception as e:
        return {"error":type(e).__name__,"detail":str(e)[:500],"model":MODEL_NAME}

if __name__=="__main__":
    runpod.serverless.start({"handler":handler})
