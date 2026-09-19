#!/usr/bin/env node
import {randomUUID} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {spawn,spawnSync} from 'node:child_process';
import {
  COMPUTE_PROFILES,assessHardware,buildComputeAttemptReceipt,buildMsSwiftColocateLoRAArgs,
  getComputeProfile,parseGpuIndices,parseNvidiaSmiInventory,parsePayloadTelemetry,payloadIdentity,
  validateExecutionAuthorization,verifyComputeAttemptReceipt,
} from '../lib/aqlevon/compute-dispatch.js';
import {validateP4ExecutionAuthorization} from '../lib/aqlevon/compute-cost-orchestrator.js';

const PAID_WATCHDOG_TERMINATION_MARGIN_MS=5000;
const PAID_WATCHDOG_KILL_GRACE_MS=1000;
const SENSITIVE_ENV_NAME_RE=/(?:api_?key|token|secret|password|credential|private_?key)/i;

function payloadEnvironment(baseEnv,gpuIndices){
  const env={...baseEnv,CUDA_VISIBLE_DEVICES:gpuIndices.join(',')};
  for(const key of Object.keys(env)){
    if(SENSITIVE_ENV_NAME_RE.test(key))delete env[key];
  }
  return env;
}

function die(message,code=2){console.error(JSON.stringify({event:'p3_dispatch_error',error:message}));process.exit(code)}
function intArg(value,{min=0,max=Number.MAX_SAFE_INTEGER}={}){if(!/^\d+$/.test(String(value??'')))return null;const n=Number(value);return Number.isSafeInteger(n)&&n>=min&&n<=max?n:null}
function parseArgs(argv){
  const opts={profile:null,runManifestSha:null,gpuIndices:null,receiptDir:'artifacts/p3-compute',telemetryJson:null,maxRetries:0,retrySafe:false,sampleMs:250,execute:false,list:false,msSwift:null,managerAuthorization:null,runTaskId:null,providerHourlyUsd:null,payload:[]};
  for(let i=0;i<argv.length;i++){
    const a=argv[i];if(a==='--'){opts.payload=argv.slice(i+1);break}
    if(a==='--profile')opts.profile=argv[++i];
    else if(a==='--run-manifest-sha')opts.runManifestSha=argv[++i];
    else if(a==='--gpu-indices')opts.gpuIndices=argv[++i];
    else if(a==='--receipt-dir')opts.receiptDir=argv[++i];
    else if(a==='--telemetry-json')opts.telemetryJson=argv[++i];
    else if(a==='--max-retries')opts.maxRetries=intArg(argv[++i],{min:0,max:3});
    else if(a==='--retry-safe')opts.retrySafe=true;
    else if(a==='--sample-ms')opts.sampleMs=intArg(argv[++i],{min:25,max:10000});
    else if(a==='--manager-authorization')opts.managerAuthorization=argv[++i];
    else if(a==='--run-task-id')opts.runTaskId=argv[++i];
    else if(a==='--provider-hourly-usd')opts.providerHourlyUsd=argv[++i];
    else if(a==='--execute')opts.execute=true;
    else if(a==='--dry-run')opts.execute=false;
    else if(a==='--list-profiles')opts.list=true;
    else if(a==='--ms-swift-dataset'){opts.msSwift=opts.msSwift||{};opts.msSwift.datasetPath=argv[++i]}
    else if(a==='--ms-swift-plugin'){opts.msSwift=opts.msSwift||{};opts.msSwift.rewardPluginPath=argv[++i]}
    else if(a==='--ms-swift-reward-func'){opts.msSwift=opts.msSwift||{};(opts.msSwift.rewardFunctions??=[]).push(argv[++i])}
    else if(a==='--ms-swift-lora-rank'){opts.msSwift=opts.msSwift||{};opts.msSwift.loraRank=intArg(argv[++i],{min:1,max:256})}
    else die(`unknown_arg:${a}`);
  }
  return opts;
}
function inventory(){
  const r=spawnSync('nvidia-smi',['--query-gpu=index,name,memory.total','--format=csv,noheader,nounits'],{encoding:'utf8'});
  if(r.status!==0)return {ok:false,error:'nvidia_smi_inventory_unavailable',rows:[]};
  const normalized=String(r.stdout).split(/\r?\n/).filter(Boolean).map(line=>{
    const p=line.split(',').map(x=>x.trim());return p.length>=3?`${p[0]}|${p.slice(1,-1).join(', ')}|${p.at(-1)}`:'';
  }).filter(Boolean).join('\n');
  const rows=parseNvidiaSmiInventory(normalized);return {ok:rows.length>0,error:rows.length?'':'nvidia_smi_inventory_empty',rows};
}
function memorySample(indices){
  const peaks=new Map(indices.map(i=>[i,0]));
  const r=spawnSync('nvidia-smi',['--query-gpu=index,memory.used','--format=csv,noheader,nounits'],{encoding:'utf8'});
  if(r.status!==0)return [...peaks.values()];
  for(const line of String(r.stdout).split(/\r?\n/)){
    const p=line.split(',').map(x=>x.trim());if(p.length!==2||!/^\d+$/.test(p[0])||!/^\d+$/.test(p[1]))continue;
    const idx=Number(p[0]);if(peaks.has(idx))peaks.set(idx,Math.max(peaks.get(idx),Number(p[1])));
  }
  return indices.map(i=>peaks.get(i)||0);
}
function readTelemetry(file){if(!file)return null;try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}}
function readJson(file){if(!file)return null;try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}}
function failureCode(code,signal,telemetryOk,timedOut=false){if(timedOut)return 'manager_budget_timeout';if(code===0&&!signal&&!telemetryOk)return 'telemetry_incomplete';if(signal)return 'payload_signal';if(code!==0)return 'payload_exit_nonzero';return null}
function terminateTree(child,signal='SIGTERM'){
  if(!child?.pid)return;
  try{if(process.platform!=='win32')process.kill(-child.pid,signal);else child.kill(signal)}catch{try{child.kill(signal)}catch{}}
}
async function runChild(argv,env,maxRuntimeMs=null){
  return await new Promise(resolve=>{
    const child=spawn(argv[0],argv.slice(1),{stdio:'inherit',env,shell:false,detached:process.platform!=='win32'});
    let timedOut=false,timer=null,killTimer=null,settled=false;
    const done=(value)=>{if(settled)return;settled=true;if(timer)clearTimeout(timer);if(killTimer)clearTimeout(killTimer);resolve({...value,timedOut})};
    if(Number.isSafeInteger(maxRuntimeMs)&&maxRuntimeMs>0){
      timer=setTimeout(()=>{
        timedOut=true;
        terminateTree(child,'SIGTERM');
        killTimer=setTimeout(()=>terminateTree(child,'SIGKILL'),PAID_WATCHDOG_KILL_GRACE_MS);
        killTimer.unref();
      },maxRuntimeMs);
      timer.unref();
    }
    child.once('error',err=>done({code:null,signal:null,spawnError:err}));
    child.once('exit',(code,signal)=>done({code,signal,spawnError:null}));
  });
}

const opts=parseArgs(process.argv.slice(2));
if(opts.list){console.log(JSON.stringify({profiles:Object.values(COMPUTE_PROFILES)},null,2));process.exit(0)}
if(opts.maxRetries===null||opts.sampleMs===null)die('invalid_integer_argument');
if(opts.maxRetries>0&&!opts.retrySafe)die('retries_require_explicit_retry_safe');
const profile=getComputeProfile(opts.profile);if(!profile)die('unknown_profile');
const gpuIndices=parseGpuIndices(opts.gpuIndices);if(!gpuIndices)die('invalid_gpu_indices');
if(!/^[0-9a-f]{64}$/.test(String(opts.runManifestSha||'')))die('run_manifest_sha256_required');
let payload=opts.payload;
if(opts.msSwift){
  if(payload.length)die('cannot_mix_payload_and_ms_swift_builder');
  if(opts.profile!=='rl-qwen38-1x80-ms-swift-colocate')die('ms_swift_builder_requires_rl_profile');
  try{payload=[...buildMsSwiftColocateLoRAArgs(opts.msSwift)]}catch(err){die(String(err?.message||err))}
}
if(!payload.length)die('payload_required');
const publicPlan={event:'p3_dispatch_plan',profile_id:profile.profile_id,gpu_indices:gpuIndices,payload_identity:payloadIdentity(payload),execute:opts.execute,max_retries:opts.maxRetries,sample_ms:opts.sampleMs,telemetry_contract:'aqlevon-p3-payload-telemetry-v1',paid_manager_authorization_requested:Boolean(opts.managerAuthorization)};
console.log(JSON.stringify(publicPlan));
if(!opts.execute)process.exit(0);
const computeOrigin=String(process.env.AQLEVON_COMPUTE_ORIGIN||'').trim().toLowerCase();
let auth,maxRuntimeMs=null;
if(computeOrigin==='paid_manager_authorized'){
  const managerAuthorization=readJson(opts.managerAuthorization);
  auth=validateP4ExecutionAuthorization({
    authorized:process.env.AQLEVON_GPU_EXECUTION_AUTHORIZED,computeOrigin,runTaskId:opts.runTaskId,
    runManifestSha256:opts.runManifestSha,profileId:opts.profile,providerHourlyUsd:opts.providerHourlyUsd,
    managerAuthorization,expectedAuthorizationSha256:process.env.AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_SHA256,
  });
  if(!auth.ok)die(`execution_blocked:${auth.reasons.join(',')}`);
  const billingStart=Number(process.env.AQLEVON_BILLING_START_EPOCH_MS);
  if(!Number.isSafeInteger(billingStart)||billingStart<=0)die('execution_blocked:billing_start_epoch_ms_required');
  const remainingMs=auth.max_billed_seconds*1000-(Date.now()-billingStart);
  if(!Number.isFinite(remainingMs)||remainingMs<=0)die('execution_blocked:manager_billed_time_budget_exhausted');
  if(remainingMs<=PAID_WATCHDOG_TERMINATION_MARGIN_MS)die('execution_blocked:manager_billed_time_budget_insufficient_shutdown_margin');
  maxRuntimeMs=Math.max(1,Math.floor(remainingMs-PAID_WATCHDOG_TERMINATION_MARGIN_MS));
}else{
  auth=validateExecutionAuthorization({authorized:process.env.AQLEVON_GPU_EXECUTION_AUTHORIZED,computeOrigin});
  if(!auth.ok)die(`execution_blocked:${auth.reasons.join(',')}`);
}
const inv=inventory();if(!inv.ok)die(inv.error,3);
const hw=assessHardware(opts.profile,inv.rows,gpuIndices);if(!hw.ok)die(`hardware_preflight:${hw.reasons.join(',')}`,3);
fs.mkdirSync(opts.receiptDir,{recursive:true});
if(auth.manager_authorization_sha256){
  const useMarker=path.join(opts.receiptDir,`manager-authorization-${auth.manager_authorization_sha256}.used`);
  try{fs.writeFileSync(useMarker,new Date().toISOString()+'\n',{flag:'wx',mode:0o600})}catch{die('execution_blocked:manager_authorization_already_used')}
}
const childEnv=payloadEnvironment(process.env,gpuIndices);
let finalCode=1;
for(let retryIndex=0;retryIndex<=opts.maxRetries;retryIndex++){
  if(opts.telemetryJson){try{fs.rmSync(opts.telemetryJson,{force:true})}catch{}}
  const attemptId=randomUUID(),started=process.hrtime.bigint();
  let sampled=memorySample(gpuIndices);
  let timer=setInterval(()=>{const current=memorySample(gpuIndices);sampled=sampled.map((v,i)=>Math.max(v,current[i]||0))},opts.sampleMs);timer.unref();
  const result=await runChild(payload,childEnv,maxRuntimeMs);clearInterval(timer);const last=memorySample(gpuIndices);sampled=sampled.map((v,i)=>Math.max(v,last[i]||0));
  const elapsedMs=Number((process.hrtime.bigint()-started)/1000000n);
  const telemetryRaw=readTelemetry(opts.telemetryJson),telemetryCheck=telemetryRaw===null?{ok:false}:parsePayloadTelemetry(telemetryRaw);
  let status=result.code===0&&!result.signal&&!result.timedOut&&telemetryCheck.ok?'success':'failed';
  const failure=result.spawnError?'payload_spawn_error':failureCode(result.code,result.signal,telemetryCheck.ok,result.timedOut);
  const receipt=buildComputeAttemptReceipt({
    attemptId,profileId:opts.profile,runManifestSha256:opts.runManifestSha,payloadArgv:payload,computeOrigin:auth.compute_origin,
    hardware:{inventory:inv.rows,gpu_indices:gpuIndices},elapsedMs,payloadTelemetry:telemetryCheck.ok?telemetryRaw:null,retryIndex,
    deviceMemorySamplePeakMib:sampled,sampleIntervalMs:opts.sampleMs,status,exitCode:Number.isInteger(result.code)?result.code:null,
    signal:result.signal||null,failureCode:failure,
  });
  const verified=verifyComputeAttemptReceipt(receipt);if(!verified.ok)die(`internal_receipt_invalid:${verified.reasons.join(',')}`,4);
  const receiptPath=path.join(opts.receiptDir,`compute-attempt-${attemptId}.json`);fs.writeFileSync(receiptPath,JSON.stringify(receipt,null,2)+'\n',{mode:0o600});
  console.log(JSON.stringify({event:'p3_dispatch_attempt_complete',attempt_id:attemptId,receipt_sha256:receipt.receipt_sha256,status,telemetry_complete:receipt.telemetry.telemetry_complete,retry_index:retryIndex,elapsed_ms:receipt.telemetry.elapsed_ms,allocated_gpu_seconds:receipt.telemetry.allocated_gpu_seconds,peak_vram_bytes:receipt.telemetry.peak_vram_bytes,tokens_processed:receipt.telemetry.tokens_processed,tokens_generated:receipt.telemetry.tokens_generated,receipt_path:receiptPath}));
  finalCode=status==='success'?0:result.code||4;
  if(status==='success'||retryIndex===opts.maxRetries)break;
}
process.exit(finalCode);
