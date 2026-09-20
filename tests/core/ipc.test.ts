import {test,expect} from 'bun:test';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import os from 'node:os';
import path from 'node:path';
test('compiled IPC correlates concurrent requests and bounds admission in an empty store',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'h5p-ipc-test-'));
 const child=spawn(process.execPath,[fileURLToPath(new URL('../../dist/core/adapters/ipc.js',import.meta.url))],
  {stdio:['pipe','pipe','pipe'],windowsHide:true});
 try {
  const replies:Record<string,unknown>[]=[];let buffer='',errors='';
  child.stderr.on('data',chunk=>{errors+=chunk;});
  const done=new Promise<void>((resolve,reject)=>{
   child.on('error',reject);
   child.on('close',code=>code===0?resolve():reject(new Error(errors)));
  });
  child.stdout.on('data',chunk=>{
   buffer+=chunk;let index;
   while((index=buffer.indexOf('\n'))>=0) {
    replies.push(JSON.parse(buffer.slice(0,index)));buffer=buffer.slice(index+1);
    if(replies.length===24) child.stdin.end();
   }
  });
  for(let i=0;i<24;i++) child.stdin.write(JSON.stringify({id:String(i),request:{action:'catalog',data_dir:root}})+'\n');
  const timer=setTimeout(()=>child.kill(),10000);
  try {await done;} finally {clearTimeout(timer);}
  expect(replies).toHaveLength(24);
  expect(new Set(replies.map(reply=>reply.id)).size).toBe(24);
  expect(replies.some(reply=>reply.ok)).toBe(true);
  expect(replies.filter(reply=>!reply.ok).every(reply=>reply.code==='LIMIT_EXCEEDED')).toBe(true);
 } finally {child.kill();await rm(root,{recursive:true,force:true});}
},15000);
