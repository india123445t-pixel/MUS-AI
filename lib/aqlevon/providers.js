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
  const explicit=process.env.AQLEVON_MODEL_HEALTH_URL;
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
  const rawEndpoint=process.env.AQLEVON_MODEL_URL||null;
  const runpodEndpointId=rawEndpoint?'':String(process.env.AQLEVON_MODEL_RUNPOD_ENDPOINT_ID||'qyb4is6cl1hn22').trim();
  const runpodKey=String(process.env.AQLEVON_MODEL_RUNPOD_KEY||process.env.AQLEVON_MODEL_KEY||'').trim();
  const endpoint=normalizeEndpoint(rawEndpoint);
  const model=String(process.env.AQLEVON_MODEL_NAME||'AQLEVON-4B-Auth16');
  return Object.freeze({
    endpoint,
    model,
    key:String(process.env.AQLEVON_MODEL_KEY||''),
    health_url:endpoint?resolveHealthUrl(endpoint,settings):null,
    runpod_endpoint_id:runpodEndpointId||null,
    runpod_key:runpodKey,
    transport:runpodEndpointId?'runpod-serverless':'openai-compatible',
  });
}

export function getSelfHostedRuntimeDescriptor(settings={}){
  const cfg=resolveSelfHostedConfig(settings);
  return Object.freeze({
    configured:!!(cfg.endpoint||cfg.runpod_endpoint_id),
    provider:'aqlevon-engine',
    model:cfg.model,
    protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
    endpoint_origin:cfg.runpod_endpoint_id?'https://api.runpod.ai':(cfg.endpoint?safeUrlOrigin(cfg.endpoint):null),
    credential_configured:cfg.runpod_endpoint_id?!!cfg.runpod_key:!!cfg.key,
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
  if(!cfg.endpoint&&!cfg.runpod_endpoint_id)return Object.freeze({ok:false,configured:false,provider:'aqlevon-engine',model:cfg.model,status:0,error_class:'ENV_MISSING'});
  if(cfg.runpod_endpoint_id)return Object.freeze({ok:!!cfg.runpod_key,configured:true,provider:'aqlevon-engine',model:cfg.model,status:cfg.runpod_key?200:0,error_class:cfg.runpod_key?null:'ENV_MISSING',transport:'runpod-serverless'});
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
  if(!cfg.endpoint&&!cfg.runpod_endpoint_id)return failure({model,keyPresent:false});
  try{
    const runpod=!!cfg.runpod_endpoint_id;
    if(runpod&&!cfg.runpod_key)return failure({model,keyPresent:false});
    const url=runpod?`https://api.runpod.ai/v2/${cfg.runpod_endpoint_id}/runsync`:cfg.endpoint;
    const payload={
      model,
      messages,
      temperature:Number(opts.temperature??settings?.temperature??0.4),
      stream:false,
      aqlevon_protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
      max_tokens:Number(opts.max_tokens??512),
    };
    const response=await fetch(url,{
      method:'POST',
      headers:{'Content-Type':'application/json',...((runpod?cfg.runpod_key:cfg.key)?{Authorization:`Bearer ${runpod?cfg.runpod_key:cfg.key}`}:{})},
      body:JSON.stringify(runpod?{input:payload}:payload),
      signal:AbortSignal.timeout(65000),
      cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)return failure({model,status:response.status,body:data,keyPresent:true});
    if(!data)return failure({model,status:response.status,body:null,keyPresent:true});
    const result=runpod?(data?.output||null):data;
    const message=result?.choices?.[0]?.message||null;
    const text=message?.content||result?.message?.content||result?.response||null;
    if(!text)return failure({model:data?.model||model,status:response.status,body:{shape:'missing_content'},keyPresent:true});
    return {value:{
      text:String(text).trim(),
      provider:'aqlevon-engine',
      model:(runpod?(data?.output?.model||model):(data?.model||model)),
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
