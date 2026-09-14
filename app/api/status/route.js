import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function sb(){if(!SUPABASE_URL||!SUPABASE_KEY)return null;return createClient(SUPABASE_URL,SUPABASE_KEY,{auth:{persistSession:false}})}
const defaultSettings={runtime_mode:'openrouter_primary',openrouter_model:process.env.OPENROUTER_MODEL||'openrouter/free',web_search_default:false,temperature:0.6,max_history:16,save_training_candidates:true,allow_paid_external:false,daily_budget_usd:0,public_chat_enabled:true,public_training_enabled:true,public_web_search_enabled:false,public_rate_limit_per_hour:30,public_daily_limit:120,install_enabled:true};

function manifestResponse(){
  const icons=[{src:'/icon.svg',sizes:'192x192',type:'image/svg+xml',purpose:'any'},{src:'/icon.svg',sizes:'512x512',type:'image/svg+xml',purpose:'any maskable'}];
  const manifest={name:'MUS AI',short_name:'MUS AI',description:'MUS AI — Learn · Create · Evolve',id:'/',start_url:'/?source=pwa',scope:'/',display:'standalone',display_override:['standalone','minimal-ui'],orientation:'any',background_color:'#06101e',theme_color:'#07111f',lang:'ar',dir:'rtl',categories:['productivity','education','utilities'],icons,shortcuts:[{name:'محادثة جديدة',short_name:'دردشة',url:'/?new=1',icons:[icons[0]]}]};
  return new Response(JSON.stringify(manifest),{status:200,headers:{'Content-Type':'application/manifest+json; charset=utf-8','Cache-Control':'public, max-age=3600'}});
}
function serviceWorkerResponse(){
  const js=`const C='mus-ai-shell-v5';self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/icon.svg'])))});self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(xs=>Promise.all(xs.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()))});self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==location.origin||u.pathname.startsWith('/api/chat')||u.pathname.startsWith('/admin'))return;if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).then(r=>{const c=r.clone();caches.open(C).then(x=>x.put('/',c));return r}).catch(()=>caches.match('/')));return}e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))})`;
  return new Response(js,{status:200,headers:{'Content-Type':'application/javascript; charset=utf-8','Service-Worker-Allowed':'/','Cache-Control':'no-cache, no-store, must-revalidate'}});
}

export async function GET(req){
  const search=req.nextUrl?.searchParams||new URLSearchParams(String(req.url||'').split('?')[1]||'');
  if(search.get('icon')==='1')return new Response(null,{status:307,headers:{Location:'/icon.svg','Cache-Control':'public, max-age=3600'}});
  if(search.get('manifest')==='1')return manifestResponse();
  if(search.get('sw')==='1')return serviceWorkerResponse();
  let settings=defaultSettings;
  try{const client=sb();if(client){const r=await client.rpc('get_mus_runtime_config');if(r.data)settings={...defaultSettings,...r.data}}}catch{}
  return NextResponse.json({openrouter_configured:!!process.env.OPENROUTER_API_KEY,self_hosted_configured:!!(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL),settings},{headers:{'Cache-Control':'no-store'}});
}

export async function POST(req){
  try{
    const body=await req.json();
    if(body?.action!=='feedback')return NextResponse.json({message:'إجراء غير صالح.'},{status:400});
    const rating=body.rating==='good'?'good':body.rating==='bad'?'bad':null;
    if(!rating||!body.chatLogId||!body.sessionId)return NextResponse.json({message:'بيانات التقييم غير مكتملة.'},{status:400});
    const client=sb();if(!client)return NextResponse.json({message:'قاعدة البيانات غير متاحة.'},{status:503});
    const {data,error}=await client.rpc('log_public_feedback',{p_chat_log_id:body.chatLogId,p_session_id:body.sessionId,p_rating:rating,p_note:body.note?String(body.note).slice(0,2000):null});
    if(error)throw error;
    return NextResponse.json({ok:true,id:data});
  }catch(e){return NextResponse.json({message:e?.message||'تعذر حفظ التقييم.'},{status:500})}
}
