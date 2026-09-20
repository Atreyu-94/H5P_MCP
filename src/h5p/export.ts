import type {Native} from '../domain/types.js';
import fs from 'node:fs';
import {finished} from 'node:stream/promises';
import {prepareActivity} from '../application/authoring.js';
import {preparationManifest,sameManifest} from '../infrastructure/manifest.js';
import {attachMathDependency} from './math.js';
import {user} from './editor.js';
export async function exportActivity(editor: Native,request: Native,libraries: string,report: Native) {
    if (!report.ok) throw Object.assign(new Error(report.errors.join('\n')), {code:'INVALID_PARAMETER', details:report.diagnostics});
    const uploaded = await prepareActivity(editor, report.activity, user, true);
    if (!uploaded.ok) throw Object.assign(new Error(uploaded.errors.join('\n')), {code:'INVALID_PARAMETER', details:uploaded.diagnostics});
    const activity = uploaded.activity;
    const mainLibrary = activity.library;
    const params = activity.params;
    const metadata = { title: activity.title, language: activity.language, license: activity.license,
      embedTypes: ['div'], mainLibrary: mainLibrary.split(' ')[0] };
    const id = await editor.saveOrUpdateContent(undefined, params, metadata, mainLibrary, user);
    await attachMathDependency(editor, id, user);
    const output = fs.createWriteStream(request.path, { flags: 'wx' });
    const done = finished(output);
    // Attach immediately to avoid unhandled rejection if export fails first.
    done.catch(() => {});
    try {
      await editor.exportContent(id, output, user);
      await done;
    } catch (error) {
      output.destroy();
      await done.catch(() => {});
      throw error;
    }
    const finalManifest = await preparationManifest(editor, libraries, report.activity, report.mathematics);
    if (!sameManifest(report.activity.preparation, finalManifest)) throw Object.assign(new Error('Dependencies changed during export'), {code:'STALE_PREPARATION'});
    const saved = await editor.getContent(id, user);
    return { h5p_json: saved.h5p, content_json: saved.params.params, preparation_manifest:report.activity.preparation };
}
