import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {generateChildResponse} from '../../../../../lib/aqlevon/child-runtime.js';
import {redactSecrets,sanitizeHistory} from '../../../../../lib/aqlevon/security.js';

export const maxDuration=300;
export const dynamic='force-dynamic';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function bearer(req){const h=req.headers.get('authorization')||'';return h.startsWith('Bearer ')?h.slice(7).trim():''}
function client(token){if(!URL||!KEY)throw new Error('Supabase environment is not configured.');return createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false,autoRefreshToken:false}})}
async function owner(req){
  const token=bearer(req);if(!token)return {error:NextResponse.json({message:'TOKEN_MISSING'},{status:401})};
  const sb=client(token);const auth=await sb.auth.getUser(token);const user=auth.data?.user;
  if(auth.error||!user)return {error:NextResponse.json({message:'SESSION_INVALID'},{status:401})};
  const own=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();
  if(own.error||!own.data)return {error:NextResponse.json({message:'OWNER_REQUIRED'},{status:403})};
  return {user};
}

export async function POST(req){
  try{
    const gate=await owner(req);if(gate.error)return gate.error;
    const body=await req.json();
    const input=redactSecrets(String(body.input||'').trim());
    if(!input)return NextResponse.json({message:'اكتب للطفل أولًا.'},{status:400});
    if(input.length>20000)return NextResponse.json({message:'الطلب طويل جدًا.'},{status:413});
    const persona=redactSecrets(String(body.persona||'')).slice(0,12000);
    const lessons=Array.isArray(body.lessons)?body.lessons.map(x=>redactSecrets(String(x))).slice(-30):[];
    const memories=Array.isArray(body.memories)?body.memories.slice(0,24).map(x=>({
      id:String(x?.id||'').slice(0,120),
      kind:String(x?.kind||'memory').slice(0,60),
      topic:String(x?.topic||'general').slice(0,120),
      text:redactSecrets(String(x?.text||'')).slice(0,1800),
      relevance_score:Number(x?.relevance_score||0)
    })):[];
    const history=sanitizeHistory(body.history,24);
    const trial=body.trial&&typeof body.trial==='object'?{
      goal:String(body.trial.goal||'').slice(0,3000),
      success_criteria:String(body.trial.success_criteria||'').slice(0,3000),
      mode:String(body.trial.mode||'sandbox').slice(0,100),
    }:null;
    const result=await generateChildResponse({
      messages:[...history,{role:'user',content:input}],
      persona,lessons,memories,trial,temperature:0.5
    });
    if(!result||result.unavailable)return NextResponse.json({
      message:'Runtime الطفل غير متصل بعد.',
      error_class:result?.error_class||'CHILD_RUNTIME_UNAVAILABLE',
      isolated:true
    },{status:503});
    return NextResponse.json({
      text:result.text,
      model:result.model,
      runtime:'AQLEVON_CHILD_RUNTIME_V1',
      isolated:true,
      production_weight_write:false,
      training_lane_write:false,
      execution_state:'LAB_ONLY'
    });
  }catch(e){return NextResponse.json({message:e?.message||'CHILD_LAB_FAILED'},{status:500})}
}
