// Assemble a private, reviewable distribution without modifying the source manifest.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const repo=fileURLToPath(new URL('../../',import.meta.url));
const stage=await fs.mkdtemp(path.join(os.tmpdir(),'h5p-pack-stage-'));
const manifest=JSON.parse(await fs.readFile(path.join(repo,'package.json'),'utf8'));
delete manifest.dependencies['@lumieducation/h5p-server'];
delete manifest.devDependencies;
delete manifest.scripts;
for(const folder of ['dist/core','h5p_mcp/contracts','h5p_mcp/skills','h5p_mcp/lumi']) {
 await fs.cp(path.join(repo,folder),path.join(stage,folder),{recursive:true,filter:source=>!source.includes('node_modules')&&!source.includes('__pycache__')&&!source.endsWith('.py')&&!/[\\/]adapters[\\/]ipc\.(?:js|d\.ts)$/.test(source)});
}
for(const entry of await fs.readdir(repo)) if(/^(LICENSE|NOTICE)/.test(entry)) await fs.copyFile(path.join(repo,entry),path.join(stage,entry));
await fs.writeFile(path.join(stage,'package.json'),JSON.stringify(manifest,null,2)+'\n');
// Pack follows the explicitly bundled dependency tree; no source-tree mutation.
await fs.symlink(path.join(repo,'node_modules'),path.join(stage,'node_modules'),process.platform==='win32'?'junction':'dir');
const destination=path.resolve(process.argv[2]||process.cwd());
await fs.mkdir(destination,{recursive:true});
const result=spawnSync(process.execPath,['pm','pack','--ignore-scripts','--destination',destination,'--quiet'],{cwd:stage,stdio:'inherit'});
if(result.status!==0) throw new Error('Package assembly failed');
console.error('Private package stage: '+stage);
