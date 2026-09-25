import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {evaluateChildTeachingCandidate} from '../../../../../lib/aqlevon/child-eval.js';

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
    const result=evaluateChildTeachingCandidate(body?.candidate);
    return NextResponse.json({
      evaluation:result,
      execution_state:'EVALUATED_ONLY',
      training_started:false,
      gpu_requested:false,
      production_weight_write:false,
      training_lane_write:false,
      worker03_access:false,
    });
  }catch(e){return NextResponse.json({message:e?.message||'CHILD_EVAL_FAILED',training_started:false},{status:400})}
}
