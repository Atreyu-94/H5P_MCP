import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {Engine} from '../application/engine.js';
import type {CoreRequest,Native} from '../domain/types.js';
import {checkTree,limit} from '../domain/limits.js';
import {projectSemantics} from '../domain/contracts.js';
import {Resources,hash,canonical} from './resources.js';
import {base,operations,codes,examples,schema,valid,invalidInput,report,failure,diagnostic,verification} from './contracts.js';
const scopes:Record<string,string>={refresh_h5p_catalog:'catalog:refresh',install_h5p_library:'libraries:install',install_h5p_library_package:'libraries:install'};
export const aliases:Record<string,string>={list_h5p_activities:'search_h5p_types',get_h5p_activity_schema:'get_h5p_type_contract',create_h5p_activity:'prepare_h5p_activity',export_h5p:'export_h5p_activity',validate_h5p:'validate_h5p_package'};
async function resolved(filename:string):Promise<string> {
 const absolute=path.resolve(filename);
 try{return await fs.realpath(absolute);}catch(error:Native){
  if(error.code!=='ENOENT') throw error;
  const parent=path.dirname(absolute);if(parent===absolute) throw error;
  return path.join(await resolved(parent),path.basename(absolute));
 }
}
export class Service {
 engine=new Engine();
 resources=new Resources();
 readonly data=path.resolve(process.env.H5P_MCP_DATA_DIR||path.join(os.homedir(),'.h5p-mcp'));
 readonly exportDir=path.resolve(process.env.H5P_MCP_EXPORT_DIR||path.join(process.cwd(),'exports'));
 readonly immutable=process.env.H5P_MCP_IMMUTABLE==='1';
 readonly scopes=new Set((process.env.H5P_MCP_ADMIN_SCOPES||'').split(/\s+/).filter(Boolean));
 readonly roots:Record<string,string[]|undefined>={};
 readonly definitions:Record<string,string[]>={...operations.local,prepare_h5p_activity:['prepare_local_input','preparation_report']};
 async initialize() {
  if(!['0','1',undefined].includes(process.env.H5P_MCP_IMMUTABLE)) throw new Error('Invalid immutable policy');
  if([...this.scopes].some(s=>!['catalog:refresh','libraries:install'].includes(s))) throw new Error('Invalid administration scope');
  for(const kind of ['PACKAGE','EXPORT']) {
   const setting=process.env['H5P_MCP_'+kind+'_ROOTS'];
   if(setting===undefined) continue;
   const roots=JSON.parse(setting);
   if(!Array.isArray(roots)||roots.some(r=>typeof r!=='string'||!path.isAbsolute(r))) throw new Error('Invalid authorized roots');
   this.roots[kind]=await Promise.all(roots.map(r=>resolved(r)));
  }
  await this.resources.initialize();
  for(const [name,value] of Object.entries({schema:base,codes,profiles:operations})) {
   const uri='h5p-contract://v1/'+name;
   this.resources.texts.set(uri,{uri,name,mimeType:'application/json',text:JSON.stringify(value)});
  }
 }
 allowed(name:string) {return !scopes[name]||(!this.immutable&&this.scopes.has(scopes[name]));}
 tools() {
  const tools:Native[]=Object.entries(this.definitions).filter(([name])=>this.allowed(name)).map(([name,[input,output]])=>({
   name,description:name.replaceAll('_',' '),inputSchema:schema(input),
   outputSchema:output==='preparation_report'||output==='operation_report'?schema(output):{type:'object',anyOf:[schema(output),schema('error_report')]},
   annotations:{readOnlyHint:['search_h5p_types','get_h5p_type_contract','validate_h5p_package'].includes(name),destructiveHint:false,openWorldHint:!!scopes[name]}
  }));
  for(const [name,target] of Object.entries(aliases)) {
   const inputSchema=schema(this.definitions[target][0]);
   if(name==='list_h5p_activities') inputSchema.properties.refresh={type:'boolean',default:false};
   if(name==='get_h5p_activity_schema') inputSchema.properties.install_if_missing={type:'boolean',default:false};
   tools.push({name,description:'Legacy local compatibility: '+name,inputSchema});
  }
  return tools;
 }
 async authorize(filename:string,kind:string) {
  const real=await resolved(filename);
  const roots=this.roots[kind];
  if(roots&&!roots.some(root=>{const rel=path.relative(root,real);return !rel||(!rel.startsWith('..'+path.sep)&&rel!=='..'&&!path.isAbsolute(rel));})) throw failure('PERMISSION_DENIED');
  return real;
 }
 async run(action:CoreRequest['action'],args:Native,signal:AbortSignal):Promise<Native> {
  return this.engine.run({action,data_dir:this.data,...args},signal);
 }
 async dispatch(name:string,args:Native,signal:AbortSignal):Promise<Native> {
  if(!this.allowed(name)) throw failure('PERMISSION_DENIED');
  if(name==='search_h5p_types'||name==='refresh_h5p_catalog') return this.run('discover',{query:'',installed_only:false,offset:0,limit:20,...args,refresh:name==='refresh_h5p_catalog'},signal);
  if(name==='get_h5p_type_contract'||name==='install_h5p_library') {
   const raw=await this.run('schema',{...args,install_if_missing:name==='install_h5p_library'},signal);
   if(name==='install_h5p_library') return raw;
   return {contract_version:'1',format:'h5p-native-compact-v1',library:raw.library,patch_version:raw.patch_version,core:raw.core,
    ...projectSemantics(raw.semantics),examples:examples.filter((item:Native)=>item.library===raw.library&&item.patch_version===raw.patch_version&&item.semantics_sha256===hash(JSON.stringify(canonical(raw.semantics)))).map(({title,params,evidence}:Native)=>({title,params,evidence})),raw_schema:this.resources.snapshot(raw),
    'x-h5p':{verification:verification(),note:'Native semantics are authoritative; playback and grading require target testing.'}};
  }
  if(name==='install_h5p_library_package') {
   const filename=await this.authorize(args.path,'PACKAGE');
   return this.run('setup',{packages:[filename]},signal);
  }
  if(name==='prepare_h5p_activity') {
   const result=await this.run('prepare',{activity:{language:'en',license:'U',assets:{},...args}},signal);
   return {...report(result.ok?'preparation':'validation',result.ok,result.diagnostics,{structure:result.ok?'passed':'failed',semantics:result.ok?'passed':'failed'}),activity:result.ok?result.activity:null};
  }
  if(name==='validate_h5p_package') {
   const filename=await this.authorize(args.path,'PACKAGE');
   await this.run('validate',{path:filename},signal);
   return report('validation',true,[],{structure:'passed',importation:'passed'});
  }
  if(name==='export_h5p_activity') {
   await this.authorize(this.exportDir,'EXPORT');
   await fs.mkdir(this.exportDir,{recursive:true});
   const directory=await this.authorize(this.exportDir,'EXPORT');
   const filename=(args.output_name.replace(/[^A-Za-z0-9._-]/g,'_').replace(/^[._-]+|[._-]+$/g,'')||'export').replace(/\.h5p$/i,'')+'.h5p';
   const destination=path.join(directory,filename);
   const result=await this.run('export',{activity:{language:'en',license:'U',assets:{},...args.activity},path:destination},signal);
   const artifact=await this.resources.artifact(destination,{h5p:result.h5p_json,preparation:result.preparation_manifest},result.content_json);
   return {...report('export',true,[],{structure:'passed',semantics:'passed'}),artifact};
  }
  if(name==='export_h5p_batch') {
   if(args.activities.length>limit('BATCH',50)) throw failure('LIMIT_EXCEEDED');
   const results=[];
   for(const [index,activity] of args.activities.entries()) {
    signal.throwIfAborted();
    const output_name=(args.name_prefix||'activity')+'_'+String(index+1).padStart(3,'0');
    try {const item=await this.dispatch('export_h5p_activity',{activity,output_name},signal);results.push({ok:true,output_name,output_path:this.resources.artifacts.get(item.artifact.uri)!.filename});}
    catch(error) {results.push({ok:false,output_name,kind:'operational_error',diagnostics:[diagnostic(error)]});}
   }
   return {count:results.length,succeeded:results.filter(r=>r.ok).length,results};
  }
  throw failure('SCHEMA_VALIDATION_FAILED');
 }
 async call(name:string,args:Native,signal:AbortSignal=AbortSignal.timeout(limit('SECONDS',300)*1000)):Promise<Native> {
  if(Object.hasOwn(aliases,name)) return this.legacy(name,args,signal);
  const definition=this.definitions[name];
  let result:Native;
  try {
   checkTree(args);
   if(!definition) throw failure('SCHEMA_VALIDATION_FAILED');
   if(!valid(definition[0],args)) throw invalidInput(definition[0]);
   result=await this.dispatch(name,args,signal);
   if(!valid(definition[1],result)) throw failure('INTERNAL_ERROR');
   if(Buffer.byteLength(JSON.stringify(result))>limit('OUTPUT_BYTES',16777216)) throw failure('LIMIT_EXCEEDED');
  } catch(error:Native) {
   const code=['TimeoutError','AbortError'].includes(error.name)?'BACKEND_TIMEOUT':error.code==='EEXIST'?'OUTPUT_ALREADY_EXISTS':error.code==='ENOENT'?'ASSET_NOT_FOUND':['EACCES','EPERM'].includes(error.code)?'PERMISSION_DENIED':error.code;
   const item=diagnostic({...error,code});
   const validation=['SCHEMA_VALIDATION_FAILED','LIBRARY_NOT_INSTALLED','LIBRARY_VERSION_MISMATCH','UNSAFE_ARCHIVE','STALE_PREPARATION','ASSET_NOT_FOUND','MIME_MISMATCH'].includes(item.code);
   result=report(validation?'validation':'operational_error',false,[item]);
   if(name==='prepare_h5p_activity') result.activity=null;
  }
  const content:Native[]=[{type:'text',text:JSON.stringify(result)}];
  if(result.artifact) content.push({type:'resource_link',uri:result.artifact.uri,name:'H5P package',mimeType:'application/zip',size:result.artifact.size});
  return {content,structuredContent:result,isError:result.kind==='operational_error'};
 }
 async legacy(name:string,args:Native,signal:AbortSignal):Promise<Native> {
  const target=aliases[name],input={...args};
  const checked={...input};delete checked.refresh;delete checked.install_if_missing;
  if(!valid(this.definitions[target][0],checked)) return this.call(target,checked,signal);
  for(const flag of ['refresh','install_if_missing']) if(flag in input&&typeof input[flag]!=='boolean') return this.call(target,{invalid:true},signal);
  let mapped=target;
  if(name==='list_h5p_activities') {
   if(input.refresh) {
    if(!this.allowed('refresh_h5p_catalog')) return this.call('refresh_h5p_catalog',{},signal);
    const refreshed=await this.call('refresh_h5p_catalog',{},signal);
    if(refreshed.structuredContent.ok===false) return refreshed;
   }
   delete input.refresh;
  }
  if(name==='get_h5p_activity_schema') {
   if(input.install_if_missing) mapped='install_h5p_library';
   delete input.install_if_missing;
  }
  const response=await this.call(mapped,input,signal),result=response.structuredContent;
  if(result.ok===false) return response;
  let legacy:Native=result;
  if(name==='get_h5p_activity_schema'&&mapped===target) legacy=JSON.parse((await this.resources.read(result.raw_schema.uri)).contents[0].text);
  if(name==='create_h5p_activity') legacy={...result,errors:[],warnings:[]};
  if(name==='export_h5p') {
   const entry=this.resources.artifacts.get(result.artifact.uri)!;
   legacy={output_path:entry.filename,h5p_json:result.artifact.manifest.h5p,content_json:entry.content,verification:result.verification};
  }
  if(name==='validate_h5p') legacy={ok:true,errors:[],warnings:[],verification:result.verification};
  return {content:[{type:'text',text:JSON.stringify(legacy)}],structuredContent:legacy,isError:false};
 }
 close(){return this.engine.close();}
}
