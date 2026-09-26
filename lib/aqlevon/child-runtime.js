export const AQLEVON_CHILD_PROTOCOL='AQLEVON_CHILD_RUNTIME_V1';

function normalize(raw){
  if(!raw)return null;
  const url=String(raw).replace(/\/$/,'');
  if(url.endsWith('/chat/completions'))return url;
  if(url.endsWith('/v1'))return url+'/chat/completions';
  return url;
}

export function resolveChildRuntime(){
  const rawEndpoint=process.env.AQLEVON_CHILD_MODEL_URL||null;
  const runpodEndpointId=rawEndpoint?'':String(process.env.AQLEVON_CHILD_RUNPOD_ENDPOINT_ID||'qyb4is6cl1hn22').trim();
  const runpodKey=String(process.env.AQLEVON_CHILD_RUNPOD_KEY||process.env.AQLEVON_CHILD_MODEL_KEY||process.env.AQLEVON_MODEL_RUNPOD_KEY||process.env.AQLEVON_MODEL_KEY||process.env.RUNPOD_API_KEY||'').trim();
  return Object.freeze({
    endpoint:normalize(rawEndpoint),
    model:String(process.env.AQLEVON_CHILD_MODEL_NAME||'AQLEVON-4B-Auth16-CHILD'),
    key:String(process.env.AQLEVON_CHILD_MODEL_KEY||process.env.AQLEVON_MODEL_KEY||''),
    health_url:String(process.env.AQLEVON_CHILD_MODEL_HEALTH_URL||''),
    protocol:AQLEVON_CHILD_PROTOCOL,
    runpod_endpoint_id:runpodEndpointId||null,
    runpod_key:runpodKey,
    transport:runpodEndpointId?'runpod-serverless':'openai-compatible',
  });
}

export async function childHealth(opts={}){
  const cfg=resolveChildRuntime();
  if(!cfg.endpoint&&!cfg.runpod_endpoint_id)return Object.freeze({ok:false,configured:false,error_class:'ENV_MISSING',model:cfg.model,protocol:cfg.protocol});
  if(cfg.runpod_endpoint_id)return Object.freeze({ok:!!cfg.runpod_key,configured:true,status:cfg.runpod_key?200:0,error_class:cfg.runpod_key?null:'ENV_MISSING',model:cfg.model,protocol:cfg.protocol,transport:'runpod-serverless'});
  const fetchImpl=opts.fetchImpl||fetch;
  const health=cfg.health_url||(()=>{try{const u=new URL(cfg.endpoint);u.pathname='/health';u.search='';u.hash='';return u.toString()}catch{return null}})();
  if(!health)return Object.freeze({ok:false,configured:true,error_class:'HEALTH_URL_INVALID',model:cfg.model,protocol:cfg.protocol});
  try{
    const r=await fetchImpl(health,{method:'GET',cache:'no-store',signal:AbortSignal.timeout(Number(opts.timeoutMs||5000))});
    return Object.freeze({ok:r.ok,configured:true,status:r.status,error_class:r.ok?null:'RUNTIME_UNHEALTHY',model:cfg.model,protocol:cfg.protocol});
  }catch{
    return Object.freeze({ok:false,configured:true,status:0,error_class:'NETWORK_ERROR',model:cfg.model,protocol:cfg.protocol});
  }
}

export async function generateChildResponse({messages=[],persona='',lessons=[],memories=[],trial=null,temperature=0.5}={}){
  const cfg=resolveChildRuntime();
  if(!cfg.endpoint&&!cfg.runpod_endpoint_id)return Object.freeze({unavailable:true,error_class:'ENV_MISSING',protocol:cfg.protocol});
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
    const runpod=!!cfg.runpod_endpoint_id;
    if(runpod&&!cfg.runpod_key)return Object.freeze({unavailable:true,error_class:'ENV_MISSING',protocol:cfg.protocol});
    const url=runpod?`https://api.runpod.ai/v2/${cfg.runpod_endpoint_id}/runsync`:cfg.endpoint;
    const payload={
      model:cfg.model,
      messages:[{role:'system',content:system},...messages.slice(-24)],
      temperature:Number(temperature||0.5),
      stream:false,
      aqlevon_protocol:cfg.protocol,
      max_tokens:512,
    };
    const r=await fetch(url,{
      method:'POST',
      headers:{'Content-Type':'application/json',...((runpod?cfg.runpod_key:cfg.key)?{Authorization:`Bearer ${runpod?cfg.runpod_key:cfg.key}`}:{})},
      body:JSON.stringify(runpod?{input:payload}:payload),
      cache:'no-store',
      signal:AbortSignal.timeout(65000),
    });
    const data=await r.json().catch(()=>null);
    if(!r.ok)return Object.freeze({unavailable:true,error_class:'RUNTIME_ERROR',status:r.status,protocol:cfg.protocol});
    const result=runpod?(data?.output||null):data;
    const text=result?.choices?.[0]?.message?.content||result?.message?.content||result?.response||'';
    if(!text)return Object.freeze({unavailable:true,error_class:'INVALID_RESPONSE',protocol:cfg.protocol});
    return Object.freeze({text:String(text).trim(),model:cfg.model,provider:'aqlevon-child',protocol:cfg.protocol});
  }catch{
    return Object.freeze({unavailable:true,error_class:'NETWORK_ERROR',protocol:cfg.protocol});
  }
}
