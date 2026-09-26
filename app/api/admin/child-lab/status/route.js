import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {childHealth} from '../../../../../lib/aqlevon/child-runtime.js';
import {childToolStatus} from '../../../../../lib/aqlevon/child-tools.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'https://yaqjhcfitxhtzpaswuif.supabase.co';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_1uRtACKcyT2ZQH9ixdKQ-Q_ARbY6xET';

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

export async function GET(req){
  try{
    const gate=await owner(req);if(gate.error)return gate.error;
    const health=await childHealth();
    return NextResponse.json({
      isolated:true,
      runtime:'AQLEVON_CHILD_RUNTIME_V1',
      child_model_configured:health.configured===true,
      child_model_ready:health.ok===true,
      health,
      policy_mode:'owner-controlled',
      owner_policy_source:'client-owner-session',
      memory_scope:'child-lab-only',
      tools:childToolStatus()
    },{headers:{'Cache-Control':'no-store'}});
  }catch(e){return NextResponse.json({message:e?.message||'CHILD_LAB_STATUS_FAILED'},{status:500})}
}
