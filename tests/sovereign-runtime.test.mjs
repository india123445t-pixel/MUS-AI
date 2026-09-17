import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {checkSelfHostedHealth,generateModelResponse,getSelfHostedRuntimeDescriptor,resolveSelfHostedConfig} from '../lib/kite/providers.js';

const TARGET='Qwen/Qwen3.8-27B-FP8';

function saveEnv(keys){return Object.fromEntries(keys.map(k=>[k,process.env[k]]))}
function restoreEnv(saved){for(const [k,v] of Object.entries(saved)){if(v===undefined)delete process.env[k];else process.env[k]=v}}

async function mockEndpoint({chatStatus=200}={}){
  const requests=[];
  const server=http.createServer(async(req,res)=>{
    if(req.url==='/health'){
      res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({status:'ok'}));return;
    }
    if(req.url==='/v1/chat/completions'){
      let raw='';for await(const chunk of req)raw+=chunk;
      requests.push({url:req.url,headers:req.headers,body:JSON.parse(raw||'{}')});
      if(chatStatus!==200){res.writeHead(chatStatus,{'content-type':'application/json'});res.end(JSON.stringify({error:{message:'mock upstream unavailable'}}));return;}
      res.writeHead(200,{'content-type':'application/json'});
      res.end(JSON.stringify({id:'mock-1',object:'chat.completion',model:TARGET,choices:[{index:0,message:{role:'assistant',content:'KITE sovereign mock response'}}]}));
      return;
    }
    res.writeHead(404);res.end();
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  const {port}=server.address();
  return {server,requests,base:`http://127.0.0.1:${port}`};
}

test('Qwen sovereign target is selectable through settings or env without provider hard-code',()=>{
  const saved=saveEnv(['KITE_MODEL_NAME','KITE_MODEL_URL']);
  try{
    process.env.KITE_MODEL_NAME=TARGET;process.env.KITE_MODEL_URL='http://127.0.0.1:9999/v1';
    assert.equal(resolveSelfHostedConfig({}).model,TARGET);
    assert.equal(resolveSelfHostedConfig({self_hosted_model:'custom/model'}).model,'custom/model');
    assert.equal(resolveSelfHostedConfig({self_hosted_url:'http://localhost:8000/v1'}).endpoint,'http://localhost:8000/v1/chat/completions');
  }finally{restoreEnv(saved)}
});

test('mock OpenAI-compatible endpoint proves self_hosted_only request/response without external inference',async()=>{
  const mock=await mockEndpoint();
  const keys=['KITE_MODEL_URL','KITE_MODEL_NAME','KITE_MODEL_KEY','OPENROUTER_API_KEY','GROQ_API_KEY','GEMINI_API_KEY','MISTRAL_API_KEY','CEREBRAS_API_KEY','HF_TOKEN'];
  const saved=saveEnv(keys);const originalFetch=globalThis.fetch;const seen=[];
  try{
    process.env.KITE_MODEL_URL=`${mock.base}/v1`;
    process.env.KITE_MODEL_NAME=TARGET;
    process.env.KITE_MODEL_KEY='local-test-key';
    process.env.OPENROUTER_API_KEY='must-not-be-used';process.env.GROQ_API_KEY='must-not-be-used';process.env.GEMINI_API_KEY='must-not-be-used';process.env.MISTRAL_API_KEY='must-not-be-used';process.env.CEREBRAS_API_KEY='must-not-be-used';process.env.HF_TOKEN='must-not-be-used';
    globalThis.fetch=async(url,init)=>{
      seen.push(String(url));
      assert.ok(String(url).startsWith(mock.base),`external provider attempted in self_hosted_only: ${url}`);
      return originalFetch(url,init);
    };
    const result=await generateModelResponse([{role:'user',content:'ping'}],false,{runtime_mode:'self_hosted_only',self_hosted_model:TARGET},{includeDiagnostics:true});
    assert.equal(result.provider,'kite-engine');
    assert.equal(result.model,TARGET);
    assert.equal(result.text,'KITE sovereign mock response');
    assert.deepEqual(seen,[`${mock.base}/v1/chat/completions`]);
    assert.equal(mock.requests.length,1);
    assert.equal(mock.requests[0].body.model,TARGET);
    assert.equal(mock.requests[0].headers.authorization,'Bearer local-test-key');
  }finally{globalThis.fetch=originalFetch;restoreEnv(saved);mock.server.close();await once(mock.server,'close')}
});

test('self_hosted_only failure does not fall back to OpenRouter/Gemini/other external providers',async()=>{
  const mock=await mockEndpoint({chatStatus:503});
  const keys=['KITE_MODEL_URL','KITE_MODEL_NAME','OPENROUTER_API_KEY','GROQ_API_KEY','GEMINI_API_KEY','MISTRAL_API_KEY','CEREBRAS_API_KEY','HF_TOKEN'];
  const saved=saveEnv(keys);const originalFetch=globalThis.fetch;const seen=[];
  try{
    process.env.KITE_MODEL_URL=`${mock.base}/v1/chat/completions`;process.env.KITE_MODEL_NAME=TARGET;
    process.env.OPENROUTER_API_KEY='present-but-forbidden';process.env.GROQ_API_KEY='present-but-forbidden';process.env.GEMINI_API_KEY='present-but-forbidden';
    globalThis.fetch=async(url,init)=>{seen.push(String(url));assert.ok(String(url).startsWith(mock.base),`external fallback attempted: ${url}`);return originalFetch(url,init)};
    const result=await generateModelResponse([{role:'user',content:'fail closed'}],false,{runtime_mode:'self_hosted_only'},{includeDiagnostics:true});
    assert.equal(result.unavailable,true);
    assert.equal(result.error_class,'UPSTREAM_5XX');
    assert.equal(result.diagnostics.length,1);
    assert.equal(result.diagnostics[0].provider,'kite-engine');
    assert.deepEqual(seen,[`${mock.base}/v1/chat/completions`]);
  }finally{globalThis.fetch=originalFetch;restoreEnv(saved);mock.server.close();await once(mock.server,'close')}
});

test('self-hosted health and descriptor are secret-safe',async()=>{
  const mock=await mockEndpoint();
  const saved=saveEnv(['KITE_MODEL_URL','KITE_MODEL_NAME','KITE_MODEL_KEY']);
  try{
    process.env.KITE_MODEL_URL=`${mock.base}/v1/chat/completions`;process.env.KITE_MODEL_NAME=TARGET;process.env.KITE_MODEL_KEY='super-secret-health-key';
    const descriptor=getSelfHostedRuntimeDescriptor({runtime_mode:'self_hosted_only'});
    assert.equal(descriptor.model,TARGET);assert.equal(descriptor.configured,true);assert.equal(descriptor.credential_configured,true);
    assert.equal(JSON.stringify(descriptor).includes('super-secret-health-key'),false);
    const health=await checkSelfHostedHealth({runtime_mode:'self_hosted_only'});
    assert.deepEqual(health,{ok:true,configured:true,provider:'kite-engine',model:TARGET,status:200,error_class:null});
    assert.equal(JSON.stringify(health).includes('super-secret-health-key'),false);
  }finally{restoreEnv(saved);mock.server.close();await once(mock.server,'close')}
});

test('sovereign evaluation runner covers required categories and stays self_hosted_only',async()=>{
  const {readFile}=await import('node:fs/promises');
  const source=await readFile(new URL('../scripts/sovereign-eval.mjs',import.meta.url),'utf8');
  for(const category of ['reasoning','coding','arabic','moroccan_darija','tool_use'])assert.ok(source.includes(`category:'${category}'`));
  assert.ok(source.includes("runtime_mode:'self_hosted_only'"));
  assert.ok(source.includes('latency_ms'));
});
