import type {Native, Activity} from '../domain/types.js';
import {legacyRoot} from './runtime.js';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {readBounded} from './media.js';
import {limit} from '../domain/limits.js';
const hash = (data: Native) => createHash('sha256').update(data).digest('hex');
export async function preparationManifest(editor: Native, root: string, activity: Activity, mathematics: Native) {
  const libraries: Record<string, Native> = {};
  const visiting = new Set();
  let edges = 0;
  let total = 0, files = 0;
  async function digestFile(filename: string) {
    const data = await readBounded(filename, limit('ASSET_BYTES', 67108864));
    total += data.length;
    if (++files > limit('ZIP_MEMBERS', 20000) || total > limit('ZIP_BYTES', 536870912)) throw new Error('Manifest file budget exceeded');
    return hash(data);
  }
  async function add(name: string, depth = 0) {
    if (visiting.has(name)) throw new Error('Cyclic library dependency');
    if (depth > limit('DEPENDENCY_DEPTH',32)) throw new Error('Library dependency depth budget exceeded');
    if (libraries[name]) return;
    if (Object.keys(libraries).length >= limit('LIBRARIES',1000)) throw new Error('Library node budget exceeded');
    visiting.add(name);
    const [machineName, version] = name.split(' ');
    const [majorVersion, minorVersion] = version.split('.').map(Number);
    const meta = await editor.libraryManager.getLibrary({machineName, majorVersion, minorVersion});
    const entry = libraries[name] = {patch:meta.patchVersion, files:{} as Record<string,string>};
    const base = path.join(root, `${machineName}-${version}`);
    async function walk(dir: string, depth = 0) {
      if (depth > 32) throw new Error('Library path too deep');
      for (const file of (await fs.readdir(dir, {withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))) {
        const full = path.join(dir, file.name);
        if (file.isSymbolicLink()) throw new Error('Library symlinks are unsupported');
        if (file.isDirectory()) await walk(full, depth + 1);
        else entry.files[path.relative(base, full).split(path.sep).join('/')] = await digestFile(full);
      }
    }
    await walk(base);
    for (const dep of [...(meta.preloadedDependencies || []), ...(meta.dynamicDependencies || []), ...(meta.editorDependencies || [])]) {
      if (++edges > limit('DEPENDENCY_EDGES',5000)) throw new Error('Library edge budget exceeded');
      await add(`${dep.machineName} ${dep.majorVersion}.${dep.minorVersion}`, depth + 1);
    }
    visiting.delete(name);
  }
  await add(activity.library);
  const stack = [activity.params];
  while (stack.length) {
    const value = stack.pop();
    if (!value || typeof value !== 'object') continue;
    if (typeof value.library === 'string' && value.params) await add(value.library);
    stack.push(...Object.values(value));
  }
  if (mathematics.detected) await add('H5P.MathDisplay 1.0');
  const assets: Record<string,string> = {};
  for (const [id, file] of Object.entries(activity.assets || {})) assets[id] = await digestFile(file);
  const backend: Record<string,string> = {};
  for (const file of (await fs.readdir(legacyRoot)).filter(n=>n.endsWith('.cjs') || n === 'package-lock.json' || n === 'provenance.json').sort())
    backend[file] = hash(await fs.readFile(path.join(legacyRoot, file)));
  // Ported rules have their own provenance; legacy manifests cannot hide a core change.
  const coreRoot=fileURLToPath(new URL('../',import.meta.url));
  async function coreFiles(dir:string):Promise<void> {
    for(const entry of (await fs.readdir(dir,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))) {
      const full=path.join(dir,entry.name);
      if(entry.isDirectory()) await coreFiles(full);
      else if(entry.name.endsWith('.js')) backend['core/'+path.relative(coreRoot,full).split(path.sep).join('/')]=hash(await fs.readFile(full));
    }
  }
  await coreFiles(coreRoot);
  return {version:1, libraries, assets, backend};
}
export function sameManifest(a: Native,b: Native) {
  const canonical = (value: Native): Native => value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])])) : value;
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}
