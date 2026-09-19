import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
async function listen(server){server.listen(0,'127.0.0.1');await once(server,'listening');return server.address().port}
async function runWorker(env,{timeoutMs=5000}={}){
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);
  const timer=setTimeout(()=>child.kill('SIGKILL'),timeoutMs);
  const [code,signal]=await once(child,'exit');clearTimeout(timer);
  return {code,signal,stdout,stderr};
}
function jsonLines(text){return text.split('\n').filter(Boolean).map(line=>JSON.parse(line))}

test('commons worker emits token/GPU accounting without logging secrets',async()=>{
  let completeBody=null;
  let claimCount=0;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;
    const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){
        claimCount++;
        res.end(JSON.stringify({ok:true,job:{id:'job-1',model_request:{messages:[{role:'user',content:'ping'}],temperature:0,model:'AQLEVON-27B'}}}));
        return;
      }
      if(body.op==='complete'){
        completeBody=body;res.end(JSON.stringify({ok:true}));return;
      }
    }
    if(req.url==='/v1/chat/completions'){
      await new Promise(r=>setTimeout(r,40));
      res.setHeader('content-type','application/json');
      res.end(JSON.stringify({
        model:'AQLEVON-27B',
        choices:[{message:{content:'pong'}}],
        usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15,prompt_tokens_details:{cached_tokens:4}}
      }));
      return;
    }
    res.statusCode=404;res.end();
  });
  const port=await listen(server);
  const modelKey='super-secret-model-key';
  const result=await runWorker({
    AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
    AQLEVON_COMMONS_WORKER_TOKEN:'super-secret-worker-token',
    AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
    AQLEVON_MODEL_KEY:modelKey,
    AQLEVON_MODEL_NAME:'AQLEVON-27B',
    AQLEVON_COMMONS_ONCE:'1',
    AQLEVON_COMMONS_CONCURRENCY:'4',
    AQLEVON_COMPUTE_DEVICE:'test-gpu',
    AQLEVON_GPU_COUNT:'1',
    AQLEVON_GPU_POWER_WATTS:'300',
    AQLEVON_GPU_HOURLY_USD:'1.5',
  });
  server.close();await once(server,'close');
  assert.equal(result.code,0,result.stderr);
  assert.equal(claimCount,1,'AQLEVON_COMMONS_ONCE must remain a single-job smoke even when concurrency is configured');
  assert.ok(completeBody?.result?.runtime_metrics);
  assert.equal(completeBody.error,null);
  assert.equal(completeBody.result.runtime_metrics.prompt_tokens,10);
  assert.equal(completeBody.result.runtime_metrics.completion_tokens,5);
  assert.equal(completeBody.result.runtime_metrics.cached_prompt_tokens,4);
  assert.equal(completeBody.result.runtime_metrics.gpu_count,1);
  assert.ok(completeBody.result.runtime_metrics.allocated_gpu_seconds>0);
  assert.ok(completeBody.result.runtime_metrics.estimated_energy_wh>0);
  assert.ok(completeBody.result.runtime_metrics.estimated_gpu_cost_usd>0);
  for(const secret of ['super-secret-worker-token',modelKey])assert.equal((result.stdout+result.stderr).includes(secret),false);
  const start=jsonLines(result.stdout).find(x=>x.event==='commons_worker_start');
  assert.equal(start.concurrency,1,'ONCE mode must force concurrency=1');
});

test('delayed model HTTP failure retains runtime metrics and compute cost while outcome remains failed',async()=>{
  let completeBody=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;
    const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){
        res.end(JSON.stringify({ok:true,job:{id:'job-fail',model_request:{messages:[{role:'user',content:'fail'}],model:'AQLEVON-27B'}}}));
        return;
      }
      if(body.op==='complete'){
        completeBody=body;res.end(JSON.stringify({ok:true}));return;
      }
    }
    if(req.url==='/v1/chat/completions'){
      await new Promise(r=>setTimeout(r,80));
      res.writeHead(503,{'content-type':'application/json'});
      res.end(JSON.stringify({error:{message:'mock unavailable'}}));
      return;
    }
    res.statusCode=404;res.end();
  });
  const port=await listen(server);
  const result=await runWorker({
    AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
    AQLEVON_COMMONS_WORKER_TOKEN:'failure-worker-secret',
    AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
    AQLEVON_MODEL_NAME:'AQLEVON-27B',
    AQLEVON_COMMONS_ONCE:'1',
    AQLEVON_COMPUTE_DEVICE:'test-gpu',
    AQLEVON_GPU_COUNT:'1',
    AQLEVON_GPU_POWER_WATTS:'300',
    AQLEVON_GPU_HOURLY_USD:'3.6',
  });
  server.close();await once(server,'close');
  assert.equal(result.code,0,result.stderr);
  assert.equal(completeBody.error,'model_http_503');
  assert.equal(completeBody.result?.ok,false);
  assert.equal(completeBody.result?.outcome,'failed');
  const failed=completeBody.result.runtime_metrics;
  assert.ok(failed.elapsed_ms>=50,`expected measurable delayed failure, got ${failed.elapsed_ms}ms`);
  assert.ok(failed.allocated_gpu_seconds>0);
  assert.ok(failed.estimated_gpu_cost_usd>0);
  assert.equal(failed.completion_tokens,null);
  const summary=summarizeVerifiedEfficiency([
    {verified:true,runtime_metrics:{allocated_gpu_seconds:1,estimated_gpu_cost_usd:0.001}},
    {verified:false,runtime_metrics:failed},
  ]);
  assert.ok(summary.allocated_gpu_seconds_total>1,'failed attempt GPU time must remain in aggregate numerator');
  assert.ok(summary.estimated_gpu_cost_usd_total>0.001,'failed attempt estimated cost must remain in aggregate numerator');
  assert.equal(summary.verified_successes,1);
});

test('decimal Commons concurrency is integer-normalized identically in advertised capability and slot count',async()=>{
  let claims=0;
  let maxAdvertised=null;
  let child=null;
  const server=http.createServer(async(req,res)=>{
    let body={};let text='';for await(const chunk of req)text+=chunk;if(text)body=JSON.parse(text);
    res.setHeader('content-type','application/json');
    if(body.op==='claim'){
      claims++;
      maxAdvertised=body.capabilities?.max_concurrency;
      res.end(JSON.stringify({ok:true,job:null}));
      if(claims>=2)setTimeout(()=>child?.kill('SIGTERM'),10);
      return;
    }
    res.end(JSON.stringify({ok:true}));
  });
  const port=await listen(server);
  child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}`,
      AQLEVON_COMMONS_WORKER_TOKEN:'concurrency-secret',
      AQLEVON_MODEL_URL:'http://127.0.0.1:9',
      AQLEVON_COMMONS_CONCURRENCY:'2.9',
      AQLEVON_COMMONS_POLL_MS:'500',
    },
    stdio:['ignore','pipe','pipe']
  });
  let stdout='',stderr='';child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);
  const timer=setTimeout(()=>child.kill('SIGKILL'),3000);
  const [code,signal]=await once(child,'exit');clearTimeout(timer);
  server.close();await once(server,'close');
  assert.ok(code===0||signal==='SIGTERM',stderr);
  const start=jsonLines(stdout).find(x=>x.event==='commons_worker_start');
  assert.equal(start.concurrency,2);
  assert.equal(maxAdvertised,2);
  assert.ok(claims>=2);
});

test('worker startup log sanitizes URL userinfo/query/path secrets and model key',async()=>{
  let claimCount=0;
  const server=http.createServer(async(req,res)=>{
    let text='';for await(const chunk of req)text+=chunk;
    const body=text?JSON.parse(text):{};
    res.setHeader('content-type','application/json');
    if(body.op==='claim')claimCount++;
    res.end(JSON.stringify({ok:true,job:null}));
  });
  const port=await listen(server);
  const secrets=['url-user-secret','url-pass-secret','path-signed-secret','query-secret','model-key-secret'];
  const result=await runWorker({
    AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}`,
    AQLEVON_COMMONS_WORKER_TOKEN:'log-worker-secret',
    AQLEVON_MODEL_URL:'https://url-user-secret:url-pass-secret@example.invalid/path-signed-secret/v1?token=query-secret',
    AQLEVON_MODEL_KEY:'model-key-secret',
    AQLEVON_COMMONS_ONCE:'1',
  });
  server.close();await once(server,'close');
  assert.equal(result.code,0,result.stderr);
  assert.equal(claimCount,1);
  const combined=result.stdout+result.stderr;
  for(const secret of secrets)assert.equal(combined.includes(secret),false,`secret leaked: ${secret}`);
  const start=jsonLines(result.stdout).find(x=>x.event==='commons_worker_start');
  assert.equal(start.model_origin,'https://example.invalid');
  assert.equal(Object.hasOwn(start,'model_url'),false);
});

test('malformed model timeout fails closed before any Commons/model request',async()=>{
  const result=await runWorker({
    AQLEVON_COMMONS_URL:'http://127.0.0.1:9',
    AQLEVON_COMMONS_WORKER_TOKEN:'timeout-worker-secret',
    AQLEVON_MODEL_URL:'http://127.0.0.1:9',
    AQLEVON_COMMONS_MODEL_TIMEOUT_MS:'12.5',
  });
  assert.equal(result.code,2);
  const lines=jsonLines(result.stderr);
  assert.equal(lines[0].event,'commons_worker_config_error');
  assert.equal(lines[0].field,'AQLEVON_COMMONS_MODEL_TIMEOUT_MS');
});

test('commons worker can opt into bounded parallel claims so upstream engines can batch',async()=>{
  let nextJob=0;
  let completes=0;
  let inFlight=0;
  let maxInFlight=0;
  let child=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;
    const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){
        const index=nextJob++;
        const job=index<2?{id:`job-${index+1}`,model_request:{messages:[{role:'user',content:`ping-${index+1}`}],model:'AQLEVON-27B'}}:null;
        res.end(JSON.stringify({ok:true,job}));
        return;
      }
      if(body.op==='complete'){
        completes++;
        res.end(JSON.stringify({ok:true}));
        if(completes===2)setTimeout(()=>child?.kill('SIGTERM'),25);
        return;
      }
    }
    if(req.url==='/v1/chat/completions'){
      inFlight++;maxInFlight=Math.max(maxInFlight,inFlight);
      await new Promise(r=>setTimeout(r,100));
      inFlight--;
      res.setHeader('content-type','application/json');
      res.end(JSON.stringify({model:'AQLEVON-27B',choices:[{message:{content:'pong'}}],usage:{prompt_tokens:2,completion_tokens:1,total_tokens:3}}));
      return;
    }
    res.statusCode=404;res.end();
  });
  const port=await listen(server);
  child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
      AQLEVON_COMMONS_WORKER_TOKEN:'parallel-worker-secret',
      AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
      AQLEVON_COMMONS_CONCURRENCY:'2',
      AQLEVON_COMMONS_POLL_MS:'500',
    },
    stdio:['ignore','pipe','pipe']
  });
  let stdout='',stderr='';child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);
  const timeout=setTimeout(()=>child?.kill('SIGKILL'),5000);
  const [code,signal]=await once(child,'exit');clearTimeout(timeout);
  server.close();await once(server,'close');
  assert.ok(code===0||signal==='SIGTERM',stderr);
  assert.equal(completes,2);
  assert.equal(maxInFlight,2,'two claimed jobs should overlap at the model endpoint');
  assert.equal((stdout+stderr).includes('parallel-worker-secret'),false);
  const start=jsonLines(stdout).find(x=>x.event==='commons_worker_start');
  assert.equal(start.concurrency,2);
});
