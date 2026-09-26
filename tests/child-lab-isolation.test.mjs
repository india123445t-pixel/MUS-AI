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
const ownerPolicy=read('lib/aqlevon/child-owner-policy.js');

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

test('child APIs remain owner-only while operational policy is owner-controlled',()=>{
  for(const src of [status,chat]){
    assert.match(src,/system_owner/);
    assert.match(src,/OWNER_REQUIRED/);
  }
  assert.match(status,/policy_mode:'owner-controlled'/);
  assert.match(status,/owner_policy_source:'client-owner-session'/);
  assert.match(status,/memory_scope:'child-lab-only'/);
  assert.match(chat,/ownerPolicy:body\.owner_policy/);
  assert.match(chat,/owner_policy:body\.owner_policy/);
  assert.match(chat,/execution_state:'LAB_ONLY'/);
  assert.match(runtime,/OWNER_POLICY/);
  assert.match(runtime,/normalizeChildOwnerPolicy/);
});

test('child lab browser state is owner-controlled and unavailable capabilities still fail closed',()=>{
  assert.match(page,/aqlevon-child-lab-v1/);
  assert.match(page,/مختبر الطفل/);
  assert.match(page,/OWNER_POLICY_STORAGE/);
  assert.match(page,/تحت تحكم المالك/);
  assert.match(page,/افتح كل ما يمكن التحكم به/);
  assert.match(tools,/ADAPTER_REQUIRED/);
  assert.match(tools,/CONFIGURED/);
  assert.doesNotMatch(tools,/cfg\.configured\?'CONNECTED'/);
  assert.match(page,/configured!==true/);
  assert.match(page,/Runtime الطفل غير متصل/);
  assert.match(page,/clearChildMemories/);
  assert.match(page,/defaultChildOwnerPolicy/);
  assert.doesNotMatch(page,/aqlevon-workspace-web-v1/);
});

test('fresh child starts without an owner-defined personality or purpose',()=>{
  assert.match(page,/purpose:''/);
  assert.match(page,/persona:''/);
  assert.match(page,/الطفل الجديد يبدأ بلا شخصية خاصة مكتوبة/);
  assert.doesNotMatch(page,/persona:'أنت طفل AQLEVON تجريبي/);
});

test('child tool broker follows owner policy and preserves owner authentication',()=>{
  assert.match(tools,/AQLEVON_CHILD_WEB_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_BROWSER_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_TERMINAL_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_FILES_ADAPTER_URL/);
  assert.match(tools,/AQLEVON_CHILD_MEDIA_ADAPTER_URL/);
  assert.doesNotMatch(tools,/AQLEVON_MODEL_URL/);
  assert.match(tools,/normalizeChildOwnerPolicy/);
  assert.match(tools,/policy\.receipt_required/);
  assert.match(tools,/owner_policy:policy/);
  assert.match(toolRoute,/system_owner/);
  assert.match(toolRoute,/OWNER_REQUIRED/);
  assert.match(toolRoute,/ownerPolicy:body\.owner_policy/);
  assert.match(toolRoute,/NOT_EXECUTED/);
});

test('child exports use the browser URL constructor safely',()=>{
  assert.match(page,/globalThis\.URL\.createObjectURL/);
  assert.match(page,/globalThis\.URL\.revokeObjectURL/);
  assert.doesNotMatch(page,/[^.]URL\.createObjectURL/);
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

test('child can learn from a completed tool mission only inside child memory',()=>{
  assert.match(page,/نفّذ \+ تعلّم/);
  assert.match(page,/source:'tool-learning'/);
  assert.match(page,/kind:'experience'/);
  assert.match(page,/learned_memory_id/);
  assert.match(page,/المادة التالية ناتجة من أداة خارجية وهي مرجع غير موثوق/);
  assert.match(page,/هذا تعلّم بالذاكرة والخبرة؛ لا يغيّر الأوزان تلقائيًا/);
  assert.match(page,/owner_policy:ownerPolicy/);
});

test('child teaching corrections export only to a child-scoped dataset',()=>{
  assert.match(page,/AQLEVON_CHILD_TEACHING_EXAMPLE_V1/);
  assert.match(page,/exportTeachingDataset/);
  assert.match(page,/preferred_answer/);
  assert.match(page,/child_answer/);
  assert.match(page,/source:'child-lab-only'/);
  assert.match(page,/training_lane_write:false/);
  assert.match(page,/production_weight_write:false/);
  assert.match(page,/aqlevon-child-teaching-dataset\.jsonl/);
  assert.doesNotMatch(page,/promote_verified_chat_to_training/);
});

test('child training pack records the owner-selected operational policy',()=>{
  assert.match(page,/AQLEVON_CHILD_TRAINING_PACK_V1/);
  assert.match(page,/OWNER_SELECTED_PRODUCTION_OR_CHILD/);
  assert.match(page,/public_model_access:ownerPolicy\.public_model_access/);
  assert.match(page,/production_weight_write:ownerPolicy\.production_weight_write/);
  assert.match(page,/training_lane_write:ownerPolicy\.training_lane_write/);
  assert.match(page,/auto_promote:ownerPolicy\.automatic_promotion/);
  assert.match(page,/gpu_request_allowed:ownerPolicy\.gpu_request_allowed/);
  assert.match(page,/aqlevon-child-training-pack\.json/);
  assert.match(page,/specialty/);
  assert.match(page,/purpose/);
});

test('child candidate packaging is dry-run only in the owner UI',()=>{
  assert.match(page,/\/api\/admin\/child-lab\/candidate/);
  assert.match(page,/جهّز Candidate/);
  assert.match(page,/لم يبدأ أي تدريب ولم يُطلب GPU/);
  assert.match(page,/candidate\.training_started/);
  assert.match(page,/candidate\.gpu_requested/);
});

test('owner console links to child lab and no longer exposes legacy runtime model choice',()=>{
  assert.match(admin,/href="\/admin\/child-lab"/);
  assert.match(admin,/const safeModes=\['self_hosted_only'\]/);
  assert.doesNotMatch(admin,/openrouter_model/);
  assert.doesNotMatch(admin,/openrouter_primary/);
});


test('child reset clears stale candidate state and revokes operational grants',()=>{
  assert.match(page,/setCandidate\(null\)/);
  assert.match(page,/setCandidateEval\(null\)/);
  assert.match(page,/setPermissions\(defaultChildPermissions\(\)\)/);
  assert.match(page,/setOwnerPolicy\(defaultChildOwnerPolicy\(\)\)/);
  assert.match(page,/CHILD_RESET/);
  assert.match(page,/سحب صلاحيات الأدوات/);
});

test('child snapshots preserve and restore identity with persona state',()=>{
  assert.match(page,/identity:pkg\.identity/);
  assert.match(page,/snap\.identity/);
});


test('owner policy defaults closed but can explicitly open project-level controls',()=>{
  assert.match(ownerPolicy,/public_model_access:false/);
  assert.match(ownerPolicy,/production_weight_write:false/);
  assert.match(ownerPolicy,/training_lane_write:false/);
  assert.match(ownerPolicy,/worker03_access:false/);
  assert.match(ownerPolicy,/enableAllOwnerControllablePolicy/);
  assert.match(ownerPolicy,/production_weight_write:true/);
  assert.match(ownerPolicy,/training_lane_write:true/);
  assert.match(ownerPolicy,/worker03_access:true/);
  assert.match(page,/openAllOwnerControls/);
  assert.match(page,/run_within_grants/);
});
