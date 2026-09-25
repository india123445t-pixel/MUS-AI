export const RUNPOD_QUEUE_TRANSPORT='runpod_queue';

function baseUrl(raw){return raw?String(raw).replace(/\/$/,''):null}

async function jsonOrNull(response){try{return await response.json()}catch{return null}}

export async function runpodQueueHealth({endpoint,key,fetchImpl=fetch,timeoutMs=7000}={}){
  const base=baseUrl(endpoint);
  if(!base)return {ok:false,status:0,error_class:'ENV_MISSING'};
  try{
    const r=await fetchImpl(base+'/health',{
      method:'GET',
      headers:key?{Authorization:`Bearer ${key}`}:{},
      signal:AbortSignal.timeout(Number(timeoutMs||7000)),
      cache:'no-store',
    });
    return {ok:r.ok,status:r.status,error_class:r.ok?null:'RUNTIME_UNHEALTHY'};
  }catch{return {ok:false,status:0,error_class:'NETWORK_ERROR'}}
}

export async function runpodQueueCompletion({endpoint,key,input,fetchImpl=fetch,timeoutMs=65000}={}){
  const base=baseUrl(endpoint);
  if(!base)return {ok:false,status:0,error_class:'ENV_MISSING',body:null};
  if(!key)return {ok:false,status:0,error_class:'ENV_MISSING',body:null};
  try{
    const r=await fetchImpl(base+'/runsync',{
      method:'POST',
      headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'},
      body:JSON.stringify({input}),
      signal:AbortSignal.timeout(Number(timeoutMs||65000)),
      cache:'no-store',
    });
    const data=await jsonOrNull(r);
    if(!r.ok)return {ok:false,status:r.status,error_class:r.status===401||r.status===403?'AUTH_ERROR':'UPSTREAM_ERROR',body:data};
    if(data?.status==='COMPLETED'&&data?.output)return {ok:true,status:r.status,output:data.output,job_id:data.id||null,body:data};
    if(data?.status==='FAILED')return {ok:false,status:r.status,error_class:'UPSTREAM_ERROR',body:data};
    return {ok:false,status:r.status,error_class:'RUNTIME_PENDING',body:data};
  }catch(error){
    const name=String(error?.name||'').toLowerCase();
    return {ok:false,status:0,error_class:name.includes('abort')?'NETWORK_ERROR':'NETWORK_ERROR',body:null};
  }
}
