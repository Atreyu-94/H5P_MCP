// Generic native-semantics checks. This is not a replacement for browser tests
// or every content type's editor widget/business rules.
const {createMediaResolver} = require('./media.cjs');
const { randomUUID } = require('node:crypto');
const { inspectMath } = require('./math.cjs');
const { checkTree, limit } = require('./limits.cjs');
const { scalarErrors } = require('./semantics.cjs');
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

async function prepareActivity(editor, activity, user, upload = false) {
  const errors = [];
  const diagnostics = [];
  const identities = new Set();
  try { checkTree(activity.params); } catch (error) {
    return {ok:false, errors:[error.message], diagnostics:[{code:error.code, path:'params', message:error.message, retryable:false}], warnings:[], mathematics:{detected:false}, activity:{...activity, params:{}}};
  }
  const warnings = new Set(['Native field checks do not verify editor-widget rules, HTML safety, playback, accessibility or Moodle grading.']);
  const schemas = new Map();
  let visitedFields = 0;
  let exhausted = false;
  const usedAssets = new Set();
  const assets = activity.assets || {};
  const fail = (at, message, code = 'INVALID_PARAMETER') => { errors.push(`${at}: ${message}`); diagnostics.push({code, path:at, message, retryable:false}); };
  async function schema(library, at, top = false) {
    const match = /^([A-Za-z0-9][A-Za-z0-9_.-]*) ([0-9]+)\.([0-9]+)$/.exec(library || '');
    if (!match) { fail(at, 'expected exact library "Name major.minor"'); return; }
    const version = { machineName: match[1], majorVersion: Number(match[2]), minorVersion: Number(match[3]) };
    try {
      if (!schemas.has(library)) {
        if (schemas.size >= limit('LIBRARIES',1000)) throw new Error('Library node budget exceeded');
        const metadata = await editor.libraryManager.getLibrary(version);
        const core = metadata.coreApi;
        if (core && (core.majorVersion > editor.config.coreApiVersion.major ||
          (core.majorVersion === editor.config.coreApiVersion.major && core.minorVersion > editor.config.coreApiVersion.minor))) {
          throw new Error('requires a newer H5P Core');
        }
        const semantics = await editor.libraryManager.getSemantics(version);
        checkTree(semantics);
        schemas.set(library, { metadata, fields: semantics });
      }
      const result = schemas.get(library);
      if (top && Number(result.metadata.runnable) !== 1) { fail(at, 'library is not runnable'); return; }
      return result.fields;
    } catch (error) { fail(at, `library ${library} unavailable: ${error.message}`, 'LIBRARY_NOT_INSTALLED'); }
  }
  async function fields(entries, value, at, depth) {
    if (!object(value)) { fail(at, 'expected object'); return value; }
    const result = {};
    const names = new Set(entries.map(e => e.name));
    for (const key of Object.keys(value)) if (!names.has(key)) fail(`${at}.${key}`, 'unknown field');
    for (const entry of entries) {
      const item = await field(entry, value[entry.name], `${at}.${entry.name}`, depth + 1);
      if (item !== undefined) result[entry.name] = item;
    }
    return result;
  }
  const media = createMediaResolver({editor, user, upload, assets, usedAssets, warnings, fail});
  async function field(entry, value, at, depth) {
    if (exhausted) return undefined;
    if (++visitedFields > limit('NODES',100000)) { exhausted = true; fail(at,'Expanded field budget exceeded','INPUT_TOO_LARGE'); return undefined; }
    if (depth > limit('DEPTH',64)) { fail(at, 'maximum nesting depth exceeded'); return value; }
    // H5P flattens a group with one field (e.g. overallFeedback) into
    // that field's value; this must agree with Lumi's ContentScanner.
    if (entry.type === 'group' && entry.fields?.length === 1) {
      if (value === undefined && entry.optional) return undefined;
      return field(entry.fields[0], value, at, depth + 1);
    }
    if (value === undefined) {
      if (entry.default !== undefined) value = structuredClone(entry.default);
      else if (entry.optional) return undefined;
      else if (entry.type === 'group') value = {};
      else { fail(at, 'required field missing'); return undefined; }
    }
    switch (entry.type) {
      case 'group': return fields(entry.fields || [], value, at, depth);
      case 'list':
        if (!Array.isArray(value)) { fail(at, 'expected list'); return value; }
        if (entry.min != null && value.length < entry.min) fail(at, `minimum ${entry.min} items`);
        if (entry.max != null && value.length > entry.max) fail(at, `maximum ${entry.max} items`);
        { const items = []; for (let i = 0; i < value.length; i++) items.push(await field(entry.field, value[i], `${at}[${i}]`, depth + 1)); return items; }
      case 'library': {
        if (!object(value)) { fail(at, 'expected library object'); return value; }
        if (!entry.options?.includes(value.library)) { fail(at, 'library is not an allowed exact version'); return value; }
        const entries = await schema(value.library, at);
        const id = value.subContentId === undefined ? randomUUID() : value.subContentId;
        if (typeof id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) fail(`${at}.subContentId`, 'expected UUID', 'INVALID_SUBCONTENT_ID');
        else if (identities.has(id.toLowerCase())) fail(`${at}.subContentId`, 'duplicate UUID', 'DUPLICATE_SUBCONTENT_ID');
        else identities.add(id.toLowerCase());
        return { ...value, subContentId: id,
          params: entries ? await fields(entries, value.params, `${at}.params`, depth + 1) : value.params };
      }
      case 'text': case 'number':
        for (const message of scalarErrors(entry, value)) fail(at, message);
        break;
      case 'boolean': if (typeof value !== 'boolean') fail(at, 'expected boolean'); break;
      case 'select': {
        const options = (entry.options || []).map(o => o.value);
        const values = entry.multiple ? value : [value];
        if (!Array.isArray(values) || values.some(v => !options.includes(v))) fail(at, 'invalid select option');
        break;
      }
      case 'image': case 'file': return media(entry, value, at);
      case 'audio': case 'video':
        if (!Array.isArray(value)) { fail(at, 'expected media list'); return value; }
        { const items = []; for (let i = 0; i < value.length; i++) items.push(await media(entry, value[i], `${at}[${i}]`)); return items; }
      default: fail(at, `unsupported semantic field type ${entry.type}`);
    }
    return value;
  }
  const entries = await schema(activity.library, 'library', true);
  const params = entries ? await fields(entries, activity.params, 'params', 0) : activity.params;
  const mathematics = errors.length ? {detected:false} : await inspectMath(editor.libraryManager, params);
  if (mathematics.error) fail('params', mathematics.error, 'LIBRARY_NOT_INSTALLED');
  if (mathematics.detected) warnings.add('LaTeX requires MathDisplay at playback. Check TeX syntax and rendering in the destination; this is not a symbolic answer checker.');
  for (const id of Object.keys(assets)) if (!usedAssets.has(id)) fail(`assets.${id}`, 'asset is not referenced in a native media field');
  return { ok: errors.length === 0, errors, diagnostics, warnings: [...warnings], mathematics, activity: { ...activity, params } };
}

module.exports = { prepareActivity };
