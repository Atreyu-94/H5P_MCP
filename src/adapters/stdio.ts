import {serveStdio,StdioServerTransport} from '@modelcontextprotocol/server/stdio';
import {Service} from './service.js';
import {mcp} from './mcp.js';
import {limit} from '../domain/limits.js';
export async function stdio() {
 const service=new Service();await service.initialize();
 const shutdown=new AbortController(),pending=new Set<Promise<unknown>>();
 const server=mcp(service,shutdown.signal,pending);
 const handle=serveStdio(()=>server,{transport:new StdioServerTransport(process.stdin,process.stdout,{maxBufferSize:limit('INPUT_BYTES',16777216)}),onerror:()=>console.error('MCP transport error')});
 let closing:Promise<void>|undefined;
 const close=()=>closing??=Promise.resolve().then(async()=>{shutdown.abort();await handle.close();await Promise.allSettled(pending);await service.close();});
 server.onclose=()=>{void close();};
 process.stdin.once('end',()=>{void close();});
 process.once('SIGINT',()=>{void close();});
 process.once('SIGTERM',()=>{void close();});
}
