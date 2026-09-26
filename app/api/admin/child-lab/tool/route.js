import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';
import {executeChildTool} from '../../../../../lib/aqlevon/child-tools.js';
import {redactSecrets} from '../../../../../lib/aqlevon/security.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'https://yaqjhcfitxhtzpaswuif.supabase.co';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_1uRtACKcyT2ZQH9ixdKQ-Q_ARbY6xET';
const ALLOWED=new Set(['web','browser','terminal','files','media']);

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
    const tool=String(body.tool||'').toLowerCase();
    if(!ALLOWED.has(tool))return NextResponse.json({message:'TOOL_NOT_ALLOWED'},{status:400});
    const action=String(body.action||'run').slice(0,120);
    const input=redactSecrets(String(body.input||'')).slice(0,20000);
    if(!input)return NextResponse.json({message:'TOOL_INPUT_REQUIRED'},{status:400});
    const result=await executeChildTool(tool,{
      action,input,
      permissions:body.permissions,
      ownerPolicy:body.owner_policy,
      constraints:{
        ...(body.constraints&&typeof body.constraints==='object'?body.constraints:{}),
        owner_only:true,
        scope:'owner-controlled-child-lab',
      }
    });
    if(!result.ok){
      const status=result.error_class==='PERMISSION_DISABLED'?403:result.error_class==='ADAPTER_REQUIRED'?503:result.error_class==='ACTION_UNKNOWN'?400:502;
      return NextResponse.json({
        message:result.error_class,
        tool,
        required_permissions:result.required_permissions||[],
        missing_permissions:result.missing_permissions||[],
        isolated:true,
        owner_policy:body.owner_policy||null,
        execution_state:'NOT_EXECUTED'
      },{status});
    }
    return NextResponse.json({
      ...result,
      isolated:true,
      execution_state:'EXECUTED_WITH_RECEIPT',
      owner_policy:result.owner_policy||body.owner_policy||null,
    });
  }catch(e){return NextResponse.json({message:e?.message||'CHILD_TOOL_FAILED'},{status:500})}
}
