import { NextResponse } from 'next/server';
import { commonsHealth } from '../../../../lib/aqlevon/commons-edge.js';

export const dynamic='force-dynamic';

export async function GET(){
  const h=await commonsHealth();
  return NextResponse.json({
    runtime:'aqlevon-commons',
    available:!!h.available,
    active_workers:Number(h.active_workers||0),
    transport:'supabase-edge-pull-queue',
    inference_protocol:'openai-compatible',
    cost_policy:'worker-supplied-compute',
    edge_reachable:!!h.ok
  },{status:h.ok?200:503,headers:{'Cache-Control':'no-store'}});
}
