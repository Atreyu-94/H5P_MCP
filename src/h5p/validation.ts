import type {Native} from '../domain/types.js';
import {load} from '../infrastructure/runtime.js';
import {user} from './editor.js';
export async function validate(editor: Native,filename: string) {
 const H5pError=load('@lumieducation/h5p-server/build/src/helpers/H5pError').default;
 const imported=await editor.packageImporter.addPackageLibrariesAndTemporaryFiles(filename,user).catch((error: Native)=>{
  if(error instanceof H5pError) error.code='SCHEMA_VALIDATION_FAILED';
  throw error;
 });
 return {ok:true,errors:[],warnings:[],engine:'Lumi',libraries:imported.installedLibraries.length};
}
