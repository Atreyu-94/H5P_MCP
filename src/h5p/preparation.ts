import type {Native} from '../domain/types.js';
import {prepareActivity} from '../application/authoring.js';
import {auditLumiSemantics} from './compatibility.js';
import {preparationManifest,sameManifest} from '../infrastructure/manifest.js';
import {load} from '../infrastructure/runtime.js';
import {user} from './editor.js';
export async function prepare(editor: Native,request: Native,libraries: string) {
    const report = await prepareActivity(editor, request.activity, user);
    await auditLumiSemantics(editor, report, load);
    if (report.ok) {
      const manifest = await preparationManifest(editor, libraries, report.activity, report.mathematics);
      if (request.action === 'export' && request.activity.preparation && !sameManifest(request.activity.preparation, manifest))
        throw Object.assign(new Error('Preparation dependencies changed; prepare again'), {code:'STALE_PREPARATION'});
      report.activity.preparation = manifest;
    }
 return report;
}
