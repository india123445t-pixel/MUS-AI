import {NextResponse} from 'next/server';
import {checkSelfHostedHealth,getSelfHostedRuntimeDescriptor} from '../../../../lib/kite/providers.js';

export const dynamic='force-dynamic';

export async function GET(){
  const settings={runtime_mode:'self_hosted_only'};
  const descriptor=getSelfHostedRuntimeDescriptor(settings);
  const health=await checkSelfHostedHealth(settings);
  return NextResponse.json({
    runtime:'sovereign-self-hosted',
    configured:descriptor.configured,
    provider:descriptor.provider,
    model:descriptor.model,
    protocol:descriptor.protocol,
    credential_configured:descriptor.credential_configured,
    health,
  },{status:health.ok?200:503,headers:{'Cache-Control':'no-store'}});
}
