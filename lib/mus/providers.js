function normalizeEndpoint(raw){
  if(!raw)return null;
  const url=String(raw).replace(/\/$/,'');
  if(url.endsWith('/chat/completions'))return url;
  if(url.endsWith('/v1'))return `${url}/chat/completions`;
  return url;
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

async function openAICompatible({key,url,model,provider,messages,temperature=0.4,headers={},payloadExtra={}}){
  if(!key)return null;
  try{
    const response=await fetch(url,{
      method:'POST',
      headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json',...headers},
      body:JSON.stringify({model,messages,temperature,stream:false,...payloadExtra}),
      signal:AbortSignal.timeout(75000),
      cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok||!data)return null;
    const message=data?.choices?.[0]?.message||{};
    const text=typeof message?.content==='string'?message.content.trim():'';
    return text?{text,provider,model:data?.model||model,citations:extractCitations(message)}:null;
  }catch{return null}
}

async function selfHosted(messages,settings,opts={}){
  if((opts.excludeProviders||[]).includes('mus-engine'))return null;
  const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);
  if(!endpoint)return null;
  try{
    const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;
    const response=await fetch(endpoint,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},
      body:JSON.stringify({
        model:settings?.self_hosted_model||process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',
        messages,
        temperature:Number(opts.temperature??settings?.temperature??0.4),
        stream:false,
      }),
      signal:AbortSignal.timeout(65000),
      cache:'no-store',
    });
    if(!response.ok)return null;
    const data=await response.json().catch(()=>null);
    const message=data?.choices?.[0]?.message||null;
    const text=message?.content||data?.message?.content||data?.response||null;
    return text?{text:String(text).trim(),provider:'mus-engine',model:data?.model||settings?.self_hosted_model||'MUS AI',citations:[]}:null;
  }catch{return null}
}

async function openRouter(messages,webSearch,settings,opts={}){
  const key=process.env.OPENROUTER_API_KEY;
  if(!key)return null;
  let model=settings?.openrouter_model||process.env.OPENROUTER_MODEL||'openrouter/free';
  const allowPaid=!!settings?.allow_paid_external;
  if(!allowPaid&&!String(model).includes(':free')&&model!=='openrouter/free')model='openrouter/free';
  const payloadExtra={};
  if(webSearch&&allowPaid&&settings?.public_web_search_enabled)payloadExtra.plugins=[{id:'web',max_results:5}];
  return openAICompatible({
    key,
    url:'https://openrouter.ai/api/v1/chat/completions',
    model,
    provider:'openrouter',
    messages,
    temperature:Number(opts.temperature??settings?.temperature??0.4),
    headers:{'X-Title':'MUS AI'},
    payloadExtra,
  });
}

async function groq(messages,settings,opts={}){
  return openAICompatible({
    key:process.env.GROQ_API_KEY,
    url:'https://api.groq.com/openai/v1/chat/completions',
    model:process.env.GROQ_MODEL||'openai/gpt-oss-120b',
    provider:'groq',messages,
    temperature:Number(opts.temperature??settings?.temperature??0.4),
    payloadExtra:{reasoning_effort:Number(opts.temperature??0.4)<=0.15?'low':'medium'},
  });
}

async function mistral(messages,settings,opts={}){
  return openAICompatible({key:process.env.MISTRAL_API_KEY,url:'https://api.mistral.ai/v1/chat/completions',model:process.env.MISTRAL_MODEL||'mistral-small-latest',provider:'mistral',messages,temperature:Number(opts.temperature??settings?.temperature??0.4)});
}

async function cerebras(messages,settings,opts={}){
  return openAICompatible({key:process.env.CEREBRAS_API_KEY,url:'https://api.cerebras.ai/v1/chat/completions',model:process.env.CEREBRAS_MODEL||'gpt-oss-120b',provider:'cerebras',messages,temperature:Number(opts.temperature??settings?.temperature??0.4),headers:{'X-Cerebras-Version-Patch':'2'}});
}

async function huggingFace(messages,settings,opts={}){
  if(process.env.HF_FREE_FALLBACK_ENABLED!=='true')return null;
  return openAICompatible({key:process.env.HF_TOKEN,url:'https://router.huggingface.co/v1/chat/completions',model:process.env.HF_MODEL||'openai/gpt-oss-120b:cheapest',provider:'huggingface',messages,temperature:Number(opts.temperature??settings?.temperature??0.4)});
}

async function gemini(messages,settings,opts={}){
  const key=process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY;
  if(!key)return null;
  try{
    const model=process.env.GEMINI_MODEL||'gemini-2.5-flash';
    const systemParts=messages.filter(m=>m.role==='system').map(m=>String(m.content||''));
    const contents=messages.filter(m=>m.role!=='system').map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:String(m.content||'')}]}));
    const body={
      contents,
      generationConfig:{temperature:Number(opts.temperature??settings?.temperature??0.4)},
      ...(systemParts.length?{systemInstruction:{parts:[{text:systemParts.join('\n\n')}]} }:{}),
    };
    const response=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{
      method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},body:JSON.stringify(body),signal:AbortSignal.timeout(75000),cache:'no-store',
    });
    const data=await response.json().catch(()=>null);
    if(!response.ok||!data)return null;
    const text=(data?.candidates?.[0]?.content?.parts||[]).map(p=>p?.text||'').join('').trim();
    return text?{text,provider:'gemini',model,citations:[]}:null;
  }catch{return null}
}

export async function generateModelResponse(messages,webSearch,settings={},opts={}){
  const excluded=new Set(opts.excludeProviders||[]);
  const mode=settings?.runtime_mode||'openrouter_primary';
  const external=[
    ['openrouter',()=>openRouter(messages,webSearch,settings,opts)],
    ['groq',()=>groq(messages,settings,opts)],
    ['gemini',()=>gemini(messages,settings,opts)],
    ['mistral',()=>mistral(messages,settings,opts)],
    ['cerebras',()=>cerebras(messages,settings,opts)],
    ['huggingface',()=>huggingFace(messages,settings,opts)],
  ];
  async function tryExternal(){
    for(const [name,run] of external){
      if(excluded.has(name))continue;
      try{const value=await run();if(value)return value}catch{}
    }
    return null;
  }
  if(mode==='self_hosted_only')return selfHosted(messages,settings,opts);
  if(mode==='self_hosted_primary')return await selfHosted(messages,settings,opts)||await tryExternal();
  return await tryExternal()||await selfHosted(messages,settings,opts);
}
