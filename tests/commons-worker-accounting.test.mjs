import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {verifyRuntimeAttemptReceipt} from '../lib/aqlevon/runtime-receipts.js';

async function listen(server){server.listen(0,'127.0.0.1');await once(server,'listening');return server.address().port}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const CANDIDATE='a'.repeat(64),HARNESS='b'.repeat(64);

test('commons worker emits signed attempt receipt plus token/GPU accounting without logging auth sentinels',async()=>{
  let completeBody=null,claimCount=0;
  const workerSentinel='TEST_WORKER_'+['MARKER','01'].join('_');
  const modelSentinel='TEST_MODEL_'+['MARKER','02'].join('_');
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){claimCount++;res.end(JSON.stringify({ok:true,job:{id:'job-1',model_request:{messages:[{role:'user',content:'ping'}],temperature:0,model:'AQLEVON-27B'}}}));return}
      if(body.op==='complete'){completeBody=body;res.end(JSON.stringify({ok:true}));return}
    }
    if(req.url==='/v1/chat/completions'){
      await new Promise(r=>setTimeout(r,40));res.setHeader('content-type','application/json');
      res.end(JSON.stringify({model:'AQLEVON-27B',choices:[{message:{content:'pong'}}],usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15,prompt_tokens_details:{cached_tokens:4}}}));return;
    }
    res.statusCode=404;res.end();
  });
  const port=await listen(server);
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,
    AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,AQLEVON_COMMONS_WORKER_TOKEN:workerSentinel,
    AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,AQLEVON_MODEL_KEY:modelSentinel,AQLEVON_MODEL_NAME:'AQLEVON-27B',
    AQLEVON_COMMONS_ONCE:'1',AQLEVON_COMMONS_CONCURRENCY:'4',AQLEVON_COMPUTE_DEVICE:'test-gpu',AQLEVON_GPU_COUNT:'1',AQLEVON_GPU_POWER_WATTS:'300',AQLEVON_GPU_HOURLY_USD:'1.5',
    AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256:CANDIDATE,AQLEVON_RUNTIME_HARNESS_MANIFEST_SHA256:HARNESS,
  },stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);
  const [code]=await once(child,'exit');server.close();await once(server,'close');
  assert.equal(code,0,stderr);assert.equal(claimCount,1);assert.ok(completeBody?.result?.runtime_metrics);
  const receipt=completeBody.result.runtime_attempt_receipt;assert.equal(verifyRuntimeAttemptReceipt(receipt).ok,true);
  assert.equal(receipt.transport_outcome.status,'success');assert.equal(receipt.candidate_artifact_manifest_sha256,CANDIDATE);
  assert.equal(receipt.request_identity.harness_manifest_sha256,HARNESS);assert.equal(receipt.task_id,'job-1');
  assert.equal((stdout+stderr).includes(workerSentinel),false);assert.equal((stdout+stderr).includes(modelSentinel),false);
  const start=stdout.split('\n').filter(Boolean).map(JSON.parse).find(x=>x.event==='commons_worker_start');
  assert.equal(start.concurrency,1);assert.equal(start.runtime_attempt_receipt,'v1');
});

test('delayed model HTTP failure retains signed failed receipt and compute cost',async()=>{
  let completeBody=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){res.end(JSON.stringify({ok:true,job:{id:'job-fail',model_request:{messages:[{role:'user',content:'fail'}],model:'AQLEVON-27B'}}}));return}
      if(body.op==='complete'){completeBody=body;res.end(JSON.stringify({ok:true}));return}
    }
    if(req.url==='/v1/chat/completions'){await new Promise(r=>setTimeout(r,80));res.writeHead(503,{'content-type':'application/json'});res.end(JSON.stringify({error:{message:'mock unavailable'}}));return}
    res.statusCode=404;res.end();
  });
  const port=await listen(server);
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,
    AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,AQLEVON_COMMONS_WORKER_TOKEN:'TEST_FAILURE_MARKER',AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,AQLEVON_MODEL_NAME:'AQLEVON-27B',AQLEVON_COMMONS_ONCE:'1',
    AQLEVON_COMPUTE_DEVICE:'test-gpu',AQLEVON_GPU_COUNT:'1',AQLEVON_GPU_POWER_WATTS:'300',AQLEVON_GPU_HOURLY_USD:'3.6',
    AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256:CANDIDATE,AQLEVON_RUNTIME_HARNESS_MANIFEST_SHA256:HARNESS,
  },stdio:['ignore','pipe','pipe']});
  let stderr='';child.stderr.on('data',x=>stderr+=x);const [code]=await once(child,'exit');server.close();await once(server,'close');
  assert.equal(code,0,stderr);assert.equal(completeBody.error,'model_http_503');assert.equal(completeBody.result?.outcome,'failed');
  const receipt=completeBody.result.runtime_attempt_receipt;assert.equal(verifyRuntimeAttemptReceipt(receipt).ok,true);
  assert.equal(receipt.transport_outcome.status,'failed');assert.equal(receipt.transport_outcome.failure_code,'model_http_503');
  assert.ok(receipt.runtime_metrics.allocated_gpu_seconds>0);assert.ok(receipt.runtime_metrics.estimated_gpu_cost_usd>0);
});

test('commons worker can opt into integer-normalized parallel claims so upstream engines can batch',async()=>{
  let nextJob=0,completes=0,inFlight=0,maxInFlight=0,maxAdvertised=null,child=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){maxAdvertised=body.capabilities?.max_concurrency;const index=nextJob++;const job=index<2?{id:`job-${index+1}`,model_request:{messages:[{role:'user',content:`ping-${index+1}`}],model:'AQLEVON-27B'}}:null;res.end(JSON.stringify({ok:true,job}));return}
      if(body.op==='complete'){completes++;res.end(JSON.stringify({ok:true}));if(completes===2)setTimeout(()=>child?.kill('SIGTERM'),25);return}
    }
    if(req.url==='/v1/chat/completions'){inFlight++;maxInFlight=Math.max(maxInFlight,inFlight);await new Promise(r=>setTimeout(r,100));inFlight--;res.setHeader('content-type','application/json');res.end(JSON.stringify({model:'AQLEVON-27B',choices:[{message:{content:'pong'}}],usage:{prompt_tokens:2,completion_tokens:1,total_tokens:3}}));return}
    res.statusCode=404;res.end();
  });
  const port=await listen(server);
  child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,AQLEVON_COMMONS_WORKER_TOKEN:'TEST_PARALLEL_MARKER',AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,AQLEVON_COMMONS_CONCURRENCY:'2.9',AQLEVON_COMMONS_POLL_MS:'500'},stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);const timeout=setTimeout(()=>child?.kill('SIGKILL'),5000);const [code,signal]=await once(child,'exit');clearTimeout(timeout);server.close();await once(server,'close');
  assert.ok(code===0||signal==='SIGTERM',stderr);assert.equal(completes,2);assert.equal(maxInFlight,2);assert.equal(maxAdvertised,2);
});

test('worker stdout/stderr never exposes URL identity markers or model auth marker',async()=>{
  let claimCount=0;
  const userMarker='url-user-marker',passMarker='url-pass-marker',pathMarker='path-marker',queryMarker='query-marker',modelMarker='model-auth-marker';
  const modelUrl=`https://${userMarker}:${passMarker}@example.invalid/${pathMarker}/v1?token=${queryMarker}`;
  const server=http.createServer(async(req,res)=>{let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};res.setHeader('content-type','application/json');if(body.op==='claim')claimCount++;res.end(JSON.stringify({ok:true,job:null}))});
  const port=await listen(server);
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}`,AQLEVON_COMMONS_WORKER_TOKEN:'TEST_LOG_MARKER',AQLEVON_MODEL_URL:modelUrl,AQLEVON_MODEL_KEY:modelMarker,AQLEVON_COMMONS_ONCE:'1'},stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);const [code]=await once(child,'exit');server.close();await once(server,'close');
  assert.equal(code,0,stderr);assert.equal(claimCount,1);const combined=stdout+stderr;for(const marker of [userMarker,passMarker,pathMarker,queryMarker,modelMarker])assert.equal(combined.includes(marker),false);
});


test('partial runtime receipt identity configuration fails closed before polling Commons',async()=>{
  for(const envPatch of [
    {AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256:CANDIDATE},
    {AQLEVON_RUNTIME_HARNESS_MANIFEST_SHA256:HARNESS},
  ]){
    const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,
      AQLEVON_COMMONS_URL:'http://127.0.0.1:9',AQLEVON_COMMONS_WORKER_TOKEN:'TEST_CONFIG_MARKER',AQLEVON_MODEL_URL:'http://127.0.0.1:9',...envPatch,
    },stdio:['ignore','pipe','pipe']});
    let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
    const [code]=await once(child,'exit');
    assert.equal(code,2,stderr);
    assert.equal(stdout.includes('commons_worker_start'),false);
    const line=stderr.split('\\n').filter(Boolean).map(JSON.parse)[0];
    assert.equal(line.event,'commons_worker_config_error');
    assert.equal(line.field,'runtime_receipt_identity');
    assert.equal(stderr.includes('ECONNREFUSED'),false);
  }
});
