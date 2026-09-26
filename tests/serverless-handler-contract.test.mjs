import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const handler=fs.readFileSync(path.join(root,'deploy/serverless-auth16/handler.py'),'utf8');

test('Auth16 worker compacts context before tokenization and preserves a user message',()=>{
  assert.match(handler,/def compact_messages/);
  assert.match(handler,/input_budget=3328/);
  assert.match(handler,/keep_tail=True/);
  assert.match(handler,/if not any\(m\["role"\]=="user" for m in final\)/);
  assert.match(handler,/messages=compact_messages\(req\.get\("messages"\),max\(2048,4096-max_tokens\)\)/);
  assert.match(handler,/truncation=False/);
  assert.doesNotMatch(handler,/truncation=True,\s*\n\s*max_length=4096/);
});

test('Auth16 generation output remains bounded',()=>{
  assert.match(handler,/max_tokens=max\(1,min\(768,max_tokens\)\)/);
  assert.match(handler,/max_new_tokens=max_tokens/);
});
