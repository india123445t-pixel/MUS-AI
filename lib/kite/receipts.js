import { randomUUID } from 'crypto';
import { stableJson } from './security.js';

export function createActionReceipt({attempt,intent,permit,executor_identity,observed_resource=null,request_digest=null,transport_status={},executor_reported_outcome=null,provider_operation_id=null}){
  if(!attempt||!intent||!permit)throw new Error('receipt requires attempt, intent and permit');
  if(String(attempt.action_intent_id)!==String(intent.id))throw new Error('receipt attempt/intention mismatch');
  if(String(attempt.permit_id)!==String(permit.id))throw new Error('receipt attempt/permit mismatch');
  if(String(permit.action_intent_id)!==String(intent.id))throw new Error('receipt permit/intention mismatch');
  if(request_digest&&permit.parameter_digest&&String(request_digest)!==String(permit.parameter_digest))throw new Error('receipt request digest does not match authorized parameters');
  return Object.freeze({
    id:randomUUID(),action_attempt_id:attempt.id,action_intent_id:intent.id,permit_id:permit.id,
    executor_identity:String(executor_identity||''),observed_resource,request_digest:request_digest||permit.parameter_digest,
    transport_status:JSON.parse(stableJson(transport_status)),executor_reported_outcome,provider_operation_id,
    emitted_at:new Date().toISOString(),
    verification_result:null,
  });
}

export function receiptProvesWorldState(){return false}
