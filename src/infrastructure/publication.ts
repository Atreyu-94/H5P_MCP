import fs from 'node:fs/promises';
import path from 'node:path';
import type {CoreRequest} from '../domain/types.js';
import {isolated} from './worker.js';
export async function publish(request:CoreRequest,signal:AbortSignal):Promise<unknown> {
 if(!request.path||!path.isAbsolute(request.path)) throw new Error('Absolute export path required');
 const destination=request.path;
 const stage=await fs.mkdtemp(path.join(path.dirname(destination),'.h5p-core-'));
 try {
  const source=path.join(stage,'activity.h5p');
  const result=await isolated({...request,path:source},signal);
  signal.throwIfAborted();
  // Portable atomic no-replace. Fail closed on filesystems without hard links;
  // the Python publication adapter retains its certified native fallback.
  await fs.link(source,destination);
  return result;
 } finally {await fs.rm(stage,{recursive:true,force:true});}
}
