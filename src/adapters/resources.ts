import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash,randomBytes} from 'node:crypto';
import {repositoryRoot} from '../infrastructure/runtime.js';
import {readBounded} from '../infrastructure/media.js';
import {failure} from './contracts.js';
import type {Native} from '../domain/types.js';
export const hash=(bytes:Buffer|string)=>createHash('sha256').update(bytes).digest('hex');
export const skillURI='skill://h5p-authoring/SKILL.md';
export const extensionID='io.modelcontextprotocol/skills';
export class Resources {
 texts=new Map<string,{uri:string,name:string,mimeType:string,text:string}>();
 artifacts=new Map<string,{filename:string,size:number,sha256:string,content:Native}>();
 snapshots:string[]=[];
 skill:Native;
 async initialize() {
  const root=path.join(repositoryRoot,'h5p_mcp/skills/h5p-authoring');
  const names:string[]=JSON.parse(await fs.readFile(path.join(root,'resources.json'),'utf8'));
  const resources=[];
  for(const name of names) {
   if(!/^(?:SKILL\.md|references\/[a-z-]+\.md|examples\/[a-z-]+\.json)$/.test(name)) throw new Error('Invalid packaged skill resource');
   const raw=await readBounded(path.join(root,name),262144),uri='skill://h5p-authoring/'+name;
   this.texts.set(uri,{uri,name,mimeType:name.endsWith('.json')?'application/json':'text/markdown',text:raw.toString('utf8')});
   resources.push({uri,digest:'sha256:'+hash(raw),size:raw.length});
  }
  const text=this.texts.get(skillURI)!.text;
  this.skill={uri:skillURI,frontmatter:{name:'h5p-authoring',description:text.match(/^description: (.+)$/m)![1],license:'Apache-2.0'},resources};
 }
 snapshot(value:Native) {
  const text=JSON.stringify(value);
  if(Buffer.byteLength(text)>2097152) throw failure('LIMIT_EXCEEDED');
  const sha256=hash(text),uri='h5p-schema://snapshot/'+sha256;
  if(!this.texts.has(uri)) {
   while(this.snapshots.length>=8) this.texts.delete(this.snapshots.shift()!);
   this.snapshots.push(uri);
   this.texts.set(uri,{uri,name:'Native schema',mimeType:'application/json',text});
  }
  return {uri,sha256,mime_type:'application/json',size:Buffer.byteLength(text),lifetime:'process lifetime; bounded cache'};
 }
 async artifact(filename:string,manifest:Native,content:Native=null) {
  const bytes=await readBounded(filename,16777216),uri='h5p-artifact://package/'+randomBytes(16).toString('hex');
  const entry={filename,size:bytes.length,sha256:hash(bytes),content};
  if(this.artifacts.size>=128) this.artifacts.delete(this.artifacts.keys().next().value!);
  this.artifacts.set(uri,entry);
  return {uri,mime_type:'application/zip',size:entry.size,sha256:entry.sha256,manifest};
 }
 async read(uri:string):Promise<Native> {
  const text=this.texts.get(uri);
  if(text) return {contents:[{uri,mimeType:text.mimeType,text:text.text}]};
  const entry=this.artifacts.get(uri);
  if(!entry) throw failure('PERMISSION_DENIED');
  const bytes=await readBounded(entry.filename,16777216);
  if(bytes.length!==entry.size||hash(bytes)!==entry.sha256) throw failure('STALE_PREPARATION');
  return {contents:[{uri,mimeType:'application/zip',blob:bytes.toString('base64')}]};
 }
}
