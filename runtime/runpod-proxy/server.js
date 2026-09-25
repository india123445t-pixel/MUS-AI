import http from 'node:http';

const PORT=Number(process.env.PORT||8080);
const RUNPOD_API_KEY=String(process.env.RUNPOD_API_KEY||'');
const PUBLIC_ENDPOINT_ID=String(process.env.PUBLIC_ENDPOINT_ID||'');
const CHILD_ENDPOINT_ID=String(process.env.CHILD_ENDPOINT_ID||'');
const SUPABASE_URL=String(process.env.SUPABASE_URL||'https://yaqjhcfitxhtzpaswuif.supabase.co').replace(/\/$/,'');
const SUPABASE_PUBLISHABLE_KEY=String(process.env.SUPABASE_PUBLISHABLE_KEY||'sb_publishable_1uRtACKcyT2ZQH9ixdKQ-Q_ARbY6xET');
const MODEL='AQLEVON-4B-Auth16';
const ADAPTER_SHA='2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a';
const rates=new Map();

function send(res,status,obj){
  const body=JSON.stringify(obj);
  res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','content-length':Buffer.byteLength(body)});
  res.end(body);
}
function ipOf(req){return String(req.headers['x-forwarded-for']||req.socket.remoteAddress||'unknown').split(',')[0].trim()}
function allow(ip,limit=40){
  const now=Date.now(),windowMs=60_000;
  const x=rates.get(ip)||{at:now,n:0};
  if(now-x.at>windowMs){x.at=now;x.n=0}
  x.n++;rates.set(ip,x);
  return x.n<=limit;
}
async function body(req){
  let size=0;const chunks=[];
  for await(const c of req){size+=c.length;if(size>128_000)throw new Error('body_too_large');chunks.push(c)}
  return JSON.parse(Buffer.concat(chunks).toString('utf8')||'{}');
}
async function verifyOwner(token){
  if(!token||!SUPABASE_PUBLISHABLE_KEY)return false;
  const headers={Authorization:`Bearer ${token}`,apikey:SUPABASE_PUBLISHABLE_KEY};
  const u=await fetch(SUPABASE_URL+'/auth/v1/user',{headers,signal:AbortSignal.timeout(7000)});
  if(!u.ok)return false;
  const user=await u.json();
  if(!user?.id)return false;
  const q=new URL(SUPABASE_URL+'/rest/v1/system_owner');
  q.searchParams.set('select','owner_id');
  q.searchParams.set('owner_id',`eq.${user.id}`);
  const r=await fetch(q,{headers:{...headers,Accept:'application/json'},signal:AbortSignal.timeout(7000)});
  if(!r.ok)return false;
  const rows=await r.json();
  return Array.isArray(rows)&&rows.some(x=>x?.owner_id===user.id);
}
async function run(endpointId,input){
  if(!RUNPOD_API_KEY||!endpointId)throw new Error('runtime_not_configured');
  const r=await fetch(`https://api.runpod.ai/v2/${endpointId}/runsync`,{
    method:'POST',
    headers:{Authorization:`Bearer ${RUNPOD_API_KEY}`,'Content-Type':'application/json'},
    body:JSON.stringify({input}),
    signal:AbortSignal.timeout(120_000),
  });
  const data=await r.json().catch(()=>null);
  if(!r.ok)throw new Error(`runpod_http_${r.status}`);
  if(data?.status!=='COMPLETED'||!data?.output)throw new Error(`runpod_status_${data?.status||'unknown'}`);
  const out=data.output;
  if(out?.adapter_sha256!==ADAPTER_SHA)throw new Error('adapter_identity_mismatch');
  if(out?.error)throw new Error(String(out.detail||out.error));
  return out;
}
function sanitize(input){
  const messages=Array.isArray(input?.messages)?input.messages.slice(-16).map(m=>({
    role:['system','user','assistant'].includes(m?.role)?m.role:'user',
    content:String(m?.content||'').slice(0,12000)
  })):[];
  if(!messages.length)throw new Error('messages_required');
  return {
    model:MODEL,
    messages,
    temperature:Math.max(0,Math.min(Number(input?.temperature??0.2),1.2)),
    max_tokens:Math.max(1,Math.min(Number(input?.max_tokens??512),768)),
    stream:false,
    aqlevon_protocol:String(input?.aqlevon_protocol||'AQLEVON_CHAT_RUNTIME_V1').slice(0,80)
  };
}

const server=http.createServer(async(req,res)=>{
  const path=(req.url||'/').split('?')[0];
  if(req.method==='GET'&&path==='/health'){
    return send(res,200,{ok:true,service:'aqlevon-runtime-proxy',model:MODEL,adapter_sha256:ADAPTER_SHA,public_configured:!!PUBLIC_ENDPOINT_ID,child_configured:!!CHILD_ENDPOINT_ID});
  }
  if(req.method!=='POST'||!['/v1/chat/completions','/child/v1/chat/completions'].includes(path))return send(res,404,{error:'not_found'});
  const ip=ipOf(req);
  if(!allow(ip,path.startsWith('/child/')?60:30))return send(res,429,{error:'rate_limited'});
  try{
    if(path.startsWith('/child/')){
      const auth=String(req.headers.authorization||'');
      const token=auth.startsWith('Bearer ')?auth.slice(7).trim():'';
      if(!(await verifyOwner(token)))return send(res,403,{error:'owner_required'});
    }
    const input=sanitize(await body(req));
    const out=await run(path.startsWith('/child/')?CHILD_ENDPOINT_ID:PUBLIC_ENDPOINT_ID,input);
    return send(res,200,out);
  }catch(e){
    const msg=String(e?.message||e);
    const status=msg==='body_too_large'?413:msg==='messages_required'?400:503;
    return send(res,status,{error:'runtime_unavailable',detail:msg.slice(0,240),model:MODEL});
  }
});
server.listen(PORT,'0.0.0.0',()=>console.log(JSON.stringify({event:'AQLEVON_PROXY_READY',port:PORT,model:MODEL,adapter_sha256:ADAPTER_SHA})));
