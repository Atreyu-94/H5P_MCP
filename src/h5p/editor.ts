import type {Native} from '../domain/types.js';
import fsp from 'node:fs/promises';
import path from 'node:path';
import {load,legacyRoot} from '../infrastructure/runtime.js';
import {createRequire} from 'node:module';
import {semanticsCache} from './schema-cache.js';
const {H5PEditor,H5PConfig,fsImplementations:stores}=load('@lumieducation/h5p-server');
createRequire(import.meta.url)(path.join(legacyRoot,'extraction.cjs')).installBoundedExtraction(load);
export const user={id:'local-author',name:'Local author',email:'',type:'local'};
export {stores};
class ExportLibraryStorage extends stores.FileLibraryStorage {
  // Lumi appends ALL installed addons, even ones already in the dependency
  // graph. Exports use explicit dependencies to avoid duplicates/cache leakage.
  async listAddons() { return []; }
}

export async function editorAt(root: string, libraries: string, explicitDependencies = false): Promise<Native> {
  await fsp.mkdir(root, { recursive: true });
  await fsp.mkdir(libraries, { recursive: true });
  for (const name of ['cache.json', 'config.json']) {
    try { await fsp.writeFile(path.join(root, name), '{}', { flag: 'wx' }); }
    catch (error: Native) { if (error.code !== 'EEXIST') throw error; }
  }
  const cache = new stores.JsonStorage(path.join(root, 'cache.json'));
  const config = new H5PConfig(new stores.JsonStorage(path.join(root, 'config.json')));
  await config.load();
  config.sendUsageStatistics = false;
  const LibraryStorage = explicitDependencies ? ExportLibraryStorage : stores.FileLibraryStorage;
  const editor = new H5PEditor(cache, config, new LibraryStorage(libraries),
    new stores.FileContentStorage(path.join(root, 'content')),
    new stores.DirectoryTemporaryFileStorage(path.join(root, 'temporary')));
  const original=editor.libraryManager.getSemantics.bind(editor.libraryManager);
  editor.libraryManager.getSemantics=async (version: Native)=>semanticsCache.get(libraries,await original(version));
  return editor;
}
