import { NextResponse } from 'next/server';
import { commonsSubmitAndWait } from '../../../../lib/aqlevon/commons-edge.js';

export const dynamic='force-dynamic';
export const maxDuration=60;

export async function GET(){
  const result=await commonsSubmitAndWait({
    input:'AQLEVON Commons end-to-end smoke',
    history:[],
    messages:[{role:'user',content:'Reply exactly COMMONS_SMOKE_OK'}],
    temperature:0,
    model:'AQLEVON-27B',
    timeoutMs:30000,
    pollMs:500
  });
  return NextResponse.json({ok:!!result,result:result||null},{status:result?200:503,headers:{'Cache-Control':'no-store'}});
}
