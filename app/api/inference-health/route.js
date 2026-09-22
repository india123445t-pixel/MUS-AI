import { NextResponse } from 'next/server';

function providerFlags(){
  return {
    openrouter:!!process.env.OPENROUTER_API_KEY,
    groq:!!process.env.GROQ_API_KEY,
    gemini:!!(process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY),
    mistral:!!process.env.MISTRAL_API_KEY,
    cerebras:!!process.env.CEREBRAS_API_KEY,
    huggingface:!!process.env.HF_TOKEN&&process.env.HF_FREE_FALLBACK_ENABLED==='true',
    self_hosted:!!(process.env.AQLEVON_MODEL_URL||process.env.LOCAL_MODEL_URL)
  };
}
async function checkOpenRouter(){
  const key=process.env.OPENROUTER_API_KEY;
  if(!key)return {configured:false,ok:false,status:0,error_class:'ENV_MISSING'};
  try{
    const r=await fetch('https://openrouter.ai/api/v1/key',{headers:{Authorization:`Bearer ${key}`},cache:'no-store',signal:AbortSignal.timeout(5000)});
    return {configured:true,ok:r.ok,status:r.status,error_class:r.ok?null:(r.status===401||r.status===403?'AUTH_ERROR':r.status===429?'RATE_LIMIT':r.status>=500?'UPSTREAM_5XX':'UNKNOWN_PROVIDER_ERROR')};
  }catch{return {configured:true,ok:false,status:0,error_class:'NETWORK_ERROR'}}
}
export async function GET(){
  const providers=providerFlags();
  const openrouter=await checkOpenRouter();
  const fallbackConfigured=Object.entries(providers).some(([name,value])=>name!=='openrouter'&&!!value);
  const inference_ready=openrouter.ok||fallbackConfigured;
  const primary_error_class=inference_ready?null:(openrouter.error_class||'NO_PROVIDER');
  return NextResponse.json({providers,openrouter,fallback_configured:fallbackConfigured,inference_ready,primary_error_class},{headers:{'Cache-Control':'no-store'}});
}
