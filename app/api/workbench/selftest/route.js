import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {runAdapterSelfTest} from '../../../../lib/aqlevon/workbench.js';
import {redactSecrets} from '../../../../lib/aqlevon/security.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'';
const ALLOWED=new Set(['web','browser','terminal','files','media']);
const LEVELS=new Set(['L1','L2','L3']);

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

export async function POST(req){
  try{
    const gate=await owner(req);if(gate.error)return gate.error;
    const body=await req.json();
    const tool=String(body?.tool||'').toLowerCase();
    const level=String(body?.level||'L1').toUpperCase();
    if(!ALLOWED.has(tool))return NextResponse.json({ok:false,error_class:'TOOL_UNKNOWN',state:'TOOL_UNKNOWN'},{status:200});
    if(!LEVELS.has(level))return NextResponse.json({ok:false,error_class:'SELFTEST_LEVEL_UNKNOWN',state:'SELFTEST_LEVEL_UNKNOWN'},{status:200});
    const result=await runAdapterSelfTest(tool,{level,permissions:body?.permissions,ownerPolicy:body?.ownerPolicy});
    const row={
      user_id:gate.user.id,
      tool:redactSecrets(tool),
      action:redactSecrets(level==='L3'&&tool==='web'?'research':'aqlevon.ping'),
      level:redactSecrets(level),
      ok:result.ok===true,
      error_class:result.error_class?redactSecrets(String(result.error_class)):null,
      state:result.state?redactSecrets(String(result.state)):null,
      latency_ms:Number(result.latency_ms||0),
    };
    const saved=await gate.sb.from('workbench_logs').insert(row).select('id,created_at').single();
    if(saved.error)return NextResponse.json(safe({...result,log_written:false,log_error:'WORKBENCH_LOG_WRITE_FAILED'}),{status:200});
    return NextResponse.json(safe({...result,log_written:true,log_id:saved.data?.id||null,created_at:saved.data?.created_at||null}),{status:200});
  }catch(error){
    return NextResponse.json({message:redactSecrets(error?.message||'WORKBENCH_SELFTEST_FAILED')},{status:500});
  }
}