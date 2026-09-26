import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {redactSecrets} from '../../../../lib/aqlevon/security.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'';

function bearer(req){const value=req.headers.get('authorization')||'';return value.startsWith('Bearer ')?value.slice(7).trim():''}
function client(token){if(!URL||!KEY)throw new Error('ENV_MISSING');return createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false,autoRefreshToken:false}})}
function safe(value){return Object.freeze(JSON.parse(redactSecrets(JSON.stringify(value))))}
async function owner(req){
  const token=bearer(req);if(!token)return {error:NextResponse.json({message:'TOKEN_MISSING'},{status:401})};
  const sb=client(token);const auth=await sb.auth.getUser(token);const user=auth.data?.user;
  if(auth.error||!user)return {error:NextResponse.json({message:'SESSION_INVALID'},{status:401})};
  const own=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();
  if(own.error||!own.data)return {error:NextResponse.json({message:'OWNER_REQUIRED'},{status:403})};
  return {sb,user};
}

export async function GET(req){
  try{
    const gate=await owner(req);if(gate.error)return gate.error;
    const rows=await gate.sb.from('workbench_logs').select('id,tool,action,level,ok,error_class,state,latency_ms,created_at').eq('user_id',gate.user.id).order('created_at',{ascending:false}).limit(50);
    if(rows.error)throw new Error('WORKBENCH_LOG_READ_FAILED');
    return NextResponse.json(safe({logs:rows.data||[]}),{headers:{'Cache-Control':'no-store'}});
  }catch(error){
    return NextResponse.json({message:redactSecrets(error?.message||'WORKBENCH_LOGS_FAILED')},{status:500});
  }
}