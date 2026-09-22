import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const api=read('app/workspace/api.js');
const chat=read('app/workspace/pages/ChatPage.jsx');
const work=read('app/workspace/pages/WorkPage.jsx');
const library=read('app/workspace/pages/LibraryPage.jsx');
const dev=read('app/workspace/pages/DeveloperPage.jsx');
const scheduled=read('app/workspace/pages/ScheduledPage.jsx');
const plugins=read('app/workspace/pages/PluginsPage.jsx');
const settings=read('app/workspace/pages/SettingsPage.jsx');
const i18n=read('app/workspace/i18n/index.js');
const ar=read('app/workspace/i18n/ar.js');
const en=read('app/workspace/i18n/en.js');
const health=read('app/api/inference-health/route.js');
const chatRoute=read('app/api/chat/route.js');
const statusRoute=read('app/api/status/route.js');
const benchmarkRoute=read('app/api/benchmark/run/route.js');
const goalRoute=read('app/api/goal/run/route.js');
const evalRoute=read('app/api/internal/eval-snapshot/route.js');
const providerTestRoute=read('app/api/provider-test/route.js');

test('browser workspace fails closed for unavailable adapters',()=>{
  assert.match(api,/adapter_state:'NOT_CONNECTED'/);
  assert.match(api,/exitCode=126/);
  assert.match(api,/connection:\{status:'disconnected',scopes:\[\]\}/);
  assert.doesNotMatch(api,/code-interpreter'.*enabled:1/);
  assert.doesNotMatch(api,/image-gen'.*enabled:1/);
  assert.match(scheduled,/disabled title=\{t\('auto\.adapterRequired'\)\}/);
  assert.match(plugins,/t\('apps\.adapterRequired'\)/);
});

test('chat exposes real inference readiness and disables unavailable actions',()=>{
  assert.match(health,/openrouter\.ai\/api\/v1\/key/);
  assert.match(health,/api\.groq\.com\/openai\/v1\/models/);
  assert.match(health,/generativelanguage\.googleapis\.com\/v1beta\/models/);
  assert.match(health,/api\.mistral\.ai\/v1\/models/);
  assert.match(health,/api\.cerebras\.ai\/v1\/models/);
  assert.match(health,/huggingface\.co\/api\/whoami-v2/);
  assert.match(health,/checkSelfHostedHealth/);
  assert.match(health,/mode==='self_hosted_only'\?selfHostedReady:anyProviderReady/);
  assert.match(health,/modeKnown\?\(mode==='self_hosted_only'\?selfHostedReady:anyProviderReady\):false/);
  assert.match(api,/inference-health\?runtime_mode=/);
  assert.match(api,/runtimeMode:status\?\.settings\?\.runtime_mode\|\|null/);
  assert.match(health,/AUTH_ERROR/);
  assert.match(api,/\/api\/inference-health/);
  assert.match(api,/allow_paid_external===true&&!!status\?\.settings\?\.public_web_search_enabled/);
  assert.match(chat,/runtime\.inferenceReady !== true/);
  assert.match(chat,/runtimeAuthError/);
  assert.match(chat,/webSearchAvailable !== true/);
});

test('apps never solicit browser secrets or claim disconnected capabilities are live',()=>{
  assert.doesNotMatch(plugins,/type="password"/);
  assert.doesNotMatch(plugins,/token\.trim\(\)/);
  assert.doesNotMatch(plugins,/setConnecting/);
  assert.match(plugins,/disabled title=\{t\('apps\.browserNotice'\)\}/);
  assert.match(en,/code-interpreter': 'Not connected in the browser edition/);
  assert.match(en,/image-gen': 'Not connected in the browser edition/);
  assert.match(en,/github': 'Not connected in the browser edition/);
  assert.match(ar,/code-interpreter': 'غير متصل في نسخة المتصفح/);
  assert.match(ar,/image-gen': 'غير متصل في نسخة المتصفح/);
});

test('public work surface only advertises the format it actually renders',()=>{
  assert.match(work,/format: 'md'/);
  assert.doesNotMatch(work,/format: 'pdf'/);
  assert.doesNotMatch(work,/format: 'xlsx'/);
  assert.doesNotMatch(work,/format: 'pptx'/);
  assert.match(work,/work\.browserOnly/);
});

test('browser chat controls do not overclaim stop reasoning temporary privacy or dictation',()=>{
  assert.match(chat,/const stop = \(\) => abortRef\.current\?\.abort\(\)/);
  assert.doesNotMatch(chat,/stream\/stop/);
  assert.doesNotMatch(chat,/reasoning: thinkLonger/);
  assert.match(chat,/disabled\s*\n\s*aria-pressed=\{false\}/);
  assert.match(chat,/speechAvailable/);
  assert.match(chat,/disabled=\{!speechAvailable\}/);
  assert.match(en,/Hidden from history · stored locally/);
  assert.match(ar,/مخفية من السجل · محفوظة محليًا/);
  assert.match(en,/Export Workspace metadata \(file contents excluded\)/);
  assert.match(ar,/تصدير بيانات Workspace الوصفية \(دون محتوى الملفات\)/);
});

test('chat text-file attachment sends real content and multimodal stays fail-closed',()=>{
  assert.match(chat,/const text = await f\.text\(\)/);
  assert.match(chat,/32 \* 1024/);
  assert.match(chat,/text\.length > 12000/);
  assert.match(chatRoute,/rawInput\.length>20000/);
  assert.match(chat,/chat\.fileUnsupported/);
  assert.match(chat,/chat\.imageUnavailable/);
  assert.doesNotMatch(chat,/imgRef/);
  assert.doesNotMatch(chat,/\[\$\{t\('chat\.attached'\)\}: \$\{file\.name\}\]/);
  assert.match(en,/Summarize a text file/);
  assert.match(ar,/تلخيص ملف نصي/);
});

test('Work fails closed when inference is unavailable and Library stays browser-local',()=>{
  assert.match(work,/runtime\?\.inferenceReady !== true/);
  assert.match(work,/work\.runtimeUnavailable/);
  assert.match(work,/disabled=\{!form\.prompt\.trim\(\) \|\| runtime\?\.inferenceReady !== true\}/);
  assert.match(library,/api\.fileUrl\(preview\.file\.id\)/);
  assert.doesNotMatch(library,/\/api\/files\/\$\{preview\.file\.id\}\/content/);
});

test('new users default to Arabic and persistence claims are truthful',()=>{
  assert.match(i18n,/\|\| 'ar'\) : 'ar'/);
  assert.match(ar,/بيانات Workspace المحلية تُحفظ على هذا الجهاز/);
  assert.match(en,/local Workspace data is stored on this device/);
  assert.doesNotMatch(en,/Everything is saved on your server/);
  assert.doesNotMatch(en,/Public repositories clone without a token/);
  assert.match(dev,/browserSandboxNotice/);
  assert.match(settings,/set\.webUnavailable/);
});


test('public runtime never silently falls back to the legacy Supabase project',()=>{
  const guarded=[chatRoute,statusRoute,benchmarkRoute,goalRoute,evalRoute,providerTestRoute];
  for(const src of guarded){
    assert.doesNotMatch(src,/qkoscgdegnqcypkjrefn/);
    assert.doesNotMatch(src,/sb_publishable_wGDAyv5bwOrGjNX6QK0KzQ_K_xWI6w8/);
  }
  assert.match(chatRoute,/ENV_MISSING/);
  assert.match(chatRoute,/status:503/);
  assert.match(statusRoute,/database_configured:!!client/);
});
