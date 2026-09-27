import {NextResponse} from 'next/server';
import {createClient} from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'';

function bearer(req){
  const header=req.headers.get('authorization')||'';
  return header.startsWith('Bearer ')?header.slice(7).trim():'';
}

export async function requireSystemOwner(req){
  const token=bearer(req);
  if(!token)return {error:NextResponse.json({message:'TOKEN_MISSING'},{status:401,headers:{'Cache-Control':'no-store'}})};
  if(!URL||!KEY)return {error:NextResponse.json({message:'OWNER_AUTH_UNAVAILABLE',error_class:'ENV_MISSING'},{status:503,headers:{'Cache-Control':'no-store'}})};
  try{
    const sb=createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false,autoRefreshToken:false}});
    const auth=await sb.auth.getUser(token);
    const user=auth.data?.user;
    if(auth.error||!user)return {error:NextResponse.json({message:'SESSION_INVALID'},{status:401,headers:{'Cache-Control':'no-store'}})};
    const owner=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();
    if(owner.error||!owner.data)return {error:NextResponse.json({message:'OWNER_REQUIRED'},{status:403,headers:{'Cache-Control':'no-store'}})};
    return {user,sb};
  }catch{
    return {error:NextResponse.json({message:'OWNER_AUTH_UNAVAILABLE',error_class:'AUTH_CONTROL_PLANE_ERROR'},{status:503,headers:{'Cache-Control':'no-store'}})};
  }
}
