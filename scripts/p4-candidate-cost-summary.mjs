#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {
  buildVerifiedCandidateCostSummary,verifyComputeCostReceipt,verifyVerifiedCandidateCostSummary,
} from '../lib/aqlevon/compute-cost-orchestrator.js';

function die(message,code=2){console.error(JSON.stringify({event:'p4_candidate_cost_error',error:message}));process.exit(code)}
function readJson(file){try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}}
const opts={candidate:null,worker05:null,manager:null,costReceipts:[],out:null};
const argv=process.argv.slice(2);
for(let i=0;i<argv.length;i++){
  const a=argv[i],v=()=>argv[++i];
  if(a==='--candidate-manifest-sha')opts.candidate=v();
  else if(a==='--worker05-evaluation-receipt-sha')opts.worker05=v();
  else if(a==='--manager-acceptance-receipt-sha')opts.manager=v();
  else if(a==='--cost-receipt')opts.costReceipts.push(v());
  else if(a==='--out')opts.out=v();
  else die(`unknown_arg:${a}`);
}
if(!opts.out||!opts.costReceipts.length)die('out_and_cost_receipts_required');
const receipts=opts.costReceipts.map(file=>{
  const r=readJson(file);if(!r)die(`cost_receipt_json:${file}`);
  const check=verifyComputeCostReceipt(r);if(!check.ok)die(`cost_receipt_invalid:${check.reasons.join(',')}`);
  return r;
});
const summary=buildVerifiedCandidateCostSummary({
  candidateArtifactManifestSha256:opts.candidate,
  worker05EvaluationReceiptSha256:opts.worker05,
  managerAcceptanceReceiptSha256:opts.manager,
  costReceipts:receipts,
});
const check=verifyVerifiedCandidateCostSummary(summary);if(!check.ok)die(`internal_summary_invalid:${check.reasons.join(',')}`,4);
fs.mkdirSync(path.dirname(opts.out),{recursive:true});
fs.writeFileSync(opts.out,JSON.stringify(summary,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify({event:'p4_verified_candidate_cost_written',summary_sha256:summary.summary_sha256,cost_basis:summary.cost_basis,estimated_total_cost_usd:summary.estimated_total_cost_usd,actual_total_cost_usd:summary.actual_total_cost_usd,out:opts.out}));
