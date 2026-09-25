export const PROVIDER_ERROR_CLASSES = Object.freeze([
  'ENV_MISSING','AUTH_ERROR','RATE_LIMIT','MODEL_UNAVAILABLE','INVALID_MODEL',
  'NETWORK_ERROR','UPSTREAM_5XX','INVALID_RESPONSE','UNKNOWN_PROVIDER_ERROR'
]);

export const AQLEVON_CHAT_RUNTIME_PROTOCOL = 'AQLEVON_CHAT_RUNTIME_V1';

function isRunpodQueueEndpoint(raw){
  try{
    const u=new URL(String(raw||''));
    return u.hostname==='api.runpod.ai'&&/^\/v2\/[^/]+\/(?:run|runsync)$/.test(u.pathname);
  }catch{return false}
}

function normalizeRunpodEndpoint(raw){
  try{
    const u=new URL(String(raw||'').replace(/\/$/,''));
    if(u.hostname!=='api.runpod.ai')return null;
    if(/^\/v2\/[^/]+$/.test(u.pathname))u.pathname=u.pathname+'/runsync';
    if(/^\/v2\/[^/]+\/(?:run|runsync)$/.test(u.pathname))return u.toString().replace(/\/$/,'');
    return null;
  }catch{return null}
}

function runpodBase(endpoint){
  try{
    const u=new URL(endpoint);
    const m=u.pathname.match(/^(\/v2\/[^/]+)/);
    if(!m)return null;
    u.pathname=m[1];u.search='';u.hash='';
    return u.toString().replace(/\/$/,'');
  }catch{return null}
}

export function normalizeEndpoint(raw){
  if(!raw)return null;
  const rp=normalizeRunpodEndpoint(raw);
  if(rp)return rp;
  const url=String(raw).replace(/\/$/,'');
  if(url.endsWith('/chat/completions'))return url;
  if(url.endsWith('/v1'))return `${url}/chat/completions`;
  return url;
}

function safeUrlOrigin(raw){
  try{return new URL(String(raw)).origin}catch{return null}
}

function resolveHealthUrl(endpoint,settings={}){
  const explicit=process.env.AQLEVON_MODEL_HEALTH_URL;
  if(explicit)return String(explicit);
  if(isRunpodQueueEndpoint(endpoint)){
    const base=runpodBase(endpoint);
    return base?base+'/health':null;
  }
  try{
    const url=new URL(endpoint);
    url.pathname='/health';
    url.search='';
    url.hash='';
    return url.toString();
  }catch{return null}
}

export function resolveSelfHostedConfig(settings={}){
  const rawEndpoint=process.env.AQLEVON_MODEL_URL||null;
  const endpoint=normalizeEndpoint(rawEndpoint);
  const model=String(process.env.AQLEVON_MODEL_NAME||'AQLEVON');
  const key=process.env.AQLEVON_MODEL_KEY||'';
  return Object.freeze({endpoint,model,key,health_url:endpoint?resolveHealthUrl(endpoint,settings):null});
}

export function getSelfHostedRuntimeDescriptor(settings={}){
  const cfg=resolveSelfHostedConfig(settings);
  return Object.freeze({
    configured:!!cfg.endpoint,
    provider:'aqlevon-engine',
    model:cfg.model,
    protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
    endpoint_origin:cfg.endpoint?safeUrlOrigin(cfg.endpoint):null,
    credential_configured:!!cfg.key,
    runtime_mode:'self_hosted_only',
  });
}

function bodySignal(body){
  try{return JSON.stringify(body??'').toLowerCase().slice(0,2400)}catch{return ''}
}

export function classifyProviderFailure({status=0,body=null,error=null,keyPresent=true}){
  if(!keyPresent)return 'ENV_MISSING';
  if(error){
    const name=String(error?.name||'').toLowerCase();
    const message=String(error?.message||'').toLowerCase();
    if(name.includes('abort')||message.includes('timeout')||message.includes('network')||message.includes('fetch'))return 'NETWORK_ERROR';
  }
  const signal=bodySignal(body);
  if(status===401||status===403)return 'AUTH_ERROR';
  if(status===429)return 'RATE_LIMIT';
  if((status===400||status===404)&&signal.includes('invalid')&&signal.includes('model'))return 'INVALID_MODEL';
  if(status===404||signal.includes('model not found')||signal.includes('model unavailable')||signal.includes('no such model'))return 'MODEL_UNAVAILABLE';
  if(status>=500&&status<=599)return 'UPSTREAM_5XX';
  if(status>=200&&status<300)return 'INVALID_RESPONSE';
  return 'UNKNOWN_PROVIDER_ERROR';
}

export function safeProviderDiagnostic({provider='aqlevon-engine',model='AQLEVON',route='self_hosted_only',status=0,error_class}){
  const safeClass=PROVIDER_ERROR_CLASSES.includes(error_class)?error_class:'UNKNOWN_PROVIDER_ERROR';
  return Object.freeze({
    provider:String(provider||'aqlevon-engine'),
    model:String(model||'AQLEVON'),
    route:'self_hosted_only',
    status:Number.isFinite(Number(status))?Number(status):0,
    error_class:safeClass,
  });
}

function failure({model,status=0,body=null,error=null,keyPresent=true}){
  return {value:null,diagnostic:safeProviderDiagnostic({
    provider:'aqlevon-engine',
    model,
    route:'self_hosted_only',
    status,
    error_class:classifyProviderFailure({status,body,error,keyPresent}),
  })};
}

export async function checkSelfHostedHealth(settings={},opts={}){
  const cfg=resolveSelfHostedConfig(settings);
  if(!cfg.endpoint)return Object.freeze({ok:false,configured:false,provider:'aqlevon-engine',model:cfg.model,status:0,error_class:'ENV_MISSING'});
  const fetchImpl=opts.fetchImpl||fetch;
  try{
    const response=await fetchImpl(cfg.health_url,{method:'GET',headers:{...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},signal:AbortSignal.timeout(Number(opts.timeoutMs||8000)),cache:'no-store'});
    return Object.freeze({
      ok:response.ok,
      configured:true,
      provider:'aqlevon-engine',
      model:cfg.model,
      status:response.status,
      error_class:response.ok?null:classifyProviderFailure({status:response.status,keyPresent:true}),
    });
  }catch(error){
    return Object.freeze({ok:false,configured:true,provider:'aqlevon-engine',model:cfg.model,status:0,error_class:classifyProviderFailure({error,keyPresent:true})});
  }
}

async function aqlevonRuntime(messages,settings={},opts={}){
  const cfg=resolveSelfHostedConfig(settings);
  const model=cfg.model;
  if(!cfg.endpoint)return failure({model,keyPresent:false});
  try{
    const runpod=isRunpodQueueEndpoint(cfg.endpoint);
    let target=cfg.endpoint;
    if(runpod&&target.includes('/runsync')&&!/[?&]wait=/.test(target))target+=(target.includes('?')?'&':'?')+'wait=300000';
    const response=await fetch(target,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify(runpod?{input:{
        model,
        messages,
        temperature:Number(opts.temperature??settings?.temperature??0.4),
        max_tokens:Number(opts.maxTokens||512),
        top_p:0.8,
        top_k:20,
        aqlevon_protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
      }}:{
        model,
        messages,
        temperature:Number(opts.temperature??settings?.temperature??0.4),
        stream:false,
        aqlevon_protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
      }),
      signal:AbortSignal.timeout(runpod?295000:75000),
      cache:'no-store',
    });
    let data=await response.json().catch(()=>null);
    if(!response.ok)return failure({model,status:response.status,body:data,keyPresent:true});
    if(runpod&&data?.id&&['IN_QUEUE','IN_PROGRESS'].includes(String(data.status||''))){
      const base=runpodBase(cfg.endpoint);
      const deadline=Date.now()+285000;
      while(base&&Date.now()<deadline){
        await new Promise(r=>setTimeout(r,2000));
        const pr=await fetch(`${base}/status/${encodeURIComponent(data.id)}`,{
          headers:{...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
          cache:'no-store',
          signal:AbortSignal.timeout(10000),
        });
        const pd=await pr.json().catch(()=>null);
        if(pr.ok&&pd){
          data=pd;
          if(!['IN_QUEUE','IN_PROGRESS'].includes(String(pd.status||'')))break;
        }
      }
    }
    if(!data)return failure({model,status:response.status,body:null,keyPresent:true});
    const payload=runpod?(data?.output||data):data;
    const message=payload?.choices?.[0]?.message||null;
    const text=message?.content||payload?.message?.content||payload?.response||payload?.text||null;
    if(!text)return failure({model:payload?.model||model,status:response.status,body:{shape:'missing_content',runpod_status:data?.status||null},keyPresent:true});
    return {value:{
      text:String(text).trim(),
      provider:'aqlevon-engine',
      model:payload?.model||model,
      citations:[],
      protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
    },diagnostic:null};
  }catch(error){
    return failure({model,error,keyPresent:true});
  }
}

function selectPrimaryDiagnostic(diagnostics=[]){
  return diagnostics.find(Boolean)||safeProviderDiagnostic({error_class:'UNKNOWN_PROVIDER_ERROR'});
}

export async function generateModelResponse(messages,_webSearch,settings={},opts={}){
  const diagnostics=[];
  const result=await aqlevonRuntime(messages,{...settings,runtime_mode:'self_hosted_only'},opts);
  if(result?.diagnostic){
    diagnostics.push(result.diagnostic);
    if(opts.logDiagnostics===true)console.warn('AQLEVON_RUNTIME_DIAGNOSTIC',result.diagnostic);
  }
  if(result?.value)return result.value;
  if(opts.includeDiagnostics===true){
    const primary=selectPrimaryDiagnostic(diagnostics);
    return Object.freeze({unavailable:true,error_class:primary.error_class,diagnostics:Object.freeze(diagnostics.slice())});
  }
  return null;
}
