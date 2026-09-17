import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  isVerifiedTrace,isUnresolvedTrace,isDeepRoute,traceDomain,verificationLabel,formalLearningEligible,
} from '../lib/aqlevon/control-center-compat.js';
import { buildTaskContract, detectPlanningIntent } from '../lib/aqlevon/kernel.js';
import { classifyProviderFailure, safeProviderDiagnostic, PROVIDER_ERROR_CLASSES } from '../lib/aqlevon/providers.js';
import {
  decideControllerAction,createIsolatedResultStore,deterministicFixtureAdapter,runIsolatedEvaluation,
  createCredentialBroker,dispatchRegisteredAction,reconciliationPlan,validateRetryAttempt,
  compensationRequiresSeparateAuthority,recoverCanonicalRuntime,
} from '../lib/aqlevon/frozen-foundations.js';
import { createTrustedRegistry } from '../lib/aqlevon/tool-registry.js';
import { createActionIntent, issuePermit } from '../lib/aqlevon/authority.js';

const decisionBase={task:{id:'t1',phase:'RUNNING',outcome:'NONE'},taskContract:{contract_id:'c1'}};

function executionFixture(){
  const registry=createTrustedRegistry({toolSpecs:[{tool_id:'repo.write',version:'1',provider:'github',adapter_identity:'fake@1',lifecycle:'ACTIVE',capabilities:['WRITE'],resource_types:['repository'],consequential_parameters:['path','content'],reconciliation:{supported:true}}]});
  const tool=registry.getTool('repo.write','1');
  const principal={id:'p1',status:'ACTIVE'},taskContract={contract_id:'c1'};
  const intent=createActionIntent({task_id:'t1',contract_id:'c1',semantic_action:'update',resource:{provider:'github',tenant:'owner',project:'AQLEVON-AI',environment:'staging',resource_id:'repo1'},parameters:{path:'x',content:'y'},capabilities:['WRITE']});
  const permit=issuePermit({principal,taskContract,intent,toolSpec:tool,constraints:[]});
  const attempt={id:'a1',action_intent_id:intent.id,permit_id:permit.id,phase:'QUEUED',outcome:'NONE'};
  return {registry,tool,principal,taskContract,intent,permit,attempt};
}
function fakeStore(){let owner=null;return {async claim({worker_id}){if(owner)return false;owner=worker_id;return true},async complete(v){this.completed=v},async markReconciling(v){this.reconciling=v}}}

test('control center consumes current VerificationState result semantics',()=>{
  assert.equal(isVerifiedTrace({verification:{result:'VERIFIED'}}),true);
  assert.equal(isVerifiedTrace({verification:{verdict:'pass'}}),false);
  assert.equal(isUnresolvedTrace({verification:{result:'INCONCLUSIVE'}}),true);
  assert.equal(verificationLabel({result:'REFUTED'}),'REFUTED');
  assert.equal(verificationLabel({verdict:'pass'}),'LEGACY_PASS');
});

test('control center reads current reasoning/domain fields and formal learning gate',()=>{
  const log={route_decision:{mode:'HIGH',reasoning:'deep'},task_contract:{primary_domain:'planning',domains:['planning']},verification:{result:'VERIFIED'},learning_eligible:true};
  assert.equal(isDeepRoute(log),true);assert.equal(traceDomain(log),'planning');assert.equal(formalLearningEligible(log),true);
  assert.equal(formalLearningEligible({...log,verification:{result:'INCONCLUSIVE'}}),false);
});

test('control center source no longer saves legacy learning confidence or reads verdict as formal truth',async()=>{
  const source=await readFile(new URL('../control-center/intelligence-source.js',import.meta.url),'utf8');
  assert.equal(source.includes('learning_gate_min_confidence:Number'),false);
  assert.equal(source.includes("verification?.verdict==='pass'"),false);
  assert.equal(source.includes("route_decision?.mode==='deep'"),false);
  assert.equal(source.includes('task_contract?.domain'),false);
  assert.equal(source.includes("from '../../../lib/aqlevon/control-center-compat.js'"),true);
});

test('Arabic structured project planning preserves scheduling dependencies resources and durations',()=>{
  const input='خطة مشروع:\nمهمة A: 3 ساعات\nمهمة B: ساعتان وتعتمد على مهمة A\nلدينا عاملان. ما أقل زمن لإنهاء المشروع؟';
  const p=detectPlanningIntent(input);assert.equal(p.detected,true);assert.equal(p.scheduling_intent,true);assert.equal(p.dependency_intent,true);assert.equal(p.resource_constraints,true);assert.equal(p.duration_constraints,true);assert.equal(p.structured_input,true);
  const c=buildTaskContract(input,{contractId:'plan-ar'});assert.equal(c.primary_domain,'planning');assert.ok(c.domains.includes('planning'));assert.equal(c.protocol_ids.includes('aqlevon.planning.v1'),false);assert.ok(c.success_criteria.some(x=>x.includes('task labels')));assert.deepEqual(c.planning.preserve,['task_labels','quantities','dependencies','resources','durations','objective']);
});

test('English planning recovery recognizes project schedule without creating a Round-G protocol',()=>{
  const c=buildTaskContract('Project plan:\nTask A: 2 hours\nTask B: 4 hours depends on Task A\nTwo workers. Find the minimum time.',{contractId:'plan-en'});
  assert.equal(c.primary_domain,'planning');assert.equal(c.planning.dependency_intent,true);assert.equal(c.planning.resource_constraints,true);assert.equal(c.protocol_ids.some(x=>x.includes('planning')),false);
});

test('provider failures map to safe diagnostic classes',()=>{
  assert.equal(classifyProviderFailure({keyPresent:false}),'ENV_MISSING');
  assert.equal(classifyProviderFailure({status:401,body:{error:'bad token'}}),'AUTH_ERROR');
  assert.equal(classifyProviderFailure({status:429}),'RATE_LIMIT');
  assert.equal(classifyProviderFailure({status:400,body:{error:'invalid model'}}),'INVALID_MODEL');
  assert.equal(classifyProviderFailure({status:404,body:{error:'model not found'}}),'MODEL_UNAVAILABLE');
  assert.equal(classifyProviderFailure({status:503}),'UPSTREAM_5XX');
  assert.equal(classifyProviderFailure({status:200,body:{}}),'INVALID_RESPONSE');
  assert.equal(classifyProviderFailure({status:400,body:{error:'No endpoints found for free route'}}),'FREE_ROUTE_UNAVAILABLE');
});

test('safe diagnostic never includes upstream body, authorization, or secret value',()=>{
  const d=safeProviderDiagnostic({provider:'openrouter',model:'openrouter/free',route:'openrouter_primary',status:401,error_class:'AUTH_ERROR',body:'sk-secret'});
  const text=JSON.stringify(d);assert.equal(PROVIDER_ERROR_CLASSES.includes(d.error_class),true);assert.equal(text.includes('sk-secret'),false);assert.equal(text.includes('Authorization'),false);
});

test('READ precedes ASK when objective current state is safely readable',()=>{const r=decideControllerAction({...decisionBase,read:{available:true,safe:true,objective:true,has_side_effects:false},ambiguity:{material:true}});assert.equal(r.decision,'READ')});
test('ASK handles material ambiguity not safely readable',()=>{const r=decideControllerAction({...decisionBase,ambiguity:{material:true,ask_can_resolve:true}});assert.equal(r.decision,'ASK')});
test('ASSUME is bounded/reversible and never expands authority',()=>{const r=decideControllerAction({...decisionBase,assumption:{available:true,reversible:true,materiality:'LOW',authority_expansion:false,scope_expansion:false},acting_risk:'LOW',waiting_risk:'MATERIAL'});assert.equal(r.decision,'ASSUME');const blocked=decideControllerAction({...decisionBase,action:{requested:true,externally_actionable:true},authority:{sufficient:false,exact_permit:false},assumption:{available:true,reversible:true,materiality:'LOW'}});assert.equal(blocked.decision,'BLOCK')});
test('acting/waiting risk is lexicographic and preference never widens authority',()=>{const wait=decideControllerAction({...decisionBase,acting_risk:'HIGH',waiting_risk:'LOW',can_wait:true,user_preference:'skip confirmations'});assert.equal(wait.decision,'WAIT');assert.equal(wait.authority_unchanged,true);const esc=decideControllerAction({...decisionBase,authority:{requires_external_authenticated_override:true}});assert.equal(esc.decision,'ESCALATE')});

test('isolated evaluation is zero-cost credential-free and cannot target production learning state',async()=>{
  const store=createIsolatedResultStore();const adapter=deterministicFixtureAdapter(f=>({correct:f.expected===f.observed}));
  const out=await runIsolatedEvaluation({fixtures:[{id:'h1',hidden:true,first_exposure:true,expected:7,observed:7}],adapter,resultStore:store});
  assert.equal(out.production_state_mutated,false);assert.equal(out.network_used,false);assert.equal(out.credentials_used,false);assert.equal(out.cost_usd,0);assert.equal(store.snapshot()[0].authority,'ISOLATED_EVALUATION_ONLY');
  await assert.rejects(()=>runIsolatedEvaluation({fixtures:[],adapter,resultStore:{kind:'production-learning',write(){}}}),/isolated result store/);
});

test('first-exposure fixtures are contamination-safe within isolated store',async()=>{const store=createIsolatedResultStore(),adapter=deterministicFixtureAdapter(()=>1);await runIsolatedEvaluation({fixtures:[{id:'x',first_exposure:true,contamination_key:'secret-case'}],adapter,resultStore:store});const second=await runIsolatedEvaluation({fixtures:[{id:'x',first_exposure:true,contamination_key:'secret-case'}],adapter,resultStore:store});assert.equal(second.results[0].status,'SKIPPED_CONTAMINATED')});

test('credential broker exposes references only and injects raw secret only at transport boundary',()=>{
  const secret='sk-this-is-a-very-secret-test-value',events=[];
  const broker=createCredentialBroker({registry:[{credential_ref:'cred:github:test',provider:'github',account:'owner',environment:'staging',env_var:'TEST_SECRET',allowed_tool_ids:['repo.write'],allowed_capabilities:['WRITE']}],secretResolver:name=>name==='TEST_SECRET'?secret:null,audit:e=>events.push(e)});
  const toolSpec={tool_id:'repo.write'},resource={provider:'github',tenant:'owner',environment:'staging'};
  const descriptor=broker.describe('cred:github:test');assert.equal(JSON.stringify(descriptor).includes(secret),false);assert.equal(JSON.stringify(descriptor).includes('TEST_SECRET'),false);
  const injector=broker.createTransportInjector({credential_ref:'cred:github:test',toolSpec,resource,capabilities:['WRITE']});assert.equal(JSON.stringify(injector).includes(secret),false);assert.equal(JSON.stringify(events).includes(secret),false);
  const headers=injector.apply({'content-type':'application/json'});assert.equal(headers.Authorization,`Bearer ${secret}`);
});

test('registered execution envelope is default-deny and dispatch-fenced',async()=>{
  const f=executionFixture(),store=fakeStore();const adapters={'repo.write@1':{family:'api',identity:'fake@1',async execute(){return {outcome:'SUCCESS',transport_status:{status:200}}}}};
  const out=await dispatchRegisteredAction({...f,adapters,attemptStore:store,worker_id:'w1'});assert.equal(out.outcome,'SUCCESS');assert.equal(out.receipt.verification_result,null);
  const duplicate=await dispatchRegisteredAction({...f,adapters,attemptStore:store,worker_id:'w2'});assert.equal(duplicate.dispatched,false);assert.match(duplicate.reasons[0],/already claimed/);
  await assert.rejects(()=>dispatchRegisteredAction({...f,adapters:{},attemptStore:fakeStore(),worker_id:'w3'}),/no registered adapter/);
});

test('UNKNOWN requires reconciliation and cannot auto-retry',async()=>{
  const f=executionFixture(),store=fakeStore();const adapters={'repo.write@1':{family:'api',async execute(){return {outcome:'UNKNOWN',provider_operation_id:'op1'}}}};
  const out=await dispatchRegisteredAction({...f,adapters,attemptStore:store,worker_id:'w1'});assert.equal(out.outcome,'UNKNOWN');assert.equal(out.reconciliation_required,true);
  const prior={...f.attempt,phase:'CLOSED',outcome:'UNKNOWN'};const blocked=reconciliationPlan({attempt:prior,toolSpec:f.tool});assert.equal(blocked.retry_allowed,false);
  assert.throws(()=>validateRetryAttempt({priorAttempt:prior,newAttempt:{id:'a2',action_intent_id:f.intent.id},reconciliation:blocked}),/unsafe retry blocked/);
  const reconciled=reconciliationPlan({attempt:prior,toolSpec:f.tool,observation:{effect_state:'CONFIRMED_NOT_APPLIED'}});assert.equal(reconciled.retry_allowed,true);assert.equal(validateRetryAttempt({priorAttempt:prior,newAttempt:{id:'a2',action_intent_id:f.intent.id},reconciliation:reconciled}),true);
});

test('compensation requires a separate exact ActionIntent and Permit',()=>{assert.throws(()=>compensationRequiresSeparateAuthority({compensationIntent:{id:'ci'},compensationPermit:{action_intent_id:'other'}}));assert.equal(compensationRequiresSeparateAuthority({compensationIntent:{id:'ci'},compensationPermit:{action_intent_id:'ci'}}),true)});

test('crash recovery is canonical-first and never auto-resumes uncertain effects',()=>{
  const out=recoverCanonicalRuntime({task:{id:'t1',phase:'RUNNING',outcome:'NONE'},permits:[{id:'p1',status:'ACTIVE'}],attempts:[{id:'a1',action_intent_id:'i1',permit_id:'p1',phase:'IN_FLIGHT',outcome:'NONE'},{id:'a2',action_intent_id:'i2',permit_id:'p1',phase:'CLOSED',outcome:'UNKNOWN'},{id:'a3',action_intent_id:'i3',permit_id:'p1',phase:'CLOSED',outcome:'SUCCESS'}],verificationStates:[{id:'v1',phase:'PENDING'}]});
  assert.equal(out.narrative_used,false);assert.equal(out.history_used_as_authority,false);assert.equal(out.auto_resume_uncertain_effects,false);assert.deepEqual(out.reconciliation.map(x=>x.attempt_id),['a1','a2']);assert.equal(out.reconciliation.every(x=>x.auto_resume===false&&x.success_claim_allowed===false),true);assert.deepEqual(out.closed_attempt_ids,['a3']);
});

test('Frozen A responsibility map documents six logical domains plus offline harness without inventing runtime enum',async()=>{const text=await readFile(new URL('../docs/FROZEN_AUTHORITY_DOMAIN_MAPPING.md',import.meta.url),'utf8');for(const heading of ['## 1. Task & Contract Controller','## 2. Canonical State & Audit','## 3. Model Gateway','## 4. Authority & Policy Gate','## 5. Action Executor & Receipt Collector','## 6. Outcome Truth & Response Governor','## Offline 7. Isolated Evaluation Harness'])assert.ok(text.includes(heading));assert.ok(text.includes('not a new runtime enum'))});
