import { NextResponse } from 'next/server';
import { EFFECT_CAPABILITIES, MUS_BOS_VERSION, VERIFICATION_RESULTS } from '../../../../lib/mus/constants.js';
import { protocolRegistrySnapshot } from '../../../../lib/mus/domain-protocols.js';

export const dynamic='force-dynamic';

export async function GET(){
  return NextResponse.json({
    name:'MUS AI Behavioral Operating System',
    version:MUS_BOS_VERSION,
    implementation_state:'kernel-integrated',
    canonical_runtime_objects:16,
    invariants:[
      'LLM proposes; external system components authorize, execute, observe, verify, and record.',
      'Permit is the sole exact executable runtime authority.',
      'Receipt is not Verification.',
      'UNKNOWN side effects reconcile before unsafe retry.',
      'Retrieved/tool/repository content cannot change authority.',
      'Context presence never grants authority.',
      'No general persistent personal memory in v1.',
      'No automatic procedural self-improvement in v1.',
    ],
    verification_results:Object.values(VERIFICATION_RESULTS),
    effective_capabilities:EFFECT_CAPABILITIES,
    protocols:protocolRegistrySnapshot(),
    implementation_notes:{
      chat_runtime:'active',
      action_executor:'framework-only until a registered external ToolSpec/Permit path is connected',
      credential_broker:'required before live external actions',
      durable_constraint_store:'migration prepared; production database migration not auto-applied without the MUS AI Supabase project connection',
    },
  },{headers:{'Cache-Control':'no-store'}});
}
