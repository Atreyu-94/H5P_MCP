const fs = require('node:fs/promises');
const path = require('node:path');
const {limit} = require('./limits.cjs');
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
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
      if (total > maximum) throw new Error('media byte budget exceeded');
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
    if (typeof filename !== 'string' || !path.isAbsolute(filename)) { fail(at, `missing absolute asset path for ${id}`); return value; }
    try {
      const real = await fs.realpath(filename);
      const roots = process.env.H5P_MCP_ASSET_ROOTS ? JSON.parse(process.env.H5P_MCP_ASSET_ROOTS) : [];
      if (roots.length) {
        let allowed = false;
        for (const root of roots) {
          const relative = path.relative(await fs.realpath(root), real);
          if (!relative || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative))) allowed = true;
        }
        if (!allowed) throw new Error('asset outside authorized roots');
      }
      const stat = await fs.stat(real);
      if (!stat.isFile()) throw new Error('not a file');
      mediaBytes += stat.size;
      if (stat.size > limit('ASSET_BYTES', 67108864) || mediaBytes > limit('MEDIA_BYTES', 268435456)) throw new Error('media byte budget exceeded');
      usedAssets.add(id);
      if (typeof value.mime !== 'string' || !value.mime) throw new Error('media mime is required');
      if (upload) {
        // Read a copy: upstream sanitizers/scanners must never mutate the source.
        const saved = await editor.saveContentFile(undefined, entry,
          { name: path.basename(filename), mimetype: value.mime, data: await readBounded(filename, limit('ASSET_BYTES', 67108864)) }, user);
        return { ...value, ...saved };
      }
    } catch (error) { fail(at, `asset ${id}: ${error.message}`); }
    return value;
  }
  return media;
}
module.exports = {readBounded, createMediaResolver};
