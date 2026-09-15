import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createHash, randomUUID } from 'crypto';
import { generateModelResponse } from '../../../lib/mus/providers.js';
import {
  adjudicateFormalVerification,
  buildMessages,
  buildRouteDecision,
  buildTaskContract,
  buildVerifierPrompt,
  chooseCandidate,
  makeAuditSummary,
  normalizeAdvisoryVerifier,
  safeJson,
  taskContractDigest,
} from '../../../lib/mus/kernel.js';
import { redactSecrets } from '../../../lib/mus/security.js';
import { MUS_BOS_VERSION } from '../../../lib/mus/constants.js';
import { governResponse } from '../../../lib/mus/response-governor.js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function client(){
  if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');
  return createClient(SUPABASE_URL,SUPABASE_KEY,{auth:{persistSession:false}});
}
function isUuid(v=''){return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(v))}
function ipHash(req){
  const raw=(req.headers.get('x-forwarded-for')||req.headers.get('x-real-ip')||'unknown').split(',')[0].trim();
  return createHash('sha256').update(`mus-ai|${raw}`).digest('hex').slice(0,32);
}

async function loadRuntime(sb){
  const fallback={
    settings:{
      public_chat_enabled:true,
      intelligence_router_enabled:true,
      verification_enabled:true,
      deep_reasoning_enabled:true,
      max_model_calls_per_request:3,
      max_history:16,
      temperature:0.4,
      allow_paid_external:false,
      public_web_search_enabled:false,
    },
    lessons:[],
  };
  try{
    const [cfg,lessons]=await Promise.all([
      sb.rpc('get_mus_runtime_config'),
      sb.rpc('get_mus_runtime_lessons',{p_limit:18}),
    ]);
    return {
      settings:cfg.error?fallback.settings:{...fallback.settings,...(cfg.data||{})},
      lessons:lessons.error?[]:(lessons.data||[]),
    };
  }catch{return fallback}
}

async function getQuota(sb,sessionId,hash){
  try{
    const result=await sb.rpc('public_chat_allowed',{p_session_id:sessionId,p_ip_hash:hash});
    if(result.error)return {allowed:true,remaining:null,reason:null,degraded:true};
    return result.data||{allowed:true,remaining:null};
  }catch{return {allowed:true,remaining:null,reason:null,degraded:true}}
}

async function runAdvisoryVerifier({contract,candidates,settings,webSearch}){
  const excluded=[...new Set(candidates.map(c=>c?.provider).filter(Boolean))];
  const prompt=buildVerifierPrompt({contract,candidates});
  const result=await generateModelResponse([
    {role:'system',content:prompt.system},
    {role:'user',content:JSON.stringify(prompt.payload)},
  ],webSearch,settings,{temperature:0.05,excludeProviders:excluded});
  if(!result)return {relation:'INCONCLUSIVE',confidence:0,issues:['No independent advisory verifier was available'],preferred:null,corrected_answer:'',independent:false};
  return {
    ...normalizeAdvisoryVerifier(safeJson(result.text)),
    independent:!excluded.includes(result.provider),
    verifier_provider:result.provider,
    verifier_model:result.model,
  };
}

async function maybeAdjudicateRepair({contract,selected,advisory,candidates,settings,webSearch,maxCalls,modelCalls}){
  if(!advisory?.corrected_answer||advisory.relation!=='REPAIR'||modelCalls>=maxCalls)return {selected,modelCalls,adjudication:null};
  const excluded=[...new Set([...candidates.map(c=>c.provider),advisory.verifier_provider].filter(Boolean))];
  const system=`You are an independent MUS response adjudicator. Choose between ORIGINAL and REPAIR for the frozen task contract. Do not treat agreement, confidence, or style as truth. Never invent tool execution. Return STRICT JSON only: {"choice":"original|repair|uncertain","reason":"short reason"}.`;
  const result=await generateModelResponse([
    {role:'system',content:system},
    {role:'user',content:JSON.stringify({task_contract:contract,original:selected.text,repair:advisory.corrected_answer})},
  ],webSearch,settings,{temperature:0.05,excludeProviders:excluded});
  if(!result)return {selected,modelCalls:modelCalls+1,adjudication:null};
  const parsed=safeJson(result.text)||{};
  const adjudication={choice:['original','repair','uncertain'].includes(parsed.choice)?parsed.choice:'uncertain',reason:String(parsed.reason||''),provider:result.provider,model:result.model};
  if(adjudication.choice==='repair'){
    return {selected:{...selected,text:advisory.corrected_answer,provider:result.provider,model:result.model,citations:selected.citations||[]},modelCalls:modelCalls+1,adjudication};
  }
  return {selected,modelCalls:modelCalls+1,adjudication};
}

async function logExchange(sb,{sessionId,conversationId,redactedInput,selected,runId,contract,route,verification,latency,modelCalls,learningEligible,audit,requestHash}){
  try{
    const logged=await sb.rpc('log_public_exchange_v2',{
      p_session_id:sessionId,
      p_conversation_id:conversationId,
      p_user_input:redactedInput,
      p_assistant_output:selected.text,
      p_provider:selected.provider,
      p_model:selected.model,
      p_web_search:route.web_search,
      p_ip_hash:requestHash,
      p_run_id:runId,
      p_task_contract:{...contract,contract_digest:taskContractDigest(contract),bos_version:MUS_BOS_VERSION},
      p_route_decision:route,
      p_verification:verification,
      p_latency_ms:latency,
      p_model_calls:modelCalls,
      p_difficulty:contract.difficulty,
      p_learning_eligible:learningEligible,
    });
    return logged.error?null:logged.data;
  }catch{return null}
}

export async function POST(req){
  const started=Date.now();
  const runId=randomUUID();
  try{
    const body=await req.json();
    const rawInput=String(body.input||'').trim();
    if(!rawInput)return NextResponse.json({message:'اكتب رسالة أولًا.'},{status:400});
    if(rawInput.length>20000)return NextResponse.json({message:'الرسالة طويلة جدًا.'},{status:413});

    const redactedInput=redactSecrets(rawInput);
    const sb=client();
    const {settings,lessons}=await loadRuntime(sb);
    if(settings.public_chat_enabled===false)return NextResponse.json({message:'MUS AI في وضع صيانة مؤقتًا.'},{status:503});

    const sessionId=isUuid(body.sessionId)?body.sessionId:randomUUID();
    const conversationId=isUuid(body.conversationId)?body.conversationId:randomUUID();
    const requestHash=ipHash(req);
    const quota=await getQuota(sb,sessionId,requestHash);
    if(quota.allowed===false){
      const msg=quota.reason==='daily_limit'?'وصلت إلى الحد اليومي المجاني لهذه الجلسة.':'تم الوصول إلى الحد المؤقت للمحادثات. جرّب بعد قليل.';
      return NextResponse.json({message:msg},{status:429});
    }

    const contract=buildTaskContract(redactedInput);
    const route=buildRouteDecision(contract,settings,body);
    const messages=buildMessages({
      input:redactedInput,
      history:body.history,
      contract,
      lessons,
      maxHistory:Math.max(4,Math.min(64,Number(settings?.max_history||16))),
    });

    let modelCalls=0;
    const candidates=[];
    const first=await generateModelResponse(messages,route.web_search,settings,{temperature:Number(settings?.temperature??0.4)});
    modelCalls++;
    if(!first)return NextResponse.json({message:'لا يوجد محرك استدلال متاح الآن.'},{status:503});
    candidates.push(first);

    if(route.reasoning==='deep'&&modelCalls<route.max_model_calls-1){
      const independent=[
        {role:'system',content:`${messages[0].content}\n\nINDEPENDENT SOLUTION PATH: solve from scratch. Do not assume another candidate is correct. Return the user-facing answer only.`},
        ...messages.slice(1),
      ];
      const second=await generateModelResponse(independent,route.web_search,settings,{temperature:0.25,excludeProviders:[first.provider]});
      modelCalls++;
      if(second)candidates.push(second);
    }

    let advisory=null;
    if(route.advisory_verifier&&modelCalls<route.max_model_calls){
      advisory=await runAdvisoryVerifier({contract,candidates,settings,webSearch:route.web_search});
      modelCalls++;
    }

    let selected=chooseCandidate(candidates,advisory)||first;
    const repair=await maybeAdjudicateRepair({contract,selected,advisory,candidates,settings,webSearch:route.web_search,maxCalls:route.max_model_calls,modelCalls});
    selected=repair.selected;
    modelCalls=repair.modelCalls;
    if(advisory&&repair.adjudication)advisory={...advisory,adjudication:repair.adjudication};

    // Current public chat has no external executor. Formal verification is therefore deliberately conservative.
    const deterministic={
      executionEvidence:false,
      postconditionEvidence:false,
      verified:false,
      refuted:false,
      conflicting:false,
    };
    const formal=adjudicateFormalVerification({contract,route,candidate:selected,advisoryVerifier:advisory,deterministic});
    const verification={
      required:formal.required,
      result:formal.result,
      reasons:formal.reasons||[],
      advisory:advisory?{
        relation:advisory.relation,
        confidence:advisory.confidence,
        issues:advisory.issues||[],
        independent:!!advisory.independent,
        verifier_provider:advisory.verifier_provider||null,
        verifier_model:advisory.verifier_model||null,
        adjudication:advisory.adjudication||null,
      }:null,
    };

    const governed=governResponse({text:selected.text,contract,verification,deterministic});
    selected={...selected,text:governed.text};
    const latency=Date.now()-started;
    const evidenceReady=!contract.external_evidence_required||(route.external_evidence_available&&(selected.citations||[]).length>0);
    const learningEligible=verification.result==='VERIFIED'&&evidenceReady&&!contract.high_consequence&&selected.text.length>=40;
    const audit=makeAuditSummary({runId,contract,route,verification:{...verification,response_governor_notes:governed.notes},candidates,selected,modelCalls,latencyMs:latency,redactedInput});
    const logData=await logExchange(sb,{sessionId,conversationId,redactedInput,selected,runId,contract,route,verification:{...verification,response_governor_notes:governed.notes},latency,modelCalls,learningEligible,audit,requestHash});

    return NextResponse.json({
      text:selected.text,
      provider:'mus-ai',
      model:'MUS AI',
      bos_version:MUS_BOS_VERSION,
      session_id:sessionId,
      conversation_id:conversationId,
      chat_log_id:logData?.chat_log_id||null,
      training_example_id:logData?.training_example_id||null,
      remaining:quota.remaining??null,
      run_id:runId,
      epistemic:{verification:verification.result,formal_required:verification.required},
    });
  }catch(error){
    return NextResponse.json({message:error?.message||'حدث خطأ في خدمة MUS AI.'},{status:500});
  }
}
