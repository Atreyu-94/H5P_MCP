import type {Native, Pointer} from '../domain/types.js';
// Contrast with the exact Lumi implementation that will save the activity.
// Never silently replace answer text or LaTeX with the sanitizer's result.
import {diagnostic, displayPath, pointer} from '../domain/diagnostics.js';
export async function auditLumiSemantics(editor: Native, report: Native, load: NodeRequire) {
  report.transformations = [];
  const fail=(path: Pointer,message: string,code: string)=>{
    report.ok=false;
    report.errors.push(`${displayPath(path)}: ${message}`);
    report.diagnostics.push(diagnostic(path,message,code));
  };
  const metadata=load('@lumieducation/h5p-server/build/src/schemas/save-metadata.json');
  for(const field of ['title','language','license']) {
    const value=report.activity[field];
    if(typeof value!=='string' || !new RegExp(metadata.properties[field].pattern).test(value))
      fail([field],'Not accepted by the pinned Lumi metadata schema','INVALID_METADATA');
  }
  try { new Intl.Locale(report.activity.language); }
  catch { fail(['language'],'Invalid supported BCP 47 language tag','INVALID_METADATA'); }
  if(!report.ok) return;
  const proposed=structuredClone(report.activity.params);
  const [machineName,version]=report.activity.library.split(' ');
  const [majorVersion,minorVersion]=version.split('.').map(Number);
  const Enforcer=load('@lumieducation/h5p-server/build/src/SemanticsEnforcer').default;
  await new Enforcer(editor.libraryManager).enforceSemanticStructure(proposed,{machineName,majorVersion,minorVersion});
  // Lumi's scanner may attach named properties to arrays; JSON serialization
  // discards them. Compare the content that will actually be persisted.
  const pending: Native[]=[{before:report.activity.params,after:JSON.parse(JSON.stringify(proposed)),path:['params']}];
  while(pending.length) {
    const {before,after,path}=pending.pop();
    if(before===after) continue;
    if(before && after && typeof before==='object' && typeof after==='object') {
      for(const key of new Set([...Object.keys(before),...Object.keys(after)]))
        pending.push({before:before[key],after:after[key],path:[...path,key]});
    } else {
      report.transformations.push({path:displayPath(path),pointer:pointer(path),before:before ?? null,after:after ?? null});
      fail(path,'Lumi would transform this value; review transformations and resubmit explicitly','LUMI_TRANSFORMATION_REQUIRED');
    }
  }
}
