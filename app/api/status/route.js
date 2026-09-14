import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL,KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
function client(token){if(!URL||!KEY)return null;return createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}})}

export async function GET(req){
  const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';
  let settings=null;
  try{const sb=client(token);if(sb&&token){const r=await sb.from('control_settings').select('*').maybeSingle();settings=r.data||null}}catch{}
  return NextResponse.json({
    openrouter_configured:!!process.env.OPENROUTER_API_KEY,
    self_hosted_configured:!!(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL),
    settings:settings||{runtime_mode:'openrouter_primary',openrouter_model:process.env.OPENROUTER_MODEL||'openrouter/free',web_search_default:false,save_training_candidates:true,daily_budget_usd:0}
  });
}
