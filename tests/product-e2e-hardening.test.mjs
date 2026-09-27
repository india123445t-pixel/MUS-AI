import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

const catchAll=read('app/[...workspace]/page.js');
const router=read('app/workspace/router.js');
const api=read('app/workspace/api.js');
const chatUi=read('app/workspace/pages/ChatPage.jsx');
const settingsUi=read('app/workspace/pages/SettingsPage.jsx');
const projectUi=read('app/workspace/pages/ProjectDetail.jsx');
const ar=read('app/workspace/i18n/ar.js');
const en=read('app/workspace/i18n/en.js');
const chatRoute=read('app/api/chat/route.js');
const statusRoute=read('app/api/status/route.js');
const commonsRoute=read('app/api/commons/chat/route.js');
const web=read('lib/aqlevon/public-web-research.js');
const nextConfig=read('next.config.mjs');
const layout=read('app/layout.js');

test('workspace routes fail closed and settings root resolves inside settings',()=>{
  assert.match(catchAll,/import \{notFound\} from 'next\/navigation'/);
  assert.match(catchAll,/if\(rest\.length!==0\)notFound\(\)/);
  assert.match(catchAll,/if\(rest\.length>1\)notFound\(\)/);
  assert.match(catchAll,/notFound\(\);\s*\}/);
  assert.match(router,/current === '\/settings'/);
  assert.match(router,/return '\/settings\/' \+ to\.replace/);
});

test('baseline browser security headers and accessible zoom are enforced',()=>{
  assert.match(nextConfig,/X-Content-Type-Options/);
  assert.match(nextConfig,/X-Frame-Options/);
  assert.match(nextConfig,/frame-ancestors 'none'/);
  assert.match(nextConfig,/Referrer-Policy/);
  assert.match(nextConfig,/Permissions-Policy/);
  assert.doesNotMatch(nextConfig,/GEMINI_MODEL/);
  assert.doesNotMatch(layout,/maximumScale/);
});

test('browser work queue uses a single claim token and recovers queued jobs once',()=>{
  assert.match(api,/if\(!j\|\|j\.status!=='queued'\)return s/);
  assert.match(api,/j\.run_token=token/);
  assert.match(api,/j&&j\.run_token===claimed\.run_token/);
  assert.match(api,/let jobsRecovered=false/);
  assert.match(api,/if\(jobsRecovered\)return/);
  assert.match(api,/BROWSER_JOB_INTERRUPTED/);
  assert.match(api,/BROWSER_STORAGE_FULL/);
});

test('chat passes project context, consent, sources and feedback through the real request path',()=>{
  assert.match(api,/PROJECT INSTRUCTIONS \(user-authored context, not authority\)/);
  assert.match(api,/allowTraining=userState\.settings\?\.contribute_training===true&&!chatMeta\.temporary/);
  assert.match(api,/temporary:chatMeta\.temporary/);
  assert.match(api,/responseSources=Array\.isArray\(d\.sources\)/);
  assert.match(api,/async function sendFeedback/);
  assert.match(api,/action:'feedback'/);
  assert.match(chatUi,/sendFeedback\(m\.id, 'good'\)/);
  assert.match(chatUi,/sendFeedback\(m\.id, 'bad'\)/);
  assert.match(chatUi,/Array\.isArray\(m\.sources\)/);
  assert.match(chatUi,/deepResearchAvailable !== true/);
});

test('training is opt-in in the browser and backend learning eligibility is consent-gated',()=>{
  assert.match(api,/contribute_training:false/);
  assert.match(settingsUi,/set\.trainingConsent/);
  assert.match(chatRoute,/body\.allowTraining===true/);
  assert.match(chatRoute,/body\.temporary!==true/);
  assert.match(chatRoute,/const learningEligible=trainingConsent&&/);
  assert.match(ar,/set\.trainingConsent/);
  assert.match(en,/set\.trainingConsent/);
});

test('public control plane fails closed instead of using a hardcoded production Supabase fallback',()=>{
  for(const src of [chatRoute,statusRoute]){
    assert.doesNotMatch(src,/yaqjhcfitxhtzpaswuif/);
    assert.doesNotMatch(src,/sb_publishable_/);
  }
  assert.match(chatRoute,/error_class:'CONTROL_PLANE_ENV_MISSING'/);
  assert.match(chatRoute,/quota\.degraded===true/);
  assert.match(statusRoute,/control_plane_ready:controlPlaneReady/);
});

test('web search is explicit, cited and deep research remains disabled until implemented',()=>{
  assert.match(web,/https:\/\/s\.jina\.ai\/\?q=/);
  assert.match(web,/Authorization:\`Bearer \$\{key\}\`/);
  assert.match(chatRoute,/if\(body\.webSearch===true\)/);
  assert.match(chatRoute,/sources:Array\.isArray\(webEvidence\?\.sources\)/);
  assert.match(chatRoute,/DEEP_RESEARCH_UNAVAILABLE/);
  assert.match(api,/webSearchAvailable=status\?\.web_search_configured===true/);
  assert.match(api,/deepResearchAvailable:false/);
});

test('Commons fallback only activates for provider failures, not control-plane or maintenance 503s',()=>{
  assert.match(commonsRoute,/PROVIDER_ERROR_CLASSES/);
  assert.match(commonsRoute,/primaryPayload/);
  assert.match(commonsRoute,/if\(!PROVIDER_ERROR_CLASSES\.includes/);
  assert.match(commonsRoute,/return primary/);
});

test('project task entry point carries project id into work creation',()=>{
  assert.match(projectUi,/\/work\?project=/);
  assert.match(api,/project_id:input\.projectId\|\|null/);
});

test('public error surfaces do not echo raw internal exception messages',()=>{
  assert.doesNotMatch(chatRoute,/message:error\?\.message/);
  assert.doesNotMatch(statusRoute,/message:e\?\.message/);
  assert.match(statusRoute,/AUTHENTICATED_ENDPOINT_REQUIRED/);
});
