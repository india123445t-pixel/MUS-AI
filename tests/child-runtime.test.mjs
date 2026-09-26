import test from 'node:test';
import assert from 'node:assert/strict';
import {childHealth,generateChildResponse} from '../lib/aqlevon/child-runtime.js';

function saveEnv(keys){return Object.fromEntries(keys.map(k=>[k,process.env[k]]))}
function restoreEnv(saved){for(const [k,v] of Object.entries(saved)){if(v===undefined)delete process.env[k];else process.env[k]=v}}

test('child RunPod health uses zero-inference health endpoint',async()=>{
  const saved=saveEnv(['AQLEVON_CHILD_MODEL_URL','AQLEVON_CHILD_RUNPOD_ENDPOINT_ID','AQLEVON_CHILD_RUNPOD_KEY']);
  try{
    delete process.env.AQLEVON_CHILD_MODEL_URL;
    process.env.AQLEVON_CHILD_RUNPOD_ENDPOINT_ID='child-test-endpoint';
    process.env.AQLEVON_CHILD_RUNPOD_KEY='child-test-key';
    let seen=null;
    const h=await childHealth({fetchImpl:async(url,init)=>{
      seen={url:String(url),auth:init?.headers?.Authorization};
      return {ok:true,status:200};
    }});
    assert.equal(h.ok,true);
    assert.equal(h.transport,'runpod-serverless');
    assert.equal(seen.url,'https://api.runpod.ai/v2/child-test-endpoint/health');
    assert.equal(seen.auth,'Bearer child-test-key');
  }finally{restoreEnv(saved)}
});

test('child response embeds owner policy without undefined variables',async()=>{
  const saved=saveEnv(['AQLEVON_CHILD_MODEL_URL','AQLEVON_CHILD_RUNPOD_ENDPOINT_ID','AQLEVON_CHILD_RUNPOD_KEY']);
  const originalFetch=globalThis.fetch;
  try{
    delete process.env.AQLEVON_CHILD_MODEL_URL;
    process.env.AQLEVON_CHILD_RUNPOD_ENDPOINT_ID='child-test-endpoint';
    process.env.AQLEVON_CHILD_RUNPOD_KEY='child-test-key';
    let body=null;
    globalThis.fetch=async(_url,init)=>{
      body=JSON.parse(init.body);
      return {ok:true,status:200,async json(){return {output:{choices:[{message:{content:'ok'}}]}}}};
    };
    const r=await generateChildResponse({
      messages:[{role:'user',content:'hello'}],
      ownerPolicy:{external_network:true,production_weight_write:true}
    });
    assert.equal(r.text,'ok');
    const system=body.input.messages[0].content;
    assert.match(system,/OWNER_POLICY/);
    assert.match(system,/"production_weight_write":true/);
  }finally{globalThis.fetch=originalFetch;restoreEnv(saved)}
});
