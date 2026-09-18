const ENDPOINT='https://qkoscgdegnqcypkjrefn.supabase.co/functions/v1/aqlevon-commons';

async function callCommons(body,{timeoutMs=15000}={}){
  const r=await fetch(ENDPOINT,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body),
    signal:AbortSignal.timeout(timeoutMs),
    cache:'no-store'
  });
  const data=await r.json().catch(()=>({}));
  if(!r.ok)return {ok:false,status:r.status,...data};
  return {ok:true,status:r.status,...data};
}

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export async function commonsHealth(){
  try{return await callCommons({op:'health'},{timeoutMs:8000})}
  catch{return {ok:false,available:false,active_workers:0,error:'commons_unreachable'}}
}

export async function commonsSubmitAndWait({
  input,
  history=[],
  messages=[],
  temperature=0.4,
  model='AQLEVON-27B',
  timeoutMs=120000,
  pollMs=1200
}={}){
  const health=await commonsHealth();
  if(!health.ok||Number(health.active_workers||0)<1)return null;

  const submit=await callCommons({
    op:'submit',
    input:String(input||'').slice(0,12000),
    history:Array.isArray(history)?history.slice(-32):[],
    messages:Array.isArray(messages)?messages.slice(-32):[],
    temperature:Number(temperature)||0,
    model
  },{timeoutMs:10000});
  if(!submit.ok||!submit.job_id)return null;

  const deadline=Date.now()+Math.max(5000,Math.min(240000,Number(timeoutMs)||120000));
  while(Date.now()<deadline){
    const state=await callCommons({op:'status',job_id:submit.job_id},{timeoutMs:8000});
    if(!state.ok)return null;
    if(state.status==='completed'){
      const result=state.result||{};
      const text=String(result.text||result.response||'').trim();
      if(!text)return null;
      return {
        text,
        model:String(result.model||model),
        provider:'aqlevon-commons',
        citations:Array.isArray(result.citations)?result.citations:[],
        commons_job_id:String(submit.job_id)
      };
    }
    if(state.status==='failed'||state.status==='expired')return null;
    await sleep(Math.max(250,Math.min(5000,pollMs)));
  }
  return null;
}
