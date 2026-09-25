import {RUNPOD_QUEUE_TRANSPORT,runpodQueueCompletion,runpodQueueHealth} from './runpod-runtime.js';

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

function resolveHealthUrl(endpoint,transport){
  const explicit=process.env.AQLEVON_MODEL_HEALTH_URL;
  if(explicit)return String(explicit);
  if(transport===RUNPOD_QUEUE_TRANSPORT)return endpoint?String(endpoint).replace(/\/$/,'')+'/health':null;
  try{
    const url=new URL(endpoint);
    url.pathname='/health';url.search='';url.hash='';
    return url.toString();
  }catch{return null}
}

export function resolveSelfHostedConfig(){
  const raw=process.env.AQLEVON_MODEL_URL||null;
  const transport=String(process.env.AQLEVON_MODEL_TRANSPORT||'openai_compatible');
  const endpoint=transport===RUNPOD_QUEUE_TRANSPORT?(raw?String(raw).replace(/\/$/,''):null):normalizeEndpoint(raw);
  const model=String(process.env.AQLEVON_MODEL_NAME||'AQLEVON');
  const key=process.env.AQLEVON_MODEL_KEY||'';
  return Object.freeze({endpoint,model,key,transport,health_url:endpoint?resolveHealthUrl(endpoint,transport):null});
}

export function getSelfHostedRuntimeDescriptor(){
  const cfg=resolveSelfHostedConfig();
  return Object.freeze({
    configured:!!cfg.endpoint,
    provider:'aqlevon-engine',
    model:cfg.model,
    protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
    transport:cfg.transport,
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

function failure({model,status=0,body=null,error=null,keyPresent=true,errorClass=null}){
  return {value:null,diagnostic:safeProviderDiagnostic({
    provider:'aqlevon-engine',model,route:'self_hosted_only',status,
    error_class:errorClass||classifyProviderFailure({status,body,error,keyPresent}),
  })};
}

export async function checkSelfHostedHealth(_settings={},opts={}){
  const cfg=resolveSelfHostedConfig();
  if(!cfg.endpoint)return Object.freeze({ok:false,configured:false,provider:'aqlevon-engine',model:cfg.model,status:0,error_class:'ENV_MISSING'});
  if(cfg.transport===RUNPOD_QUEUE_TRANSPORT){
    const h=await runpodQueueHealth({endpoint:cfg.endpoint,key:cfg.key,fetchImpl:opts.fetchImpl||fetch,timeoutMs:Number(opts.timeoutMs||7000)});
    return Object.freeze({ok:h.ok,configured:true,provider:'aqlevon-engine',model:cfg.model,status:h.status,error_class:h.ok?null:h.error_class,transport:cfg.transport});
  }
  const fetchImpl=opts.fetchImpl||fetch;
  try{
    const response=await fetchImpl(cfg.health_url,{method:'GET',headers:cfg.key?{Authorization:`Bearer ${cfg.key}`}:{},signal:AbortSignal.timeout(Number(opts.timeoutMs||5000)),cache:'no-store'});
    return Object.freeze({
      ok:response.ok,configured:true,provider:'aqlevon-engine',model:cfg.model,status:response.status,
      error_class:response.ok?null:classifyProviderFailure({status:response.status,keyPresent:true}),
    });
  }catch(error){
    return Object.freeze({ok:false,configured:true,provider:'aqlevon-engine',model:cfg.model,status:0,error_class:classifyProviderFailure({error,keyPresent:true})});
  }
}

async function aqlevonRuntime(messages,settings={},opts={}){
  const cfg=resolveSelfHostedConfig();
  const model=cfg.model;
  if(!cfg.endpoint)return failure({model,keyPresent:false});
  const payload={
    model,messages,
    temperature:Number(opts.temperature??settings?.temperature??0.4),
    max_tokens:Number(opts.max_tokens??settings?.max_tokens??512),
    stream:false,
    aqlevon_protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL,
  };
  if(cfg.transport===RUNPOD_QUEUE_TRANSPORT){
    const r=await runpodQueueCompletion({endpoint:cfg.endpoint,key:cfg.key,input:payload,timeoutMs:Number(opts.timeoutMs||65000)});
    if(!r.ok)return failure({model,status:r.status,body:r.body,keyPresent:!!cfg.key,errorClass:r.error_class==='AUTH_ERROR'?'AUTH_ERROR':r.error_class==='NETWORK_ERROR'?'NETWORK_ERROR':'UNKNOWN_PROVIDER_ERROR'});
    const data=r.output;
    const message=data?.choices?.[0]?.message||null;
    const text=message?.content||data?.message?.content||data?.response||null;
    if(!text)return failure({model:data?.model||model,status:r.status,body:{shape:'missing_content'},keyPresent:true});
    return {value:{text:String(text).trim(),provider:'aqlevon-engine',model:data?.model||model,citations:[],protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL},diagnostic:null};
  }
  try{
    const response=await fetch(cfg.endpoint,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify(payload),
      signal:AbortSignal.timeout(65000),
      cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)return failure({model,status:response.status,body:data,keyPresent:true});
    if(!data)return failure({model,status:response.status,body:null,keyPresent:true});
    const message=data?.choices?.[0]?.message||null;
    const text=message?.content||data?.message?.content||data?.response||null;
    if(!text)return failure({model:data?.model||model,status:response.status,body:{shape:'missing_content'},keyPresent:true});
    return {value:{text:String(text).trim(),provider:'aqlevon-engine',model:data?.model||model,citations:[],protocol:AQLEVON_CHAT_RUNTIME_PROTOCOL},diagnostic:null};
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
