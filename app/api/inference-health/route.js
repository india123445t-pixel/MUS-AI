import { NextResponse } from 'next/server';
import { checkSelfHostedHealth } from '../../../lib/aqlevon/providers.js';

function classify(status){
  if(status===401||status===403)return 'AUTH_ERROR';
  if(status===429)return 'RATE_LIMIT';
  if(status>=500)return 'UPSTREAM_5XX';
  if(status===0)return 'NETWORK_ERROR';
  return 'UNKNOWN_PROVIDER_ERROR';
}
async function probe({configured,url,headers={}}){
  if(!configured)return {configured:false,ok:false,status:0,error_class:'ENV_MISSING'};
  try{
    const r=await fetch(url,{headers,cache:'no-store',signal:AbortSignal.timeout(5000)});
    return {configured:true,ok:r.ok,status:r.status,error_class:r.ok?null:classify(r.status)};
  }catch{return {configured:true,ok:false,status:0,error_class:'NETWORK_ERROR'}}
}
async function providerHealth(){
  const openrouterKey=process.env.OPENROUTER_API_KEY||'';
  const groqKey=process.env.GROQ_API_KEY||'';
  const geminiKey=process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY||'';
  const mistralKey=process.env.MISTRAL_API_KEY||'';
  const cerebrasKey=process.env.CEREBRAS_API_KEY||'';
  const hfKey=process.env.HF_FREE_FALLBACK_ENABLED==='true'?(process.env.HF_TOKEN||''):'';
  const [openrouter,groq,gemini,mistral,cerebras,huggingface,selfHosted]=await Promise.all([
    probe({configured:!!openrouterKey,url:'https://openrouter.ai/api/v1/key',headers:{Authorization:`Bearer ${openrouterKey}`}}),
    probe({configured:!!groqKey,url:'https://api.groq.com/openai/v1/models',headers:{Authorization:`Bearer ${groqKey}`}}),
    probe({configured:!!geminiKey,url:'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1',headers:{'x-goog-api-key':geminiKey}}),
    probe({configured:!!mistralKey,url:'https://api.mistral.ai/v1/models',headers:{Authorization:`Bearer ${mistralKey}`}}),
    probe({configured:!!cerebrasKey,url:'https://api.cerebras.ai/v1/models',headers:{Authorization:`Bearer ${cerebrasKey}`}}),
    probe({configured:!!hfKey,url:'https://huggingface.co/api/whoami-v2',headers:{Authorization:`Bearer ${hfKey}`}}),
    checkSelfHostedHealth({}, {timeoutMs:5000}),
  ]);
  return {openrouter,groq,gemini,mistral,cerebras,huggingface,self_hosted:selfHosted};
}
export async function GET(){
  const providers=await providerHealth();
  const ready=Object.values(providers).some(x=>x?.ok===true);
  const configured=Object.values(providers).filter(x=>x?.configured===true);
  const primaryError=ready?null:(configured.find(x=>x.error_class&&x.error_class!=='ENV_MISSING')?.error_class||'ENV_MISSING');
  return NextResponse.json({
    providers,
    openrouter:providers.openrouter,
    inference_ready:ready,
    primary_error_class:primaryError,
  },{headers:{'Cache-Control':'no-store'}});
}
