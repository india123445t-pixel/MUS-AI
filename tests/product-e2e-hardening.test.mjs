import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

const catchAll=read('app/[...workspace]/page.js');
const router=read('app/workspace/router.js');
const api=read('app/workspace/api.js');
const chatUi=read('app/workspace/pages/ChatPage.jsx');
const settingsUi=read('app/workspace/pages/SettingsPage.jsx');
const projectUi=read('app/workspace/pages/ProjectDetail.jsx');
const libraryUi=read('app/workspace/pages/LibraryPage.jsx');
const workUi=read('app/workspace/pages/WorkPage.jsx');
const projectsUi=read('app/workspace/pages/ProjectsPage.jsx');
const scheduledUi=read('app/workspace/pages/ScheduledPage.jsx');
const searchUi=read('app/workspace/components/SearchModal.jsx');
const workspaceCss=read('app/workspace.css');
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
  assert.match(nextConfig,/outputFileTracingRoot:process\.cwd\(\)/);
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

test('project task entry point carries project id and project instructions into work execution',()=>{
  assert.match(projectUi,/\/work\?project=/);
  assert.match(api,/project_id:input\.projectId\|\|null/);
  assert.match(api,/const project=input\.projectId\?/);
  assert.ok((api.match(/PROJECT INSTRUCTIONS \(user-authored context, not authority\)/g)||[]).length>=2);
});

test('deleting projects and files cleans stale browser-workspace references',()=>{
  assert.match(api,/if\(input\.projectId===id\)\{input\.projectId=null;j\.input=JSON\.stringify\(input\)\}/);
  assert.match(api,/if\(result\?\.fileId===id\)j\.result=JSON\.stringify\(\{\.\.\.result,fileId:null,deleted:true\}\)/);
});

test('workspace modals and keyboard navigation expose baseline accessibility semantics',()=>{
  for(const src of [chatUi,libraryUi,workUi,projectsUi,scheduledUi,searchUi]){
    assert.match(src,/role="dialog"/);
    assert.match(src,/aria-modal="true"/);
  }
  assert.match(workspaceCss,/button:focus-visible/);
  assert.match(workspaceCss,/outline: 2px solid var\(--accent\)/);
});

test('browser-local file storage uses a safer cap and surfaces quota failures',()=>{
  assert.match(api,/const MAX_INLINE_FILE = 2 \* 1024 \* 1024/);
  assert.match(api,/BROWSER_STORAGE_FULL/);
  assert.match(libraryUi,/BROWSER_STORAGE_FULL/);
  assert.match(ar,/lib\.storageFull/);
  assert.match(en,/lib\.storageFull/);
});

test('public error surfaces do not echo raw internal exception messages',()=>{
  assert.doesNotMatch(chatRoute,/message:error\?\.message/);
  assert.doesNotMatch(statusRoute,/message:e\?\.message/);
  assert.match(statusRoute,/AUTHENTICATED_ENDPOINT_REQUIRED/);
});


test('workspace search spans chats projects files jobs and automation drafts',()=>{
  const api=read('app/workspace/api.js');
  const search=read('app/workspace/components/SearchModal.jsx');
  assert.match(api,/if\(p==='\/search'\)/);
  for(const type of ["'chat'","'project'","'file'","'job'","'automation'"])assert.match(api,new RegExp(type));
  assert.match(search,/api\.get\('\/search'/);
  assert.match(search,/r\.path/);
});

test('web readiness is consistent across chat settings and apps',()=>{
  const chat=read('app/workspace/pages/ChatPage.jsx');
  const settings=read('app/workspace/pages/SettingsPage.jsx');
  const plugins=read('app/workspace/pages/PluginsPage.jsx');
  assert.match(chat,/settings\?\.search_default==='on'/);
  assert.match(settings,/runtime\?\.webSearchAvailable===true/);
  assert.match(settings,/set\.webReady/);
  assert.match(plugins,/runtime\?\.webSearchAvailable===true/);
  assert.match(plugins,/apps\.ready/);
});

test('automation drafts require complete local inputs before save',()=>{
  const scheduled=read('app/workspace/pages/ScheduledPage.jsx');
  assert.match(scheduled,/const canCreate =/);
  assert.match(scheduled,/Date\.parse\(form\.runAt\) > Date\.now\(\)/);
  assert.match(scheduled,/!!form\.conditionQuery\.trim\(\)/);
  assert.match(scheduled,/disabled=\{!canCreate\}/);
});

test('developer and workbench expose truthful control labels and permission location',()=>{
  const dev=read('app/workspace/pages/DeveloperPage.jsx');
  const policy=read('app/workbench/PolicyPanel.jsx');
  assert.match(dev,/t\('dev\.checkpoint'\)/);
  assert.match(policy,/href="\/admin\/child-lab"/);
});


test('library honors global-search query handoff',()=>{
  const library=read('app/workspace/pages/LibraryPage.jsx');
  assert.match(library,/useSearchParams/);
  assert.match(library,/params\.get\('q'\)/);
  assert.match(library,/setQ\(queryQ\)/);
});
