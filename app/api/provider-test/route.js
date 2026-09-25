import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { generateModelResponse } from '../../../lib/aqlevon/providers.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'';
function db(){if(!URL||!KEY)return null;return createClient(URL,KEY,{auth:{persistSession:false}})}

export async function GET(req){
  const q=req.nextUrl.searchParams,token=String(q.get('token')||'');
  const requested=String(q.get('provider')||'aqlevon').toLowerCase();
  const sb=db();if(!sb)return NextResponse.json({message:'db unavailable'},{status:503});
  const gate=await sb.rpc('consume_benchmark_token',{p_token:token});
  if(gate.error||gate.data!==true)return NextResponse.json({message:'denied'},{status:403});

  if(!['aqlevon','self_hosted','aqlevon-engine'].includes(requested)){
    return NextResponse.json({
      message:'AQLEVON runtime only',
      provider:requested,
      external_provider_routing:false
    },{status:410});
  }

  const result=await generateModelResponse(
    [{role:'user',content:'Reply exactly OK'}],
    false,
    {runtime_mode:'self_hosted_only',allow_paid_external:false,public_web_search_enabled:false,temperature:0},
    {includeDiagnostics:true,temperature:0}
  );
  if(!result||result.unavailable){
    return NextResponse.json({
      provider:'aqlevon-engine',
      configured:result?.error_class!=='ENV_MISSING',
      ok:false,
      error_class:result?.error_class||'UNKNOWN_PROVIDER_ERROR',
      external_provider_routing:false
    },{status:503});
  }
  return NextResponse.json({
    provider:'aqlevon-engine',
    configured:true,
    ok:true,
    model:result.model,
    external_provider_routing:false
  });
}
