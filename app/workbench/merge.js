'use client';

import {requiredChildPermissions} from '../../lib/aqlevon/child-permissions.js';

const ACTION=Object.freeze({web:'research',browser:'navigate',terminal:'run',files:'read',media:'read'});
const KNOWN_STATES=new Set(['CONFIGURED_OK','ADAPTER_SELFTEST_UNSUPPORTED','ADAPTER_REQUIRED','PERMISSION_DISABLED','OWNER_POLICY_DISABLED']);

export function mergeToolStates(serverSnapshot,localPermissions){
  const snapshot=serverSnapshot&&typeof serverSnapshot==='object'?serverSnapshot:{tools:[]};
  const permissions=localPermissions&&typeof localPermissions==='object'?localPermissions:{};
  const policy=permissions.owner_policy&&typeof permissions.owner_policy==='object'?permissions.owner_policy:{};
  const tools=(Array.isArray(snapshot.tools)?snapshot.tools:[]).map(tool=>{
    const required=requiredChildPermissions(tool.name,ACTION[tool.name]||'');
    const enabled=permissions.execution_enabled===true&&required.every(id=>permissions.grants?.[id]===true);
    let state='ADAPTER_REQUIRED';
    if(policy.external_network===false)state='OWNER_POLICY_DISABLED';
    else if(!enabled)state='PERMISSION_DISABLED';
    else if(KNOWN_STATES.has(tool.last_selftest?.state))state=tool.last_selftest.state;
    else if(tool.last_selftest?.state==='KEY_PRESENT')state='CONFIGURED_OK';
    else if(tool.configured===true)state='CONFIGURED_OK';
    return Object.freeze({...tool,permissions_needed:Object.freeze(required),state});
  });
  return Object.freeze({...snapshot,tools:Object.freeze(tools)});
}