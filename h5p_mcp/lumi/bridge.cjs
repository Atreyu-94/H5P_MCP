// JSON on stdin/stdout; diagnostics on stderr. This is not an HTTP service.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { finished } = require('node:stream/promises');
const { createRequire } = require('node:module');
const load = createRequire(path.join(process.env.H5P_MCP_LUMI_RUNTIME || __dirname, 'package.json'));
const { H5PEditor, H5PConfig, fsImplementations: stores } = load('@lumieducation/h5p-server');
const { prepareActivity } = require('./authoring.cjs');
const { attachMathDependency } = require('./math.cjs');
const user = { id: 'local-author', name: 'Local author', email: '', type: 'local' };

class ExportLibraryStorage extends stores.FileLibraryStorage {
  // Lumi appends ALL installed addons, even ones already in the dependency
  // graph. Exports use explicit dependencies to avoid duplicates/cache leakage.
  async listAddons() { return []; }
}

async function editorAt(root, libraries, explicitDependencies = false) {
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
  const LibraryStorage = explicitDependencies ? ExportLibraryStorage : stores.FileLibraryStorage;
  return new H5PEditor(cache, config, new LibraryStorage(libraries),
    new stores.FileContentStorage(path.join(root, 'content')),
    new stores.DirectoryTemporaryFileStorage(path.join(root, 'temporary')));
}

async function catalog(editor) {
  const installed = await editor.libraryManager.listInstalledLibraries();
  const result = {};
  for (const name of Object.keys(installed)) {
    const versions = installed[name] || [];
    versions.sort((a, b) => b.majorVersion - a.majorVersion || b.minorVersion - a.minorVersion);
    if (!versions.length) continue;
    const v = versions[0];
    result[name] = `${name} ${v.majorVersion}.${v.minorVersion}`;
  }
  return result;
}

async function main(request) {
  if (!request.data_dir || !path.isAbsolute(request.data_dir)) throw new Error('An absolute data_dir is required');
  const libraries = path.join(request.data_dir, 'libraries');
  if (['discover', 'schema'].includes(request.action)) {
    const editor = await editorAt(request.data_dir, libraries);
    const manager = editor.libraryManager;
    let installed = await manager.listInstalledLibraries();
    const sortVersions = versions => [...versions].sort((a, b) =>
      b.majorVersion - a.majorVersion || b.minorVersion - a.minorVersion);
    const compatible = (major, minor) => major == null || minor == null ? null :
      Number(major) < editor.config.coreApiVersion.major ||
      (Number(major) === editor.config.coreApiVersion.major && Number(minor) <= editor.config.coreApiVersion.minor);
    if (request.action === 'discover') {
      if (request.refresh && !await editor.contentTypeCache.forceUpdate()) throw new Error('H5P Hub refresh failed; retry with refresh=false to use cached data');
      const hub = await editor.contentTypeCache.get() || [];
      const entries = new Map(hub.map(item => [item.machineName, {
        machine_name: item.machineName, title: item.title, summary: item.summary,
        hub_version: `${item.majorVersion}.${item.minorVersion}.${item.patchVersion}`,
        required_core: { major: item.h5pMajorVersion, minor: item.h5pMinorVersion },
        core_compatible: compatible(item.h5pMajorVersion, item.h5pMinorVersion),
        installed_versions: [], authoring_supported: compatible(item.h5pMajorVersion, item.h5pMinorVersion) !== false,
      }]));
      for (const [name, versions] of Object.entries(installed)) {
        const runnable = versions.filter(v => Number(v.runnable) === 1);
        if (!entries.has(name) && !runnable.length) continue;
        if (!entries.has(name)) entries.set(name, { machine_name: name, title: runnable[0].title,
          hub_version: null, core_compatible: null, authoring_supported: true });
        entries.get(name).installed_versions = sortVersions(versions).map(v => `${v.majorVersion}.${v.minorVersion}.${v.patchVersion}`);
      }
      const query = (request.query || '').toLowerCase();
      const all = [...entries.values()].filter(item =>
        (!request.installed_only || item.installed_versions.length) &&
        `${item.machine_name} ${item.title} ${item.summary || ''}`.toLowerCase().includes(query)
      ).sort((a, b) => a.machine_name.localeCompare(b.machine_name));
      return { core: editor.config.h5pVersion, last_updated: await editor.contentTypeCache.getLastUpdate() || null,
        total: all.length, offset: request.offset, activities: all.slice(request.offset, request.offset + request.limit),
        note: 'Hub compatibility is not Moodle verification. Generic authoring uses native schemas; support does not guarantee every editor widget or playback behavior.' };
    }
    const name = request.machine_name;
    if (typeof name !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(name)) throw new Error('Invalid library machine name');
    const select = () => sortVersions(installed[name] || []).find(v =>
      request.major_version == null || (Number(v.majorVersion) === request.major_version && Number(v.minorVersion) === request.minor_version));
    let version = select();
    if (!version && request.install_if_missing) {
      if (!await editor.contentTypeCache.forceUpdate()) throw new Error('H5P Hub refresh failed');
      const [entry] = await editor.contentTypeCache.get(name);
      if (!entry) throw new Error('Activity is not available in the H5P Hub');
      if (request.major_version != null && (Number(entry.majorVersion) !== request.major_version || Number(entry.minorVersion) !== request.minor_version)) {
        throw new Error('Requested version is not installed and is not the current Hub version');
      }
      await editor.installLibraryFromHub(name, user);
      installed = await manager.listInstalledLibraries();
      version = select();
    }
    if (!version) throw new Error('Library version is not installed. Use install_if_missing=true for an explicit Hub download, or install a local package with --setup-lumi --lumi-package.');
    const metadata = await manager.getLibrary(version);
    return { core: editor.config.h5pVersion, library: `${name} ${version.majorVersion}.${version.minorVersion}`,
      patch_version: metadata.patchVersion, metadata, semantics: await manager.getSemantics(version),
      authoring_supported: Number(metadata.runnable) === 1 && compatible(metadata.coreApi?.majorVersion, metadata.coreApi?.minorVersion) !== false,
      note: 'Native H5P semantics, not JSON Schema. Nested library options refer to separate schemas; query those exact versions. Use the exact library and native params with create_h5p_activity.' };
  }
  if (request.action === 'setup') {
    const editor = await editorAt(request.data_dir, libraries);
    if (request.packages?.length) {
      for (const filename of request.packages) await editor.packageImporter.installLibrariesFromPackage(filename);
    } else {
      if (!await editor.contentTypeCache.forceUpdate()) throw new Error('H5P Hub catalog could not be downloaded');
      // Activity installation is explicit through schema requests or local packages.
    }
    return { libraries: await catalog(editor), core: editor.config.h5pVersion };
  }
  const job = await fsp.mkdtemp(path.join(os.tmpdir(), 'h5p-lumi-'));
  try {
    // Validation always starts with EMPTY library storage. Installed libraries
    // must not conceal a broken or content-only export.
    const editor = await editorAt(job, request.action === 'validate' ? path.join(job, 'libraries') : libraries, request.action === 'export');
    if (request.action === 'catalog') return { libraries: await catalog(editor), core: editor.config.h5pVersion };
    if (request.action === 'validate') {
      const imported = await editor.packageImporter.addPackageLibrariesAndTemporaryFiles(request.path, user);
      return { ok: true, errors: [], warnings: [], engine: 'Lumi', libraries: imported.installedLibraries.length };
    }
    if (!['prepare', 'export'].includes(request.action)) throw new Error('Unknown action');
    const report = await prepareActivity(editor, request.activity, user);
    if (request.action === 'prepare') return report;
    if (!report.ok) throw new Error(report.errors.join('\n'));
    const uploaded = await prepareActivity(editor, report.activity, user, true);
    if (!uploaded.ok) throw new Error(uploaded.errors.join('\n'));
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
