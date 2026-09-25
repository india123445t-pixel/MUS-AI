import {RUNPOD_QUEUE_TRANSPORT,runpodQueueCompletion,runpodQueueHealth} from './runpod-runtime.js';

export const AQLEVON_CHILD_PROTOCOL='AQLEVON_CHILD_RUNTIME_V1';

function normalize(raw,transport){
  if(!raw)return null;
  const url=String(raw).replace(/\/$/,'');
  if(transport===RUNPOD_QUEUE_TRANSPORT)return url;
  if(url.endsWith('/chat/completions'))return url;
  if(url.endsWith('/v1'))return url+'/chat/completions';
  return url;
}

export function resolveChildRuntime(){
  const transport=String(process.env.AQLEVON_CHILD_MODEL_TRANSPORT||'openai_compatible');
  const endpoint=normalize(process.env.AQLEVON_CHILD_MODEL_URL||null,transport);
  return Object.freeze({
    endpoint,
    model:String(process.env.AQLEVON_CHILD_MODEL_NAME||'AQLEVON-CHILD'),
    key:String(process.env.AQLEVON_CHILD_MODEL_KEY||''),
    health_url:String(process.env.AQLEVON_CHILD_MODEL_HEALTH_URL||''),
    transport,
    protocol:AQLEVON_CHILD_PROTOCOL,
  });
}

export async function childHealth(opts={}){
  const cfg=resolveChildRuntime();
  if(!cfg.endpoint)return Object.freeze({ok:false,configured:false,error_class:'ENV_MISSING',model:cfg.model,protocol:cfg.protocol});
  if(cfg.transport===RUNPOD_QUEUE_TRANSPORT){
    const h=await runpodQueueHealth({endpoint:cfg.endpoint,key:cfg.key,fetchImpl:opts.fetchImpl||fetch,timeoutMs:Number(opts.timeoutMs||7000)});
    return Object.freeze({ok:h.ok,configured:true,status:h.status,error_class:h.ok?null:h.error_class,model:cfg.model,protocol:cfg.protocol,transport:cfg.transport});
  }
  const fetchImpl=opts.fetchImpl||fetch;
  const health=cfg.health_url||(()=>{try{const u=new URL(cfg.endpoint);u.pathname='/health';u.search='';u.hash='';return u.toString()}catch{return null}})();
  if(!health)return Object.freeze({ok:false,configured:true,error_class:'HEALTH_URL_INVALID',model:cfg.model,protocol:cfg.protocol});
  try{
    const r=await fetchImpl(health,{method:'GET',headers:cfg.key?{Authorization:`Bearer ${cfg.key}`}:{},cache:'no-store',signal:AbortSignal.timeout(Number(opts.timeoutMs||5000))});
    return Object.freeze({ok:r.ok,configured:true,status:r.status,error_class:r.ok?null:'RUNTIME_UNHEALTHY',model:cfg.model,protocol:cfg.protocol});
  }catch{
    return Object.freeze({ok:false,configured:true,status:0,error_class:'NETWORK_ERROR',model:cfg.model,protocol:cfg.protocol});
  }
}

export async function generateChildResponse({messages=[],persona='',lessons=[],memories=[],trial=null,temperature=0.5}={}){
  const cfg=resolveChildRuntime();
  if(!cfg.endpoint)return Object.freeze({unavailable:true,error_class:'ENV_MISSING',protocol:cfg.protocol});
  const system=[
    'You are AQLEVON Child Lab, an isolated experimental personality owned by the project owner.',
    'You are NOT the public AQLEVON runtime and you must not claim to modify public model weights or production state.',
    'Follow the owner-defined personality and lessons inside this lab only.',
    persona?('PERSONALITY:\n'+String(persona).slice(0,12000)):'',
    lessons?.length?('LESSONS:\n'+lessons.slice(-30).map((x,i)=>`${i+1}. ${String(x).slice(0,2000)}`).join('\n')):'',
    memories?.length?('RELEVANT LONG-TERM MEMORY:\n'+memories.slice(0,24).map((x,i)=>`${i+1}. [${String(x.kind||'memory')}/${String(x.topic||'general')}] ${String(x.text||'').slice(0,1800)}`).join('\n')):'',
    trial?('CURRENT TEST:\n'+JSON.stringify(trial).slice(0,6000)):'',
  ].filter(Boolean).join('\n\n');
  const payload={
    model:cfg.model,
    messages:[{role:'system',content:system},...messages.slice(-24)],
    temperature:Number(temperature||0.5),
    max_tokens:512,
    stream:false,
    aqlevon_protocol:cfg.protocol,
  };
  if(cfg.transport===RUNPOD_QUEUE_TRANSPORT){
    const result=await runpodQueueCompletion({endpoint:cfg.endpoint,key:cfg.key,input:payload,timeoutMs:65000});
    if(!result.ok)return Object.freeze({unavailable:true,error_class:result.error_class||'RUNTIME_ERROR',status:result.status,protocol:cfg.protocol});
    const data=result.output;
    const text=data?.choices?.[0]?.message?.content||data?.message?.content||data?.response||'';
    if(!text)return Object.freeze({unavailable:true,error_class:'INVALID_RESPONSE',protocol:cfg.protocol});
    return Object.freeze({text:String(text).trim(),model:data?.model||cfg.model,provider:'aqlevon-child',protocol:cfg.protocol});
  }
  try{
    const r=await fetch(cfg.endpoint,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify(payload),
      cache:'no-store',
      signal:AbortSignal.timeout(65000),
    });
    const data=await r.json().catch(()=>null);
    if(!r.ok)return Object.freeze({unavailable:true,error_class:'RUNTIME_ERROR',status:r.status,protocol:cfg.protocol});
    const text=data?.choices?.[0]?.message?.content||data?.message?.content||data?.response||'';
    if(!text)return Object.freeze({unavailable:true,error_class:'INVALID_RESPONSE',protocol:cfg.protocol});
    return Object.freeze({text:String(text).trim(),model:data?.model||cfg.model,provider:'aqlevon-child',protocol:cfg.protocol});
  }catch{
    return Object.freeze({unavailable:true,error_class:'NETWORK_ERROR',protocol:cfg.protocol});
  }
}
