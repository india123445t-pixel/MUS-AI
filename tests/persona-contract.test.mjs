import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPersonaPrompt } from '../lib/aqlevon/persona.js';
import { buildSystemPrompt, buildTaskContract } from '../lib/aqlevon/kernel.js';

test('AQLEVON persona explicitly preserves provider-independent identity',()=>{
  const p=buildPersonaPrompt('ar');
  assert.ok(p.includes('أنت AQLEVON AI'));
  assert.ok(p.includes('مستقلة عن مزوّد النموذج'));
  assert.ok(p.includes('غير متملّق'));
});

test('AQLEVON persona refuses execution theatre and provider impersonation',()=>{
  const p=buildPersonaPrompt('other');
  assert.ok(p.includes('independent from the underlying model provider'));
  assert.ok(p.includes('Never claim execution or verification without actual external evidence'));
});

test('controller law remains above personality in system prompt',()=>{
  const contract=buildTaskContract('Explain binary trees.');
  const prompt=buildSystemPrompt({contract,lessons:[]});
  assert.ok(prompt.includes('The model proposes; external system components authorize, execute, observe, verify, and record.'));
  assert.ok(prompt.includes('TASK CONTRACT (controller-owned; do not rewrite it)'));
});
