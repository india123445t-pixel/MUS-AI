'use client';

import {normalizeChildMemory,selectChildMemories} from '../../../lib/aqlevon/child-memory.js';

const DB_NAME='aqlevon-child-memory-v1';
const STORE='memories';
const VERSION=1;

function openDb(){
  return new Promise((resolve,reject)=>{
    if(typeof indexedDB==='undefined')return reject(new Error('INDEXEDDB_UNAVAILABLE'));
    const req=indexedDB.open(DB_NAME,VERSION);
    req.onupgradeneeded=()=>{
      const db=req.result;
      if(!db.objectStoreNames.contains(STORE)){
        const store=db.createObjectStore(STORE,{keyPath:'id'});
        store.createIndex('kind','kind',{unique:false});
        store.createIndex('topic','topic',{unique:false});
        store.createIndex('created_at','created_at',{unique:false});
        store.createIndex('active','active',{unique:false});
      }
    };
    req.onsuccess=()=>resolve(req.result);
    req.onerror=()=>reject(req.error||new Error('INDEXEDDB_OPEN_FAILED'));
  });
}

function waitTx(tx){
  return new Promise((resolve,reject)=>{
    tx.oncomplete=()=>resolve();
    tx.onerror=()=>reject(tx.error);
    tx.onabort=()=>reject(tx.error||new Error('INDEXEDDB_ABORTED'));
  });
}

export async function putChildMemory(row){
  const now=new Date().toISOString();
  const item=normalizeChildMemory({...row,id:row.id||crypto.randomUUID(),created_at:row.created_at||now,updated_at:now});
  const db=await openDb();
  const tx=db.transaction(STORE,'readwrite');
  tx.objectStore(STORE).put(item);
  await waitTx(tx);
  db.close();
  return item;
}

export async function deleteChildMemory(id){
  const db=await openDb();
  const tx=db.transaction(STORE,'readwrite');
  tx.objectStore(STORE).delete(String(id));
  await waitTx(tx);
  db.close();
}

export async function listChildMemories({limit=5000}={}){
  const db=await openDb();
  const tx=db.transaction(STORE,'readonly');
  const store=tx.objectStore(STORE);
  const out=[];
  await new Promise((resolve,reject)=>{
    const req=store.openCursor();
    req.onsuccess=()=>{
      const cursor=req.result;
      if(!cursor||out.length>=limit)return resolve();
      out.push(cursor.value);
      cursor.continue();
    };
    req.onerror=()=>reject(req.error);
  });
  db.close();
  return out;
}

export async function searchChildMemories(query,{limit=24,scanLimit=5000}={}){
  const rows=await listChildMemories({limit:scanLimit});
  return selectChildMemories(rows,query,{limit});
}

export async function childMemoryStats(){
  const rows=await listChildMemories({limit:50000});
  const byKind={};
  for(const row of rows)byKind[row.kind]=(byKind[row.kind]||0)+1;
  return {count:rows.length,by_kind:byKind,db:DB_NAME,scope:'child-lab-only'};
}

export async function exportChildMemories(){
  const rows=await listChildMemories({limit:50000});
  return {schema:'AQLEVON_CHILD_MEMORY_EXPORT_V1',created_at:new Date().toISOString(),scope:'child-lab-only',memories:rows};
}

export async function importChildMemories(payload){
  if(payload?.schema!=='AQLEVON_CHILD_MEMORY_EXPORT_V1'||!Array.isArray(payload.memories))throw new Error('MEMORY_EXPORT_INVALID');
  let count=0;
  for(const row of payload.memories){await putChildMemory({...row,id:row.id||crypto.randomUUID()});count++}
  return count;
}
