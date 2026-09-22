import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'';

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

function client(token){
  if(!URL||!KEY)throw new Error('Supabase environment is not configured.');
  return createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}});
}

export async function GET(req){
  try{
    const auth=req.headers.get('authorization')||'';
    const token=auth.startsWith('Bearer ')?auth.slice(7):'';
    if(!token)return NextResponse.json({message:'يلزم تسجيل الدخول.'},{status:401});

    const sb=client(token);
    const userResult=await sb.auth.getUser();
    if(userResult.error||!userResult.data?.user)return NextResponse.json({message:'جلسة غير صالحة.'},{status:401});

    const [snapshotResult,runtimeResult]=await Promise.all([
      sb.rpc('get_aqlevon_intelligence_snapshot'),
      sb.rpc('get_aqlevon_runtime_config')
    ]);
    if(snapshotResult.error)throw snapshotResult.error;
    if(runtimeResult.error)throw runtimeResult.error;

    const settings=runtimeResult.data||{};
    const providers=providerFlags();
    const paidBlocked=settings.allow_paid_external===false&&settings.allow_paid_gpu!==true&&Number(settings.daily_budget_usd||0)===0;

    return NextResponse.json({
      ok:true,
      snapshot:snapshotResult.data||{},
      runtime:{
        ...settings,
        zero_cost_guard:paidBlocked,
        provider_flags:providers,
        configured_zero_cost_provider_count:Object.values(providers).filter(Boolean).length
      },
      evidence_policy:{
        unseen_first_exposure_required:true,
        teacher_generated_hidden_benchmark:false,
        public_feedback_auto_gold:false,
        weights_trained:false
      }
    },{headers:{'Cache-Control':'no-store'}});
  }catch(e){
    return NextResponse.json({message:e?.message||'تعذر تحميل حالة التقييم.'},{status:500});
  }
}
