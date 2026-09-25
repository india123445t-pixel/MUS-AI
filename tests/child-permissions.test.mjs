import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {defaultChildPermissions,normalizeChildPermissions,isChildPermissionGranted,requiredChildPermissions,CHILD_PERMISSION_CATALOG,CHILD_TOOL_ACTIONS} from '../lib/aqlevon/child-permissions.js';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const tools=fs.readFileSync(path.join(root,'lib/aqlevon/child-tools.js'),'utf8');
const route=fs.readFileSync(path.join(root,'app/api/admin/child-lab/tool/route.js'),'utf8');
const page=fs.readFileSync(path.join(root,'app/admin/child-lab/page.js'),'utf8');

test('permissions default to execution off and all grants off',()=>{
  const p=defaultChildPermissions();
  assert.equal(p.execution_enabled,false);
  assert.ok(CHILD_PERMISSION_CATALOG.length>=10);
  for(const item of CHILD_PERMISSION_CATALOG)assert.equal(p.grants[item.id],false);
});

test('owner can enable only selected operational permissions',()=>{
  const p=normalizeChildPermissions({
    execution_enabled:true,
    autonomy:'run_within_grants',
    grants:{'web.research':true,'browser.navigate':true,'files.delete':false}
  });
  assert.equal(isChildPermissionGranted(p,'web.research'),true);
  assert.equal(isChildPermissionGranted(p,'browser.navigate'),true);
  assert.equal(isChildPermissionGranted(p,'files.delete'),false);
});

test('master execution off blocks a granted permission',()=>{
  const p=normalizeChildPermissions({execution_enabled:false,grants:{'terminal.run':true}});
  assert.equal(isChildPermissionGranted(p,'terminal.run'),false);
});

test('tool broker enforces every permission required by the selected action',()=>{
  assert.match(tools,/requiredChildPermissions/);
  assert.match(tools,/PERMISSION_DISABLED/);
  assert.match(tools,/missing_permissions/);
  assert.match(tools,/required_permissions/);
  assert.match(route,/permissions:body\.permissions/);
  assert.match(route,/missing_permissions/);
  assert.deepEqual(requiredChildPermissions('browser','publish'),['browser.submit','external.publish']);
  assert.deepEqual(requiredChildPermissions('browser','account_modify',{multi_step:true}),['browser.submit','account.modify','workflow.multi_step']);
  assert.deepEqual(requiredChildPermissions('files','delete'),['files.delete']);
  assert.equal(CHILD_TOOL_ACTIONS.browser.some(x=>x.id==='session_login'),true);
});

test('owner UI exposes permission toggles autonomy log and emergency stop',()=>{
  assert.match(page,/صلاحيات الطفل/);
  assert.match(page,/شغّل التنفيذ/);
  assert.match(page,/STOP · إيقاف وسحب الصلاحيات/);
  assert.match(page,/run_within_grants/);
  assert.match(page,/permissionLog/);
  assert.match(page,/togglePermission/);
  assert.match(page,/emergencyStop/);
  assert.match(page,/aqlevon-child-permissions-v1/);
  assert.match(page,/مهمة متعددة الخطوات/);
  assert.match(page,/الصلاحيات المطلوبة/);
  assert.match(page,/CHILD_TOOL_ACTIONS/);
});
