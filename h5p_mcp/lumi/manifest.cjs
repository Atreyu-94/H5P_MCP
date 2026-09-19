const fs = require('node:fs/promises');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {readBounded} = require('./media.cjs');
const {limit} = require('./limits.cjs');
const hash = data => createHash('sha256').update(data).digest('hex');
async function preparationManifest(editor, root, activity, mathematics) {
  const libraries = {};
  let total = 0, files = 0;
  async function digestFile(filename) {
    const data = await readBounded(filename, limit('ASSET_BYTES', 67108864));
    total += data.length;
    if (++files > limit('ZIP_MEMBERS', 20000) || total > limit('ZIP_BYTES', 536870912)) throw new Error('Manifest file budget exceeded');
    return hash(data);
  }
  async function add(name) {
    if (libraries[name]) return;
    const [machineName, version] = name.split(' ');
    const [majorVersion, minorVersion] = version.split('.').map(Number);
    const meta = await editor.libraryManager.getLibrary({machineName, majorVersion, minorVersion});
    const entry = libraries[name] = {patch:meta.patchVersion, files:{}};
    const base = path.join(root, `${machineName}-${version}`);
    async function walk(dir, depth = 0) {
      if (depth > 32) throw new Error('Library path too deep');
      for (const file of (await fs.readdir(dir, {withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))) {
        const full = path.join(dir, file.name);
        if (file.isSymbolicLink()) throw new Error('Library symlinks are unsupported');
        if (file.isDirectory()) await walk(full, depth + 1);
        else entry.files[path.relative(base, full).split(path.sep).join('/')] = await digestFile(full);
      }
    }
    await walk(base);
    for (const dep of [...(meta.preloadedDependencies || []), ...(meta.dynamicDependencies || []), ...(meta.editorDependencies || [])])
      await add(`${dep.machineName} ${dep.majorVersion}.${dep.minorVersion}`);
  }
  await add(activity.library);
  const stack = [activity.params];
  while (stack.length) {
    const value = stack.pop();
    if (!value || typeof value !== 'object') continue;
    if (typeof value.library === 'string' && value.params) await add(value.library);
    stack.push(...Object.values(value));
  }
  if (mathematics.detected) await add('H5P.MathDisplay 1.0');
  const assets = {};
  for (const [id, file] of Object.entries(activity.assets || {})) assets[id] = await digestFile(file);
  const backend = {};
  for (const file of (await fs.readdir(__dirname)).filter(n=>n.endsWith('.cjs') || n === 'package-lock.json' || n === 'provenance.json').sort())
    backend[file] = hash(await fs.readFile(path.join(__dirname, file)));
  return {version:1, libraries, assets, backend};
}
function sameManifest(a,b) {
  const canonical = value => value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])])) : value;
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}
module.exports = {preparationManifest, sameManifest};
