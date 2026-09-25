export const CHILD_MEMORY_SCHEMA='AQLEVON_CHILD_MEMORY_V1';

function words(value){
  return [...new Set(String(value||'').toLowerCase().split(/\s+/).map(x=>x.replace(/[.,!?;:()\[\]{}"'<>]/g,'')).filter(x=>x.length>1).slice(0,200))];
}

export function normalizeChildMemory(row={}){
  const text=String(row.text||'').trim();
  if(!text)throw new Error('MEMORY_TEXT_REQUIRED');
  return Object.freeze({
    schema:CHILD_MEMORY_SCHEMA,
    id:String(row.id||''),
    text:text.slice(0,20000),
    kind:String(row.kind||'lesson').slice(0,60),
    topic:String(row.topic||'general').slice(0,120),
    tags:Array.isArray(row.tags)?row.tags.map(x=>String(x).trim()).filter(Boolean).slice(0,30):[],
    importance:Math.max(0,Math.min(1,Number(row.importance??0.5))),
    source:String(row.source||'owner').slice(0,80),
    active:row.active!==false,
    created_at:String(row.created_at||new Date().toISOString()),
    updated_at:String(row.updated_at||new Date().toISOString()),
    last_used_at:row.last_used_at?String(row.last_used_at):null,
    use_count:Math.max(0,Number(row.use_count||0)),
    scope:'child-lab-only'
  });
}

export function scoreChildMemory(memory,query){
  if(!memory?.active)return -1;
  const q=words(query);
  if(!q.length)return Number(memory.importance||0);
  const hay=new Set(words([memory.text,memory.topic,...(memory.tags||[])].join(' ')));
  let overlap=0;
  for(const t of q)if(hay.has(t))overlap++;
  const lexical=overlap/q.length;
  const importance=Math.max(0,Math.min(1,Number(memory.importance||0)));
  return lexical*0.8+importance*0.2;
}

export function selectChildMemories(memories,query,{limit=24,minScore=0.05}={}){
  return (memories||[])
    .map(memory=>({memory,score:scoreChildMemory(memory,query)}))
    .filter(x=>x.score>=minScore)
    .sort((a,b)=>b.score-a.score)
    .slice(0,Math.max(1,Math.min(50,Number(limit||24))))
    .map(x=>Object.freeze({...x.memory,relevance_score:Number(x.score.toFixed(6))}));
}
