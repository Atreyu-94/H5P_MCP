import {Server,ProtocolError} from '@modelcontextprotocol/server';
import {serveStdio,StdioServerTransport} from '@modelcontextprotocol/server/stdio';
import {Service,aliases} from './service.js';
import {extensionID,skillURI} from './resources.js';
import {limit} from '../domain/limits.js';
import type {Native} from '../domain/types.js';
const params={'~standard':{version:1 as const,vendor:'h5p',validate(value:unknown){return value&&typeof value==='object'?{value}:{issues:[{message:'Expected object'}]};}}};
export async function stdio() {
 const service=new Service();await service.initialize();
 const shutdown=new AbortController(),pending=new Set<Promise<unknown>>();
 const server=new Server({name:'h5p-mcp-core',version:'0.1.0'},{capabilities:{tools:{},resources:{},extensions:{[extensionID]:{}}}});
 server.setRequestHandler('tools/list',async request=>{
  if(request.params?.cursor!==undefined) throw new ProtocolError(-32602,'Unknown tools cursor');
  return {tools:service.tools()};
 });
 server.setRequestHandler('tools/call',async(request,ctx)=>{
  if(!Object.hasOwn(service.definitions,request.params.name)&&!Object.hasOwn(aliases,request.params.name)) throw new ProtocolError(-32602,'Unknown tool');
  const signal=AbortSignal.any([ctx.mcpReq.signal,shutdown.signal,AbortSignal.timeout(limit('SECONDS',300)*1000)]);
  const job=service.call(request.params.name,request.params.arguments||{},signal);
  pending.add(job);
  try{return await job;}finally{pending.delete(job);}
 });
 server.setRequestHandler('resources/list',async request=>{
  if(request.params?.cursor!==undefined) throw new ProtocolError(-32602,'Unknown resources cursor');
  return {resources:[...service.resources.texts.values()].map(({uri,name,mimeType})=>({uri,name,mimeType}))};
 });
 server.setRequestHandler('resources/read',async request=>{
  try{return await service.readResource(request.params.uri);}
  catch{throw new ProtocolError(-32602,'Unknown or unavailable resource');}
 });
 const complete=(payload:Native)=>({resultType:'complete',ttlMs:300000,cacheScope:'public',...payload});
 server.setRequestHandler('skills/list',{params},async(value:Native)=>{
  if(value.cursor!==undefined||Object.keys(value).some(k=>!['cursor','_meta'].includes(k))) throw new ProtocolError(-32602,'Unknown skills cursor or parameter');
  return complete({skills:[service.resources.skill]});
 });
 server.setRequestHandler('skills/get',{params},async(value:Native)=>{
  if(value.uri!==skillURI||Object.keys(value).some(k=>!['uri','_meta'].includes(k))) throw new ProtocolError(-32602,'Unknown skill URI or parameter');
  return complete({skill:service.resources.skill});
 });
 const handle=serveStdio(()=>server,{transport:new StdioServerTransport(process.stdin,process.stdout,{maxBufferSize:limit('INPUT_BYTES',16777216)}),onerror:()=>console.error('MCP transport error')});
 let closing:Promise<void>|undefined;
 const close=()=>closing??=Promise.resolve().then(async()=>{shutdown.abort();await handle.close();await Promise.allSettled(pending);await service.close();});
 server.onclose=()=>{void close();};
 process.stdin.once('end',()=>{void close();});
 process.once('SIGINT',()=>{void close();});
 process.once('SIGTERM',()=>{void close();});
}
