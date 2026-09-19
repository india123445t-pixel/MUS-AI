import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

async function listen(server){server.listen(0,'127.0.0.1');await once(server,'listening');return server.address().port}

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
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
      AQLEVON_COMMONS_WORKER_TOKEN:'super-secret-worker-token',
      AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
      AQLEVON_MODEL_NAME:'AQLEVON-27B',
      AQLEVON_COMMONS_ONCE:'1',
      AQLEVON_COMMONS_CONCURRENCY:'4',
      AQLEVON_COMPUTE_DEVICE:'test-gpu',
      AQLEVON_GPU_COUNT:'1',
      AQLEVON_GPU_POWER_WATTS:'300',
      AQLEVON_GPU_HOURLY_USD:'1.5',
    },
    stdio:['ignore','pipe','pipe']
  });
  let stdout='',stderr='';child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c);
  const [code]=await once(child,'exit');
  server.close();await once(server,'close');
  assert.equal(code,0,stderr);
  assert.equal(claimCount,1,'AQLEVON_COMMONS_ONCE must remain a single-job smoke even when concurrency is configured');
  assert.ok(completeBody?.result?.runtime_metrics);
  assert.equal(completeBody.result.runtime_metrics.prompt_tokens,10);
  assert.equal(completeBody.result.runtime_metrics.completion_tokens,5);
  assert.equal(completeBody.result.runtime_metrics.cached_prompt_tokens,4);
  assert.equal(completeBody.result.runtime_metrics.gpu_count,1);
  assert.ok(completeBody.result.runtime_metrics.allocated_gpu_seconds>0);
  assert.ok(completeBody.result.runtime_metrics.estimated_energy_wh>0);
  assert.ok(completeBody.result.runtime_metrics.estimated_gpu_cost_usd>0);
  assert.equal((stdout+stderr).includes('super-secret-worker-token'),false);
  const start=stdout.split('\n').filter(Boolean).map(line=>JSON.parse(line)).find(x=>x.event==='commons_worker_start');
  assert.equal(start.concurrency,1,'ONCE mode must force concurrency=1');
});

test('commons worker can opt into bounded parallel claims so upstream engines can batch',async()=>{
  let nextJob=0;
  let completes=0;
  let inFlight=0;
  let maxInFlight=0;
  let maxAdvertised=null;
  let child=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;
    const body=raw?JSON.parse(raw):{};
    if(req.url==='/commons'){
      res.setHeader('content-type','application/json');
      if(body.op==='claim'){
        maxAdvertised=body.capabilities?.max_concurrency;
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
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
      AQLEVON_COMMONS_WORKER_TOKEN:'parallel-worker-secret',
      AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
      AQLEVON_COMMONS_CONCURRENCY:'2.9',
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
  assert.equal(maxAdvertised,2,'decimal concurrency must advertise the same integer slot count');
  assert.equal((stdout+stderr).includes('parallel-worker-secret'),false);
  const start=stdout.split('\n').filter(Boolean).map(line=>JSON.parse(line)).find(x=>x.event==='commons_worker_start');
  assert.equal(start.concurrency,2);
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
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
      AQLEVON_COMMONS_WORKER_TOKEN:'failure-worker-secret',
      AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
      AQLEVON_MODEL_NAME:'AQLEVON-27B',
      AQLEVON_COMMONS_ONCE:'1',
      AQLEVON_COMPUTE_DEVICE:'test-gpu',
      AQLEVON_GPU_COUNT:'1',
      AQLEVON_GPU_POWER_WATTS:'300',
      AQLEVON_GPU_HOURLY_USD:'3.6',
    },
    stdio:['ignore','pipe','pipe']
  });
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
  const [code]=await once(child,'exit');
  server.close();await once(server,'close');
  assert.equal(code,0,stderr);
  assert.equal(completeBody.error,'model_http_503');
  assert.equal(completeBody.result?.ok,false);
  assert.equal(completeBody.result?.outcome,'failed');
  const failed=completeBody.result.runtime_metrics;
  assert.ok(failed.elapsed_ms>=50,`expected measurable delayed failure, got ${failed.elapsed_ms}ms`);
  assert.ok(failed.allocated_gpu_seconds>0);
  assert.ok(failed.estimated_gpu_cost_usd>0);
  const summary=summarizeVerifiedEfficiency([
    {verified:true,runtime_metrics:{allocated_gpu_seconds:1,estimated_gpu_cost_usd:0.001}},
    {verified:false,runtime_metrics:failed},
  ]);
  assert.ok(summary.allocated_gpu_seconds_total>1);
  assert.ok(summary.estimated_gpu_cost_usd_total>0.001);
  assert.equal(summary.verified_successes,1);
});


test('worker stdout/stderr never exposes URL-embedded credentials/query tokens or model key',async()=>{
  let claimCount=0;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const chunk of req)raw+=chunk;
    const body=raw?JSON.parse(raw):{};
    res.setHeader('content-type','application/json');
    if(body.op==='claim')claimCount++;
    res.end(JSON.stringify({ok:true,job:null}));
  });
  const port=await listen(server);
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}`,
      AQLEVON_COMMONS_WORKER_TOKEN:'log-worker-secret',
      AQLEVON_MODEL_URL:'https://url-user-secret:url-pass-secret@example.invalid/path-signed-secret/v1?token=query-secret',
      AQLEVON_MODEL_KEY:'model-key-secret',
      AQLEVON_COMMONS_ONCE:'1',
    },
    stdio:['ignore','pipe','pipe']
  });
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
  const [code]=await once(child,'exit');
  server.close();await once(server,'close');
  assert.equal(code,0,stderr);
  assert.equal(claimCount,1);
  const combined=stdout+stderr;
  for(const secret of ['url-user-secret','url-pass-secret','path-signed-secret','query-secret','model-key-secret']){
    assert.equal(combined.includes(secret),false,`secret leaked: ${secret}`);
  }
  const start=stdout.split('\n').filter(Boolean).map(line=>JSON.parse(line)).find(x=>x.event==='commons_worker_start');
  assert.equal(start.model_origin,'https://example.invalid');
  assert.equal(Object.hasOwn(start,'model_url'),false);
});


test('malformed model timeout fails closed before Commons or model network activity',async()=>{
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{
    cwd:root,
    env:{...process.env,
      AQLEVON_COMMONS_URL:'http://127.0.0.1:9',
      AQLEVON_COMMONS_WORKER_TOKEN:'timeout-worker-secret',
      AQLEVON_MODEL_URL:'http://127.0.0.1:9',
      AQLEVON_COMMONS_MODEL_TIMEOUT_MS:'12.5',
    },
    stdio:['ignore','pipe','pipe']
  });
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
  const [code]=await once(child,'exit');
  assert.equal(code,2);
  assert.equal(stdout,'');
  assert.equal(stderr.includes('timeout-worker-secret'),false);
  const lines=stderr.split('\n').filter(Boolean).map(line=>JSON.parse(line));
  assert.equal(lines[0].event,'commons_worker_config_error');
  assert.equal(lines[0].field,'AQLEVON_COMMONS_MODEL_TIMEOUT_MS');
});
