export const AQLEVON_CHILD_PROTOCOL='AQLEVON_CHILD_RUNTIME_V1';

function isRunpodQueueEndpoint(raw){
  try{
    const u=new URL(String(raw||''));
    return u.hostname==='api.runpod.ai'&&/^\/v2\/[^/]+\/(?:run|runsync)$/.test(u.pathname);
  }catch{return false}
}
function runpodBase(endpoint){
  try{
    const u=new URL(endpoint);const m=u.pathname.match(/^(\/v2\/[^/]+)/);
    if(!m)return null;u.pathname=m[1];u.search='';u.hash='';return u.toString().replace(/\/$/,'');
  }catch{return null}
}
function normalize(raw){
  if(!raw)return null;
  try{
    const u=new URL(String(raw).replace(/\/$/,''));
    if(u.hostname==='api.runpod.ai'){
      if(/^\/v2\/[^/]+$/.test(u.pathname))u.pathname=u.pathname+'/runsync';
      if(/^\/v2\/[^/]+\/(?:run|runsync)$/.test(u.pathname))return u.toString().replace(/\/$/,'');
    }
  }catch{}
  const url=String(raw).replace(/\/$/,'');
  if(url.endsWith('/chat/completions'))return url;
  if(url.endsWith('/v1'))return url+'/chat/completions';
  return url;
}

export function resolveChildRuntime(){
  return Object.freeze({
    endpoint:normalize(process.env.AQLEVON_CHILD_MODEL_URL||null),
    model:String(process.env.AQLEVON_CHILD_MODEL_NAME||'AQLEVON-CHILD'),
    key:String(process.env.AQLEVON_CHILD_MODEL_KEY||''),
    health_url:String(process.env.AQLEVON_CHILD_MODEL_HEALTH_URL||''),
    protocol:AQLEVON_CHILD_PROTOCOL,
  });
}

export async function childHealth(opts={}){
  const cfg=resolveChildRuntime();
  if(!cfg.endpoint)return Object.freeze({ok:false,configured:false,error_class:'ENV_MISSING',model:cfg.model,protocol:cfg.protocol});
  const fetchImpl=opts.fetchImpl||fetch;
  const health=cfg.health_url||(isRunpodQueueEndpoint(cfg.endpoint)?(()=>{const b=runpodBase(cfg.endpoint);return b?b+'/health':null})():(()=>{try{const u=new URL(cfg.endpoint);u.pathname='/health';u.search='';u.hash='';return u.toString()}catch{return null}})());
  if(!health)return Object.freeze({ok:false,configured:true,error_class:'HEALTH_URL_INVALID',model:cfg.model,protocol:cfg.protocol});
  try{
    const r=await fetchImpl(health,{method:'GET',headers:{...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},cache:'no-store',signal:AbortSignal.timeout(Number(opts.timeoutMs||8000))});
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

  try{
    const runpod=isRunpodQueueEndpoint(cfg.endpoint);
    let target=cfg.endpoint;
    if(runpod&&target.includes('/runsync')&&!/[?&]wait=/.test(target))target+=(target.includes('?')?'&':'?')+'wait=300000';
    const payload={
      model:cfg.model,
      messages:[{role:'system',content:system},...messages.slice(-24)],
      temperature:Number(temperature||0.5),
      max_tokens:512,
      top_p:0.8,
      top_k:20,
      aqlevon_protocol:cfg.protocol,
    };
    const r=await fetch(target,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify(runpod?{input:payload}:{...payload,stream:false}),
      cache:'no-store',
      signal:AbortSignal.timeout(runpod?295000:75000),
    });
    let data=await r.json().catch(()=>null);
    if(!r.ok)return Object.freeze({unavailable:true,error_class:'RUNTIME_ERROR',status:r.status,protocol:cfg.protocol});
    if(runpod&&data?.id&&['IN_QUEUE','IN_PROGRESS'].includes(String(data.status||''))){
      const base=runpodBase(cfg.endpoint);const deadline=Date.now()+285000;
      while(base&&Date.now()<deadline){
        await new Promise(r=>setTimeout(r,2000));
        const pr=await fetch(`${base}/status/${encodeURIComponent(data.id)}`,{headers:{...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},cache:'no-store',signal:AbortSignal.timeout(10000)});
        const pd=await pr.json().catch(()=>null);
        if(pr.ok&&pd){data=pd;if(!['IN_QUEUE','IN_PROGRESS'].includes(String(pd.status||'')))break;}
      }
    }
    const out=runpod?(data?.output||data):data;
    const text=out?.choices?.[0]?.message?.content||out?.message?.content||out?.response||out?.text||'';
    if(!text)return Object.freeze({unavailable:true,error_class:'INVALID_RESPONSE',protocol:cfg.protocol});
    return Object.freeze({text:String(text).trim(),model:out?.model||cfg.model,provider:'aqlevon-child',protocol:cfg.protocol});
  }catch{
    return Object.freeze({unavailable:true,error_class:'NETWORK_ERROR',protocol:cfg.protocol});
  }
}

