import test from 'node:test';
import assert from 'node:assert/strict';
import {childWebResearch} from '../lib/aqlevon/child-web-research.js';

test('child web research fails closed without a search key',async()=>{
  const r=await childWebResearch('AQLEVON',{key:''});
  assert.equal(r.ok,false);
  assert.equal(r.error_class,'SEARCH_KEY_MISSING');
});

test('child web research returns bounded sources and a receipt',async()=>{
  let seenUrl='';
  let seenAuth='';
  const fetchImpl=async(url,opts={})=>{
    seenUrl=String(url);
    seenAuth=String(opts.headers?.Authorization||'');
    return {
      ok:true,
      status:200,
      async json(){
        return {data:[
          {title:'Source A',url:'https://example.com/a',content:'Useful fact A'},
          {title:'Source B',url:'https://example.com/b',content:'Useful fact B'}
        ]};
      }
    };
  };
  const r=await childWebResearch('learn a task',{key:'test-key',fetchImpl,timeoutMs:1000});
  assert.equal(r.ok,true);
  assert.match(seenUrl,/^https:\/\/s\.jina\.ai\/\?q=/);
  assert.equal(seenAuth,'Bearer test-key');
  assert.equal(r.output.results.length,2);
  assert.equal(r.evidence.length,2);
  assert.equal(r.receipt.provider,'jina-search');
  assert.equal(r.receipt.status,'SUCCESS');
  assert.ok(r.receipt.query_sha256);
});
