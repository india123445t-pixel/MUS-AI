import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
function bearer(req){const h=req.headers.get('authorization')||'';return h.startsWith('Bearer ')?h.slice(7).trim():''}
function client(token){if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');return createClient(SUPABASE_URL,SUPABASE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false,autoRefreshToken:false}})}

export async function PATCH(req){
  try{
    const token=bearer(req);if(!token)return NextResponse.json({message:'TOKEN_MISSING'},{status:401});
    const sb=client(token);const auth=await sb.auth.getUser(token);const user=auth.data?.user;if(auth.error||!user)return NextResponse.json({message:'SESSION_INVALID'},{status:401});
    const owner=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();if(owner.error||!owner.data)return NextResponse.json({message:'OWNER_REQUIRED'},{status:403});
    const body=await req.json();const taskId=String(body.task_id||'');const action=String(body.action||'');if(!taskId)return NextResponse.json({message:'TASK_ID_REQUIRED'},{status:400});
    const current=await sb.from('aqlevon_tasks').select('id,phase,outcome,title,scope').eq('id',taskId).maybeSingle();if(current.error||!current.data)return NextResponse.json({message:'TASK_NOT_FOUND'},{status:404});
    if(action==='approve'){
      if(current.data.phase!=='OPEN')return NextResponse.json({message:'يمكن اعتماد Mission وهي OPEN فقط.'},{status:409});
      const scope={...(current.data.scope||{}),executor_state:'NOT_CONNECTED',owner_approved:true,owner_approved_at:new Date().toISOString()};
      const updated=await sb.from('aqlevon_tasks').update({phase:'READY',scope,updated_at:new Date().toISOString()}).eq('id',taskId).eq('phase','OPEN').select('id,phase,outcome,title,scope,updated_at').maybeSingle();if(updated.error)throw updated.error;
      if(!updated.data)return NextResponse.json({message:'Mission تغيّرت قبل الموافقة. حدّث الحالة وراجعها من جديد.'},{status:409});
      await sb.from('aqlevon_audit_events').insert({owner_id:user.id,task_id:taskId,event_type:'OWNER_APPROVED_MISSION',subject_type:'TASK',subject_ref:taskId,event_data:{executor_state:scope.executor_state||'NOT_CONNECTED'}});
      const message='تم اعتماد Mission. لا يوجد Executor Adapter متصل بعد، لذلك لم يبدأ أي تنفيذ خارجي ولم يتم ادعاء نجاح مزيف.';
      return NextResponse.json({task:updated.data,message});
    }
    if(action==='cancel'){
      if(current.data.phase==='CLOSED')return NextResponse.json({message:'Mission مغلقة بالفعل.'},{status:409});
      const updated=await sb.from('aqlevon_tasks').update({phase:'CLOSED',outcome:'CANCELLED',updated_at:new Date().toISOString()}).eq('id',taskId).select('id,phase,outcome,title,scope,updated_at').single();if(updated.error)throw updated.error;
      await sb.from('aqlevon_audit_events').insert({owner_id:user.id,task_id:taskId,event_type:'OWNER_CANCELLED_MISSION',subject_type:'TASK',subject_ref:taskId,event_data:{}});
      return NextResponse.json({task:updated.data,message:'تم إلغاء Mission.'});
    }
    if(action==='stop'){
      const inFlight=await sb.from('aqlevon_action_attempts').select('id').eq('task_id',taskId).eq('phase','IN_FLIGHT').limit(1);
      if(inFlight.error)throw inFlight.error;
      if(!(inFlight.data||[]).length)return NextResponse.json({message:'لا توجد ActionAttempt حقيقية In-Flight لإيقافها.'},{status:409});
      await sb.from('aqlevon_audit_events').insert({owner_id:user.id,task_id:taskId,event_type:'OWNER_STOP_REQUESTED',subject_type:'TASK',subject_ref:taskId,event_data:{dispatch_stop_supported:false}});
      return NextResponse.json({message:'تم تسجيل STOP REQUEST، لكن لا يوجد Executor cancellation adapter مربوط بهذا الإصدار؛ لم يتم ادعاء أن العملية الخارجية توقفت.'},{status:409});
    }
    return NextResponse.json({message:'ACTION_NOT_SUPPORTED'},{status:400});
  }catch(error){return NextResponse.json({message:error?.message||'تعذر تحديث Mission.'},{status:500})}
}