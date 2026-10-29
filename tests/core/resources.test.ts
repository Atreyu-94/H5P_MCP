import {test,expect} from 'bun:test';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {Resources,hash} from '../../src/adapters/resources.js';
import {Service} from '../../src/adapters/service.js';
import {configureLimits} from '../../src/domain/limits.js';
import type {CoreRequest,Native} from '../../src/domain/types.js';

test('published exports above 16 MiB register successfully and respect the configurable read limit',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'h5p-large-resource-'));
 const bytes=Buffer.alloc(16777217,65);
 // Exercise the service publication-to-resource boundary without coupling package size to compression.
 class ExportFixture extends Service {
  override readonly exportDir=root;
  override async run(_action:CoreRequest['action'],args:Native):Promise<Native>{
   await fs.writeFile(args.path,bytes,{flag:'wx'});
   return {h5p_json:{},preparation_manifest:{},content_json:{}};
  }
 }
 const service=new ExportFixture();
 try {
  configureLimits({});
  const result=await service.dispatch('export_h5p_activity',{activity:{},output_name:'large'},new AbortController().signal);
  expect(result.ok).toBe(true);
  expect(result.artifact.size).toBe(bytes.length);
  expect(result.artifact.sha256).toBe(hash(bytes));
  await expect(service.readResource(result.artifact.uri)).rejects.toMatchObject({code:'LIMIT_EXCEEDED'});
  expect((await fs.stat(path.join(root,'large.h5p'))).size).toBe(bytes.length);
  configureLimits({H5P_MCP_MAX_RESOURCE_BYTES:String(bytes.length)});
  expect(Buffer.from((await service.readResource(result.artifact.uri)).contents[0].blob,'base64')).toEqual(bytes);
  await expect(service.dispatch('export_h5p_activity',{activity:{},output_name:'large'},new AbortController().signal)).rejects.toMatchObject({code:'EEXIST'});
 }finally{configureLimits(process.env);await service.close();await fs.rm(root,{recursive:true,force:true});}
});

test('local and persistent resource reads share byte limits independently of tool output limits',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'h5p-resource-limits-'));
 const service=new Service(undefined,{data:path.join(root,'data'),store:path.join(root,'store')});
 try {
  const filename=path.join(root,'local.h5p');await fs.writeFile(filename,'AB');
  const local=await service.resources.artifact(filename,{});
  const vault=await service.vault();
  const stored=await vault.objects.publish('artifact',60000,async stage=>{await fs.writeFile(path.join(stage,'payload'),'AB');return {mime:'application/zip'};});
  const uris=[local.uri,'h5p-artifact://stored/'+stored.id];
  configureLimits({H5P_MCP_MAX_RESOURCE_BYTES:'1',H5P_MCP_MAX_OUTPUT_BYTES:'100'});
  for(const uri of uris)await expect(service.readResource(uri)).rejects.toMatchObject({code:'LIMIT_EXCEEDED'});
  configureLimits({H5P_MCP_MAX_RESOURCE_BYTES:'2',H5P_MCP_MAX_OUTPUT_BYTES:'1'});
  for(const uri of uris)expect(Buffer.from((await service.readResource(uri)).contents[0].blob,'base64').toString()).toBe('AB');
  await fs.writeFile(filename,'AC');
  await expect(service.readResource(local.uri)).rejects.toMatchObject({code:'STALE_PREPARATION'});
 }finally{configureLimits(process.env);await service.close();await fs.rm(root,{recursive:true,force:true});}
});

test('artifact registry honors configured retention without deleting exported files',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'h5p-resource-retention-'));
 try {
  configureLimits({H5P_MCP_MAX_ARTIFACTS:'1'});
  const resources=new Resources(),file=path.join(root,'package.h5p');await fs.writeFile(file,'AB');
  const first=await resources.artifact(file,{}),second=await resources.artifact(file,{});
  await expect(resources.read(first.uri)).rejects.toThrow('PERMISSION_DENIED');
  expect((await resources.read(second.uri)).contents).toHaveLength(1);
  expect(await fs.readFile(file,'utf8')).toBe('AB');
 }finally{configureLimits(process.env);await fs.rm(root,{recursive:true,force:true});}
});
