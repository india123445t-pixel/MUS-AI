#!/usr/bin/env node
const COMMONS_URL=process.env.AQLEVON_COMMONS_URL||'https://qkoscgdegnqcypkjrefn.supabase.co/functions/v1/aqlevon-commons';
const WORKER_TOKEN=process.env.AQLEVON_COMMONS_WORKER_TOKEN||'';
const MODEL_URL=(process.env.AQLEVON_MODEL_URL||process.env.LOCAL_MODEL_URL||'http://127.0.0.1:8080').replace(/\/$/,'');
const MODEL_KEY=process.env.AQLEVON_MODEL_KEY||process.env.LOCAL_MODEL_KEY||'';
const MODEL_NAME=process.env.AQLEVON_MODEL_NAME||'AQLEVON-27B';
const POLL_MS=Math.max(500,Number(process.env.AQLEVON_COMMONS_POLL_MS||1500));
const ONCE=process.env.AQLEVON_COMMONS_ONCE==='1';

if(!WORKER_TOKEN){
  console.error('AQLEVON_COMMONS_WORKER_TOKEN is required.');
  process.exit(2);
}

async function commons(body){
  const r=await fetch(COMMONS_URL,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body),
    signal:AbortSignal.timeout(15000)
  });
  const data=await r.json().catch(()=>({}));
  if(!r.ok||data.ok===false)throw new Error(data.error||`commons_http_${r.status}`);
  return data;
}
function modelEndpoint(){
  if(/\/v1\/chat\/completions$/.test(MODEL_URL))return MODEL_URL;
  if(/\/v1$/.test(MODEL_URL))return MODEL_URL+'/chat/completions';
  return MODEL_URL+'/v1/chat/completions';
}
async function infer(job){
  const req=job.model_request||{};
  const messages=Array.isArray(req.messages)&&req.messages.length?req.messages:[
    ...(Array.isArray(job.history)?job.history:[]),
    {role:'user',content:String(job.prompt||'')}
  ];
  const headers={'Content-Type':'application/json'};
  if(MODEL_KEY)headers.Authorization=`Bearer ${MODEL_KEY}`;
  const r=await fetch(modelEndpoint(),{
    method:'POST',
    headers,
    body:JSON.stringify({
      model:req.model||MODEL_NAME,
      messages,
      temperature:Number.isFinite(Number(req.temperature))?Number(req.temperature):0.4,
      stream:false
    }),
    signal:AbortSignal.timeout(Number(process.env.AQLEVON_COMMONS_MODEL_TIMEOUT_MS||240000))
  });
  const data=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(`model_http_${r.status}`);
  const text=String(data?.choices?.[0]?.message?.content||'').trim();
  if(!text)throw new Error('empty_model_response');
  return {text,model:data?.model||MODEL_NAME,provider:'aqlevon-commons',citations:[]};
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let stopping=false;
process.on('SIGINT',()=>{stopping=true});
process.on('SIGTERM',()=>{stopping=true});

console.log(JSON.stringify({event:'commons_worker_start',model:MODEL_NAME,model_url:MODEL_URL}));
do{
  let job=null;
  try{
    const claimed=await commons({
      op:'claim',
      worker_token:WORKER_TOKEN,
      capabilities:{protocol:'openai-compatible',model:MODEL_NAME,engine:'local'}
    });
    job=claimed.job||null;
    if(job){
      const started=Date.now();
      try{
        const result=await infer(job);
        await commons({op:'complete',worker_token:WORKER_TOKEN,job_id:job.id,result:{...result,latency_ms:Date.now()-started},error:null});
        console.log(JSON.stringify({event:'job_completed',job_id:job.id,latency_ms:Date.now()-started}));
      }catch(err){
        const error=String(err?.message||err).slice(0,1000);
        await commons({op:'complete',worker_token:WORKER_TOKEN,job_id:job.id,result:null,error}).catch(()=>{});
        console.error(JSON.stringify({event:'job_failed',job_id:job.id,error}));
      }
    }
  }catch(err){
    console.error(JSON.stringify({event:'worker_poll_error',error:String(err?.message||err).slice(0,500)}));
  }
  if(ONCE)break;
  if(!stopping&&!job)await sleep(POLL_MS);
}while(!stopping);
console.log(JSON.stringify({event:'commons_worker_stop'}));
