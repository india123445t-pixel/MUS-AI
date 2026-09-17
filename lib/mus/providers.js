export const PROVIDER_ERROR_CLASSES = Object.freeze([
  'ENV_MISSING','AUTH_ERROR','RATE_LIMIT','MODEL_UNAVAILABLE','FREE_ROUTE_UNAVAILABLE','INVALID_MODEL',
  'NETWORK_ERROR','UPSTREAM_5XX','INVALID_RESPONSE','UNKNOWN_PROVIDER_ERROR'
]);

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
  const explicit=settings?.self_hosted_health_url||process.env.MUS_MODEL_HEALTH_URL||process.env.LOCAL_MODEL_HEALTH_URL;
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
  const rawEndpoint=settings?.self_hosted_url||settings?.mus_model_url||process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL||null;
  const endpoint=normalizeEndpoint(rawEndpoint);
  const model=String(settings?.self_hosted_model||process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai');
  const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY||'';
  return Object.freeze({endpoint,model,key,health_url:endpoint?resolveHealthUrl(endpoint,settings):null});
}

export function getSelfHostedRuntimeDescriptor(settings={}){
  const cfg=resolveSelfHostedConfig(settings);
  return Object.freeze({
    configured:!!cfg.endpoint,
    provider:'mus-engine',
    model:cfg.model,
    protocol:'openai-compatible',
    endpoint_origin:cfg.endpoint?safeUrlOrigin(cfg.endpoint):null,
    credential_configured:!!cfg.key,
    runtime_mode:settings?.runtime_mode||null,
  });
}

function extractCitations(message){
  return (message?.annotations||[])
    .filter(a=>a?.type==='url_citation'&&a?.url_citation?.url)
    .slice(0,12)
    .map(a=>({
      url:String(a.url_citation.url),
      title:String(a.url_citation.title||''),
      content:String(a.url_citation.content||'').slice(0,2400),
    }));
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
  if(signal.includes('no endpoints found')||signal.includes('no provider')&&signal.includes('free')||signal.includes('free route')&&signal.includes('unavailable'))return 'FREE_ROUTE_UNAVAILABLE';
  if((status===400||status===404)&&signal.includes('invalid')&&signal.includes('model'))return 'INVALID_MODEL';
  if(status===404||signal.includes('model not found')||signal.includes('model unavailable')||signal.includes('no such model'))return 'MODEL_UNAVAILABLE';
  if(status>=500&&status<=599)return 'UPSTREAM_5XX';
  if(status>=200&&status<300)return 'INVALID_RESPONSE';
  return 'UNKNOWN_PROVIDER_ERROR';
}

export function safeProviderDiagnostic({provider,model,route,status=0,error_class}){
  const safeClass=PROVIDER_ERROR_CLASSES.includes(error_class)?error_class:'UNKNOWN_PROVIDER_ERROR';
  return Object.freeze({
    provider:String(provider||'unknown'),
    model:String(model||'unknown'),
    route:String(route||'unknown'),
    status:Number.isFinite(Number(status))?Number(status):0,
    error_class:safeClass,
  });
}

function failure({provider,model,route,status=0,body=null,error=null,keyPresent=true}){
  return {value:null,diagnostic:safeProviderDiagnostic({
    provider,model,route,status,
    error_class:classifyProviderFailure({status,body,error,keyPresent}),
  })};
}

async function openAICompatible({key,url,model,provider,messages,temperature=0.4,headers={},payloadExtra={},route='external'}){
  if(!key)return failure({provider,model,route,keyPresent:false});
  try{
    const response=await fetch(url,{
      method:'POST',
      headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json',...headers},
      body:JSON.stringify({model,messages,temperature,stream:false,...payloadExtra}),
      signal:AbortSignal.timeout(75000),
      cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)return failure({provider,model,route,status:response.status,body:data});
    if(!data)return failure({provider,model,route,status:response.status,body:null});
    const message=data?.choices?.[0]?.message||{};
    const text=typeof message?.content==='string'?message.content.trim():'';
    if(!text)return failure({provider,model:data?.model||model,route,status:response.status,body:{shape:'missing_content'}});
    return {value:{text,provider,model:data?.model||model,citations:extractCitations(message)},diagnostic:null};
  }catch(error){return failure({provider,model,route,error})}
}

export async function checkSelfHostedHealth(settings={},opts={}){
  const cfg=resolveSelfHostedConfig(settings);
  if(!cfg.endpoint)return Object.freeze({ok:false,configured:false,provider:'mus-engine',model:cfg.model,status:0,error_class:'ENV_MISSING'});
  const fetchImpl=opts.fetchImpl||fetch;
  try{
    const response=await fetchImpl(cfg.health_url,{method:'GET',signal:AbortSignal.timeout(Number(opts.timeoutMs||5000)),cache:'no-store'});
    return Object.freeze({
      ok:response.ok,
      configured:true,
      provider:'mus-engine',
      model:cfg.model,
      status:response.status,
      error_class:response.ok?null:classifyProviderFailure({status:response.status,keyPresent:true}),
    });
  }catch(error){
    return Object.freeze({ok:false,configured:true,provider:'mus-engine',model:cfg.model,status:0,error_class:classifyProviderFailure({error,keyPresent:true})});
  }
}

async function selfHosted(messages,settings,opts={}){
  const provider='mus-engine';
  const cfg=resolveSelfHostedConfig(settings);
  const model=cfg.model;
  const route=settings?.runtime_mode||'self_hosted';
  if((opts.excludeProviders||[]).includes(provider))return {value:null,diagnostic:null};
  if(!cfg.endpoint)return failure({provider,model,route,keyPresent:false});
  try{
    const response=await fetch(cfg.endpoint,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify({model,messages,temperature:Number(opts.temperature??settings?.temperature??0.4),stream:false}),
      signal:AbortSignal.timeout(65000),
      cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)return failure({provider,model,route,status:response.status,body:data,keyPresent:true});
    if(!data)return failure({provider,model,route,status:response.status,body:null,keyPresent:true});
    const message=data?.choices?.[0]?.message||null;
    const text=message?.content||data?.message?.content||data?.response||null;
    if(!text)return failure({provider,model:data?.model||model,route,status:response.status,body:{shape:'missing_content'},keyPresent:true});
    return {value:{text:String(text).trim(),provider,model:data?.model||model,citations:[]},diagnostic:null};
  }catch(error){return failure({provider,model,route,error,keyPresent:true})}
}

async function openRouter(messages,webSearch,settings,opts={}){
  const key=process.env.OPENROUTER_API_KEY;
  let model=settings?.openrouter_model||process.env.OPENROUTER_MODEL||'openrouter/free';
  const allowPaid=!!settings?.allow_paid_external;
  if(!allowPaid&&!String(model).includes(':free')&&model!=='openrouter/free')model='openrouter/free';
  const payloadExtra={};
  if(webSearch&&allowPaid&&settings?.public_web_search_enabled)payloadExtra.plugins=[{id:'web',max_results:5}];
  return openAICompatible({
    key,url:'https://openrouter.ai/api/v1/chat/completions',model,provider:'openrouter',messages,
    temperature:Number(opts.temperature??settings?.temperature??0.4),headers:{'X-Title':'MUS AI'},payloadExtra,
    route:settings?.runtime_mode||'openrouter_primary',
  });
}

async function groq(messages,settings,opts={}){
  return openAICompatible({
    key:process.env.GROQ_API_KEY,url:'https://api.groq.com/openai/v1/chat/completions',
    model:process.env.GROQ_MODEL||'openai/gpt-oss-120b',provider:'groq',messages,
    temperature:Number(opts.temperature??settings?.temperature??0.4),
    payloadExtra:{reasoning_effort:Number(opts.temperature??0.4)<=0.15?'low':'medium'},route:settings?.runtime_mode||'external',
  });
}

async function mistral(messages,settings,opts={}){
  return openAICompatible({key:process.env.MISTRAL_API_KEY,url:'https://api.mistral.ai/v1/chat/completions',model:process.env.MISTRAL_MODEL||'mistral-small-latest',provider:'mistral',messages,temperature:Number(opts.temperature??settings?.temperature??0.4),route:settings?.runtime_mode||'external'});
}

async function cerebras(messages,settings,opts={}){
  return openAICompatible({key:process.env.CEREBRAS_API_KEY,url:'https://api.cerebras.ai/v1/chat/completions',model:process.env.CEREBRAS_MODEL||'gpt-oss-120b',provider:'cerebras',messages,temperature:Number(opts.temperature??settings?.temperature??0.4),headers:{'X-Cerebras-Version-Patch':'2'},route:settings?.runtime_mode||'external'});
}

async function huggingFace(messages,settings,opts={}){
  const model=process.env.HF_MODEL||'openai/gpt-oss-120b:cheapest';
  if(process.env.HF_FREE_FALLBACK_ENABLED!=='true')return failure({provider:'huggingface',model,route:settings?.runtime_mode||'external',keyPresent:false});
  return openAICompatible({key:process.env.HF_TOKEN,url:'https://router.huggingface.co/v1/chat/completions',model,provider:'huggingface',messages,temperature:Number(opts.temperature??settings?.temperature??0.4),route:settings?.runtime_mode||'external'});
}

async function gemini(messages,settings,opts={}){
  const provider='gemini';
  const key=process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY;
  const model=process.env.GEMINI_MODEL||'gemini-2.5-flash';
  const route=settings?.runtime_mode||'external';
  if(!key)return failure({provider,model,route,keyPresent:false});
  try{
    const systemParts=messages.filter(m=>m.role==='system').map(m=>String(m.content||''));
    const contents=messages.filter(m=>m.role!=='system').map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:String(m.content||'')}]}));
    const body={contents,generationConfig:{temperature:Number(opts.temperature??settings?.temperature??0.4)},...(systemParts.length?{systemInstruction:{parts:[{text:systemParts.join('\n\n')}]} }:{}),};
    const response=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{
      method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},body:JSON.stringify(body),signal:AbortSignal.timeout(75000),cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok)return failure({provider,model,route,status:response.status,body:data});
    if(!data)return failure({provider,model,route,status:response.status,body:null});
    const text=(data?.candidates?.[0]?.content?.parts||[]).map(p=>p?.text||'').join('').trim();
    if(!text)return failure({provider,model,route,status:response.status,body:{shape:'missing_content'}});
    return {value:{text,provider,model,citations:[]},diagnostic:null};
  }catch(error){return failure({provider,model,route,error})}
}

function selectPrimaryDiagnostic(diagnostics=[]){
  return diagnostics.find(d=>d&&d.error_class!=='ENV_MISSING')||diagnostics.find(Boolean)||safeProviderDiagnostic({error_class:'UNKNOWN_PROVIDER_ERROR'});
}

export async function generateModelResponse(messages,webSearch,settings={},opts={}){
  const excluded=new Set(opts.excludeProviders||[]);
  const mode=settings?.runtime_mode||'openrouter_primary';
  const diagnostics=[];
  const external=[
    ['openrouter',()=>openRouter(messages,webSearch,settings,opts)],
    ['groq',()=>groq(messages,settings,opts)],
    ['gemini',()=>gemini(messages,settings,opts)],
    ['mistral',()=>mistral(messages,settings,opts)],
    ['cerebras',()=>cerebras(messages,settings,opts)],
    ['huggingface',()=>huggingFace(messages,settings,opts)],
  ];
  async function record(result){
    if(result?.diagnostic){
      diagnostics.push(result.diagnostic);
      if(opts.logDiagnostics===true)console.warn('MUS_PROVIDER_DIAGNOSTIC',result.diagnostic);
    }
    return result?.value||null;
  }
  async function tryExternal(){
    for(const [name,run] of external){
      if(excluded.has(name))continue;
      const value=await record(await run());
      if(value)return value;
    }
    return null;
  }
  let value=null;
  // Sovereign guarantee: self_hosted_only never evaluates tryExternal(), even after failure.
  if(mode==='self_hosted_only')value=await record(await selfHosted(messages,settings,opts));
  else if(mode==='self_hosted_primary')value=await record(await selfHosted(messages,settings,opts))||await tryExternal();
  else value=await tryExternal()||await record(await selfHosted(messages,settings,opts));
  if(value)return value;
  if(opts.includeDiagnostics===true){
    const primary=selectPrimaryDiagnostic(diagnostics);
    return Object.freeze({unavailable:true,error_class:primary.error_class,diagnostics:Object.freeze(diagnostics.slice())});
  }
  return null;
}
