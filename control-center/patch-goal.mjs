import { writeFile } from 'node:fs/promises';

const route=`export async function POST(req){
  try{
    const auth=req.headers.get('authorization')||'';
    const origin=new URL(req.url).origin;
    const r=await fetch(origin+'/api/benchmark/run',{
      method:'POST',
      headers:{'content-type':'application/json',...(auth?{authorization:auth}:{})},
      body:'{}',
      cache:'no-store',
      signal:AbortSignal.timeout(105000)
    });
    const text=await r.text();
    return new Response(text,{status:r.status,headers:{'content-type':r.headers.get('content-type')||'application/json','cache-control':'no-store'}});
  }catch{
    return Response.json({message:'تعذر تشغيل دورة MUS AI عبر مسار التقييم المجاني.'},{status:502});
  }
}`;

await writeFile('app/api/goal/run/route.js',route);
console.log('MUS AI goal route patched to zero-cost objective runner.');
