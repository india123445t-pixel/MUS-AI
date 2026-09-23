export const PROVIDER_ERROR_CLASSES = Object.freeze([
  'ENV_MISSING','AUTH_ERROR','RATE_LIMIT','MODEL_UNAVAILABLE','INVALID_MODEL',
  'NETWORK_ERROR','UPSTREAM_5XX','INVALID_RESPONSE','UNKNOWN_PROVIDER_ERROR'
]);

export const AQLEVON_CHAT_RUNTIME_PROTOCOL = 'AQLEVON_CHAT_RUNTIME_V1';

export function normalizeEndpoint(raw){
  if(!raw)return null;
  const url=String(raw).replace(/\/$/,'');
  if(url.endsWith('/chat/completions'))return url;
  if(url.endsWith('/v1'))return `${url}/chat/completions`;
  return url;
}

function safeUrlOrigin(raw){
  try{return new URL(String(raw)).origin}catch{return null}
}

function resolveHealthUrl(endpoint,settings={}){
  const explicit=settings?.self_hosted_health_url||process.env.AQLEVON_MODEL_HEALTH_URL||process.env.LOCAL_MODEL_HEALTH_URL;
  if(explicit)return String(explicit);
  try{
    const url=new URL(endpoint);
    url.pathname='/health';
    url.search='';
    url.hash='';
    return url.toString();
  }catch{return null}
}

export function resolveSelfHostedConfig(settings={}){
  const rawEndpoint=settings?.self_hosted_url||settings?.aqlevon_model_url||process.env.AQLEVON_MODEL_URL||process.env.LOCAL_MODEL_URL||null;
  const endpoint=normalizeEndpoint(rawEndpoint);
  const model=String(settings?.self_hosted_model||process.env.AQLEVON_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'AQLEVON-27B');
  const key=process.env.AQLEVON_MODEL_KEY||process.env.LOCAL_MODEL_KEY||'';
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
    const response=await fetchImpl(cfg.health_url,{method:'GET',signal:AbortSignal.timeout(Number(opts.timeoutMs||5000)),cache:'no-store'});
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
  if((opts.excludeProviders||[]).includes('aqlevon-engine'))return {value:null,diagnostic:null};
  if(!cfg.endpoint)return failure({model,keyPresent:false});
  try{
    const response=await fetch(cfg.endpoint,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify({
        model,
        messages,
        temperature:Number(opts.temperature??settings?.temperature??0.4),
        stream:false,
        aqlevon_protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
      }),
      signal:AbortSignal.timeout(65000),
      cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)return failure({model,status:response.status,body:data,keyPresent:true});
    if(!data)return failure({model,status:response.status,body:null,keyPresent:true});
    const message=data?.choices?.[0]?.message||null;
    const text=message?.content||data?.message?.content||data?.response||null;
    if(!text)return failure({model:data?.model||model,status:response.status,body:{shape:'missing_content'},keyPresent:true});
    return {value:{
      text:String(text).trim(),
      provider:'aqlevon-engine',
      model:data?.model||model,
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
