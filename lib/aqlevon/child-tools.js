import {requiredChildPermissions,isChildPermissionGranted} from './child-permissions.js';
import {childWebResearch,resolveChildWebSearchKey} from './child-web-research.js';
export const CHILD_TOOL_PROTOCOL='AQLEVON_CHILD_TOOL_V1';

const defs=Object.freeze({
  web:{url:'AQLEVON_CHILD_WEB_ADAPTER_URL',key:'AQLEVON_CHILD_WEB_ADAPTER_KEY'},
  browser:{url:'AQLEVON_CHILD_BROWSER_ADAPTER_URL',key:'AQLEVON_CHILD_BROWSER_ADAPTER_KEY'},
  terminal:{url:'AQLEVON_CHILD_TERMINAL_ADAPTER_URL',key:'AQLEVON_CHILD_TERMINAL_ADAPTER_KEY'},
  files:{url:'AQLEVON_CHILD_FILES_ADAPTER_URL',key:'AQLEVON_CHILD_FILES_ADAPTER_KEY'},
  media:{url:'AQLEVON_CHILD_MEDIA_ADAPTER_URL',key:'AQLEVON_CHILD_MEDIA_ADAPTER_KEY'},
});

export function childToolConfig(name){
  const def=defs[name];if(!def)return null;
  const url=String(process.env[def.url]||'').trim();
  const key=String(process.env[def.key]||'').trim();
  const nativeWeb=name==='web'&&!url&&!!resolveChildWebSearchKey();
  return Object.freeze({name,url,key,configured:!!url||nativeWeb,mode:nativeWeb?'native-jina':url?'external-adapter':'unconfigured',protocol:CHILD_TOOL_PROTOCOL});
}

export function childToolStatus(){
  return Object.fromEntries(Object.keys(defs).map(name=>{
    const cfg=childToolConfig(name);
    return [name,{state:cfg.configured?'CONFIGURED':'ADAPTER_REQUIRED',configured:cfg.configured,protocol:CHILD_TOOL_PROTOCOL}];
  }));
}

export async function executeChildTool(name,{action='',input='',constraints={},permissions=null}={}){
  const cfg=childToolConfig(name);
  if(!cfg)return Object.freeze({ok:false,error_class:'TOOL_UNKNOWN'});
  const required_permissions=requiredChildPermissions(name,action,{multi_step:constraints?.multi_step===true});
  if(!required_permissions.length)return Object.freeze({ok:false,error_class:'ACTION_UNKNOWN',tool:name,action:String(action||''),protocol:cfg.protocol});
  const missing_permissions=required_permissions.filter(id=>!isChildPermissionGranted(permissions,id));
  if(missing_permissions.length)return Object.freeze({ok:false,error_class:'PERMISSION_DISABLED',tool:name,required_permissions,missing_permissions,protocol:cfg.protocol});
  if(!cfg.configured)return Object.freeze({ok:false,error_class:'ADAPTER_REQUIRED',tool:name,required_permissions,protocol:cfg.protocol});
  if(name==='web'&&action==='research'&&cfg.mode==='native-jina'){
    const native=await childWebResearch(input);
    if(!native.ok)return Object.freeze({...native,tool:name,required_permissions,protocol:cfg.protocol});
    return Object.freeze({ok:true,tool:name,protocol:cfg.protocol,required_permissions,output:native.output,receipt:native.receipt,evidence:native.evidence});
  }
  const body={
    protocol:cfg.protocol,
    tool:name,
    action:String(action||'run').slice(0,120),
    input:String(input||'').slice(0,20000),
    constraints:constraints&&typeof constraints==='object'?constraints:{},
    permission:required_permissions[0],
    required_permissions,
    isolation:{scope:'child-lab-only',public_model_access:false,production_weight_write:false,training_lane_write:false}
  };
  try{
    const r=await fetch(cfg.url,{
      method:'POST',
      headers:{'Content-Type':'application/json',...(cfg.key?{Authorization:`Bearer ${cfg.key}`}:{})},
      body:JSON.stringify(body),
      cache:'no-store',
      signal:AbortSignal.timeout(90000),
    });
    const data=await r.json().catch(()=>null);
    if(!r.ok)return Object.freeze({ok:false,error_class:'ADAPTER_ERROR',status:r.status,tool:name,protocol:cfg.protocol});
    if(!data||data.ok!==true||!data.receipt)return Object.freeze({ok:false,error_class:'RECEIPT_REQUIRED',tool:name,protocol:cfg.protocol});
    return Object.freeze({
      ok:true,tool:name,protocol:cfg.protocol,required_permissions,
      output:data.output??null,
      receipt:data.receipt,
      evidence:Array.isArray(data.evidence)?data.evidence:[],
    });
  }catch{
    return Object.freeze({ok:false,error_class:'NETWORK_ERROR',tool:name,protocol:cfg.protocol});
  }
}
