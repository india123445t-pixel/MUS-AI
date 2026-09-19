import test from 'node:test';
import assert from 'node:assert/strict';
import {buildRuntimeAccounting,normalizeBoundedInteger,normalizeOpenAIUsage,parseStrictBoundedInteger,sanitizeEndpointForLog} from '../lib/aqlevon/runtime-economics.js';

test('runtime accounting normalizes OpenAI usage and derives bounded compute economics',()=>{
  const usage=normalizeOpenAIUsage({prompt_tokens:100,completion_tokens:50,total_tokens:150,prompt_tokens_details:{cached_tokens:20},completion_tokens_details:{reasoning_tokens:10}});
  assert.deepEqual(usage,{prompt_tokens:100,completion_tokens:50,total_tokens:150,cached_prompt_tokens:20,reasoning_tokens:10});
  const metrics=buildRuntimeAccounting({elapsedMs:2000,usage,computeDevice:'H100',gpuCount:2,gpuPowerWatts:300,gpuHourlyUsd:1.5});
  assert.equal(metrics.schema,'aqlevon-runtime-metrics-v1');
  assert.equal(metrics.allocated_gpu_seconds,4);
  assert.equal(metrics.cached_prompt_ratio,0.2);
  assert.equal(metrics.completion_tokens_per_second,25);
  assert.equal(metrics.completion_tokens_per_gpu_second,12.5);
  assert.equal(metrics.estimated_energy_wh,0.333333);
  assert.equal(metrics.estimated_gpu_cost_usd,0.00166667);
});

test('runtime accounting refuses to invent GPU energy or cost when hardware metadata is absent',()=>{
  const metrics=buildRuntimeAccounting({elapsedMs:1000,usage:{input_tokens:4,output_tokens:2,total_tokens:6}});
  assert.equal(metrics.gpu_count,null);
  assert.equal(metrics.allocated_gpu_seconds,null);
  assert.equal(metrics.estimated_energy_wh,null);
  assert.equal(metrics.estimated_gpu_cost_usd,null);
  assert.equal(metrics.completion_tokens_per_second,2);
});

test('concurrency normalization is always an explicit bounded integer',()=>{
  assert.equal(normalizeBoundedInteger(undefined,{defaultValue:1,min:1,max:16}),1);
  assert.equal(normalizeBoundedInteger('garbage',{defaultValue:1,min:1,max:16}),1);
  assert.equal(normalizeBoundedInteger('2.9',{defaultValue:1,min:1,max:16}),2);
  assert.equal(normalizeBoundedInteger('0',{defaultValue:1,min:1,max:16}),1);
  assert.equal(normalizeBoundedInteger('-4',{defaultValue:1,min:1,max:16}),1);
  assert.equal(normalizeBoundedInteger('16',{defaultValue:1,min:1,max:16}),16);
  assert.equal(normalizeBoundedInteger('999',{defaultValue:1,min:1,max:16}),16);
});

test('strict timeout parser rejects malformed, decimal, and out-of-range values',()=>{
  assert.equal(parseStrictBoundedInteger(undefined,{defaultValue:240000,min:100,max:900000}),240000);
  assert.equal(parseStrictBoundedInteger('120000',{defaultValue:240000,min:100,max:900000}),120000);
  for(const bad of ['abc','100.5','99','900001','-1','Infinity'])assert.equal(parseStrictBoundedInteger(bad,{defaultValue:240000,min:100,max:900000}),null);
});

test('endpoint log sanitizer strips userinfo, query credentials, and path tokens by logging origin only',()=>{
  const safe=sanitizeEndpointForLog('https://alice:secret@example.com:8443/private/signed-token/v1?token=query-secret#frag');
  assert.equal(safe,'https://example.com:8443');
  for(const secret of ['alice','secret','signed-token','query-secret'])assert.equal(safe.includes(secret),false);
});
