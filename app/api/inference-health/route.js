import { NextResponse } from 'next/server';
import { checkSelfHostedHealth } from '../../../lib/aqlevon/providers.js';

export async function GET(){
  const selfHosted=await checkSelfHostedHealth({}, {timeoutMs:5000});
  const ready=selfHosted?.ok===true;
  return NextResponse.json({
    providers:{self_hosted:selfHosted},
    runtime_mode:'self_hosted_only',
    sovereign_runtime:true,
    inference_target:'aqlevon-engine',
    external_provider_routing:false,
    inference_ready:ready,
    primary_error_class:ready?null:(selfHosted?.error_class||'ENV_MISSING'),
  },{headers:{'Cache-Control':'no-store'}});
}
