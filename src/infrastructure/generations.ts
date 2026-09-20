import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';
import {limit} from '../domain/limits.js';
import {readBounded} from './media.js';
/** Shared with Python; never guess that another process' lock is stale. */
export async function exclusive<T>(root:string,signal:AbortSignal,work:()=>Promise<T>):Promise<T> {
 await fs.mkdir(root,{recursive:true});
 const lock=path.join(root,'.core-lock');
 while(true) {
  signal.throwIfAborted();
  try {await fs.mkdir(lock);break;} catch(error) {if((error as NodeJS.ErrnoException).code!=='EEXIST') throw error;}
  await delay(25,undefined,{signal});
 }
 try {signal.throwIfAborted();return await work();}
 finally {await fs.rmdir(lock);}
}
async function digestTree(root:string,signal?:AbortSignal):Promise<string> {
 const hash=createHash('sha256');let files=0,bytes=0;
 async function visit(dir:string,depth=0):Promise<void> {
  if(depth>32) throw new Error('Library path too deep');
  let entries;
  try {entries=await fs.readdir(dir,{withFileTypes:true});}
  catch(error) {if((error as NodeJS.ErrnoException).code==='ENOENT') return;throw error;}
  for(const entry of entries.sort((a,b)=>a.name.localeCompare(b.name))) {
   signal?.throwIfAborted();
   const full=path.join(dir,entry.name);
   if(entry.isSymbolicLink()) throw new Error('Library symlinks are unsupported');
   hash.update(path.relative(root,full).split(path.sep).join('/'));
   if(entry.isDirectory()) await visit(full,depth+1);
   else {
    if(++files>limit('ZIP_MEMBERS',20000)) throw new Error('Snapshot file budget exceeded');
    const stream=(await fs.open(full,'r'));
    try {
     const buffer=Buffer.alloc(65536);
     while(true) {
      signal?.throwIfAborted();
      const {bytesRead}=await stream.read(buffer);if(!bytesRead) break;
      bytes+=bytesRead;if(bytes>limit('ZIP_BYTES',536870912)) throw new Error('Snapshot byte budget exceeded');
      hash.update(buffer.subarray(0,bytesRead));
     }
    } finally {await stream.close();}
   }
  }
 }
 await visit(root);return hash.digest('hex');
}
export class Generations {
 private entries=new Map<string,{root:string;references:number}>();
 private base?:string;
 constructor(private maximum=4) {}
 /** Caller holds exclusive() while acquiring; snapshots never mutate afterward. */
 async acquire(source:string,signal?:AbortSignal):Promise<{root:string;release:()=>Promise<void>}> {
  signal?.throwIfAborted();
  const digest=await digestTree(path.join(source,'libraries'),signal);
  // Config/cache are part of the generation, not a mutable shared editor.
  const config:Record<string,Buffer>={};
  for(const name of ['cache.json','config.json']) {
   try {config[name]=await readBounded(path.join(source,name),limit('JSON_BYTES',16777216));}
   catch(error) {if((error as NodeJS.ErrnoException).code!=='ENOENT') throw error;config[name]=Buffer.from('{}');}
  }
  const key=createHash('sha256').update(digest).update(config['cache.json']).update(config['config.json']).digest('hex');
  let entry=this.entries.get(key);
  if(!entry) {
   while(this.entries.size>=this.maximum) {
    const unused=[...this.entries].find(([,value])=>value.references===0);
    if(!unused) throw Object.assign(new Error('Snapshot capacity exhausted'),{code:'LIMIT_EXCEEDED'});
    this.entries.delete(unused[0]);await fs.rm(unused[1].root,{recursive:true,force:true});
   }
   this.base ||= await fs.mkdtemp(path.join(os.tmpdir(),'h5p-generations-'));
   const destination=path.join(this.base,key);
   await fs.mkdir(destination);
   try {
    try {await fs.cp(path.join(source,'libraries'),path.join(destination,'libraries'),{recursive:true,errorOnExist:true,force:false,filter:()=>{signal?.throwIfAborted();return true;}});}
    catch(error) {if((error as NodeJS.ErrnoException).code!=='ENOENT') throw error;await fs.mkdir(path.join(destination,'libraries'),{recursive:true});}
    for(const [name,data] of Object.entries(config)) await fs.writeFile(path.join(destination,name),data,{flag:'wx'});
    if(await digestTree(path.join(source,'libraries'),signal)!==digest ||
       await digestTree(path.join(destination,'libraries'),signal)!==digest) throw new Error('Libraries changed during snapshot');
    entry={root:destination,references:0};this.entries.set(key,entry);
   } catch(error) {await fs.rm(destination,{recursive:true,force:true});throw error;}
  }
  entry.references++;
  const selected=entry;
  return {root:entry.root,release:async()=>{selected.references--;}};
 }
 async close(){if(this.base) await fs.rm(this.base,{recursive:true,force:true});this.entries.clear();}
}
