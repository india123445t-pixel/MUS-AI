import {createHash} from 'crypto';

const sha256=value=>createHash('sha256').update(String(value)).digest('hex');

function cleanResult(row={}){
  let url='';
  try{url=new URL(String(row.url||'')).toString()}catch{}
  return {
    title:String(row.title||'').slice(0,500),
    url:url.slice(0,2000),
    content:String(row.content||row.description||'').slice(0,5000),
    published_at:row.publishedTime||row.published_at||row.timestamp||null,
  };
}

export function resolvePublicWebSearchKey(){
  return String(process.env.AQLEVON_WEB_SEARCH_KEY||process.env.JINA_API_KEY||'').trim();
}

export function publicWebSearchConfigured(){
  return !!resolvePublicWebSearchKey();
}

export async function publicWebResearch(query,{key=resolvePublicWebSearchKey(),fetchImpl=fetch,timeoutMs=30000,maxResults=5}={}){
  const q=String(query||'').trim().slice(0,4000);
  if(!q)return Object.freeze({ok:false,error_class:'QUERY_REQUIRED'});
  if(!key)return Object.freeze({ok:false,error_class:'SEARCH_KEY_MISSING'});
  try{
    const response=await fetchImpl('https://s.jina.ai/?q='+encodeURIComponent(q),{
      method:'GET',
      headers:{Accept:'application/json',Authorization:`Bearer ${key}`,'X-Retain-Images':'none'},
      cache:'no-store',
      signal:AbortSignal.timeout(Math.max(3000,Math.min(45000,Number(timeoutMs)||30000))),
    });
    const body=await response.json().catch(()=>null);
    if(!response.ok){
      return Object.freeze({ok:false,error_class:response.status===401||response.status===403?'AUTH_ERROR':'SEARCH_UPSTREAM_ERROR',status:response.status});
    }
    const rows=Array.isArray(body)?body:Array.isArray(body?.data)?body.data:Array.isArray(body?.results)?body.results:[];
    const results=rows.map(cleanResult).filter(x=>x.url&&x.content).slice(0,Math.max(1,Math.min(8,Number(maxResults)||5)));
    if(!results.length)return Object.freeze({ok:false,error_class:'INVALID_RESPONSE',status:response.status});
    return Object.freeze({
      ok:true,
      query_sha256:sha256(q),
      results:Object.freeze(results),
      sources:Object.freeze(results.map(x=>Object.freeze({url:x.url,title:x.title||null,published_at:x.published_at||null}))),
    });
  }catch{
    return Object.freeze({ok:false,error_class:'NETWORK_ERROR'});
  }
}
