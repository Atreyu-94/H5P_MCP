import fs from 'node:fs/promises';
import type {Native} from '../domain/types.js';
/** Atomic no-replace fallback for local filesystems without hard links. */
export async function publishFile(source:string,destination:string,link=fs.link) {
 try {await link(source,destination);return;}
 catch(error) {if(!['EPERM','ENOTSUP','ENOSYS','EACCES'].includes((error as NodeJS.ErrnoException).code||'')) throw error;}
 const {dlopen,ptr}=await import('bun:ffi');
 const windows=process.platform==='win32',mac=process.platform==='darwin';
 const library=windows?'kernel32.dll':mac?'/usr/lib/libSystem.B.dylib':'libc.so.6';
 const operation=windows?'MoveFileExW':mac?'renamex_np':'renameat2';
 const symbols=windows?{MoveFileExW:{args:['ptr','ptr','u32'],returns:'i32'},GetLastError:{args:[],returns:'u32'}}:
  mac?{renamex_np:{args:['ptr','ptr','u32'],returns:'i32'}}:{renameat2:{args:['i32','ptr','i32','ptr','u32'],returns:'i32'}};
 const api=dlopen(library,symbols as unknown as Parameters<typeof dlopen>[1]);
 try {
  const encoding=windows?'utf16le':'utf8';
  const from=Buffer.from(source+'\0',encoding),to=Buffer.from(destination+'\0',encoding);
  const fn:Native=api.symbols[operation];
  const result=windows?fn(ptr(from),ptr(to),0):mac?fn(ptr(from),ptr(to),4):fn(-100,ptr(from),-100,ptr(to),1);
  if(windows?result===0:result!==0) {
   // Never retry with an overwriting rename or expose a partially copied file.
   const exists=await fs.lstat(destination).then(()=>true,()=>false);
   throw Object.assign(new Error('Atomic publication rejected'),{code:exists?'EEXIST':'ENOTSUP'});
  }
 }finally{api.close();}
}
