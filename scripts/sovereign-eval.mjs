import {generateModelResponse,checkSelfHostedHealth,getSelfHostedRuntimeDescriptor} from '../lib/kite/providers.js';

const cases=Object.freeze([
  {id:'reasoning-1',category:'reasoning',prompt:'A box has 3 red, 4 blue, and 5 green balls. Without replacement, explain the probability that two draws are both blue. Give the exact fraction.'},
  {id:'coding-1',category:'coding',prompt:'Write a JavaScript function that returns the first non-repeating character in O(n) time. Explain complexity briefly.'},
  {id:'arabic-1',category:'arabic',prompt:'اشرح الفرق بين الاستدلال الاستنباطي والاستقرائي بالعربية الفصحى مع مثال قصير لكل واحد.'},
  {id:'darija-1',category:'moroccan_darija',prompt:'شرح ليا بالدارجة المغربية وباختصار شنو الفرق بين API وواجهة المستخدم، وعطيني مثال بسيط.'},
  {id:'tool-use-1',category:'tool_use',prompt:'You have a read-only tool named lookup_weather(city). The user asks for current weather in Rabat. Return strict JSON only: {"tool":"lookup_weather","arguments":{"city":"Rabat"},"reason":"..."}. Do not claim the tool was executed.'},
]);

const settings={runtime_mode:'self_hosted_only',self_hosted_model:process.env.KITE_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'kite-ai'};
const descriptor=getSelfHostedRuntimeDescriptor(settings);
if(!descriptor.configured){console.error(JSON.stringify({ok:false,error:'SELF_HOSTED_NOT_CONFIGURED',descriptor},null,2));process.exit(2)}
const health=await checkSelfHostedHealth(settings);
if(!health.ok){console.error(JSON.stringify({ok:false,error:'SELF_HOSTED_HEALTH_FAILED',health,descriptor},null,2));process.exit(3)}

const results=[];
for(const item of cases){
  const started=performance.now();
  const response=await generateModelResponse([{role:'system',content:'You are KITE AI evaluation runtime. Answer only the requested task. Never claim unexecuted tool actions.'},{role:'user',content:item.prompt}],false,settings,{includeDiagnostics:true,temperature:0});
  const latency_ms=Math.round(performance.now()-started);
  results.push({
    id:item.id,category:item.category,latency_ms,
    pass:!!response&&!response.unavailable&&typeof response.text==='string'&&response.text.length>0,
    provider:response?.provider||null,model:response?.model||null,
    output:response?.text||null,error_class:response?.error_class||null,
  });
}
const summary={
  ok:results.every(r=>r.pass),
  runtime:'self_hosted_only',
  provider:'kite-engine',
  model:descriptor.model,
  categories:[...new Set(results.map(r=>r.category))],
  latency_ms:{min:Math.min(...results.map(r=>r.latency_ms)),max:Math.max(...results.map(r=>r.latency_ms)),avg:Math.round(results.reduce((a,r)=>a+r.latency_ms,0)/results.length)},
  results,
};
console.log(JSON.stringify(summary,null,2));
process.exit(summary.ok?0:1);
