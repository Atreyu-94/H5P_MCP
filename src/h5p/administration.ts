import type {Native} from '../domain/types.js';
import path from 'node:path';
import {editorAt} from './editor.js';
import {catalog} from './catalog.js';
export async function administer(request: Native) {
 const libraries=path.join(request.data_dir,'libraries');
    const editor = await editorAt(request.data_dir, libraries);
    if (request.packages?.length) {
      for (const filename of request.packages) await editor.packageImporter.installLibrariesFromPackage(filename);
    } else {
      if (!await editor.contentTypeCache.forceUpdate()) throw new Error('H5P Hub catalog could not be downloaded');
      // Activity installation is explicit through schema requests or local packages.
    }
    return { libraries: await catalog(editor), core: editor.config.h5pVersion };

}
