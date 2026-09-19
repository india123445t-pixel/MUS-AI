#!/usr/bin/env node
import {buildRuntimeAccounting,normalizeBoundedInteger,parseStrictBoundedInteger,sanitizeEndpointForLog} from '../lib/aqlevon/runtime-economics.js';
import {buildRequestIdentity,buildRuntimeAttemptReceipt,isSha256,sha256Text} from '../lib/aqlevon/runtime-attempt-receipt.js';

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
const CANDIDATE_MANIFEST_SHA256=String(process.env.AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256||'').toLowerCase();
const HARNESS_MANIFEST_SHA256=String(process.env.AQLEVON_RUNTIME_HARNESS_MANIFEST_SHA256||'').toLowerCase();
const RECEIPT_IDENTITY_CONFIGURED=!!(CANDIDATE_MANIFEST_SHA256||HARNESS_MANIFEST_SHA256);
const RECEIPT_MODE=RECEIPT_IDENTITY_CONFIGURED?'enabled':'disabled';

if(!WORKER_TOKEN){
  console.error('AQLEVON_COMMONS_WORKER_TOKEN is required.');
  process.exit(2);
}
if(MODEL_TIMEOUT_MS===null){
  console.error(JSON.stringify({event:'commons_worker_config_error',field:'AQLEVON_COMMONS_MODEL_TIMEOUT_MS',reason:'must_be_integer_100_to_900000'}));
  process.exit(2);
}
if(RECEIPT_IDENTITY_CONFIGURED&&(!isSha256(CANDIDATE_MANIFEST_SHA256)||!isSha256(HARNESS_MANIFEST_SHA256))){
  console.error(JSON.stringify({event:'commons_worker_config_error',field:'runtime_receipt_identity',reason:'candidate_and_harness_sha256_required_together'}));
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
function failureCode(err){
  const message=String(err?.message||'');
  if(/^model_http_\d{3}$/.test(message))return message;
  if(message==='empty_model_response')return message;
  if(err?.name==='TimeoutError'||err?.name==='AbortError')return 'model_timeout';
  return 'model_transport_error';
}
function maybeAttemptReceipt({job,modelRequest,transportStatus,failureCodeValue,runtimeMetricsValue,rawResultSha256}){
  if(RECEIPT_MODE!=='enabled')return null;
  return buildRuntimeAttemptReceipt({
    taskId:String(job.id),
    candidateArtifactManifestSha256:CANDIDATE_MANIFEST_SHA256,
    requestIdentity:buildRequestIdentity({modelRequest,harnessManifestSha256:HARNESS_MANIFEST_SHA256}),
    transportStatus,
    failureCode:failureCodeValue,
    runtimeMetrics:runtimeMetricsValue,
    rawResultSha256,
  });
}
async function infer(job){
  const req=job.model_request||{};
  const messages=Array.isArray(req.messages)&&req.messages.length?req.messages:[
    ...(Array.isArray(job.history)?job.history:[]),
    {role:'user',content:String(job.prompt||'')}
  ];
  const headers={'Content-Type':'application/json'};
  if(MODEL_KEY)headers.Authorization=`Bearer ${MODEL_KEY}`;
  const modelRequest={
    model:req.model||MODEL_NAME,
    messages,
    temperature:Number.isFinite(Number(req.temperature))?Number(req.temperature):0.4,
    stream:false
  };
  const started=performance.now();
  let usage=null;
  let rawResultSha256=null;
  try{
    const r=await fetch(modelEndpoint(),{
      method:'POST',
      headers,
      body:JSON.stringify(modelRequest),
      signal:AbortSignal.timeout(MODEL_TIMEOUT_MS)
    });
    const raw=await r.text();
    rawResultSha256=sha256Text(raw);
    let data={};try{data=JSON.parse(raw)}catch{}
    usage=data?.usage||null;
    if(!r.ok)throw new Error(`model_http_${r.status}`);
    const text=String(data?.choices?.[0]?.message?.content||'').trim();
    if(!text)throw new Error('empty_model_response');
    const metrics=runtimeMetrics(started,usage);
    const runtime_attempt_receipt=maybeAttemptReceipt({job,modelRequest,transportStatus:'success',failureCodeValue:null,runtimeMetricsValue:metrics,rawResultSha256});
    return {text,model:data?.model||MODEL_NAME,provider:'aqlevon-commons',citations:[],runtime_metrics:metrics,runtime_attempt_receipt};
  }catch(err){
    const metrics=runtimeMetrics(started,usage);
    const runtime_attempt_receipt=maybeAttemptReceipt({job,modelRequest,transportStatus:'failure',failureCodeValue:failureCode(err),runtimeMetricsValue:metrics,rawResultSha256});
    if(!err?.runtime_metrics){try{Object.defineProperty(err,'runtime_metrics',{value:metrics,enumerable:false})}catch{}}
    if(!err?.runtime_attempt_receipt){try{Object.defineProperty(err,'runtime_attempt_receipt',{value:runtime_attempt_receipt,enumerable:false})}catch{}}
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
      capabilities:{protocol:'openai-compatible',model:MODEL_NAME,engine:'local',max_concurrency:CONCURRENCY,runtime_metrics:'v1',runtime_attempt_receipt:RECEIPT_MODE==='enabled'?'v1':'unbound'}
    });
    job=claimed.job||null;
    if(job){
      const started=Date.now();
      try{
        const result=await infer(job);
        await commons({op:'complete',worker_token:WORKER_TOKEN,job_id:job.id,result,error:null});
        console.log(JSON.stringify({event:'job_completed',job_id:job.id,slot,latency_ms:Date.now()-started,runtime_metrics:result.runtime_metrics,runtime_attempt_receipt_sha256:result.runtime_attempt_receipt?.receipt_sha256||null}));
      }catch(err){
        const error=redactKnownSecrets(err?.message||err);
        const runtime_metrics=err?.runtime_metrics||null;
        const runtime_attempt_receipt=err?.runtime_attempt_receipt||null;
        const failedResult={ok:false,outcome:'failed',provider:'aqlevon-commons',model:MODEL_NAME,runtime_metrics,runtime_attempt_receipt};
        await commons({op:'complete',worker_token:WORKER_TOKEN,job_id:job.id,result:failedResult,error}).catch(()=>{});
        console.error(JSON.stringify({event:'job_failed',job_id:job.id,slot,error,runtime_metrics,runtime_attempt_receipt_sha256:runtime_attempt_receipt?.receipt_sha256||null}));
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

console.log(JSON.stringify({event:'commons_worker_start',model:MODEL_NAME,model_origin:MODEL_LOG_ORIGIN,concurrency:CONCURRENCY,model_timeout_ms:MODEL_TIMEOUT_MS,runtime_attempt_receipt:RECEIPT_MODE}));
await Promise.all(Array.from({length:CONCURRENCY},(_,slot)=>workerLoop(slot)));
console.log(JSON.stringify({event:'commons_worker_stop'}));
