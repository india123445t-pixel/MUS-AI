import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';

const PORT=3100;
const BASE=`http://127.0.0.1:${PORT}`;
const env={
  ...process.env,
  NEXT_PUBLIC_SUPABASE_URL:'https://example.supabase.co',
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:'test-only-placeholder',
  AQLEVON_MODEL_URL:'',
  AQLEVON_MODEL_RUNPOD_ID:'',
  AQLEVON_MODEL_RUNPOD_KEY:'',
  AQLEVON_MODEL_KEY:'',
  AQLEVON_WEB_SEARCH_KEY:'',
  JINA_API_KEY:'',
};

const child=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-p',String(PORT)],{
  env,
  stdio:['ignore','pipe','pipe'],
});
let out='';
child.stdout.on('data',d=>{out+=String(d)});
child.stderr.on('data',d=>{out+=String(d)});

async function waitReady(){
  const deadline=Date.now()+30000;
  while(Date.now()<deadline){
    try{
      const r=await fetch(BASE+'/chat',{redirect:'manual'});
      if(r.status>0)return;
    }catch{}
    await new Promise(r=>setTimeout(r,300));
  }
  throw new Error('Next server did not become ready\n'+out);
}

async function get(path,init){
  return fetch(BASE+path,{redirect:'manual',...init});
}

try{
  await waitReady();

  const chat=await get('/chat');
  assert.equal(chat.status,200);
  const h=chat.headers;
  assert.equal(h.get('x-frame-options'),'DENY');
  assert.equal(h.get('x-content-type-options'),'nosniff');
  assert.match(h.get('content-security-policy')||'',/frame-ancestors 'none'/);
  assert.equal(h.get('referrer-policy'),'strict-origin-when-cross-origin');
  assert.match(h.get('permissions-policy')||'',/camera=\(\)/);

  const workbench=await get('/workbench');
  assert.equal(workbench.status,200);
  assert.match(await workbench.text(),/AQLEVON Workbench/);

  const settings=await get('/settings');
  assert.equal(settings.status,200);

  const missing=await get('/definitely-not-a-real-route-smoke');
  assert.equal(missing.status,404);
  assert.match(await missing.text(),/404/);

  const missingApi=await get('/api/definitely-not-a-real-route-smoke');
  assert.equal(missingApi.status,404);

  const wbStatus=await get('/api/workbench/status');
  assert.equal(wbStatus.status,200);
  const wbJson=await wbStatus.json();
  assert.equal(typeof wbJson.bos_version,'string');

  const wbLogs=await get('/api/workbench/logs');
  assert.equal(wbLogs.status,401);

  const intelligence=await get('/api/status?intelligence=1');
  assert.equal(intelligence.status,401);
  const intelJson=await intelligence.json();
  assert.equal(intelJson.error_class,'AUTH_REQUIRED');

  const bosInternal=await get('/api/internal/bos-status');
  assert.equal(bosInternal.status,401);
  assert.equal((await bosInternal.json()).message,'TOKEN_MISSING');

  const runtimeInternal=await get('/api/internal/self-hosted-health');
  assert.equal(runtimeInternal.status,401);
  assert.equal((await runtimeInternal.json()).message,'TOKEN_MISSING');

  const status=await get('/api/status');
  assert.equal(status.status,200);
  const statusJson=await status.json();
  assert.equal(statusJson.sovereign_runtime,true);
  assert.equal(statusJson.external_provider_routing,false);

  const chatPost=await get('/api/commons/chat',{
    method:'POST',
    headers:{'content-type':'application/json'},
    body:JSON.stringify({input:'smoke',history:[],sessionId:'00000000-0000-4000-8000-000000000001',conversationId:'00000000-0000-4000-8000-000000000002'})
  });
  assert.equal(chatPost.status,503);
  const chatJson=await chatPost.json();
  assert.ok(['ENV_MISSING','CONTROL_PLANE_UNAVAILABLE'].includes(chatJson.error_class),JSON.stringify(chatJson));

  console.log('PRODUCT_RUNTIME_SMOKE_PASS');
} finally {
  child.kill('SIGTERM');
  await new Promise(resolve=>{
    const timer=setTimeout(resolve,3000);
    child.once('exit',()=>{clearTimeout(timer);resolve()});
  });
}
