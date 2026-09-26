import {NextResponse} from 'next/server';
import {getWorkbenchSnapshot,describeAdapterSetup} from '../../../../lib/aqlevon/workbench.js';
import {redactSecrets} from '../../../../lib/aqlevon/security.js';

function safe(value){return Object.freeze(JSON.parse(redactSecrets(JSON.stringify(value))))}

export async function GET(){
  try{
    const snapshot=getWorkbenchSnapshot();
    const guides=Object.fromEntries(snapshot.tools.map(tool=>[tool.name,describeAdapterSetup(tool.name)]));
    return NextResponse.json(safe({...snapshot,guides}),{headers:{'Cache-Control':'no-store'}});
  }catch(error){
    return NextResponse.json({message:redactSecrets(error?.message||'WORKBENCH_STATUS_FAILED')},{status:500});
  }
}