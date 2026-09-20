// JSON on stdin/stdout; diagnostics on stderr. This is not an HTTP service.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { finished } = require('node:stream/promises');
const { createRequire } = require('node:module');
const {createHash} = require('node:crypto');
const load = createRequire(path.join(process.env.H5P_MCP_LUMI_RUNTIME || __dirname, 'package.json'));
const { H5PEditor, H5PConfig, fsImplementations: stores } = load('@lumieducation/h5p-server');
require('./extraction.cjs').installBoundedExtraction(load);
const { prepareActivity } = require('./authoring.cjs');
const {preparationManifest, sameManifest} = require('./manifest.cjs');
const {limit} = require('./limits.cjs');
const {auditLumiSemantics} = require('./compatibility.cjs');
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
    // Lumi constructors create storage directories. Ordinary queries use an
    // ephemeral configuration/cache snapshot, leaving durable state untouched.
    const readonly = !request.refresh && !request.install_if_missing;
    const root = readonly ? await fsp.mkdtemp(path.join(os.tmpdir(), 'h5p-query-')) : request.data_dir;
    try {
    if (readonly) {
      for (const name of ['config.json', 'cache.json']) {
        try { await fsp.copyFile(path.join(request.data_dir,name),path.join(root,name)); }
        catch (error) { if (error.code !== 'ENOENT') throw error; }
      }
    }
    const libraryRoot = readonly && !fs.existsSync(libraries) ? path.join(root,'libraries') : libraries;
    const editor = await editorAt(root, libraryRoot);
    const manager = editor.libraryManager;
    let installed = await manager.listInstalledLibraries();
    const sortVersions = versions => [...versions].sort((a, b) =>
      b.majorVersion - a.majorVersion || b.minorVersion - a.minorVersion);
    const compatible = (major, minor) => major == null || minor == null ? null :
      Number(major) < editor.config.coreApiVersion.major ||
      (Number(major) === editor.config.coreApiVersion.major && Number(minor) <= editor.config.coreApiVersion.minor);
    if (request.action === 'discover') {
      if (request.refresh && !await editor.contentTypeCache.forceUpdate()) throw Object.assign(new Error('H5P Hub refresh failed; retry with refresh=false to use cached data'), {code:'HUB_UNAVAILABLE'});
      // ContentTypeCache.get() downloads on a cache miss. Discovery without an
      // explicit refresh must read storage directly, including an absent cache.
      const hub = await new stores.JsonStorage(path.join(root, 'cache.json')).load('contentTypeCache') || [];
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
      const page = all.slice(request.offset, request.offset + request.limit);
      let inspected = 0;
      for (const item of page) {
        item.evidence = [];
        for (const version of sortVersions(installed[item.machine_name] || [])) {
          if (++inspected > limit('LIBRARIES',1000)) throw Object.assign(new Error('Evidence budget exceeded'), {code:'INPUT_TOO_LARGE'});
          const metadata = await manager.getLibrary(version);
          const semantics = await manager.getSemantics(version);
          require('./limits.cjs').checkTree(semantics);
          const pending = [...semantics], unsupported = new Set();
          const types = new Set(['group','list','library','text','number','boolean','select','image','file','audio','video']);
          while (pending.length) {
            const field = pending.pop();
            if (!types.has(field.type)) unsupported.add(field.type);
            if (field.type === 'group') pending.push(...(field.fields || []));
            if (field.type === 'list' && field.field) pending.push(field.field);
          }
          const runnable = Number(metadata.runnable) === 1;
          const coreCompatible = compatible(metadata.coreApi?.majorVersion,metadata.coreApi?.minorVersion) !== false;
          item.evidence.push({library:`${item.machine_name} ${version.majorVersion}.${version.minorVersion}`,
            patch_version:metadata.patchVersion, checked_at:new Date().toISOString(),
            schema_sha256:createHash('sha256').update(JSON.stringify({metadata,semantics})).digest('hex'),
            digest_format:'UTF-8 JSON.stringify({metadata,semantics})',
            structurally_authorable:runnable && coreCompatible && !unsupported.size,
            checks:{runnable:runnable?'passed':'failed',core:coreCompatible?'passed':'failed',
              native_types:unsupported.size?'failed':'passed',preparation:'not_run',importation:'not_run',playback:'not_run',grading:'not_run'},
            unsupported_types:[...unsupported], source:'installed library metadata and semantics; nested dependencies and concrete params not verified'});
        }
        item.structurally_authorable = item.evidence.some(e => e.structurally_authorable);
        item.authoring_supported = item.structurally_authorable;
      }
      return { core: editor.config.h5pVersion, last_updated: await editor.contentTypeCache.getLastUpdate() || null,
        total: all.length, offset: request.offset, activities: page,
        note: 'Hub compatibility is not Moodle verification. Generic authoring uses native schemas; support does not guarantee every editor widget or playback behavior.' };
    }
    const name = request.machine_name;
    if (typeof name !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(name)) throw new Error('Invalid library machine name');
    const select = () => sortVersions(installed[name] || []).find(v =>
      request.major_version == null || (Number(v.majorVersion) === request.major_version && Number(v.minorVersion) === request.minor_version));
    let version = select();
    if (!version && request.install_if_missing) {
      if (!await editor.contentTypeCache.forceUpdate()) throw Object.assign(new Error('H5P Hub refresh failed'), {code:'HUB_UNAVAILABLE'});
      const [entry] = await editor.contentTypeCache.get(name);
      if (!entry) throw new Error('Activity is not available in the H5P Hub');
      if (request.major_version != null && (Number(entry.majorVersion) !== request.major_version || Number(entry.minorVersion) !== request.minor_version)) {
        throw Object.assign(new Error('Requested version is not installed and is not the current Hub version'), {code:'LIBRARY_VERSION_MISMATCH'});
      }
      await editor.installLibraryFromHub(name, user);
      installed = await manager.listInstalledLibraries();
      version = select();
    }
    if (!version) throw Object.assign(new Error('Library version is not installed. Use an authorized installation tool or CLI setup.'), {code:'LIBRARY_NOT_INSTALLED'});
    const metadata = await manager.getLibrary(version);
    return { core: editor.config.h5pVersion, library: `${name} ${version.majorVersion}.${version.minorVersion}`,
      patch_version: metadata.patchVersion, metadata, semantics: await manager.getSemantics(version),
      authoring_supported: Number(metadata.runnable) === 1 && compatible(metadata.coreApi?.majorVersion, metadata.coreApi?.minorVersion) !== false,
      note: 'Native H5P semantics, not JSON Schema. Nested library options refer to separate schemas; query those exact versions. Use the exact library and native params with create_h5p_activity.' };
    } finally {
      if (readonly) await fsp.rm(root, {recursive:true, force:true});
    }
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
      const H5pError = load('@lumieducation/h5p-server/build/src/helpers/H5pError').default;
      const imported = await editor.packageImporter.addPackageLibrariesAndTemporaryFiles(request.path, user).catch(error => {
        if (error instanceof H5pError) error.code = 'SCHEMA_VALIDATION_FAILED';
        throw error;
      });
      return { ok: true, errors: [], warnings: [], engine: 'Lumi', libraries: imported.installedLibraries.length };
    }
    if (!['prepare', 'export'].includes(request.action)) throw new Error('Unknown action');
    const report = await prepareActivity(editor, request.activity, user);
    await auditLumiSemantics(editor, report, load);
    if (report.ok) {
      const manifest = await preparationManifest(editor, libraries, report.activity, report.mathematics);
      if (request.action === 'export' && request.activity.preparation && !sameManifest(request.activity.preparation, manifest))
        throw Object.assign(new Error('Preparation dependencies changed; prepare again'), {code:'STALE_PREPARATION'});
      report.activity.preparation = manifest;
    }
    if (request.action === 'prepare') return report;
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
  } finally {
    await fsp.rm(job, { recursive: true, force: true });
  }
}

let input = '';
process.stdin.setEncoding('utf8');
let inputBytes = 0;
process.stdin.on('data', chunk => {
  inputBytes += Buffer.byteLength(chunk);
  if (inputBytes > limit('JSON_BYTES', 16777216)) {
    process.stdout.write(JSON.stringify({ok:false, code:'INPUT_TOO_LARGE', errors:['JSON byte budget exceeded']}));
    process.exit(1);
  }
  input += chunk;
});
process.stdin.on('end', async () => {
  try { process.stdout.write(JSON.stringify(await main(JSON.parse(input)))); }
  catch (error) {
    process.stderr.write(`${error.stack || error}\n`);
    process.stdout.write(JSON.stringify({ ok: false, code:error.code || 'BACKEND_ERROR', errors: [error.message], details: error.details || error.errors }));
    process.exitCode = 1;
  }
});
