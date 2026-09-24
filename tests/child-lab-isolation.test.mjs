import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

const runtime=read('lib/aqlevon/child-runtime.js');
const status=read('app/api/admin/child-lab/status/route.js');
const chat=read('app/api/admin/child-lab/chat/route.js');
const page=read('app/admin/child-lab/page.js');
const tools=read('lib/aqlevon/child-tools.js');
const toolRoute=read('app/api/admin/child-lab/tool/route.js');
const admin=read('app/admin/page.js');

test('child runtime is physically separated from public AQLEVON runtime config',()=>{
  assert.match(runtime,/AQLEVON_CHILD_MODEL_URL/);
  assert.match(runtime,/AQLEVON_CHILD_MODEL_NAME/);
  assert.match(runtime,/AQLEVON_CHILD_MODEL_KEY/);
  assert.match(runtime,/AQLEVON_CHILD_MODEL_HEALTH_URL/);
  assert.doesNotMatch(runtime,/AQLEVON_MODEL_URL/);
  assert.doesNotMatch(runtime,/LOCAL_MODEL_/);
  assert.doesNotMatch(runtime,/generateModelResponse/);
  assert.match(runtime,/AQLEVON_CHILD_RUNTIME_V1/);
});

test('child APIs are owner-only and cannot write production or training lanes',()=>{
  for(const src of [status,chat]){
    assert.match(src,/system_owner/);
    assert.match(src,/OWNER_REQUIRED/);
  }
  assert.match(status,/public_model_access:false/);
  assert.match(status,/production_weight_write:false/);
  assert.match(status,/training_lane_write:false/);
  assert.match(status,/memory_scope:'child-lab-only'/);
  assert.match(chat,/production_weight_write:false/);
  assert.match(chat,/training_lane_write:false/);
  assert.match(chat,/execution_state:'LAB_ONLY'/);
});

test('child lab browser state is isolated and tools fail closed',()=>{
  assert.match(page,/aqlevon-child-lab-v1/);
  assert.match(page,/مختبر الطفل/);
  assert.match(page,/لا تلمس نموذج المستخدمين/);
  assert.match(status,/ADAPTER_REQUIRED/);
  assert.match(page,/Runtime الطفل غير متصل/);
  assert.match(page,/مسح ذاكرة ودروس مختبر الطفل فقط/);
  assert.doesNotMatch(page,/aqlevon-workspace-web-v1/);
});

test('child tool broker is isolated and receipt-gated',()=>{
  assert.match(tools,/AQLEVON_CHILD_WEB_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_BROWSER_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_TERMINAL_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_FILES_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_MEDIA_ADAPTER_URL/);
  assert.doesNotMatch(tools,/AQLEVON_MODEL_URL/);
  assert.match(tools,/RECEIPT_REQUIRED/);
  assert.match(tools,/production_weight_write:false/);
  assert.match(tools,/training_lane_write:false/);
  assert.match(toolRoute,/system_owner/);
  assert.match(toolRoute,/OWNER_REQUIRED/);
  assert.match(toolRoute,/EXECUTED_WITH_RECEIPT/);
  assert.match(toolRoute,/NOT_EXECUTED/);
});

test('child lab supports portable snapshots without touching production state',()=>{
  assert.match(page,/AQLEVON_CHILD_PERSONA_PACKAGE_V1/);
  assert.match(page,/saveSnapshot/);
  assert.match(page,/restoreSnapshot/);
  assert.match(page,/exportPackage/);
  assert.match(page,/importPackage/);
  assert.match(page,/aqlevon-child-/);
  assert.match(page,/toolRuns/);
  assert.match(page,/Receipt/);
});

test('owner console links to child lab and no longer exposes legacy runtime model choice',()=>{
  assert.match(admin,/href="\/admin\/child-lab"/);
  assert.match(admin,/const safeModes=\['self_hosted_only'\]/);
  assert.doesNotMatch(admin,/openrouter_model/);
  assert.doesNotMatch(admin,/openrouter_primary/);
});
