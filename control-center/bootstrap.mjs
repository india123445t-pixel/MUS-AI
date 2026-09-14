import { mkdir, writeFile } from 'node:fs/promises';

const RAW='https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/main';
async function get(path){
  const r=await fetch(`${RAW}/${path}`,{cache:'no-store'});
  if(!r.ok) throw new Error(`Failed to fetch ${path}: ${r.status}`);
  return r.text();
}

await mkdir('app/api/status',{recursive:true});
await mkdir('app/api/goal/run',{recursive:true});
await mkdir('public',{recursive:true});

let [page,css,icon]=await Promise.all([
  get('app/admin/page.js'),
  get('app/globals.css'),
  get('public/icon.svg')
]);

page=page
  .replaceAll('src="/api/status?icon=1"','src="/icon.svg"')
  .replace('href="/" target="_blank"','href="https://ibn-ai-opal.vercel.app/" target="_blank"');

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
  writeFile('app/globals.css',css),
  writeFile('app/layout.js',layout),
  writeFile('app/api/status/route.js',statusRoute),
  writeFile('app/api/goal/run/route.js',goalRoute),
  writeFile('public/icon.svg',icon)
]);
console.log('MUS AI Control Center source synchronized.');
