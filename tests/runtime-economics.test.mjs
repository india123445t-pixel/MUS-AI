import test from 'node:test';
import assert from 'node:assert/strict';
import {buildRuntimeAccounting,normalizeOpenAIUsage,summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

test('runtime accounting normalizes OpenAI usage and derives bounded compute economics',()=>{
  const usage=normalizeOpenAIUsage({
    prompt_tokens:100,
    completion_tokens:50,
    total_tokens:150,
    prompt_tokens_details:{cached_tokens:20},
    completion_tokens_details:{reasoning_tokens:10},
  });
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

test('compute-per-verified-success charges failed attempts to the efficiency denominator',()=>{
  const summary=summarizeVerifiedEfficiency([
    {verified:true,runtime_metrics:{allocated_gpu_seconds:4,estimated_energy_wh:0.4,estimated_gpu_cost_usd:0.004}},
    {verified:false,runtime_metrics:{allocated_gpu_seconds:2,estimated_energy_wh:0.2,estimated_gpu_cost_usd:0.002}},
  ]);
  assert.equal(summary.attempts,2);
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.gpu_seconds_per_verified_success,6);
  assert.equal(summary.estimated_energy_wh_per_verified_success,0.6);
  assert.equal(summary.estimated_gpu_cost_usd_per_verified_success,0.006);
});
