import {isChildPermissionGranted} from './child-permissions.js';
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
  return Object.freeze({name,url,key,configured:!!url,protocol:CHILD_TOOL_PROTOCOL});
}

export function childToolStatus(){
  return Object.fromEntries(Object.keys(defs).map(name=>{
    const cfg=childToolConfig(name);
    return [name,{state:cfg.configured?'CONNECTED':'ADAPTER_REQUIRED',protocol:CHILD_TOOL_PROTOCOL}];
  }));
}

function requiredPermission(name,action){
  const a=String(action||'run').toLowerCase();
  if(name==='web')return 'web.research';
  if(name==='browser'){
    if(a.includes('login'))return 'browser.session_login';
    if(a.includes('upload'))return 'browser.upload';
    if(a.includes('download'))return 'browser.download';
    if(a.includes('submit')||a.includes('confirm'))return 'browser.submit';
    if(a.includes('fill')||a.includes('form'))return 'browser.form_fill';
    return 'browser.navigate';
  }
  if(name==='files'){
    if(a.includes('delete')||a.includes('remove'))return 'files.delete';
    if(a.includes('write')||a.includes('edit')||a.includes('create'))return 'files.write';
    return 'files.read';
  }
  if(name==='terminal')return 'terminal.run';
  if(name==='media')return a.includes('write')||a.includes('create')||a.includes('edit')?'media.write':'media.read';
  return null;
}

export async function executeChildTool(name,{action='',input='',constraints={},permissions=null}={}){
  const cfg=childToolConfig(name);
  if(!cfg)return Object.freeze({ok:false,error_class:'TOOL_UNKNOWN'});
  const permission=requiredPermission(name,action);
  if(!permission||!isChildPermissionGranted(permissions,permission))return Object.freeze({ok:false,error_class:'PERMISSION_DISABLED',tool:name,required_permission:permission,protocol:cfg.protocol});
  if(!cfg.configured)return Object.freeze({ok:false,error_class:'ADAPTER_REQUIRED',tool:name,required_permission:permission,protocol:cfg.protocol});
  const body={
    protocol:cfg.protocol,
    tool:name,
    action:String(action||'run').slice(0,120),
    input:String(input||'').slice(0,20000),
    constraints:constraints&&typeof constraints==='object'?constraints:{},
    permission,
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
      ok:true,tool:name,protocol:cfg.protocol,
      output:data.output??null,
      receipt:data.receipt,
      evidence:Array.isArray(data.evidence)?data.evidence:[],
    });
  }catch{
    return Object.freeze({ok:false,error_class:'NETWORK_ERROR',tool:name,protocol:cfg.protocol});
  }
}
