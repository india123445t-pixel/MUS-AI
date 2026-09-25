'use client';

const STATE_KEY = 'aqlevon-workspace-web-v1';
const SESSION_KEY = 'aqlevon-workspace-session-v1';
const MAX_INLINE_FILE = 4 * 1024 * 1024;

const now = () => new Date().toISOString();
const uid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const DEFAULT_PLUGINS = [
  { id:'web-search', name:'Web Search', description:'Web search requires a connected AQLEVON runtime adapter.', installed:1, enabled:0, availableScopes:['READ'], connection:{status:'disconnected',scopes:[]} },
  { id:'code-interpreter', name:'Code Interpreter', description:'Code execution requires a connected AQLEVON runtime adapter.', installed:1, enabled:0, availableScopes:['READ'], connection:{status:'disconnected',scopes:[]} },
  { id:'image-gen', name:'Image Generation', description:'Image generation requires a connected AQLEVON runtime adapter.', installed:1, enabled:0, availableScopes:['CREATE'], connection:{status:'disconnected',scopes:[]} },
  { id:'github', name:'GitHub', description:'Connect GitHub in a trusted runtime.', installed:0, enabled:0, availableScopes:['READ','CREATE','UPDATE'], connection:{status:'disconnected',scopes:[]} },
  { id:'calendar', name:'Calendar', description:'Calendar connector.', installed:0, enabled:0, availableScopes:['READ','CREATE'], connection:{status:'disconnected',scopes:[]} },
  { id:'drive', name:'Drive', description:'Drive connector.', installed:0, enabled:0, availableScopes:['READ','CREATE','UPDATE','DELETE'], connection:{status:'disconnected',scopes:[]} },
];

function blankState(){
  return {
    version:1,
    chats:[], projects:[], files:[], jobs:[], scheduled:[], memory:[],
    plugins:DEFAULT_PLUGINS,
    settings:{
      theme:'dark', personalization:'', voice_enabled:'', notifications:'', language:'ar',
      search_default:'', research_depth:'standard', timezone_default:'', density:'comfortable', startup_page:'chat'
    },
    repos:{},
  };
}
function load(){
  if(typeof window==='undefined') return blankState();
  try{
    const x=JSON.parse(localStorage.getItem(STATE_KEY)||'null');
    if(!x||typeof x!=='object') return blankState();
    const out={...blankState(),...x,settings:{...blankState().settings,...(x.settings||{})},plugins:Array.isArray(x.plugins)&&x.plugins.length?x.plugins:DEFAULT_PLUGINS};
    out.plugins=(out.plugins||[]).map(p=>({...p,enabled:0,connection:{status:'disconnected',scopes:[]}}));
    out.scheduled=(out.scheduled||[]).map(item=>({...item,enabled:false,next_run:null,adapter_state:'NOT_CONNECTED'}));
    return out;
  }catch{return blankState()}
}
function save(s){ if(typeof window!=='undefined') localStorage.setItem(STATE_KEY,JSON.stringify(s)); return s; }
function update(fn){ const s=load(); const out=fn(s)||s; save(out); return out; }
function qs(path){ return new URL(path,'https://aqlevon.local'); }
function findChat(s,id){ return s.chats.find(c=>c.id===id); }
function publicChat(c){ const {messages,...rest}=c; return rest; }
function ensureSession(){
  if(typeof window==='undefined') return uid();
  let id=localStorage.getItem(SESSION_KEY); if(!id){id=uid();localStorage.setItem(SESSION_KEY,id)} return id;
}
function textDataUrl(text,mime='text/markdown;charset=utf-8'){
  return `data:${mime};base64,${btoa(unescape(encodeURIComponent(text)))}`;
}
function fileFromState(id){ return load().files.find(f=>f.id===id); }
function calcNext(item){
  if(!item.enabled) return null;
  if(item.kind==='once') return item.runAt ? new Date(item.runAt).toISOString() : null;
  const mins=Math.max(1,Number(item.interval_minutes||item.intervalMinutes||60));
  return new Date(Date.now()+mins*60000).toISOString();
}

async function runJob(id){
  const s0=load(); const j0=s0.jobs.find(j=>j.id===id); if(!j0||!['queued','running','claimed'].includes(j0.status)) return;
  update(s=>{const j=s.jobs.find(x=>x.id===id);if(j){j.status='running';j.updated_at=now();j.steps=[{step:'generate',name:'generate',status:'running',detail:'AQLEVON is generating the result'}]}return s});
  let input={}; try{input=JSON.parse(j0.input||'{}')}catch{}
  const prompt=input.prompt||input.question||input.goal||j0.title;
  try{
    const userState=load();
    const r=await fetch('/api/commons/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      input:prompt,
      history:[],
      webSearch:false,
      personalization:String(userState.settings?.personalization||'').slice(0,4000),
      memories:(userState.memory||[]).slice(0,16).map(x=>({content:String(x.content||'').slice(0,1000)})).filter(x=>x.content),
      sessionId:ensureSession(),
      conversationId:uid()
    })});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(d.message||'AQLEVON runtime unavailable');
    const fid=uid(), created=now();
    update(s=>{
      s.files.unshift({id:fid,project_id:input.projectId||null,name:(j0.title||'result').replace(/[\\/:*?"<>|]/g,'-')+'.md',mime:'text/markdown',size:new Blob([d.text||'']).size,kind:'generated',dataUrl:textDataUrl(d.text||''),created_at:created});
      const j=s.jobs.find(x=>x.id===id); if(j){j.status='done';j.progress=1;j.result=JSON.stringify({fileId:fid,format:'md'});j.steps=[{step:'generate',name:'generate',status:'done',detail:'AQLEVON response created'},{step:'persist',name:'persist',status:'done',detail:'Saved in your browser library'},{step:'verify',name:'verify',status:'done',detail:'Browser delivery completed'}];j.updated_at=now();}
      return s;
    });
  }catch(e){
    update(s=>{const j=s.jobs.find(x=>x.id===id);if(j){j.status='failed';j.error=String(e.message||e);j.steps=[...(j.steps||[]),{step:'verify',name:'verify',status:'failed',detail:j.error}];j.updated_at=now()}return s});
  }
}
function recoverJobs(){
  const s=load();
  for(const j of s.jobs.filter(x=>x.status==='queued')) setTimeout(()=>runJob(j.id),10);
}

async function fileToDataUrl(file){
  if(file.size>MAX_INLINE_FILE) throw new Error('Browser edition currently stores files up to 4 MB. Use the downloadable desktop/runtime package for larger files.');
  return await new Promise((resolve,reject)=>{const fr=new FileReader();fr.onload=()=>resolve(fr.result);fr.onerror=()=>reject(fr.error);fr.readAsDataURL(file)});
}

async function get(path){
  const u=qs(path), p=u.pathname, s=load();
  if(p==='/bootstrap'){
    let status=null,health=null,commons=null;
    try{
      const [sr,hr,cr]=await Promise.all([
        fetch('/api/status',{cache:'no-store'}),
        fetch('/api/inference-health',{cache:'no-store'}),
        fetch('/api/commons/health',{cache:'no-store'})
      ]);
      status=sr.ok?await sr.json():null;
      health=hr.ok?await hr.json():null;
      commons=cr.ok?await cr.json():null;
    }catch{}
    const selfHostedConfigured=status?.self_hosted_configured===true;
    const inferenceReady=health?.inference_ready===true||commons?.available===true;
    return {mode:'public-browser',workspace:{id:'local',name:'AQLEVON Workspace',created_at:now()},aiConfigured:selfHostedConfigured||commons?.available===true,inferenceReady,inferenceError:inferenceReady?null:(health?.primary_error_class||'ENV_MISSING'),webSearchAvailable:false,runtime:{provider:'AQLEVON',browserStorage:true,commonsAvailable:!!commons?.available,activeWorkers:Number(commons?.active_workers||0),runtimeMode:'self_hosted_only',sovereignRuntime:true,inferenceTarget:'aqlevon-engine',externalProviderRouting:false,providerHealth:health}};
  }
  if(p==='/chats'){
    const q=(u.searchParams.get('q')||'').toLowerCase();
    return s.chats.filter(c=>!c.temporary&&(q?(c.title||'').toLowerCase().includes(q)||(c.messages||[]).some(m=>(m.content||'').toLowerCase().includes(q)):c.project_id==null)).sort((a,b)=>String(b.updated_at).localeCompare(String(a.updated_at))).slice(0,100).map(publicChat);
  }
  let m=p.match(/^\/chats\/([^/]+)$/); if(m){const c=findChat(s,decodeURIComponent(m[1]));if(!c)throw Error('not found');return structuredClone(c)}
  if(p==='/projects') return s.projects.map(pr=>({...pr,chatCount:s.chats.filter(c=>c.project_id===pr.id).length,fileCount:s.files.filter(f=>f.project_id===pr.id).length}));
  m=p.match(/^\/projects\/([^/]+)$/); if(m){const pr=s.projects.find(x=>x.id===decodeURIComponent(m[1]));if(!pr)throw Error('not found');return {...structuredClone(pr),chats:s.chats.filter(c=>c.project_id===pr.id).map(publicChat),files:s.files.filter(f=>f.project_id===pr.id).map(({dataUrl,...f})=>f)}}
  if(p==='/files'){
    const kind=u.searchParams.get('kind')||'all', q=(u.searchParams.get('q')||'').toLowerCase();
    return s.files.filter(f=>(kind==='all'||f.kind===kind)&&(!q||(f.name||'').toLowerCase().includes(q))).map(({dataUrl,...f})=>f);
  }
  if(p==='/jobs'){recoverJobs();return s.jobs.slice().sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)))}
  m=p.match(/^\/jobs\/([^/]+)$/); if(m){const j=s.jobs.find(x=>x.id===decodeURIComponent(m[1]));if(!j)throw Error('not found');return structuredClone(j)}
  if(p==='/scheduled') return s.scheduled.slice().sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at))).map(x=>({...x,enabled:false,next_run:null,adapter_state:'NOT_CONNECTED',runs:x.runs||[]}));
  if(p==='/plugins') return structuredClone(s.plugins);
  if(p==='/memory') return structuredClone(s.memory).sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
  if(p==='/settings') return structuredClone(s.settings);
  if(p==='/dev/repos') return Object.values(s.repos).map(r=>({name:r.name,branch:r.branch||'main',dirty:!!r.dirty}));
  if(p==='/dev/github/status') return {configured:false,note:'Connectors are managed by the AQLEVON runtime, not stored in this browser.'};
  m=p.match(/^\/dev\/repos\/([^/]+)\/(tree|file|status|diff|search|checkpoints)$/);
  if(m){
    const name=decodeURIComponent(m[1]), action=m[2], r=s.repos[name]; if(!r)throw Error('repository not found');
    if(action==='tree') return Object.keys(r.files||{}).sort().map(path=>({path,type:'file'}));
    if(action==='file'){const fp=u.searchParams.get('path');if(!(fp in (r.files||{})))throw Error('file not found');return {content:r.files[fp]}}
    if(action==='status') return {branch:r.branch||'main',dirty:!!r.dirty,changes:r.dirty?[{status:'M',path:'browser workspace'}]:[],log:(r.commits||[]).slice(-8).reverse().map(c=>`${c.sha.slice(0,8)} ${c.message}`).join('\n')};
    if(action==='diff') return {diff:r.dirty?'Browser-local changes are pending. Open files to review edits.':''};
    if(action==='checkpoints') return structuredClone(r.checkpoints||[]);
    if(action==='search'){
      const q=(u.searchParams.get('q')||'').toLowerCase(); const out=[];
      for(const [file,txt] of Object.entries(r.files||{})){String(txt).split('\n').forEach((line,i)=>{if(q&&line.toLowerCase().includes(q))out.push({file,line:i+1,text:line.slice(0,180)})})}
      return out.slice(0,200);
    }
  }
  throw Error('Not found: '+path);
}

async function post(path, body={}){
  const u=qs(path), p=u.pathname;
  if(p==='/chats'){
    const c={id:uid(),project_id:body.projectId||null,title:body.title||'New chat',temporary:body.temporary?1:0,pinned:0,created_at:now(),updated_at:now(),messages:[]};
    update(s=>{s.chats.unshift(c);return s}); return publicChat(c);
  }
  let m=p.match(/^\/chats\/([^/]+)\/branch$/); if(m){
    const src=findChat(load(),decodeURIComponent(m[1]));if(!src)throw Error('not found'); const idx=body.messageId?(src.messages||[]).findIndex(x=>x.id===body.messageId):(src.messages||[]).length-1;
    const c={...structuredClone(src),id:uid(),title:(src.title||'Chat')+' (branch)',created_at:now(),updated_at:now(),messages:(src.messages||[]).slice(0,idx+1).map(x=>({...x,id:uid()}))};
    update(s=>{s.chats.unshift(c);return s});return {id:c.id};
  }
  if(/^\/chats\/[^/]+\/stream\/stop$/.test(p)) throw new Error('stop');
  if(p==='/projects'){
    const pr={id:uid(),name:body.name||'Untitled project',instructions:body.instructions||'',created_at:now()};update(s=>{s.projects.unshift(pr);return s});return pr;
  }
  if(p==='/jobs'){
    const j={id:uid(),title:body.title||'Task',kind:body.kind||'work.deliverable',status:'queued',progress:0,input:JSON.stringify(body),result:null,error:null,created_at:now(),updated_at:now(),steps:[],evidence:[]};
    update(s=>{s.jobs.unshift(j);return s});setTimeout(()=>runJob(j.id),20);return j;
  }
  m=p.match(/^\/jobs\/([^/]+)\/(cancel|retry)$/); if(m){const id=decodeURIComponent(m[1]);if(m[2]==='cancel')update(s=>{const j=s.jobs.find(x=>x.id===id);if(j)j.status='cancelled';return s});else{update(s=>{const j=s.jobs.find(x=>x.id===id);if(j){j.status='queued';j.error=null}return s});setTimeout(()=>runJob(id),20)}return {ok:true}}
  if(p==='/scheduled'){
    const item={id:uid(),title:body.title||'Automation draft',kind:body.kind||'once',prompt:body.prompt||'',runAt:body.runAt||'',interval_minutes:Number(body.intervalMinutes||60),condition_query:body.conditionQuery||'',enabled:false,next_run:null,adapter_state:'NOT_CONNECTED',created_at:now(),runs:[]};update(s=>{s.scheduled.unshift(item);return s});return item;
  }
  m=p.match(/^\/plugins\/([^/]+)\/(connect|disconnect)$/);if(m){
    const id=decodeURIComponent(m[1]); if(m[2]==='disconnect'){update(s=>{const x=s.plugins.find(p=>p.id===id);if(x)x.connection={status:'disconnected',scopes:[]};return s});return {ok:true}}
    return {status:'error',scopes:[],note:'For security, external app tokens are never stored in the public browser edition. Connect apps from the trusted AQLEVON runtime.'};
  }
  if(p==='/memory'){const x={id:uid(),content:String(body.content||''),created_at:now()};update(s=>{s.memory.unshift(x);return s});return {id:x.id}}
  if(p==='/settings'){update(s=>{s.settings={...s.settings,...body};return s});return {ok:true}}
  if(p==='/data/clear-chats'){update(s=>{s.chats=[];return s});return {ok:true}}
  if(p==='/dev/repos'){
    const name=String(body.name||'').trim()||String(body.cloneUrl||'').split('/').pop()?.replace(/\.git$/,'')||'repo';
    const readme=body.cloneUrl?`# ${name}\n\nBrowser workspace placeholder for ${body.cloneUrl}.\n\nUse the downloadable AQLEVON runtime for authenticated cloning and shell execution.`:`# ${name}\n\nCreated in AQLEVON browser workspace.\n`;
    update(s=>{if(s.repos[name])throw Error('repository already exists');s.repos[name]={name,branch:'main',dirty:false,files:{'README.md':readme},commits:[],checkpoints:[]};return s});return {name};
  }
  m=p.match(/^\/dev\/repos\/([^/]+)\/(commit|checkpoints|rollback|run)$/);if(m){
    const name=decodeURIComponent(m[1]), action=m[2]; let out;
    update(s=>{const r=s.repos[name];if(!r)throw Error('repository not found');
      if(action==='commit'){const sha=uid().replaceAll('-','');r.commits=[...(r.commits||[]),{sha,message:body.message||'update',at:now()}];r.dirty=false;out={sha}}
      if(action==='checkpoints'){const cp={id:uid(),label:body.label||'checkpoint',git_ref:(r.commits||[]).at(-1)?.sha||uid().replaceAll('-',''),snapshot:structuredClone(r.files),created_at:now()};r.checkpoints=[cp,...(r.checkpoints||[])];out=cp}
      if(action==='rollback'){const cp=(r.checkpoints||[]).find(x=>x.id===body.checkpointId);if(!cp)throw Error('checkpoint not found');r.files=structuredClone(cp.snapshot||{});r.dirty=true;out={head:cp.git_ref,restored:Object.keys(r.files).length}}
      if(action==='run'){const cmd=String(body.command||'').trim();let stdout='',stderr='',exitCode=0;if(cmd==='ls'||cmd==='dir')stdout=Object.keys(r.files||{}).join('\n');else if(cmd.startsWith('cat '))stdout=r.files[cmd.slice(4).trim()]||'';else{stderr='REAL_SHELL_ADAPTER_NOT_CONNECTED: command execution is disabled in the public browser sandbox.';exitCode=126}out={stdout,stderr,exitCode}}
      return s}); return out;
  }
  throw Error('Not found: '+path);
}

async function patch(path, body={}){
  const p=qs(path).pathname; let out={ok:true};
  let m=p.match(/^\/chats\/([^/]+)$/);if(m){update(s=>{const c=findChat(s,decodeURIComponent(m[1]));if(!c)throw Error('not found');if(body.title!==undefined)c.title=body.title;if(body.pinned!==undefined)c.pinned=body.pinned?1:0;c.updated_at=now();return s});return out}
  m=p.match(/^\/projects\/([^/]+)$/);if(m){update(s=>{const x=s.projects.find(p=>p.id===decodeURIComponent(m[1]));if(!x)throw Error('not found');Object.assign(x,body);return s});return out}
  m=p.match(/^\/files\/([^/]+)$/);if(m){update(s=>{const x=s.files.find(f=>f.id===decodeURIComponent(m[1]));if(!x)throw Error('not found');if(body.name!==undefined)x.name=body.name;return s});return out}
  m=p.match(/^\/scheduled\/([^/]+)$/);if(m){update(s=>{const x=s.scheduled.find(v=>v.id===decodeURIComponent(m[1]));if(!x)throw Error('not found');Object.assign(x,body);x.enabled=false;x.next_run=null;x.adapter_state='NOT_CONNECTED';return s});return out}
  m=p.match(/^\/plugins\/([^/]+)$/);if(m){update(s=>{const x=s.plugins.find(v=>v.id===decodeURIComponent(m[1]));if(!x)throw Error('not found');Object.assign(x,body);return s});return out}
  throw Error('Not found: '+path);
}

async function del(path){
  const p=qs(path).pathname; let m;
  m=p.match(/^\/chats\/([^/]+)$/);if(m){update(s=>{s.chats=s.chats.filter(x=>x.id!==decodeURIComponent(m[1]));return s});return {ok:true}}
  m=p.match(/^\/projects\/([^/]+)$/);if(m){const id=decodeURIComponent(m[1]);update(s=>{s.projects=s.projects.filter(x=>x.id!==id);s.chats.forEach(c=>{if(c.project_id===id)c.project_id=null});s.files.forEach(f=>{if(f.project_id===id)f.project_id=null});return s});return {ok:true}}
  m=p.match(/^\/files\/([^/]+)$/);if(m){update(s=>{s.files=s.files.filter(x=>x.id!==decodeURIComponent(m[1]));return s});return {ok:true}}
  m=p.match(/^\/scheduled\/([^/]+)$/);if(m){update(s=>{s.scheduled=s.scheduled.filter(x=>x.id!==decodeURIComponent(m[1]));return s});return {ok:true}}
  m=p.match(/^\/memory\/([^/]+)$/);if(m){update(s=>{s.memory=s.memory.filter(x=>x.id!==decodeURIComponent(m[1]));return s});return {ok:true}}
  m=p.match(/^\/jobs\/([^/]+)$/);if(m){update(s=>{s.jobs=s.jobs.filter(x=>x.id!==decodeURIComponent(m[1]));return s});return {ok:true}}
  throw Error('Not found: '+path);
}

async function put(path, body={}){
  const p=qs(path).pathname;const m=p.match(/^\/dev\/repos\/([^/]+)\/file$/);if(!m)throw Error('Not found: '+path);
  const name=decodeURIComponent(m[1]), fp=String(body.path||'').replace(/^\/+/, '');if(!fp||fp.includes('..'))throw Error('invalid path');
  update(s=>{const r=s.repos[name];if(!r)throw Error('repository not found');r.files=r.files||{};r.files[fp]=String(body.content??'');r.dirty=true;return s});return {ok:true,path:fp};
}

async function upload(path, form){
  if(qs(path).pathname!=='/files')throw Error('upload endpoint not found');
  const file=form.get('file');if(!file)throw Error('no file');const dataUrl=await fileToDataUrl(file);const x={id:uid(),project_id:form.get('projectId')||null,name:file.name,mime:file.type||'application/octet-stream',size:file.size,kind:(file.type||'').startsWith('image/')?'image':'uploaded',dataUrl,created_at:now()};update(s=>{s.files.unshift(x);return s});const {dataUrl:_,...meta}=x;return meta;
}

async function streamChat(chatId,payload,signal){
  const id=String(chatId); let prompt=''; let history=[];
  update(s=>{const c=findChat(s,id);if(!c)throw Error('chat not found');c.messages=c.messages||[];
    if(payload.editMessageId){const i=c.messages.findIndex(x=>x.id===payload.editMessageId);if(i>=0)c.messages.splice(i)}
    if(payload.regenerate){for(let i=c.messages.length-1;i>=0;i--){if(c.messages[i].role==='assistant'){c.messages.splice(i,1);break}}}
    if(payload.content){c.messages.push({id:uid(),role:'user',content:payload.content,created_at:now()});prompt=payload.content}
    else{prompt=[...c.messages].reverse().find(x=>x.role==='user')?.content||''}
    history=c.messages.slice(0,-1).slice(-20).map(({role,content})=>({role,content}));c.updated_at=now();return s});
  if(!prompt)throw Error('No user message to send');
  const userState=load();
  const personalization=String(userState.settings?.personalization||'').slice(0,4000);
  const memories=(userState.memory||[]).slice(0,16).map(x=>({content:String(x.content||'').slice(0,1000)})).filter(x=>x.content);
  const r=await fetch('/api/commons/chat',{method:'POST',headers:{'Content-Type':'application/json'},signal,body:JSON.stringify({input:prompt,history,webSearch:!!payload.useWebSearch,reasoning:payload.reasoning,personalization,memories,sessionId:ensureSession(),conversationId:id})});
  const d=await r.json().catch(()=>({}));if(!r.ok){const err=new Error(d.message||'AQLEVON runtime unavailable');err.errorClass=d.error_class||null;throw err}
  const text=String(d.text||'');
  update(s=>{const c=findChat(s,id);if(!c)return s;c.messages.push({id:uid(),role:'assistant',content:text,created_at:now(),chatLogId:d.chat_log_id||null});if(!c.title||c.title==='New chat')c.title=prompt.slice(0,70)||'Chat';c.updated_at=now();return s});
  const enc=new TextEncoder();
  return new Response(new ReadableStream({start(controller){
    let i=0;const step=Math.max(12,Math.ceil(text.length/24));
    const pump=()=>{if(signal?.aborted){controller.error(new DOMException('Aborted','AbortError'));return}if(i<text.length){const chunk=text.slice(i,i+step);i+=step;controller.enqueue(enc.encode(`event: delta\ndata: ${JSON.stringify({t:chunk})}\n\n`));setTimeout(pump,8);return}controller.enqueue(enc.encode(`event: done\ndata: ${JSON.stringify({ok:true})}\n\n`));controller.close()};pump();
  }}),{status:200,headers:{'Content-Type':'text/event-stream'}});
}

function fileUrl(id){ return fileFromState(id)?.dataUrl || 'data:text/plain,File%20not%20found'; }
async function fileText(id){ const u=fileUrl(id);const r=await fetch(u);return r.text(); }
function downloadExport(){
  const s=load();const clean={...s,files:s.files.map(({dataUrl,...f})=>f)};const blob=new Blob([JSON.stringify(clean,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='aqlevon-export.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export const api={get,post,patch,del,put,upload,streamChat,fileUrl,fileText,downloadExport};
