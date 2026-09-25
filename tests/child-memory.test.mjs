import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {normalizeChildMemory,selectChildMemories} from '../lib/aqlevon/child-memory.js';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const db=fs.readFileSync(path.join(root,'app/admin/child-lab/memory-db.js'),'utf8');
const page=fs.readFileSync(path.join(root,'app/admin/child-lab/page.js'),'utf8');
const runtime=fs.readFileSync(path.join(root,'lib/aqlevon/child-runtime.js'),'utf8');
const chat=fs.readFileSync(path.join(root,'app/api/admin/child-lab/chat/route.js'),'utf8');

test('memory ranking retrieves relevant child memories',()=>{
  const rows=[
    normalizeChildMemory({id:'1',text:'قبل البحث تحقق من مصدرين مستقلين',kind:'lesson',topic:'research',importance:0.9}),
    normalizeChildMemory({id:'2',text:'عند صناعة فيديو ابدأ بقصة قصيرة',kind:'lesson',topic:'video',importance:0.8}),
    normalizeChildMemory({id:'3',text:'تدرب على الإيقاع الموسيقي',kind:'experience',topic:'music',importance:0.7})
  ];
  const got=selectChildMemories(rows,'أريد البحث والتحقق من مصدرين',{limit:2,minScore:0});
  assert.equal(got.length,2);
  assert.equal(got[0].id,'1');
  assert.ok(got[0].relevance_score>=got[1].relevance_score);
});

test('memory records remain child-lab only',()=>{
  const m=normalizeChildMemory({id:'x',text:'درس خاص بالطفل'});
  assert.equal(m.scope,'child-lab-only');
  assert.doesNotMatch(JSON.stringify(m),/AQLEVON_MODEL_URL|Worker 03|production weights/i);
});

test('browser memory uses isolated IndexedDB and supports filtering/export/import/reset',()=>{
  assert.match(db,/aqlevon-child-memory-v1/);
  assert.match(db,/indexedDB\.open/);
  assert.match(db,/searchChildMemories/);
  assert.match(db,/childMemoryStats/);
  assert.match(db,/AQLEVON_CHILD_MEMORY_EXPORT_V1/);
  assert.match(db,/importChildMemories/);
  assert.match(db,/clearChildMemories/);
  assert.doesNotMatch(db,/aqlevon-workspace-web-v1/);
  assert.doesNotMatch(db,/AQLEVON_MODEL_URL/);
});

test('chat receives only filtered memories and runtime caps prompt memory',()=>{
  assert.match(page,/searchChildMemories\(v,\{limit:24\}\)/);
  assert.match(page,/memories,/);
  assert.match(chat,/body\.memories/);
  assert.match(chat,/slice\(0,24\)/);
  assert.match(runtime,/RELEVANT LONG-TERM MEMORY/);
  assert.match(runtime,/memories\.slice\(0,24\)/);
});

test('owner UI exposes memory filtering and isolated memory reset',()=>{
  assert.match(page,/الذاكرة الطويلة/);
  assert.match(page,/ابحث داخل ذاكرة الطفل/);
  assert.match(page,/احفظ في الذاكرة/);
  assert.match(page,/تصدير الذاكرة/);
  assert.match(page,/استيراد ذاكرة/);
  assert.match(page,/clearChildMemories/);
});
