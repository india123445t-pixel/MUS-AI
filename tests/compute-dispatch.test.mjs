import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {
  COMPUTE_PROFILES,PAYLOAD_TELEMETRY_SCHEMA,assessHardware,buildComputeAttemptReceipt,
  buildMsSwiftColocateLoRAArgs,parseGpuIndices,parseNvidiaSmiInventory,parsePayloadTelemetry,
  payloadIdentity,validateExecutionAuthorization,verifyComputeAttemptReceipt,
} from '../lib/aqlevon/compute-dispatch.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const RUN='a'.repeat(64);
const inventory=[
  {index:0,name:'Mock 80GB',memory_mib:81920},
  {index:1,name:'Mock 48GB A',memory_mib:49152},
  {index:2,name:'Mock 48GB B',memory_mib:49152},
  {index:3,name:'Mock 24GB A',memory_mib:24576},
  {index:4,name:'Mock 24GB B',memory_mib:24576},
  {index:5,name:'Mock 24GB C',memory_mib:24576},
  {index:6,name:'Mock 24GB D',memory_mib:24576},
  {index:7,name:'Mock 12GB',memory_mib:12288},
];

function completeTelemetry(){return {schema:PAYLOAD_TELEMETRY_SCHEMA,peak_vram_bytes:123456789,tokens_processed:512,tokens_generated:64}}

test('P3 profiles freeze 1x80, 2x48, 4x24, B07 <=12GB planning class, and ms-swift smoke',()=>{
  assert.equal(COMPUTE_PROFILES['g1-1x80-bf16-lora'].gpu_count,1);
  assert.equal(COMPUTE_PROFILES['g1-2x48-fsdp2'].gpu_count,2);
  assert.equal(COMPUTE_PROFILES['g1-4x24-fsdp2'].gpu_count,4);
  assert.equal(COMPUTE_PROFILES['b07-e0-1x8to12'].planned_vram_ceiling_mib_each,13000);
  assert.equal(COMPUTE_PROFILES['rl-qwen38-1x80-ms-swift-colocate'].paid_compute_authorized,false);
});

test('GPU index and nvidia-smi inventory parsers fail closed',()=>{
  assert.deepEqual(parseGpuIndices('0,2,4'),[0,2,4]);
  for(const bad of ['',',','0,0','-1','0,a','1.5'])assert.equal(parseGpuIndices(bad),null);
  assert.deepEqual(parseNvidiaSmiInventory('0|NVIDIA A100 80GB|81920\n1|L40S|49152'),[
    {index:0,name:'NVIDIA A100 80GB',memory_mib:81920},{index:1,name:'L40S',memory_mib:49152}
  ]);
});

test('hardware gate enforces count and VRAM floor while B07 larger device is only advisory',()=>{
  assert.equal(assessHardware('g1-1x80-bf16-lora',inventory,[0]).ok,true);
  assert.equal(assessHardware('g1-2x48-fsdp2',inventory,[1,2]).ok,true);
  assert.equal(assessHardware('g1-4x24-fsdp2',inventory,[3,4,5,6]).ok,true);
  assert.equal(assessHardware('g1-1x80-bf16-lora',inventory,[1]).ok,false);
  assert.ok(assessHardware('g1-2x48-fsdp2',inventory,[1]).reasons.includes('gpu_count_mismatch'));
  const b07=assessHardware('b07-e0-1x8to12',inventory,[0]);assert.equal(b07.ok,true);assert.ok(b07.advisories.length>0);
});

test('execution authorization rejects paid/spot and requires explicit authorization',()=>{
  assert.equal(validateExecutionAuthorization({authorized:'1',computeOrigin:'owned'}).ok,true);
  assert.equal(validateExecutionAuthorization({authorized:'1',computeOrigin:'free'}).ok,true);
  assert.equal(validateExecutionAuthorization({authorized:'1',computeOrigin:'donated'}).ok,true);
  for(const origin of ['paid','spot','runpod',''])assert.equal(validateExecutionAuthorization({authorized:'1',computeOrigin:origin}).ok,false);
  assert.equal(validateExecutionAuthorization({authorized:'0',computeOrigin:'owned'}).ok,false);
});

test('payload identity is hash-only and never contains argv secrets',()=>{
  const sentinel='SUPER_SECRET_TOKEN_123';const identity=payloadIdentity(['python','train.py','--token',sentinel]);
  assert.equal(identity.executable,'python');assert.match(identity.argv_sha256,/^[0-9a-f]{64}$/);
  assert.equal(JSON.stringify(identity).includes(sentinel),false);
});

test('payload telemetry contract distinguishes complete exact counters from malformed data',()=>{
  assert.equal(parsePayloadTelemetry(completeTelemetry()).ok,true);
  assert.equal(parsePayloadTelemetry({...completeTelemetry(),peak_vram_bytes:1.5}).ok,false);
  assert.equal(parsePayloadTelemetry({...completeTelemetry(),tokens_processed:'512'}).ok,false);
  assert.equal(parsePayloadTelemetry({}).ok,false);
});

test('compute attempt receipt binds exact hardware/telemetry/retry and self-hashes canonically',()=>{
  const receipt=buildComputeAttemptReceipt({
    attemptId:'attempt-1',profileId:'g1-1x80-bf16-lora',runManifestSha256:RUN,
    payloadArgv:['python','train.py','--token','SECRET_SHOULD_NOT_APPEAR'],computeOrigin:'owned',
    hardware:{inventory,gpu_indices:[0]},elapsedMs:1250,payloadTelemetry:completeTelemetry(),retryIndex:1,
    deviceMemorySamplePeakMib:[70000],sampleIntervalMs:250,status:'success',exitCode:0,
  });
  const check=verifyComputeAttemptReceipt(receipt);assert.equal(check.ok,true,check.reasons.join(','));
  assert.equal(receipt.telemetry.allocated_gpu_seconds,'1.25');assert.equal(receipt.telemetry.peak_vram_bytes,123456789);
  assert.equal(receipt.telemetry.tokens_processed,512);assert.equal(receipt.telemetry.attempt_retry_index,1);
  assert.equal(JSON.stringify(receipt).includes('SECRET_SHOULD_NOT_APPEAR'),false);
});

test('compute receipt tampering fails self-digest verification',()=>{
  const r=buildComputeAttemptReceipt({attemptId:'a',profileId:'b07-e0-1x8to12',runManifestSha256:RUN,payloadArgv:['python','x.py'],computeOrigin:'free',hardware:{inventory,gpu_indices:[7]},elapsedMs:100,payloadTelemetry:completeTelemetry(),deviceMemorySamplePeakMib:[5000],status:'success',exitCode:0});
  const bad={...r,profile_id:'g1-1x80-bf16-lora'};assert.equal(verifyComputeAttemptReceipt(bad).ok,false);
});

test('successful child without authoritative payload telemetry becomes failed/incomplete evidence',()=>{
  const r=buildComputeAttemptReceipt({attemptId:'a',profileId:'b07-e0-1x8to12',runManifestSha256:RUN,payloadArgv:['python','x.py'],computeOrigin:'free',hardware:{inventory,gpu_indices:[7]},elapsedMs:100,payloadTelemetry:null,deviceMemorySamplePeakMib:[5000],status:'failed',exitCode:0,failureCode:'telemetry_incomplete'});
  assert.equal(verifyComputeAttemptReceipt(r).ok,true);assert.equal(r.telemetry.telemetry_complete,false);assert.equal(r.outcome.status,'failed');
});

test('ms-swift builder pins Qwen3.8 BF16 LoRA colocate + LoRA-only sync and rejects quantization flags',()=>{
  const args=buildMsSwiftColocateLoRAArgs({datasetPath:'/owned/tasks.jsonl',rewardPluginPath:'/owned/reward.py',rewardFunctions:['objective_reward'],loraRank:8});
  const joined=args.join(' ');for(const required of ['Qwen/Qwen3.8-27B','--tuner_type lora','--use_vllm true','--vllm_mode colocate','--vllm_enable_lora true','--vllm_max_lora_rank 8'])assert.ok(joined.includes(required),required);
  assert.equal(/qlora|4bit|quantization/i.test(joined),false);
  assert.throws(()=>buildMsSwiftColocateLoRAArgs({datasetPath:'x',rewardPluginPath:'y',rewardFunctions:['r'],extraArgs:['--load_in_4bit','true']}));
});

async function runDispatch(args,{env={}}={}){
  const child=spawn(process.execPath,['scripts/p3-compute-dispatch.mjs',...args],{cwd:root,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);const [code,signal]=await once(child,'exit');return {code,signal,stdout,stderr};
}

test('dispatcher dry-run logs hash-only payload identity and no raw secret argv',async()=>{
  const sentinel='DRYRUN_SECRET_SENTINEL';const r=await runDispatch(['--profile','b07-e0-1x8to12','--run-manifest-sha',RUN,'--gpu-indices','0','--dry-run','--','python','runner.py','--api-key',sentinel]);
  assert.equal(r.code,0,r.stderr);assert.equal((r.stdout+r.stderr).includes(sentinel),false);const line=JSON.parse(r.stdout.trim());assert.equal(line.execute,false);assert.match(line.payload_identity.argv_sha256,/^[0-9a-f]{64}$/);
});

test('dispatcher blocks execution before GPU discovery when authorization/origin is not zero-cash explicit',async()=>{
  const r=await runDispatch(['--profile','b07-e0-1x8to12','--run-manifest-sha',RUN,'--gpu-indices','0','--execute','--','python','runner.py'],{env:{AQLEVON_GPU_EXECUTION_AUTHORIZED:'0',AQLEVON_COMPUTE_ORIGIN:'paid'}});
  assert.equal(r.code,2);assert.ok(r.stderr.includes('execution_blocked'));
});

test('CPU-only mocked dispatcher integration emits exact success receipt without secret leakage',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'aqlevon-p3-dispatch-'));const bin=path.join(tmp,'bin');fs.mkdirSync(bin);const telemetry=path.join(tmp,'telemetry.json'),receipts=path.join(tmp,'receipts');
  const fake=path.join(bin,'nvidia-smi');fs.writeFileSync(fake,`#!/bin/sh
case "$*" in
  *memory.total*) echo '0, Mock A100 80GB, 81920' ;;
  *memory.used*) echo '0, 4096' ;;
  *) exit 1 ;;
esac
`);fs.chmodSync(fake,0o755);
  const sentinel='EXEC_SECRET_SENTINEL';
  const payload=`const fs=require('fs');setTimeout(()=>{fs.writeFileSync(process.argv[1],JSON.stringify({schema:'${PAYLOAD_TELEMETRY_SCHEMA}',peak_vram_bytes:987654321,tokens_processed:321,tokens_generated:12}))},60)`;
  const r=await runDispatch(['--profile','g1-1x80-bf16-lora','--run-manifest-sha',RUN,'--gpu-indices','0','--telemetry-json',telemetry,'--receipt-dir',receipts,'--sample-ms','25','--execute','--',process.execPath,'-e',payload,telemetry,sentinel],{env:{PATH:`${bin}:${process.env.PATH}`,AQLEVON_GPU_EXECUTION_AUTHORIZED:'1',AQLEVON_COMPUTE_ORIGIN:'free'}});
  assert.equal(r.code,0,r.stderr);assert.equal((r.stdout+r.stderr).includes(sentinel),false);
  const files=fs.readdirSync(receipts);assert.equal(files.length,1);const receipt=JSON.parse(fs.readFileSync(path.join(receipts,files[0]),'utf8'));assert.equal(verifyComputeAttemptReceipt(receipt).ok,true);assert.equal(receipt.telemetry.telemetry_complete,true);assert.equal(receipt.telemetry.peak_vram_bytes,987654321);assert.equal(receipt.telemetry.tokens_processed,321);assert.equal(receipt.telemetry.tokens_generated,12);assert.equal(receipt.telemetry.attempt_retry_index,0);assert.ok(Number(receipt.telemetry.allocated_gpu_seconds)>0);assert.equal(JSON.stringify(receipt).includes(sentinel),false);
});

test('retry requires explicit retry-safe acknowledgement',async()=>{
  const r=await runDispatch(['--profile','b07-e0-1x8to12','--run-manifest-sha',RUN,'--gpu-indices','0','--max-retries','1','--dry-run','--','python','runner.py']);assert.equal(r.code,2);assert.ok(r.stderr.includes('retries_require_explicit_retry_safe'));
});

test('CPU-only mocked retry produces separate failed and successful receipts with exact retry indices',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'aqlevon-p3-retry-'));const bin=path.join(tmp,'bin');fs.mkdirSync(bin);const telemetry=path.join(tmp,'telemetry.json'),receipts=path.join(tmp,'receipts'),marker=path.join(tmp,'marker');
  const fake=path.join(bin,'nvidia-smi');fs.writeFileSync(fake,`#!/bin/sh
case "$*" in
  *memory.total*) echo '0, Mock 12GB, 12288' ;;
  *memory.used*) echo '0, 2048' ;;
  *) exit 1 ;;
esac
`);fs.chmodSync(fake,0o755);
  const payload=`const fs=require('fs');const [telemetry,marker]=process.argv.slice(1);if(!fs.existsSync(marker)){fs.writeFileSync(marker,'1');process.exit(7)}fs.writeFileSync(telemetry,JSON.stringify({schema:'${PAYLOAD_TELEMETRY_SCHEMA}',peak_vram_bytes:222222222,tokens_processed:99,tokens_generated:3}))`;
  const r=await runDispatch(['--profile','b07-e0-1x8to12','--run-manifest-sha',RUN,'--gpu-indices','0','--telemetry-json',telemetry,'--receipt-dir',receipts,'--max-retries','1','--retry-safe','--sample-ms','25','--execute','--',process.execPath,'-e',payload,telemetry,marker],{env:{PATH:`${bin}:${process.env.PATH}`,AQLEVON_GPU_EXECUTION_AUTHORIZED:'1',AQLEVON_COMPUTE_ORIGIN:'donated'}});
  assert.equal(r.code,0,r.stderr);const files=fs.readdirSync(receipts).sort();assert.equal(files.length,2);const rows=files.map(f=>JSON.parse(fs.readFileSync(path.join(receipts,f),'utf8'))).sort((a,b)=>a.telemetry.attempt_retry_index-b.telemetry.attempt_retry_index);
  assert.equal(rows[0].outcome.status,'failed');assert.equal(rows[0].outcome.failure_code,'payload_exit_nonzero');assert.equal(rows[0].telemetry.attempt_retry_index,0);assert.equal(rows[1].outcome.status,'success');assert.equal(rows[1].telemetry.attempt_retry_index,1);assert.equal(rows[1].telemetry.tokens_processed,99);for(const row of rows)assert.equal(verifyComputeAttemptReceipt(row).ok,true);
});
