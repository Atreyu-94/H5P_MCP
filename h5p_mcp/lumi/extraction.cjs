// Adapter for the pinned Lumi extraction API. Lumi still validates and installs
// packages; this boundary enforces byte budgets while its worker writes files.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const {Transform} = require('node:stream');
const {pipeline} = require('node:stream/promises');
const {limit} = require('./limits.cjs');

function installBoundedExtraction(load) {
  const PackageImporter = load('@lumieducation/h5p-server/build/src/PackageImporter').default;
  const yauzl = load('yauzl-promise');
  PackageImporter.extractPackage = async function(packagePath, directoryPath, options = {}) {
    if ((await fsp.stat(packagePath)).size > limit('ZIP_ARCHIVE_BYTES',134217728)) throw new Error('ZIP compressed byte budget exceeded');
    const zip = await yauzl.open(packagePath);
    const names = new Map();
    let members = 0, declared = 0, expanded = 0;
    try {
      for await (const entry of zip) {
        if (++members > limit('ZIP_MEMBERS',20000)) throw new Error('ZIP member budget exceeded');
        const name = entry.filename;
        const directory = name.endsWith('/');
        const parts = (directory ? name.slice(0,-1) : name).split('/');
        const mode = (entry.externalFileAttributes >>> 16) & 0xf000;
        // oxlint-disable-next-line no-control-regex -- ZIP names must reject control bytes.
        if ((mode && mode !== 0x8000 && mode !== 0x4000) || (mode === 0x4000 && !directory) || /[\\\x00-\x1f<>:"|?*]/.test(name) ||
            parts.length > limit('ZIP_PATH_DEPTH',32) || parts.some(p=>!p || p==='.' || p==='..' || /[ .]$/.test(p) || /^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]|CONIN\$|CONOUT\$)(?:\.|$)/i.test(p)))
          throw new Error('Unsafe ZIP extraction path or file type');
        for (let i=1;i<=parts.length;i++) {
          const original = parts.slice(0,i).join('/'), key=original.normalize('NFC').toLowerCase();
          const kind = directory || i<parts.length;
          const previous=names.get(key);
          if (previous && (previous.original!==original || previous.directory!==kind || (i===parts.length && previous.explicit)))
            throw new Error('ZIP extraction path collision');
          names.set(key,{original,directory:kind,explicit:(previous?.explicit || i===parts.length)});
        }
        declared += entry.uncompressedSize;
        if (entry.uncompressedSize > limit('ZIP_MEMBER_BYTES',134217728) || declared > limit('ZIP_BYTES',536870912) ||
            entry.uncompressedSize > Math.max(1,entry.compressedSize)*limit('ZIP_RATIO',1000)) throw new Error('ZIP extraction byte or ratio budget exceeded');
        const basename = path.basename(name);
        const selected = !directory && !basename.startsWith('.') && !basename.startsWith('_') &&
          ((options.includeContent && name.startsWith('content/')) ||
           (options.includeLibraries && name.includes('/') && !name.startsWith('content/')) ||
           (options.includeMetadata && name==='h5p.json'));
        if (!selected) continue;
        const target = path.resolve(directoryPath,...parts);
        const relative = path.relative(path.resolve(directoryPath),target);
        if (relative.startsWith('..'+path.sep) || path.isAbsolute(relative)) throw new Error('ZIP outside extraction root');
        await fsp.mkdir(path.dirname(target),{recursive:true});
        let size=0;
        const budget = new Transform({transform(chunk,encoding,callback) {
          size += chunk.length; expanded += chunk.length;
          if (size > limit('ZIP_MEMBER_BYTES',134217728) || expanded > limit('ZIP_BYTES',536870912))
            callback(new Error('ZIP streamed extraction budget exceeded'));
          else callback(null,chunk);
        }});
        await pipeline(await entry.openReadStream(),budget,fs.createWriteStream(target,{flags:'wx'}));
        if (size !== entry.uncompressedSize) throw new Error('ZIP extracted size mismatch');
      }
    } finally { await zip.close(); }
  };
}
module.exports = {installBoundedExtraction};
