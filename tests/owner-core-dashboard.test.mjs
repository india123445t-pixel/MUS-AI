import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const testsDir=path.dirname(new URL(import.meta.url).pathname);
const root=path.resolve(testsDir,'..');
const read=(p)=>fs.readFileSync(path.join(root,p),'utf8');
const page=read('app/admin/page.js');
const chat=read('app/api/admin/owner-core/chat/route.js');
const task=read('app/api/admin/owner-core/task/route.js');

test('Owner Core remains private to system_owner',()=>{
  assert.match(chat,/system_owner/);
  assert.match(chat,/OWNER_REQUIRED/);
  assert.match(task,/system_owner/);
  assert.match(task,/OWNER_REQUIRED/);
});

test('mission preparation never claims external execution',()=>{
  assert.match(chat,/executor_state:'NOT_CONNECTED'/);
  assert.match(chat,/AWAITING_OWNER_APPROVAL/);
  assert.doesNotMatch(chat,/executor_state:'CONNECTED'/);
});

test('approval is explicit before READY and is audited',()=>{
  assert.match(task,/current\.data\.phase!==\'OPEN\'/);
  assert.match(task,/phase:'READY'/);
  assert.match(task,/OWNER_APPROVED_MISSION/);
});

test('STOP cannot claim success without a cancellation adapter',()=>{
  assert.match(task,/OWNER_STOP_REQUESTED/);
  assert.match(task,/dispatch_stop_supported:false/);
  assert.match(task,/status:409/);
});

test('dashboard exposes owner controls and real evidence surfaces',()=>{
  assert.match(page,/AQLEVON OWNER CORE/);
  assert.match(page,/STOP NOW/);
  assert.match(page,/aqlevon_action_attempts/);
  assert.match(page,/aqlevon_action_receipts/);
  assert.match(page,/aqlevon_audit_events/);
  assert.match(page,/NO ACTIVE EXECUTOR/);
});

test('professional control plane exposes operations intelligence and access surfaces',()=>{
  assert.match(page,/Operations/);
  assert.match(page,/Project Brain/);
  assert.match(page,/Model Lab/);
  assert.match(page,/Identity & Access/);
  assert.match(page,/EXECUTION TRACES/);
  assert.match(page,/Operational truth map/);
  assert.match(page,/CAPABILITY MAP/);
  assert.match(page,/Owner-controlled execution boundary/);
});

test('trace-first V3 exposes mission trace and system workbenches',()=>{
  assert.match(page,/MISSION REGISTRY/);
  assert.match(page,/TRACE EXPLORER/);
  assert.match(page,/Control-plane trace/);
  assert.match(page,/MISSION INSPECTOR/);
  assert.match(page,/INFRASTRUCTURE/);
  assert.match(page,/AUTHORIZED SECURITY/);
  assert.match(page,/Search missions, traces, IDs, providers/);
  assert.match(page,/NO_RECEIPT/);
});

test('V3 keeps execution truth explicit',()=>{
  assert.match(page,/ADAPTER REQUIRED/);
  assert.match(page,/NOT CONNECTED/);
  assert.match(page,/OWNER APPROVAL REQUIRED/);
  assert.match(page,/No autonomous repository execution is claimed/);
  assert.match(page,/No live external process bridge connected/);
});
