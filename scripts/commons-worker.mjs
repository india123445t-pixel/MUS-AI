#!/usr/bin/env node
import {buildRuntimeAccounting,normalizeBoundedInteger,parseStrictBoundedInteger,sanitizeEndpointForLog} from '../lib/aqlevon/runtime-economics.js';

const COMMONS_URL=process.env.AQLEVON_COMMONS_URL||'https://qkoscgdegnqcypkjrefn.supabase.co/functions/v1/aqlevon-commons';
const WORKER_TOKEN=process.env.AQLEVON_COMMONS_WORKER_TOKEN||'';
const MODEL_URL=(process.env.AQLEVON_MODEL_URL||process.env.LOCAL_MODEL_URL||'http://127.0.0.1:8080').replace(/\/$/,'');
const MODEL_KEY=process.env.AQLEVON_MODEL_KEY||process.env.LOCAL_MODEL_KEY||'';
const MODEL_NAME=process.env.AQLEVON_MODEL_NAME||'AQLEVON-27B';
const POLL_MS=Math.max(500,Number(process.env.AQLEVON_COMMONS_POLL_MS||1500));
const ONCE=process.env.AQLEVON_COMMONS_ONCE==='1';
const CONFIGURED_CONCURRENCY=normalizeBoundedInteger(process.env.AQLEVON_COMMONS_CONCURRENCY,{defaultValue:1,min:1,max:16});
const CONCURRENCY=ONCE?1:CONFIGURED_CONCURRENCY;
const MODEL_TIMEOUT_MS=parseStrictBoundedInteger(process.env.AQLEVON_COMMONS_MODEL_TIMEOUT_MS,{defaultValue:240000,min:100,max:900000});
const MODEL_LOG_ORIGIN=sanitizeEndpointForLog(MODEL_URL);

if(!WORKER_TOKEN){
  console.error('AQLEVON_COMMONS_WORKER_TOKEN is required.');
  process.exit(2);
}
if(MODEL_TIMEOUT_MS===null){
  console.error(JSON.stringify({event:'commons_worker_config_error',field:'AQLEVON_COMMONS_MODEL_TIMEOUT_MS',reason:'must_be_integer_100_to_900000'}));
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
  try{
    const u=new URL(MODEL_URL);
    const path=u.pathname.replace(/\/$/,'');
    if(/\/v1\/chat\/completions$/.test(path))u.pathname=path;
    else if(/\/v1$/.test(path))u.pathname=path+'/chat/completions';
    else u.pathname=(path||'')+'/v1/chat/completions';
    return u.toString();
  }catch{
    if(/\/v1\/chat\/completions$/.test(MODEL_URL))return MODEL_URL;
    if(/\/v1$/.test(MODEL_URL))return MODEL_URL+'/chat/completions';
    return MODEL_URL+'/v1/chat/completions';
  }
}
function runtimeMetrics(started,usage){
  return buildRuntimeAccounting({
    elapsedMs:performance.now()-started,
    usage,
    computeDevice:process.env.AQLEVON_COMPUTE_DEVICE||'unknown',
    gpuCount:process.env.AQLEVON_GPU_COUNT,
    gpuPowerWatts:process.env.AQLEVON_GPU_POWER_WATTS,
    gpuHourlyUsd:process.env.AQLEVON_GPU_HOURLY_USD,
  });
}
function redactKnownSecrets(value){
  let out=String(value??'');
  const secrets=[WORKER_TOKEN,MODEL_KEY,MODEL_URL,modelEndpoint()];
  try{
    const u=new URL(MODEL_URL);
    secrets.push(u.username,u.password,u.search);
    for(const [,v] of u.searchParams)secrets.push(v);
  }catch{}
  for(const secret of secrets){
    if(!secret||String(secret).length<3)continue;
    out=out.split(String(secret)).join('[REDACTED]');
  }
  return out.slice(0,1000);
}
async function infer(job){
  const req=job.model_request||{};
  const messages=Array.isArray(req.messages)&&req.messages.length?req.messages:[
    ...(Array.isArray(job.history)?job.history:[]),
    {role:'user',content:String(job.prompt||'')}
  ];
  const headers={'Content-Type':'application/json'};
  if(MODEL_KEY)headers.Authorization=`Bearer ${MODEL_KEY}`;
  const started=performance.now();
  let usage=null;
  try{
    const r=await fetch(modelEndpoint(),{
      method:'POST',
      headers,
      body:JSON.stringify({
        model:req.model||MODEL_NAME,
        messages,
        temperature:Number.isFinite(Number(req.temperature))?Number(req.temperature):0.4,
        stream:false
      }),
      signal:AbortSignal.timeout(MODEL_TIMEOUT_MS)
    });
    const data=await r.json().catch(()=>({}));
    usage=data?.usage||null;
    if(!r.ok)throw new Error(`model_http_${r.status}`);
    const text=String(data?.choices?.[0]?.message?.content||'').trim();
    if(!text)throw new Error('empty_model_response');
    return {text,model:data?.model||MODEL_NAME,provider:'aqlevon-commons',citations:[],runtime_metrics:runtimeMetrics(started,usage)};
  }catch(err){
    if(!err?.runtime_metrics){
      try{Object.defineProperty(err,'runtime_metrics',{value:runtimeMetrics(started,usage),enumerable:false})}
      catch{}
    }
    throw err;
  }
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let stopping=false;
process.on('SIGINT',()=>{stopping=true});
process.on('SIGTERM',()=>{stopping=true});

async function processOne(slot){
  let job=null;
  try{
    const claimed=await commons({
      op:'claim',
      worker_token:WORKER_TOKEN,
      capabilities:{protocol:'openai-compatible',model:MODEL_NAME,engine:'local',max_concurrency:CONCURRENCY,runtime_metrics:'v1'}
    });
    job=claimed.job||null;
    if(job){
      const started=Date.now();
      try{
        const result=await infer(job);
        await commons({op:'complete',worker_token:WORKER_TOKEN,job_id:job.id,result,error:null});
        console.log(JSON.stringify({event:'job_completed',job_id:job.id,slot,latency_ms:Date.now()-started,runtime_metrics:result.runtime_metrics}));
      }catch(err){
        const error=redactKnownSecrets(err?.message||err);
        const runtime_metrics=err?.runtime_metrics||null;
        const failedResult={ok:false,outcome:'failed',provider:'aqlevon-commons',model:MODEL_NAME,runtime_metrics};
        await commons({op:'complete',worker_token:WORKER_TOKEN,job_id:job.id,result:failedResult,error}).catch(()=>{});
        console.error(JSON.stringify({event:'job_failed',job_id:job.id,slot,error,runtime_metrics}));
      }
    }
  }catch(err){
    console.error(JSON.stringify({event:'worker_poll_error',slot,error:redactKnownSecrets(err?.message||err)}));
  }
  return !!job;
}

async function workerLoop(slot){
  do{
    const hadJob=await processOne(slot);
    if(ONCE)break;
    if(!stopping&&!hadJob)await sleep(POLL_MS);
  }while(!stopping);
}

console.log(JSON.stringify({event:'commons_worker_start',model:MODEL_NAME,model_origin:MODEL_LOG_ORIGIN,concurrency:CONCURRENCY,model_timeout_ms:MODEL_TIMEOUT_MS}));
await Promise.all(Array.from({length:CONCURRENCY},(_,slot)=>workerLoop(slot)));
console.log(JSON.stringify({event:'commons_worker_stop'}));
