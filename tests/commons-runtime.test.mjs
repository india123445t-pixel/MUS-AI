import test from 'node:test';
import assert from 'node:assert/strict';
import { commonsSubmitAndWait } from '../lib/aqlevon/commons-edge.js';

test('commons helper does not require a Supabase key in its public interface',()=>{
  assert.equal(typeof commonsSubmitAndWait,'function');
});

test('commons helper returns null when edge health is unreachable',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async()=>{throw new Error('offline')};
  try{
    const out=await commonsSubmitAndWait({input:'hello',messages:[{role:'user',content:'hello'}],timeoutMs:50,pollMs:1});
    assert.equal(out,null);
  }finally{globalThis.fetch=original}
});
