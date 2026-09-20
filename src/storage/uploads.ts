import fs from 'node:fs/promises';
import path from 'node:path';
import {Objects,storageError} from './objects.js';
import {load} from '../infrastructure/runtime.js';
import {isolated} from '../infrastructure/worker.js';
export async function upload(store:Objects,kind:'asset'|'package',mime:string,input:AsyncIterable<Uint8Array>,ttl:number,callerSignal?:AbortSignal) {
 const allowed=new Set(['image/png','image/jpeg','image/gif','image/webp','image/bmp','image/tiff','image/avif','audio/mpeg','audio/wav','audio/ogg','audio/mp4','audio/webm','video/mp4','video/webm','video/ogg','application/pdf','text/vtt']);
 if(kind==='package'?mime!=='application/zip':!allowed.has(mime)) throw storageError('MIME_MISMATCH');
 return store.publish(kind,ttl,async(stage,_final,signal)=>{
  const file=await fs.open(path.join(stage,'payload'),'wx');let size=0;let header=Buffer.alloc(0);
  const iterator=input[Symbol.asyncIterator]();
  let abort:()=>void=()=>{};
  const cancelled=new Promise<never>((_resolve,reject)=>{abort=()=>reject(storageError('BACKEND_TIMEOUT'));signal.addEventListener('abort',abort,{once:true});});
  try {
   while(true) {
    const item=await Promise.race([iterator.next(),cancelled]);if(item.done)break;
    const chunk=Buffer.from(item.value);size+=chunk.length;
    if(size>Math.min(store.budgets.bytes,kind==='asset'?67108864:134217728)) throw storageError('LIMIT_EXCEEDED');
    if(header.length<4096)header=Buffer.concat([header,chunk.subarray(0,4096-header.length)]);
    await file.writeFile(chunk);signal.throwIfAborted();
   }
  }finally{signal.removeEventListener('abort',abort);void iterator.return?.().catch(()=>{});await file.close();}
  const types=load('magic-bytes.js').filetypeinfo(header).map((v:{mime:string})=>v.mime);
  const aliases:Record<string,string>={'audio/x-wav':'audio/wav','audio/vnd.wave':'audio/wav','application/ogg':'audio/ogg'};
  const containers:Record<string,string>={'audio/mp4':'video/mp4','audio/webm':'video/webm','video/ogg':'audio/ogg'};
  const canonical=(value:string)=>containers[aliases[value]||value]||aliases[value]||value;
  const valid=mime==='text/vtt'?/^(?:\uFEFF)?WEBVTT(?:[ \t]|\r?\n|$)/.test(header.toString('utf8')):
   types.some((type:string)=>canonical(type)===canonical(mime));
  if(!size||!valid) throw storageError('MIME_MISMATCH');
  if(kind==='package')await isolated({action:'inspect-archive',path:path.join(stage,'payload'),data_dir:stage},signal);
  return {mime};
 },{signal:callerSignal});
}
