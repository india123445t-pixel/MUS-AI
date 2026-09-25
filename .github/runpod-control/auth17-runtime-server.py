#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, json, os, pathlib, tarfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=pathlib.Path("/workspace/auth17-runtime")
MODEL_DIR=pathlib.Path("/workspace/models/qwen35-4b-daa9c16")
ADAPTER_DIR=ROOT/"adapter"
UPLOAD=ROOT/"adapter.tgz"
PORT=8000
EXPECTED_ADAPTER_SHA="2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a"
MODEL_REV="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
UPLOAD_TOKEN=os.environ["AQLEVON_UPLOAD_TOKEN"]
ROOT.mkdir(parents=True,exist_ok=True); ADAPTER_DIR.mkdir(parents=True,exist_ok=True); MODEL_DIR.mkdir(parents=True,exist_ok=True)

state={"stage":"BOOTING","detail":"server starting","ready":False,"model":"AQLEVON-4B-Auth16","adapter_sha256":EXPECTED_ADAPTER_SHA}
lock=threading.Lock(); generate_lock=threading.Lock(); adapter_event=threading.Event()
runtime={"model":None,"tokenizer":None}
last_requests=[]

def set_state(stage,detail="",ready=None):
    with lock:
        state["stage"]=stage; state["detail"]=detail
        if ready is not None: state["ready"]=ready
        state["updated_at_epoch"]=int(time.time())
    print("AQLEVON_RUNTIME_STATE",json.dumps(state,sort_keys=True),flush=True)

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def loader():
    try:
        set_state("MODEL_DOWNLOAD","downloading pinned Qwen3.5-4B-Base")
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id="Qwen/Qwen3.5-4B-Base",revision=MODEL_REV,local_dir=str(MODEL_DIR))
        set_state("WAITING_ADAPTER","base ready; waiting for frozen Auth16 adapter")
        if not adapter_event.wait(timeout=900):
            raise RuntimeError("adapter_upload_timeout")
        import torch
        from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
        from peft import PeftModel
        set_state("MODEL_LOAD","loading base + Auth16 LoRA")
        tok=AutoTokenizer.from_pretrained(str(MODEL_DIR),local_files_only=True,trust_remote_code=False)
        base=Qwen3_5ForConditionalGeneration.from_pretrained(
            str(MODEL_DIR),dtype=torch.bfloat16,device_map={"":0},
            low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
        model=PeftModel.from_pretrained(base,str(ADAPTER_DIR),is_trainable=False)
        model.eval(); model.config.use_cache=True
        runtime["model"]=model; runtime["tokenizer"]=tok
        set_state("READY","AQLEVON Auth16 candidate loaded",True)
    except Exception as e:
        set_state("FAILED",repr(e),False)

threading.Thread(target=loader,daemon=True).start()

HTML="""<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AQLEVON Auth16</title><style>
body{font-family:system-ui,-apple-system,sans-serif;background:#0b1020;color:#eef2ff;margin:0}.wrap{max-width:850px;margin:auto;padding:24px}.card{background:#121a2f;border:1px solid #263250;border-radius:18px;padding:18px;margin:14px 0}textarea{width:100%;box-sizing:border-box;min-height:130px;border-radius:12px;border:1px solid #34425f;background:#0c1427;color:white;padding:14px;font-size:16px}button{background:#eef2ff;color:#111827;border:0;border-radius:12px;padding:12px 20px;font-weight:700;cursor:pointer}.muted{opacity:.7;font-size:14px}pre{white-space:pre-wrap;word-wrap:break-word;line-height:1.6}.ok{color:#86efac}.bad{color:#fca5a5}</style></head><body><div class="wrap"><h1>AQLEVON — Auth16</h1><div class="muted">Experimental Public-Verified Candidate • Coding + Tool Use • Base 4B + frozen Auth16 LoRA</div><div class="card"><div id="status">جاري فحص النموذج…</div></div><div class="card"><textarea id="q" placeholder="اكتب طلبك هنا…"></textarea><p><button onclick="ask()">إرسال</button></p></div><div class="card"><pre id="out">الجواب سيظهر هنا.</pre></div></div><script>
async function health(){try{let r=await fetch('/health');let j=await r.json();document.getElementById('status').innerHTML=(j.ready?'<span class="ok">جاهز</span>':'<span class="bad">غير جاهز بعد</span>')+' — '+j.stage+' — '+(j.detail||'');}catch(e){document.getElementById('status').textContent='تعذر الاتصال';}}
async function ask(){let q=document.getElementById('q').value.trim();if(!q)return;let o=document.getElementById('out');o.textContent='يعمل…';try{let r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:'AQLEVON-4B-Auth16',messages:[{role:'user',content:q}],temperature:0.2,max_tokens:384})});let j=await r.json();o.textContent=j.choices?j.choices[0].message.content:JSON.stringify(j,null,2);}catch(e){o.textContent=String(e)}}setInterval(health,4000);health();</script></body></html>"""

class H(BaseHTTPRequestHandler):
    server_version="AQLEVON/1"
    def log_message(self,*a): pass
    def sendj(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.split("?")[0]=="/":
            b=HTML.encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path.split("?")[0]=="/health":
            with lock: out=dict(state)
            self.sendj(200,out); return
        self.sendj(404,{"error":"not_found"})
    def do_POST(self):
        path=self.path.split("?")[0]
        n=int(self.headers.get("Content-Length","0") or "0")
        if path=="/internal/upload-adapter":
            if self.headers.get("X-Upload-Token")!=UPLOAD_TOKEN: self.sendj(403,{"error":"forbidden"}); return
            if adapter_event.is_set(): self.sendj(409,{"error":"adapter_already_uploaded"}); return
            if n<=0 or n>20_000_000: self.sendj(413,{"error":"bad_size"}); return
            data=self.rfile.read(n); UPLOAD.write_bytes(data)
            try:
                tmp=ROOT/"extract"; tmp.mkdir(exist_ok=True)
                with tarfile.open(UPLOAD,"r:gz") as t:
                    for m in t.getmembers():
                        if m.name.startswith("/") or ".." in pathlib.PurePosixPath(m.name).parts: raise RuntimeError("unsafe_tar")
                    t.extractall(tmp)
                am=next(tmp.rglob("adapter_model.safetensors")); ac=next(tmp.rglob("adapter_config.json"))
                got=sha(am)
                if got!=EXPECTED_ADAPTER_SHA: raise RuntimeError(f"adapter_sha_mismatch:{got}")
                (ADAPTER_DIR/"adapter_model.safetensors").write_bytes(am.read_bytes())
                (ADAPTER_DIR/"adapter_config.json").write_bytes(ac.read_bytes())
                adapter_event.set(); set_state("ADAPTER_VERIFIED",got)
                self.sendj(200,{"status":"PASS","adapter_sha256":got})
            except Exception as e:
                set_state("FAILED",repr(e),False); self.sendj(400,{"error":repr(e)})
            return
        if path!="/v1/chat/completions": self.sendj(404,{"error":"not_found"}); return
        now=time.time()
        while last_requests and now-last_requests[0]>60: last_requests.pop(0)
        if len(last_requests)>=30: self.sendj(429,{"error":"rate_limited"}); return
        last_requests.append(now)
        if not state.get("ready"): self.sendj(503,{"error":"model_not_ready","stage":state.get("stage")}); return
        if n<=0 or n>100_000: self.sendj(413,{"error":"bad_size"}); return
        try: req=json.loads(self.rfile.read(n))
        except Exception: self.sendj(400,{"error":"invalid_json"}); return
        messages=req.get("messages")
        if not isinstance(messages,list) or not messages: self.sendj(400,{"error":"messages_required"}); return
        clean=[]
        total=0
        for m in messages[-12:]:
            role=str(m.get("role","user"))
            if role not in {"system","user","assistant"}: role="user"
            content=str(m.get("content",""))
            total+=len(content)
            clean.append({"role":role,"content":content})
        if total>16000: self.sendj(400,{"error":"prompt_too_long"}); return
        max_tokens=max(1,min(int(req.get("max_tokens",384)),512))
        temp=float(req.get("temperature",0.2)); temp=max(0.0,min(temp,1.2))
        try:
            import torch
            model=runtime["model"]; tok=runtime["tokenizer"]
            with generate_lock:
                prompt=tok.apply_chat_template(clean,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                enc=tok(prompt,return_tensors="pt",add_special_tokens=False).to("cuda")
                kw=dict(max_new_tokens=max_tokens,use_cache=True,pad_token_id=tok.eos_token_id)
                if temp>0:
                    kw.update(do_sample=True,temperature=temp,top_p=0.8,top_k=20)
                else: kw.update(do_sample=False)
                with torch.inference_mode(): out=model.generate(**enc,**kw)[0]
                text=tok.decode(out[enc["input_ids"].shape[1]:],skip_special_tokens=True).strip()
            self.sendj(200,{"id":"aqlevon-auth16","object":"chat.completion","model":"AQLEVON-4B-Auth16","choices":[{"index":0,"message":{"role":"assistant","content":text},"finish_reason":"stop"}]})
        except Exception as e:
            self.sendj(500,{"error":"generation_failed","detail":repr(e)[:500]})

set_state("HTTP_READY","waiting for base and adapter",False)
ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
