import {createHash,randomUUID} from 'crypto';

const sha256=value=>createHash('sha256').update(String(value)).digest('hex');

function cleanResult(row={}){
  return {
    title:String(row.title||'').slice(0,500),
    url:String(row.url||'').slice(0,2000),
    content:String(row.content||row.description||'').slice(0,6000),
    published_at:row.publishedTime||row.published_at||row.timestamp||null,
  };
}

export function resolveChildWebSearchKey(){
  return String(
    process.env.AQLEVON_CHILD_WEB_SEARCH_KEY||
    process.env.JINA_API_KEY||
    process.env.AQLEVON_CHILD_WEB_ADAPTER_KEY||
    ''
  ).trim();
}

export async function childWebResearch(query,{key=resolveChildWebSearchKey(),fetchImpl=fetch,timeoutMs=45000}={}){
  const q=String(query||'').trim().slice(0,4000);
  if(!q)return Object.freeze({ok:false,error_class:'QUERY_REQUIRED'});
  if(!key)return Object.freeze({ok:false,error_class:'SEARCH_KEY_MISSING'});

  try{
    const url='https://s.jina.ai/?q='+encodeURIComponent(q);
    const r=await fetchImpl(url,{
      method:'GET',
      headers:{
        Accept:'application/json',
        Authorization:`Bearer ${key}`,
        'X-Retain-Images':'none',
      },
      cache:'no-store',
      signal:AbortSignal.timeout(Number(timeoutMs||45000)),
    });
    const body=await r.json().catch(()=>null);
    if(!r.ok)return Object.freeze({ok:false,error_class:r.status===401||r.status===403?'AUTH_ERROR':'SEARCH_UPSTREAM_ERROR',status:r.status});

    const rows=Array.isArray(body)?body:Array.isArray(body?.data)?body.data:Array.isArray(body?.results)?body.results:[];
    const results=rows.map(cleanResult).filter(x=>x.url||x.content).slice(0,5);
    if(!results.length)return Object.freeze({ok:false,error_class:'INVALID_RESPONSE',status:r.status});

    return Object.freeze({
      ok:true,
      output:{query:q,results},
      evidence:results.filter(x=>x.url).map(x=>({type:'web_source',url:x.url,title:x.title||null})),
      receipt:{
        receipt_id:randomUUID(),
        provider:'jina-search',
        tool:'web',
        action:'research',
        query_sha256:sha256(q),
        result_count:results.length,
        status:'SUCCESS',
        observed_at:new Date().toISOString(),
      }
    });
  }catch{
    return Object.freeze({ok:false,error_class:'NETWORK_ERROR'});
  }
}
