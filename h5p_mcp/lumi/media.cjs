const fs = require('node:fs/promises');
const path = require('node:path');
const {createRequire} = require('node:module');
const {limit} = require('./limits.cjs');
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const failure = (message, code) => Object.assign(new Error(message), {code});
async function readBounded(filename, maximum) {
  const file = await fs.open(filename, 'r');
  try {
    const chunks = [];
    let total = 0;
    while (true) {
      const buffer = Buffer.alloc(Math.min(65536, maximum + 1 - total));
      const {bytesRead} = await file.read(buffer);
      if (!bytesRead) break;
      total += bytesRead;
      if (total > maximum) throw failure('media byte budget exceeded', 'ASSET_TOO_LARGE');
      chunks.push(buffer.subarray(0, bytesRead));
    }
    return Buffer.concat(chunks);
  } finally { await file.close(); }
}
function createMediaResolver({editor, user, upload, assets, usedAssets, warnings, fail}) {
  let mediaBytes = 0;
  async function media(entry, value, at) {
    if (!object(value) || typeof value.path !== 'string') { fail(at, 'expected media object with path'); return value; }
    if (!value.path.startsWith('asset:')) {
      // Remote media are left for the player, never downloaded implicitly.
      if (/^https?:\/\//i.test(value.path)) {
        warnings.add('Remote media require network access during playback and are not embedded.');
        return value;
      }
      fail(at, 'local media must reference asset:<id> with an absolute path in assets'); return value;
    }
    const id = value.path.slice(6);
    const filename = assets[id];
    if (typeof filename !== 'string' || !path.isAbsolute(filename)) { fail(at, `missing absolute asset path for ${id}`, 'ASSET_NOT_FOUND'); return value; }
    try {
      const real = await fs.realpath(filename);
      const roots = process.env.H5P_MCP_ASSET_ROOTS ? JSON.parse(process.env.H5P_MCP_ASSET_ROOTS) : [];
      if (!Array.isArray(roots) || roots.some(root=>typeof root !== 'string' || !path.isAbsolute(root))) throw new Error('asset roots must be absolute directories');
      if (process.env.H5P_MCP_ASSET_ROOTS !== undefined) {
        let allowed = false;
        for (const root of roots) {
          const relative = path.relative(await fs.realpath(root), real);
          if (!relative || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative))) allowed = true;
        }
        if (!allowed) throw new Error('asset outside authorized roots');
      }
      const stat = await fs.stat(real);
      if (!stat.isFile()) throw new Error('not a file');
      if (stat.size > limit('ASSET_BYTES', 67108864) || mediaBytes > limit('MEDIA_BYTES', 268435456)) throw failure('media byte budget exceeded', 'ASSET_TOO_LARGE');
      usedAssets.add(id);
      if (typeof value.mime !== 'string' || !value.mime) throw failure('media mime is required', 'MIME_MISMATCH');
      const allowed = new Set(['image/png','image/jpeg','image/gif','image/webp','image/bmp','image/tiff','image/avif',
        'audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/ogg','audio/mp4','audio/webm',
        'video/mp4','video/webm','video/ogg','application/pdf','text/vtt']);
      if (!allowed.has(value.mime)) throw failure('unsupported media MIME; active HTML/SVG assets are not accepted', 'MIME_MISMATCH');
      const data = await readBounded(real, Math.min(limit('ASSET_BYTES',67108864),limit('MEDIA_BYTES',268435456)-mediaBytes));
      mediaBytes += data.length;
      const load = createRequire(path.join(process.env.H5P_MCP_LUMI_RUNTIME || __dirname,'package.json'));
      const detected = load('magic-bytes.js').filetypeinfo(data).map(type=>type.mime);
      const aliases = {'audio/mp3':'audio/mpeg','audio/x-wav':'audio/wav','application/ogg':'audio/ogg','audio/vnd.wave':'audio/wav'};
      const canonical = mime=>aliases[mime] || mime;
      const vtt = value.mime === 'text/vtt' && /^(?:\uFEFF)?WEBVTT(?:[ \t]|\r?\n|$)/.test(data.toString('utf8'));
      // Containers may carry audio or video; they share magic. Codec/playback
      // validation remains the host's responsibility, not a MIME guarantee.
      const containers = {'audio/mp4':'video/mp4','audio/webm':'video/webm','video/ogg':'audio/ogg'};
      const comparable = mime=>containers[canonical(mime)] || canonical(mime);
      if (!vtt && !detected.some(mime=>comparable(mime) === comparable(value.mime)))
        throw failure(`declared MIME ${value.mime} does not match detected bytes`, 'MIME_MISMATCH');
      if (upload) {
        // Read a copy: upstream sanitizers/scanners must never mutate the source.
        const saved = await editor.saveContentFile(undefined, entry,
          { name: path.basename(filename), mimetype: value.mime, data }, user);
        return { ...value, ...saved };
      }
    } catch (error) {
      const code = error.code === 'ENOENT' ? 'ASSET_NOT_FOUND' : ['ASSET_TOO_LARGE','MIME_MISMATCH'].includes(error.code) ? error.code : 'INVALID_PARAMETER';
      fail(at, `asset ${id}: ${error.message}`, code);
    }
    return value;
  }
  return media;
}
module.exports = {readBounded, createMediaResolver};
