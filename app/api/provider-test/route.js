import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'https://qkoscgdegnqcypkjrefn.supabase.co';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_wGDAyv5bwOrGjNX6QK0KzQ_K_xWI6w8';
function db(){if(!URL||!KEY)return null;return createClient(URL,KEY,{auth:{persistSession:false}})}
async function postJson(url,headers,body){
  try{
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
    const d=await r.json().catch(()=>null);
    return {ok:r.ok,status:r.status,data:d};
  }catch(e){return {ok:false,status:0,data:{error:{message:e?.message||'network_error'}}}}
}
function msg(d){return String(d?.error?.message||d?.message||'').slice(0,300)}

export async function GET(req){
  const q=req.nextUrl.searchParams,token=String(q.get('token')||''),provider=String(q.get('provider')||'');
  const sb=db();if(!sb)return NextResponse.json({message:'db unavailable'},{status:503});
  const gate=await sb.rpc('consume_benchmark_token',{p_token:token});
  if(gate.error||gate.data!==true)return NextResponse.json({message:'denied'},{status:403});

  if(provider==='groq'){
    const key=process.env.GROQ_API_KEY;if(!key)return NextResponse.json({provider,configured:false,ok:false});
    const model=process.env.GROQ_MODEL||'openai/gpt-oss-120b';
    const r=await postJson('https://api.groq.com/openai/v1/chat/completions',{Authorization:`Bearer ${key}`},{model,messages:[{role:'user',content:'Reply exactly OK'}],max_completion_tokens:24,temperature:0});
    return NextResponse.json({provider,configured:true,ok:r.ok,status:r.status,model,error:r.ok?null:msg(r.data)});
  }
  if(provider==='gemini'){
    const key=process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY;if(!key)return NextResponse.json({provider,configured:false,ok:false});
    const model=process.env.GEMINI_MODEL||'gemini-2.5-flash';
    const r=await postJson(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{'x-goog-api-key':key},{contents:[{role:'user',parts:[{text:'Reply exactly OK'}]}],generationConfig:{temperature:0,maxOutputTokens:24}});
    return NextResponse.json({provider,configured:true,ok:r.ok,status:r.status,model,error:r.ok?null:msg(r.data)});
  }
  if(provider==='mistral'){
    const key=process.env.MISTRAL_API_KEY;if(!key)return NextResponse.json({provider,configured:false,ok:false});
    const model=process.env.MISTRAL_MODEL||'mistral-small-latest';
    const r=await postJson('https://api.mistral.ai/v1/chat/completions',{Authorization:`Bearer ${key}`},{model,messages:[{role:'user',content:'Reply exactly OK'}],max_tokens:24,temperature:0});
    return NextResponse.json({provider,configured:true,ok:r.ok,status:r.status,model,error:r.ok?null:msg(r.data)});
  }
  return NextResponse.json({message:'unknown provider'},{status:400});
}
