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

test('approval is explicit before READY, compare-and-set guarded, and audited',()=>{
  assert.match(task,/current\.data\.phase!==\'OPEN\'/);
  assert.match(task,/phase:'READY'/);
  assert.match(task,/\.eq\('id',taskId\)\.eq\('phase','OPEN'\)/);
  assert.match(task,/status:409/);
  assert.match(task,/OWNER_APPROVED_MISSION/);
});

test('STOP cannot claim success without a cancellation adapter',()=>{
  assert.match(task,/OWNER_STOP_REQUESTED/);
  assert.match(task,/dispatch_stop_supported:false/);
  assert.match(task,/status:409/);
});

test('dashboard exposes owner controls and real evidence surfaces',()=>{
  assert.match(page,/نواة مالك AQLEVON V3/);
  assert.match(page,/إيقاف الآن/);
  assert.match(page,/aqlevon_action_attempts/);
  assert.match(page,/aqlevon_action_receipts/);
  assert.match(page,/aqlevon_audit_events/);
  assert.match(page,/لا يوجد منفّذ نشط/);
  assert.match(page,/\/admin-icon\.svg/);
});

test('professional control plane exposes Arabic intelligence and access surfaces',()=>{
  assert.match(page,/المهام/);
  assert.match(page,/التتبّع/);
  assert.match(page,/ذاكرة المشروع/);
  assert.match(page,/مختبر النموذج/);
  assert.match(page,/البنية التحتية/);
  assert.match(page,/الأمن المصرّح/);
  assert.match(page,/خريطة الحقيقة التشغيلية/);
  assert.match(page,/خريطة القدرات/);
  assert.match(page,/حدود التنفيذ تحت سيطرة المالك/);
});

test('trace-first V3 exposes Arabic mission trace and system workbenches',()=>{
  assert.match(page,/سجل المهام/);
  assert.match(page,/مستكشف التتبّع/);
  assert.match(page,/تتبّع طبقة التحكم/);
  assert.match(page,/تفاصيل المهمة/);
  assert.match(page,/البنية التحتية/);
  assert.match(page,/الأمن المصرّح/);
  assert.match(page,/ابحث في المهام والتتبّعات/);
  assert.match(page,/NO_RECEIPT/);
});

test('V3 keeps execution truth explicit in Arabic',()=>{
  assert.match(page,/const executorState='NOT_CONNECTED'/);
  assert.doesNotMatch(page,/hasInFlight\?'LIVE':attempts\.length\?'IDLE'/);
  assert.match(page,/يحتاج موصل تنفيذ/);
  assert.match(page,/غير متصل/);
  assert.match(page,/موافقة المالك مطلوبة/);
  assert.match(page,/لا يوجد ادعاء بتنفيذ تلقائي على المستودع/);
  assert.match(page,/لا يوجد جسر عمليات خارجية مباشر متصل/);
});


test('V3 exposes incident and observability truth surfaces',()=>{
  assert.match(page,/مركز الحوادث/);
  assert.match(page,/P99/);
  assert.match(page,/نجاح الأدوات/);
  assert.match(page,/قياس التكلفة والرموز/);
  assert.match(page,/غير موصول بالقياس/);
  assert.match(page,/لن تُعرض أرقام تكلفة أو رموز غير حقيقية/);
});
