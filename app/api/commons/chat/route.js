import { NextResponse } from 'next/server';
import { randomUUID } from 'crypto';
import { POST as primaryChat } from '../../chat/route.js';
import { commonsSubmitAndWait } from '../../../../lib/aqlevon/commons-edge.js';
import { buildMessages, buildRouteDecision, buildTaskContract, adjudicateFormalVerification } from '../../../../lib/aqlevon/kernel.js';
import { redactSecrets } from '../../../../lib/aqlevon/security.js';
import { governResponse } from '../../../../lib/aqlevon/response-governor.js';
import { AQLEVON_BOS_VERSION } from '../../../../lib/aqlevon/constants.js';

export const maxDuration=300;

function isUuid(v=''){return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(v))}

export async function POST(req){
  const primaryRequest=req.clone();
  const primary=await primaryChat(primaryRequest);
  if(primary.status!==503)return primary;

  let body={};
  try{body=await req.json()}catch{}
  const rawInput=String(body.input||'').trim();
  if(!rawInput)return NextResponse.json({message:'اكتب رسالة أولًا.'},{status:400});

  const input=redactSecrets(rawInput);
  const settings={
    public_chat_enabled:true,
    intelligence_router_enabled:true,
    verification_enabled:true,
    deep_reasoning_enabled:true,
    max_model_calls_per_request:1,
    max_history:16,
    temperature:0.4,
    allow_paid_external:false,
    public_web_search_enabled:false
  };
  const contract=buildTaskContract(input);
  const route=buildRouteDecision(contract,settings,body);
  const messages=buildMessages({
    input,
    history:body.history,
    contract,
    lessons:[],
    personalization:String(body.personalization||'').slice(0,4000),
    memories:Array.isArray(body.memories)?body.memories.slice(0,16):[],
    maxHistory:16
  });

  const result=await commonsSubmitAndWait({
    input,
    history:Array.isArray(body.history)?body.history:[],
    messages,
    temperature:Number(settings.temperature||0.4),
    model:'AQLEVON-27B',
    timeoutMs:120000
  });
  if(!result)return primary;

  const deterministic={executionEvidence:false,postconditionEvidence:false,verified:false,refuted:false,conflicting:false};
  const verification=adjudicateFormalVerification({
    contract,
    route,
    candidate:result,
    advisoryVerifier:null,
    deterministic
  });
  const governed=governResponse({
    text:result.text,
    contract,
    verification:{required:verification.required,result:verification.result,reasons:verification.reasons||[],advisory:null},
    deterministic
  });

  return NextResponse.json({
    text:governed.text,
    provider:'aqlevon-ai',
    model:'AQLEVON AI',
    transport:'aqlevon-commons',
    commons_job_id:result.commons_job_id,
    bos_version:AQLEVON_BOS_VERSION,
    session_id:isUuid(body.sessionId)?body.sessionId:randomUUID(),
    conversation_id:isUuid(body.conversationId)?body.conversationId:randomUUID(),
    chat_log_id:null,
    training_example_id:null,
    remaining:null,
    run_id:randomUUID(),
    epistemic:{verification:verification.result,formal_required:verification.required}
  });
}
