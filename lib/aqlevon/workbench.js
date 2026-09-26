import {AQLEVON_BOS_VERSION} from './constants.js';
import {redactSecrets} from './security.js';
import {childToolStatus,childToolConfig,executeChildTool,CHILD_TOOL_PROTOCOL} from './child-tools.js';
import {requiredChildPermissions,isChildPermissionGranted,CHILD_TOOL_ACTIONS,CHILD_PERMISSION_CATALOG} from './child-permissions.js';
import {normalizeChildOwnerPolicy} from './child-owner-policy.js';
import {resolveChildWebSearchKey} from './child-web-research.js';

const TOOL_NAMES=Object.freeze(['web','browser','terminal','files','media']);
const REQUIRED_ENV=Object.freeze({
  web:Object.freeze(['AQLEVON_CHILD_WEB_ADAPTER_URL','AQLEVON_CHILD_WEB_ADAPTER_KEY']),
  browser:Object.freeze(['AQLEVON_CHILD_BROWSER_ADAPTER_URL','AQLEVON_CHILD_BROWSER_ADAPTER_KEY']),
  terminal:Object.freeze(['AQLEVON_CHILD_TERMINAL_ADAPTER_URL','AQLEVON_CHILD_TERMINAL_ADAPTER_KEY']),
  files:Object.freeze(['AQLEVON_CHILD_FILES_ADAPTER_URL','AQLEVON_CHILD_FILES_ADAPTER_KEY']),
  media:Object.freeze(['AQLEVON_CHILD_MEDIA_ADAPTER_URL','AQLEVON_CHILD_MEDIA_ADAPTER_KEY']),
});
const SELFTEST_PERMISSION_ACTION=Object.freeze({web:'research',browser:'navigate',terminal:'run',files:'read',media:'read'});
const SAFE_L3_INPUT='ابحث باختصار عن تعريف محايد لبروتوكول HTTP من مصدر عام، دون تنفيذ أي إجراء آخر.';

function deepFreeze(value){
  if(value&&typeof value==='object'&&!Object.isFrozen(value)){
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

function safeObject(value){
  return deepFreeze(JSON.parse(redactSecrets(JSON.stringify(value))));
}

function knownTool(name=''){return TOOL_NAMES.includes(String(name||'').toLowerCase())?String(name).toLowerCase():null}
function latency(started){return Math.max(0,Date.now()-started)}
function actionCatalog(){
  return Object.fromEntries(Object.entries(CHILD_TOOL_ACTIONS).map(([tool,actions])=>[
    tool,actions.map(x=>({id:x.id,permissions:[...x.permissions]})),
  ]));
}

export function describeAdapterSetup(name=''){
  const tool=knownTool(name);
  if(!tool)return deepFreeze({ok:false,error_class:'TOOL_UNKNOWN'});
  const env=REQUIRED_ENV[tool];
  const actions=actionCatalog();
  const guideAction=SELFTEST_PERMISSION_ACTION[tool];
  const guidePermissions=requiredChildPermissions(tool,guideAction);
  const request_example={
    protocol:CHILD_TOOL_PROTOCOL,
    tool,
    action:guideAction,
    input:'<safe-input>',
    constraints:{dry_run:true},
    permission:guidePermissions[0]||null,
    required_permissions:[...guidePermissions],
    owner_policy:{external_network:true,receipt_required:true},
    isolation:{scope:'owner-controlled-child-lab',public_model_access:false,production_weight_read:false,production_weight_write:false,training_lane_read:false,training_lane_write:false,worker03_access:false},
  };
  const response_example={ok:true,output:{},receipt:{receipt_id:'<adapter-generated>'},evidence:[]};
  const guide={
    name:tool,
    required_env:[...env],
    native_jina_alternative:tool==='web'?['AQLEVON_CHILD_WEB_SEARCH_KEY','JINA_API_KEY','AQLEVON_CHILD_WEB_ADAPTER_KEY']:[],
    protocol:CHILD_TOOL_PROTOCOL,
    request_example,
    response_example,
    receipt_required:'عندما تكون owner_policy.receipt_required=true يجب أن تعيد الاستجابة receipt؛ وإلا لا يعتبر التنفيذ ناجحًا.',
    real_actions:actions,
    permission_ids:CHILD_PERMISSION_CATALOG.map(item=>item.id),
  };
  return safeObject(guide);
}

export function getWorkbenchSnapshot(){
  const status=childToolStatus();
  const policy_defaults=normalizeChildOwnerPolicy({});
  const tools=TOOL_NAMES.map(name=>{
    const cfg=childToolConfig(name);
    const row=status[name]||{};
    return {
      name,
      state:row.state||'ADAPTER_REQUIRED',
      configured:row.configured===true,
      mode:cfg?.mode||'unconfigured',
      protocol:row.protocol||cfg?.protocol||CHILD_TOOL_PROTOCOL,
      required_env:[...REQUIRED_ENV[name]],
      policy_gate_default:{field:'external_network',value:policy_defaults.external_network===true},
      last_selftest:null,
    };
  });
  return safeObject({bos_version:AQLEVON_BOS_VERSION,policy_defaults,tools});
}

function permissionGate(name,permissions){
  const action=SELFTEST_PERMISSION_ACTION[name];
  const required=requiredChildPermissions(name,action);
  const missing=required.filter(id=>!isChildPermissionGranted(permissions,id));
  return {action,required,missing};
}

export async function runAdapterSelfTest(name,{level='L1',permissions=null,ownerPolicy=null}={}){
  const started=Date.now();
  const tool=knownTool(name);
  if(!tool)return safeObject({ok:false,tool:String(name||''),level,error_class:'TOOL_UNKNOWN',state:'TOOL_UNKNOWN',latency_ms:latency(started),receipt_present:false,evidence_count:0});
  const normalizedLevel=String(level||'L1').toUpperCase();
  if(!['L1','L2','L3'].includes(normalizedLevel))return safeObject({ok:false,tool,level:normalizedLevel,error_class:'SELFTEST_LEVEL_UNKNOWN',state:'SELFTEST_LEVEL_UNKNOWN',latency_ms:latency(started),receipt_present:false,evidence_count:0});
  const cfg=childToolConfig(tool);
  if(normalizedLevel==='L1'){
    if(!cfg?.configured)return safeObject({ok:false,tool,level:'L1',error_class:'ADAPTER_REQUIRED',state:'ADAPTER_REQUIRED',latency_ms:latency(started),receipt_present:false,evidence_count:0});
    return safeObject({ok:true,tool,level:'L1',error_class:null,state:'CONFIGURED_OK',mode:cfg.mode,latency_ms:latency(started),receipt_present:false,evidence_count:0});
  }

  const policy=normalizeChildOwnerPolicy(ownerPolicy||{});
  const gate=permissionGate(tool,permissions);
  if(gate.missing.length)return safeObject({ok:false,tool,level:normalizedLevel,error_class:'PERMISSION_DISABLED',state:'PERMISSION_DISABLED',required_permissions:gate.required,missing_permissions:gate.missing,latency_ms:latency(started),receipt_present:false,evidence_count:0});
  if(policy.external_network!==true)return safeObject({ok:false,tool,level:normalizedLevel,error_class:'OWNER_POLICY_DISABLED',state:'OWNER_POLICY_DISABLED',required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});
  if(!cfg?.configured)return safeObject({ok:false,tool,level:normalizedLevel,error_class:'ADAPTER_REQUIRED',state:'ADAPTER_REQUIRED',required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});

  if(normalizedLevel==='L2'){
    if(tool==='web'&&cfg.mode==='native-jina'){
      const keyPresent=!!resolveChildWebSearchKey();
      return safeObject({ok:keyPresent,tool,level:'L2',error_class:keyPresent?null:'SEARCH_KEY_MISSING',state:keyPresent?'KEY_PRESENT':'ADAPTER_REQUIRED',required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});
    }
    try{
      const payload={
        protocol:CHILD_TOOL_PROTOCOL,
        tool,
        action:'aqlevon.ping',
        input:'AQLEVON Workbench safe adapter self-test.',
        constraints:{dry_run:true,selftest:'L2'},
        permission:gate.required[0]||null,
        required_permissions:gate.required,
        owner_policy:policy,
        isolation:{scope:'owner-controlled-child-lab',public_model_access:policy.public_model_access,production_weight_read:policy.production_weight_read,production_weight_write:policy.production_weight_write,training_lane_read:policy.training_lane_read,training_lane_write:policy.training_lane_write,worker03_access:policy.worker03_access},
      };
      const response=await fetch(cfg.url,{
        method:'POST',
        headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
        body:JSON.stringify(payload),
        cache:'no-store',
        signal:AbortSignal.timeout(10000),
      });
      const data=await response.json().catch(()=>null);
      if(data?.ok===true)return safeObject({ok:true,tool,level:'L2',error_class:null,state:'CONFIGURED_OK',required_permissions:gate.required,latency_ms:latency(started),receipt_present:!!data.receipt,evidence_count:Array.isArray(data.evidence)?data.evidence.length:0});
      if(data?.error_class==='ACTION_UNKNOWN')return safeObject({ok:true,tool,level:'L2',error_class:'ACTION_UNKNOWN',state:'ADAPTER_SELFTEST_UNSUPPORTED',required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});
      return safeObject({ok:false,tool,level:'L2',error_class:'ADAPTER_ERROR',state:'ADAPTER_ERROR',status:response.status,required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});
    }catch{
      return safeObject({ok:false,tool,level:'L2',error_class:'NETWORK_ERROR',state:'NETWORK_ERROR',required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});
    }
  }

  if(tool!=='web')return safeObject({ok:false,tool,level:'L3',error_class:'SAFE_SELFTEST_UNAVAILABLE',state:'SAFE_SELFTEST_UNAVAILABLE',required_permissions:gate.required,latency_ms:latency(started),receipt_present:false,evidence_count:0});
  const result=await executeChildTool('web',{action:'research',input:SAFE_L3_INPUT,constraints:{selftest:'L3',owner_only:true,multi_step:false},permissions,ownerPolicy:policy});
  return safeObject({
    ok:result?.ok===true,
    tool:'web',
    level:'L3',
    error_class:result?.ok===true?null:(result?.error_class||'ADAPTER_ERROR'),
    state:result?.ok===true?'CONFIGURED_OK':(result?.error_class||'ADAPTER_ERROR'),
    required_permissions:gate.required,
    latency_ms:latency(started),
    receipt_present:!!result?.receipt,
    evidence_count:Array.isArray(result?.evidence)?result.evidence.length:0,
  });
}

export function inferWorkbenchTool(input=''){
  const text=String(input||'').toLowerCase();
  if(/\b(?:image|audio|video|media)\b|(?:صورة|صور|فيديو|صوت|وسائط)/i.test(text))return 'media';
  if(/\b(?:terminal|shell|command|cli|execute code|run code)\b|(?:طرفية|أمر|اوامر|أوامر|نفذ كود|شغل كود)/i.test(text))return 'terminal';
  if(/\b(?:file|files|folder|directory|write file|delete file)\b|(?:ملف|ملفات|مجلد|اكتب ملف|احذف ملف)/i.test(text))return 'files';
  if(/\b(?:browser|navigate|form|login|upload|download|submit|publish)\b|(?:متصفح|تصفح|نموذج|تسجيل دخول|ارفع|رفع|نزّل|تنزيل|إرسال نموذج|انشر)/i.test(text))return 'browser';
  if(/\b(?:web|search|research|website|url|http)\b|(?:ويب|الويب|ابحث|بحث|موقع|رابط)/i.test(text))return 'web';
  return null;
}