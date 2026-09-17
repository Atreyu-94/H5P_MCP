// JSON on stdin/stdout; diagnostics on stderr. This is not an HTTP service.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { finished } = require('node:stream/promises');
const { createRequire } = require('node:module');
const load = createRequire(path.join(process.env.H5P_MCP_LUMI_RUNTIME || __dirname, 'package.json'));
const { H5PEditor, H5PConfig, fsImplementations: stores } = load('@lumieducation/h5p-server');
const TYPES = ['H5P.MultiChoice', 'H5P.TrueFalse', 'H5P.Blanks', 'H5P.QuestionSet'];
const user = { id: 'local-author', name: 'Local author', email: '', type: 'local' };

async function editorAt(root, libraries) {
  await fsp.mkdir(root, { recursive: true });
  await fsp.mkdir(libraries, { recursive: true });
  for (const name of ['cache.json', 'config.json']) {
    try { await fsp.writeFile(path.join(root, name), '{}', { flag: 'wx' }); }
    catch (error) { if (error.code !== 'EEXIST') throw error; }
  }
  const cache = new stores.JsonStorage(path.join(root, 'cache.json'));
  const config = new H5PConfig(new stores.JsonStorage(path.join(root, 'config.json')));
  await config.load();
  config.sendUsageStatistics = false;
  return new H5PEditor(cache, config, new stores.FileLibraryStorage(libraries),
    new stores.FileContentStorage(path.join(root, 'content')),
    new stores.DirectoryTemporaryFileStorage(path.join(root, 'temporary')));
}

async function catalog(editor) {
  const installed = await editor.libraryManager.listInstalledLibraries();
  const result = {};
  for (const name of TYPES) {
    const versions = installed[name] || [];
    versions.sort((a, b) => b.majorVersion - a.majorVersion || b.minorVersion - a.minorVersion);
    if (!versions.length) throw new Error(`Missing ${name}. Run h5p-mcp --setup-lumi.`);
    const v = versions[0];
    result[name] = `${name} ${v.majorVersion}.${v.minorVersion}`;
  }
  return result;
}

async function main(request) {
  if (!request.data_dir || !path.isAbsolute(request.data_dir)) throw new Error('An absolute data_dir is required');
  const libraries = path.join(request.data_dir, 'libraries');
  if (request.action === 'setup') {
    const editor = await editorAt(request.data_dir, libraries);
    if (request.packages?.length) {
      for (const filename of request.packages) await editor.packageImporter.installLibrariesFromPackage(filename);
    } else {
      if (!await editor.contentTypeCache.forceUpdate()) throw new Error('H5P Hub catalog could not be downloaded');
      for (const name of TYPES) await editor.installLibraryFromHub(name, user);
    }
    return { libraries: await catalog(editor), core: editor.config.h5pVersion };
  }
  const job = await fsp.mkdtemp(path.join(os.tmpdir(), 'h5p-lumi-'));
  try {
    // Validation always starts with EMPTY library storage. Installed libraries
    // must not conceal a broken or content-only export.
    const editor = await editorAt(job, request.action === 'validate' ? path.join(job, 'libraries') : libraries);
    if (request.action === 'catalog') return { libraries: await catalog(editor), core: editor.config.h5pVersion };
    if (request.action === 'validate') {
      const imported = await editor.packageImporter.addPackageLibrariesAndTemporaryFiles(request.path, user);
      return { ok: true, errors: [], warnings: [], engine: 'Lumi', libraries: imported.installedLibraries.length };
    }
    if (request.action !== 'export') throw new Error('Unknown action');
    const available = await catalog(editor);
    const mainLibrary = available[request.main_library];
    if (!mainLibrary) throw new Error('Unsupported main library');
    const params = request.content;
    if (request.main_library === 'H5P.QuestionSet') {
      for (const question of params.questions) {
        const name = question.library.split(' ')[0];
        if (!available[name]) throw new Error(`Unsupported child library ${name}`);
        question.library = available[name];
      }
    }
    const metadata = { title: request.title, language: 'en', license: 'U', embedTypes: ['div'], mainLibrary: request.main_library };
    const id = await editor.saveOrUpdateContent(undefined, params, metadata, mainLibrary, user);
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
    const saved = await editor.getContent(id, user);
    return { h5p_json: saved.h5p, content_json: saved.params.params };
  } finally {
    await fsp.rm(job, { recursive: true, force: true });
  }
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
  try { process.stdout.write(JSON.stringify(await main(JSON.parse(input)))); }
  catch (error) {
    process.stderr.write(`${error.stack || error}\n`);
    process.stdout.write(JSON.stringify({ ok: false, errors: [error.message], details: error.details || error.errors }));
    process.exitCode = 1;
  }
});
