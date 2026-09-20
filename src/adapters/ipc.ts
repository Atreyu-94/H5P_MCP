/** Internal JSON-lines IPC, not the public MCP transport (F4). */
import {Engine} from '../application/engine.js';
import {limit} from '../domain/limits.js';
import type {CoreRequest,Native,Reply} from '../domain/types.js';
const engine=new Engine(), active=new Map<string,AbortController>();
const pending=new Set<Promise<void>>();
let writing=Promise.resolve();
function emit(reply:Reply):Promise<void> {
 let output=JSON.stringify(reply);
 if(Buffer.byteLength(output)>limit('OUTPUT_BYTES',33554432)) output=JSON.stringify({id:reply.id,ok:false,code:'OUTPUT_TOO_LARGE',errors:['Output budget exceeded']});
 const next=writing.then(()=>new Promise<void>((resolve,reject)=>{
  process.stdout.write(output+'\n',error=>error?reject(error):resolve());
 }));
 writing=next.catch(()=>{});
 return next;
}
async function dispatch(line:string) {
 const envelope=JSON.parse(line) as {id:string;request?:CoreRequest;cancel?:string};
 if(typeof envelope.cancel==='string'){active.get(envelope.cancel)?.abort();return;}
 if(typeof envelope.id!=='string'||!envelope.id||envelope.id.length>128||!envelope.request) throw new Error('Invalid IPC envelope');
 if(active.has(envelope.id)||active.size>=limit('WORKERS',2)+limit('QUEUE',8)) {
  await emit({id:envelope.id,ok:false,code:'LIMIT_EXCEEDED',errors:['Duplicate ID or capacity exceeded']});return;
 }
 const controller=new AbortController();active.set(envelope.id,controller);
 const timer=setTimeout(()=>controller.abort(),limit('SECONDS',300)*1000);
 const task=engine.run(envelope.request,controller.signal).then(result=>emit({id:envelope.id,ok:true,result}),
  (error:Native)=>emit({id:envelope.id,ok:false,code:controller.signal.aborted?'BACKEND_TIMEOUT':error.code||'BACKEND_ERROR',errors:[error.message],details:error.details}))
  .finally(()=>{clearTimeout(timer);active.delete(envelope.id);pending.delete(task);});
 pending.add(task);
}
let buffer=Buffer.alloc(0);
try {
 for await(const chunk of process.stdin) {
  buffer=Buffer.concat([buffer,chunk]);
  let index:number;
  while((index=buffer.indexOf(10))>=0) {
   if(index>limit('JSON_BYTES',16777216)) throw new Error('Input budget exceeded');
   const line=buffer.subarray(0,index).toString('utf8');buffer=buffer.subarray(index+1);
   if(line.trim()) await dispatch(line);
  }
  if(buffer.length>limit('JSON_BYTES',16777216)) throw new Error('Input budget exceeded');
 }
 if(buffer.length) throw new Error('Truncated IPC frame');
} catch(error) {process.stderr.write(String(error)+'\n');process.exitCode=1;}
finally {for(const controller of active.values()) controller.abort();await Promise.allSettled(pending);await writing;await engine.close();}
