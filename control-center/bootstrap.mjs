import { mkdir, writeFile } from 'node:fs/promises';

const RAW='https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/main';
const ADMIN_RAW='https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/9d286d87dd0ae1309eea3100dedb9f8b1085135a/app/admin/page.js';
async function get(path){
  const r=await fetch(`${RAW}/${path}`,{cache:'no-store'});
  if(!r.ok) throw new Error(`Failed to fetch ${path}: ${r.status}`);
  return r.text();
}
async function getAdmin(){
  const r=await fetch(ADMIN_RAW,{cache:'no-store'});
  if(!r.ok) throw new Error(`Failed to fetch admin source: ${r.status}`);
  return r.text();
}

await mkdir('app/api/status',{recursive:true});
await mkdir('app/api/goal/run',{recursive:true});
await mkdir('app/api/benchmark/run',{recursive:true});
await mkdir('app/intelligence',{recursive:true});
await mkdir('public',{recursive:true});

let [page,intelligence,css,icon]=await Promise.all([
  getAdmin(),
  get('control-center/intelligence-source.js'),
  get('app/globals.css'),
  get('public/icon.svg')
]);

const envLine="const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'https://yaqjhcfitxhtzpaswuif.supabase.co',KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_1uRtACKcyT2ZQH9ixdKQ-Q_ARbY6xET';";
page=page
  .replace("const URL=process.env.NEXT_PUBLIC_SUPABASE_URL,KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;",envLine)
  .replaceAll('src="/api/status?icon=1"','src="/icon.svg"')
  .replace('href="/" target="_blank">فتح تطبيق MUS AI ↗</a>','href="/intelligence">Intelligence Lab</a><a href="https://ibn-ai-opal.vercel.app/" target="_blank">فتح تطبيق MUS AI ↗</a>');
intelligence=intelligence.replace("const URL=process.env.NEXT_PUBLIC_SUPABASE_URL,KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;",envLine);

const layout=`import './globals.css';
export const metadata={title:'MUS AI Control Center',description:'Private MUS AI administration and model control center',robots:{index:false,follow:false}};
export const viewport={themeColor:'#07111f',width:'device-width',initialScale:1};
export default function RootLayout({children}){return <html lang="ar" dir="rtl"><body>{children}</body></html>}`;

const statusRoute=`const BASE=process.env.MUS_PUBLIC_APP_URL||'https://ibn-ai-opal.vercel.app';
export async function GET(){
  try{const r=await fetch(BASE+'/api/status',{cache:'no-store'});const body=await r.text();return new Response(body,{status:r.status,headers:{'content-type':r.headers.get('content-type')||'application/json','cache-control':'no-store'}})}catch{return Response.json({message:'تعذر الاتصال بتطبيق MUS AI.'},{status:502})}
}`;

const goalRoute=`const BASE=process.env.MUS_PUBLIC_APP_URL||'https://ibn-ai-opal.vercel.app';
export async function POST(req){
  try{const auth=req.headers.get('authorization')||'';const body=await req.text();const r=await fetch(BASE+'/api/goal/run',{method:'POST',headers:{'content-type':'application/json',...(auth?{authorization:auth}:{})},body:body||'{}',cache:'no-store'});const text=await r.text();return new Response(text,{status:r.status,headers:{'content-type':r.headers.get('content-type')||'application/json','cache-control':'no-store'}})}catch{return Response.json({message:'تعذر تشغيل دورة MUS AI.'},{status:502})}
}`;

const benchmarkRoute=`import { createClient } from '@supabase/supabase-js';
const URL=process.env.NEXT_PUBLIC_SUPABASE_URL,KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const BASE=process.env.MUS_PUBLIC_APP_URL||'https://ibn-ai-opal.vercel.app';
function parseFinalInteger(text=''){const m=String(text).match(/(?:^|\\n)\\s*FINAL\\s*[:=]\\s*(-?\\d+)\\s*(?:$|\\n)/i);return m?Number(m[1]):null}
function client(token){if(!URL||!KEY)throw new Error('Supabase environment is not configured.');return createClient(URL,KEY,{global:{headers:{Authorization:\`Bearer \${token}\`}},auth:{persistSession:false}})}
export async function POST(req){
 try{
  const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';if(!token)return Response.json({message:'يلزم تسجيل الدخول.'},{status:401});
  const sb=client(token),ur=await sb.auth.getUser(),u=ur.data?.user;if(!u)return Response.json({message:'جلسة غير صالحة.'},{status:401});
  const skills=(await sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true}).order('attempts',{ascending:true})).data||[];
  let selected=null,target=null;
  for(const s of skills){
   const cr=await sb.from('benchmark_cases').select('*').eq('active',true).eq('domain',s.domain).order('difficulty',{ascending:false}).limit(40);
   const eligible=(cr.data||[]).filter(c=>c.rubric?.held_out===true&&c.rubric?.teacher_generated===false&&c.rubric?.answer_type==='integer'&&Number.isFinite(Number(c.rubric?.exact_value)));
   if(!eligible.length)continue;
   const ids=eligible.map(c=>c.id),prior=(await sb.from('benchmark_results').select('benchmark_case_id').in('benchmark_case_id',ids)).data||[],seen=new Set(prior.map(r=>r.benchmark_case_id));
   selected=eligible.find(c=>!seen.has(c.id))||null;if(selected){target=s;break}
  }
  if(!selected)return Response.json({message:'لا يوجد Benchmark يدوي held-out غير مُختبر وله oracle حتمي.'},{status:409});
  const prompt=String(selected.prompt||'').trim();if(!prompt)return Response.json({message:'Benchmark غير صالح.'},{status:422});
  const sessionId=crypto.randomUUID(),conversationId=crypto.randomUUID();
  const r=await fetch(BASE+'/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({input:prompt+'\\n\\nاختم إجابتك بسطر مستقل بالشكل FINAL: <number>.',history:[],webSearch:false,sessionId,conversationId}),cache:'no-store'});
  const d=await r.json().catch(()=>({}));if(!r.ok||!d?.text)return Response.json({message:d?.message||'تعذر تشغيل MUS AI على الاختبار.'},{status:r.status||502});
  const got=parseFinalInteger(d.text),expected=Number(selected.rubric.exact_value),score=got===expected?100:0;
  const ins=await sb.from('benchmark_results').insert({owner_id:u.id,benchmark_case_id:selected.id,model_label:'MUS AI public runtime',answer:d.text,score,judge:'exact_integer_oracle',metadata:{held_out:true,teacher_generated:false,objective_verification:true,verification_method:'exact_integer_oracle',expected,observed:got,provider:d.provider||'mus-ai',model:d.model||'MUS AI',cost_usd:0}}).select('id').single();if(ins.error)throw ins.error;
  const old=Number(target?.score)||0,attempts=(Number(target?.attempts)||0)+1,wins=(Number(target?.wins)||0)+(score>=85?1:0),next=Number((Number(target?.attempts)>0?old*0.7+score*0.3:score).toFixed(2));
  await sb.from('skill_state').upsert({owner_id:u.id,domain:selected.domain,score:next,attempts,wins,updated_at:new Date().toISOString()},{onConflict:'owner_id,domain'});
  return Response.json({ok:true,benchmark_id:selected.id,suite:selected.suite,domain:selected.domain,difficulty:selected.difficulty,score,expected,observed:got,new_skill_score:next,cost_usd:0,verified:true,verification_method:'exact_integer_oracle'});
 }catch(e){return Response.json({message:e?.message||'فشل تشغيل Benchmark.'},{status:500})}
}`;

await Promise.all([
  writeFile('app/page.js',page),
  writeFile('app/intelligence/page.js',intelligence),
  writeFile('app/globals.css',css),
  writeFile('app/layout.js',layout),
  writeFile('app/api/status/route.js',statusRoute),
  writeFile('app/api/goal/run/route.js',goalRoute),
  writeFile('app/api/benchmark/run/route.js',benchmarkRoute),
  writeFile('public/icon.svg',icon)
]);
console.log('MUS AI Control Center source synchronized.');
