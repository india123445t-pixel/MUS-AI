import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {buildChildTeachingCandidate,evaluateChildCandidate} from '../../../../../lib/aqlevon/child-candidate.js';

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

export async function POST(req){
  try{
    const gate=await owner(req);if(gate.error)return gate.error;
    const body=await req.json();
    const candidate=buildChildTeachingCandidate({
      persona:body.persona,
      lessons:Array.isArray(body.lessons)?body.lessons:[],
      examples:Array.isArray(body.examples)?body.examples:[],
      trials:Array.isArray(body.trials)?body.trials:[],
    });
    const evaluation=evaluateChildCandidate(candidate);
    return NextResponse.json({
      candidate,
      evaluation,
      isolated:true,
      execution_state:'PACKAGED_ONLY',
      training_started:false,
      gpu_requested:false,
      production_weight_write:false,
      training_lane_write:false,
      worker03_access:false,
      automatic_promotion:false,
    });
  }catch(e){
    return NextResponse.json({message:e?.message||'CHILD_CANDIDATE_FAILED',training_started:false},{status:400});
  }
}
