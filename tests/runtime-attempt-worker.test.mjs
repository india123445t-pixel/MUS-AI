import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {validateRuntimeAttemptReceipt} from '../lib/aqlevon/runtime-attempt-receipt.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const C='a'.repeat(64),H='b'.repeat(64);
async function listen(server){server.listen(0,'127.0.0.1');await once(server,'listening');return server.address().port}
async function runOnce(port,extra={}){
  const child=spawn(process.execPath,['scripts/commons-worker.mjs'],{cwd:root,env:{...process.env,
    AQLEVON_COMMONS_URL:`http://127.0.0.1:${port}/commons`,
    AQLEVON_COMMONS_WORKER_TOKEN:'worker-secret',
    AQLEVON_MODEL_URL:`http://127.0.0.1:${port}`,
    AQLEVON_COMMONS_ONCE:'1',
    AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256:C,
    AQLEVON_RUNTIME_HARNESS_MANIFEST_SHA256:H,
    AQLEVON_GPU_COUNT:'1',AQLEVON_GPU_HOURLY_USD:'3.6',AQLEVON_GPU_POWER_WATTS:'300',
    ...extra,
  },stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
  const [code]=await once(child,'exit');return {code,stdout,stderr};
}

test('Commons success emits a self-hashed Runtime Attempt Receipt V1 without request plaintext',async()=>{
  let complete=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const c of req)raw+=c;const body=raw?JSON.parse(raw):{};
    res.setHeader('content-type','application/json');
    if(req.url==='/commons'&&body.op==='claim')return res.end(JSON.stringify({ok:true,job:{id:'task-success',model_request:{model:'AQLEVON-27B',messages:[{role:'user',content:'private runtime prompt'}]}}}));
    if(req.url==='/commons'&&body.op==='complete'){complete=body;return res.end(JSON.stringify({ok:true}))}
    if(req.url==='/v1/chat/completions')return res.end(JSON.stringify({model:'AQLEVON-27B',choices:[{message:{content:'pong'}}],usage:{prompt_tokens:3,completion_tokens:1,total_tokens:4}}));
    res.statusCode=404;res.end();
  });
  const port=await listen(server);const result=await runOnce(port);server.close();await once(server,'close');
  assert.equal(result.code,0,result.stderr);
  const receipt=complete.result.runtime_attempt_receipt;
  assert.equal(validateRuntimeAttemptReceipt(receipt).valid,true);
  assert.equal(receipt.task_id,'task-success');
  assert.equal(receipt.candidate_artifact_manifest_sha256,C);
  assert.equal(receipt.request_harness_identity.harness_manifest_sha256,H);
  assert.equal(receipt.transport_outcome.status,'success');
  assert.equal(JSON.stringify(receipt).includes('private runtime prompt'),false);
  assert.match(receipt.raw_result_sha256,/^[0-9a-f]{64}$/);
});

test('Commons failure emits failed Runtime Attempt Receipt with retained cost metrics',async()=>{
  let complete=null;
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const c of req)raw+=c;const body=raw?JSON.parse(raw):{};
    res.setHeader('content-type','application/json');
    if(req.url==='/commons'&&body.op==='claim')return res.end(JSON.stringify({ok:true,job:{id:'task-fail',model_request:{messages:[{role:'user',content:'fail'}]}}}));
    if(req.url==='/commons'&&body.op==='complete'){complete=body;return res.end(JSON.stringify({ok:true}))}
    if(req.url==='/v1/chat/completions'){await new Promise(r=>setTimeout(r,40));res.statusCode=503;return res.end(JSON.stringify({error:'nope'}))}
    res.statusCode=404;res.end();
  });
  const port=await listen(server);const result=await runOnce(port);server.close();await once(server,'close');
  assert.equal(result.code,0,result.stderr);
  assert.equal(complete.error,'model_http_503');
  assert.equal(complete.result.outcome,'failed');
  const receipt=complete.result.runtime_attempt_receipt;
  assert.equal(validateRuntimeAttemptReceipt(receipt).valid,true);
  assert.equal(receipt.transport_outcome.status,'failure');
  assert.equal(receipt.transport_outcome.failure_code,'model_http_503');
  assert.ok(receipt.runtime_metrics.allocated_gpu_seconds>0);
  assert.ok(receipt.runtime_metrics.estimated_gpu_cost_usd>0);
});
