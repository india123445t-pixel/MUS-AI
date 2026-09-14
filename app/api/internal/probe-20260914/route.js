import { NextResponse } from 'next/server';

const PROMPT=`في Python، ما العدد الصحيح الذي يطبعه البرنامج التالي؟ لا تشغّل الكود. أعط النتيجة النهائية في سطر مستقل بالشكل FINAL: <number>.\n\ndef f(xs):\n    total = 0\n    stack = [(0, 0)]\n    while stack:\n        i, s = stack.pop()\n        if i == len(xs):\n            if s % 3 == 0:\n                total += 1\n            continue\n        stack.append((i + 1, s))\n        stack.append((i + 1, s + xs[i]))\n    return total\n\nprint(f([1, 2, 3, 4, 5, 6]))`;

export async function GET(){
  const key=process.env.OPENROUTER_API_KEY;
  if(!key)return NextResponse.json({ok:false,error:'runtime unavailable'},{status:503});
  const model='openai/gpt-oss-20b:free';
  try{
    const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{
      method:'POST',
      headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json','X-Title':'MUS AI Objective Probe'},
      body:JSON.stringify({model,messages:[{role:'system',content:'أنت MUS AI. حل الاختبار بنفسك دون أدوات خارجية. أعط تبريرًا موجزًا، ثم سطرًا نهائيًا بالشكل FINAL: <number>. لا تعرض سلسلة تفكير خاصة.'},{role:'user',content:PROMPT}],temperature:0.2}),
      signal:AbortSignal.timeout(70000)
    });
    const d=await r.json();
    if(!r.ok)return NextResponse.json({ok:false,error:'model call failed',status:r.status},{status:502});
    const answer=d?.choices?.[0]?.message?.content||'';
    const m=String(answer).match(/(?:^|\n)\s*FINAL\s*[:=]\s*(-?\d+)\s*(?:$|\n)/i);
    const extracted=m?Number(m[1]):null;
    return NextResponse.json({ok:true,probe:'code_trace_subset_dp_v1',model:d?.model||model,answer,extracted,expected:24,pass:extracted===24,cost_policy:'free-model-only'});
  }catch{return NextResponse.json({ok:false,error:'probe failed'},{status:502})}
}
