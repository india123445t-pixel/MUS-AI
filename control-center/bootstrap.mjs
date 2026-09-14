import { mkdir, readFile, writeFile } from 'node:fs/promises';

const ADMIN_RAW='https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/9d286d87dd0ae1309eea3100dedb9f8b1085135a/app/admin/page.js';
async function getAdmin(){
  const r=await fetch(ADMIN_RAW,{cache:'no-store'});
  if(!r.ok) throw new Error(`Failed to fetch admin source: ${r.status}`);
  return r.text();
}
async function local(path){return readFile(new URL(path,import.meta.url),'utf8')}

await mkdir('app/api/status',{recursive:true});
await mkdir('app/api/goal/run',{recursive:true});
await mkdir('app/api/benchmark/run',{recursive:true});
await mkdir('app/api/internal/eval-snapshot',{recursive:true});
await mkdir('app/intelligence',{recursive:true});
await mkdir('public',{recursive:true});

let [page,intelligence,css,icon,benchmarkRoute,evalSnapshotRoute]=await Promise.all([
  getAdmin(),
  local('./intelligence-source.js'),
  local('../app/globals.css'),
  local('../public/icon.svg'),
  local('./templates/benchmark-route.txt'),
  local('./templates/eval-snapshot-route.txt')
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

await Promise.all([
  writeFile('app/page.js',page),
  writeFile('app/intelligence/page.js',intelligence),
  writeFile('app/globals.css',css),
  writeFile('app/layout.js',layout),
  writeFile('app/api/status/route.js',statusRoute),
  writeFile('app/api/goal/run/route.js',goalRoute),
  writeFile('app/api/benchmark/run/route.js',benchmarkRoute),
  writeFile('app/api/internal/eval-snapshot/route.js',evalSnapshotRoute),
  writeFile('public/icon.svg',icon)
]);
console.log('MUS AI Control Center source synchronized.');
