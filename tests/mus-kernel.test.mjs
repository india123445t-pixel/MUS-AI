import test from 'node:test';
import assert from 'node:assert/strict';
import { buildTaskContract, buildRouteDecision, adjudicateFormalVerification } from '../lib/mus/kernel.js';
import { redactSecrets } from '../lib/mus/security.js';
import { VERIFICATION_RESULTS } from '../lib/mus/constants.js';

const settings={
  max_model_calls_per_request:3,
  intelligence_router_enabled:true,
  verification_enabled:true,
  deep_reasoning_enabled:true,
  allow_paid_external:false,
  public_web_search_enabled:false,
};

test('stable low-stakes answer can use FAST path',()=>{
  const contract=buildTaskContract('Explain what a binary tree is.');
  assert.equal(contract.route_mode,'FAST');
  assert.equal(contract.high_consequence,false);
});

test('current research claim requires external evidence and cannot be formally verified without it',()=>{
  const contract=buildTaskContract('What is the latest current price and recent news about X?');
  const route=buildRouteDecision(contract,settings,{});
  assert.equal(contract.external_evidence_required,true);
  assert.equal(route.external_evidence_available,false);
  const result=adjudicateFormalVerification({contract,route,candidate:{citations:[]},deterministic:{}});
  assert.equal(result.result,VERIFICATION_RESULTS.INCONCLUSIVE);
});

test('software repository work activates software protocol and forbids fake execution proof',()=>{
  const contract=buildTaskContract('Fix this GitHub repository bug and run the tests.');
  assert.ok(contract.domains.includes('software'));
  assert.ok(contract.success_criteria.some(x=>x.includes('real execution evidence')));
});

test('communication and operations can compose without creating a new authority object',()=>{
  const contract=buildTaskContract('Deploy the release to production and send the client a message when done.');
  assert.ok(contract.domains.includes('operations'));
  assert.ok(contract.domains.includes('communication'));
  assert.equal(contract.externally_actionable,true);
  assert.equal(contract.route_mode,'HIGH');
});

test('obvious secrets are redacted before model-provider exposure',()=>{
  const raw='Use token sk-abcdefghijklmnopqrstuvwxyz012345 to call the API';
  const redacted=redactSecrets(raw);
  assert.equal(redacted.includes('sk-abcdefghijklmnopqrstuvwxyz012345'),false);
  assert.ok(redacted.includes('[REDACTED_SECRET]'));
});

test('model agreement alone does not mint formal VERIFIED',()=>{
  const contract=buildTaskContract('Prove that every integer of this form has property P.');
  const route=buildRouteDecision(contract,settings,{});
  const result=adjudicateFormalVerification({
    contract,
    route,
    candidate:{citations:[]},
    advisoryVerifier:{relation:'SUPPORTS',confidence:1},
    deterministic:{verified:false},
  });
  assert.equal(result.result,VERIFICATION_RESULTS.INCONCLUSIVE);
});

test('formal proof wording triggers math protocol and formal verification requirement',()=>{
  const contract=buildTaskContract('Prove that every integer n with property A also has property B.');
  assert.ok(contract.domains.includes('math'));
  assert.equal(contract.formal_verification_required,true);
  assert.notEqual(contract.route_mode,'FAST');
});

test('high consequence request is routed HIGH without trusting model confidence',()=>{
  const contract=buildTaskContract('Give medical diagnosis and exact dose for this patient.');
  assert.equal(contract.high_consequence,true);
  assert.equal(contract.route_mode,'HIGH');
});

test('deployment receipt alone cannot formally verify operations postcondition',()=>{
  const contract=buildTaskContract('Deploy this release to production.');
  const route=buildRouteDecision(contract,settings,{});
  const result=adjudicateFormalVerification({
    contract,
    route,
    candidate:{citations:[]},
    deterministic:{executionEvidence:true,postconditionEvidence:false},
  });
  assert.equal(result.result,VERIFICATION_RESULTS.INCONCLUSIVE);
  assert.ok(result.reasons.some(x=>x.includes('postcondition')));
});

test('draft communication is distinct from external send',()=>{
  const draft=buildTaskContract('Draft an email to the client explaining the delay.');
  const send=buildTaskContract('Send an email to the client explaining the delay.');
  assert.ok(draft.domains.includes('communication'));
  assert.ok(send.domains.includes('communication'));
  assert.equal(draft.externally_actionable,false);
  assert.equal(send.externally_actionable,true);
  assert.notEqual(send.route_mode,'FAST');
});
