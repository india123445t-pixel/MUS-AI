import test from 'node:test';
import assert from 'node:assert/strict';
import {searchWeb} from '../lib/aqlevon/web-research.js';

test('web research fails closed without a key',async()=>{
  const oldA=process.env.AQLEVON_WEB_SEARCH_KEY;
  const oldB=process.env.AQLEVON_CHILD_WEB_SEARCH_KEY;
  const oldC=process.env.JINA_API_KEY;
  try{
    delete process.env.AQLEVON_WEB_SEARCH_KEY;
    delete process.env.AQLEVON_CHILD_WEB_SEARCH_KEY;
    delete process.env.JINA_API_KEY;
    const r=await searchWeb('test');
    assert.equal(r.ok,false);
    assert.equal(r.error_class,'SEARCH_KEY_MISSING');
  }finally{
    if(oldA===undefined)delete process.env.AQLEVON_WEB_SEARCH_KEY;else process.env.AQLEVON_WEB_SEARCH_KEY=oldA;
    if(oldB===undefined)delete process.env.AQLEVON_CHILD_WEB_SEARCH_KEY;else process.env.AQLEVON_CHILD_WEB_SEARCH_KEY=oldB;
    if(oldC===undefined)delete process.env.JINA_API_KEY;else process.env.JINA_API_KEY=oldC;
  }
});

test('web research returns bounded evidence and never exposes the key',async()=>{
  const old=process.env.AQLEVON_WEB_SEARCH_KEY;
  process.env.AQLEVON_WEB_SEARCH_KEY='jina_test_secret';
  let seen=null;
  try{
    const r=await searchWeb('latest AQLEVON news',{fetchImpl:async(url,init)=>{
      seen={url:String(url),authorization:init?.headers?.Authorization};
      return {ok:true,status:200,async json(){return {data:[
        {title:'A',url:'https://example.com/a',content:'alpha'},
        {title:'B',url:'https://example.com/b',content:'beta'},
        {title:'C',url:'https://example.com/c',content:'gamma'},
        {title:'D',url:'https://example.com/d',content:'delta'}
      ]}}};
    },depth:'quick'});
    assert.equal(r.ok,true);
    assert.equal(r.sources.length,3);
    assert.match(seen.url,/^https:\/\/s\.jina\.ai\/\?q=/);
    assert.equal(seen.authorization,'Bearer jina_test_secret');
    assert.match(r.context,/WEB SEARCH EVIDENCE/);
    assert.equal(JSON.stringify(r).includes('jina_test_secret'),false);
  }finally{
    if(old===undefined)delete process.env.AQLEVON_WEB_SEARCH_KEY;else process.env.AQLEVON_WEB_SEARCH_KEY=old;
  }
});
