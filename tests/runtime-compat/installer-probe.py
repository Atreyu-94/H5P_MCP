"""Compare npm reference with Bun install separately from runtime semantics."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--bun',required=True)
parser.add_argument('--runtime-report',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
assert subprocess.check_output([args.bun,'--version'],text=True).strip() == '1.4.2'
reference = Path(json.loads(args.runtime_report.read_text())['npm_runtime'])
stage = Path(tempfile.mkdtemp(prefix='h5p-b0-installer-'))
for path in reference.iterdir():
    if path.name in ('package.json','package-lock.json') or path.suffix == '.tgz':
        shutil.copyfile(path, stage / path.name)
report = {'bun':'1.4.2','scripts':'disabled','linker':'hoisted','artifacts':str(stage),
          'decision':'not_certified','checks':{}}
try:
    result = subprocess.run([args.bun,'install','--ignore-scripts','--linker','hoisted'],
                            cwd=stage,text=True,capture_output=True,timeout=300)
    report['migration_log'] = result.stdout + result.stderr
    result.check_returncode()
    lock = stage / 'bun.lock'
    assert lock.is_file(), 'Text lockfile missing'
    report['bun_lock_sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
    # Fresh dependency directory for the frozen replay, without deleting data.
    replay = stage / 'frozen-replay'
    replay.mkdir()
    for path in stage.iterdir():
        if path.is_file() and (path.name in ('package.json','bun.lock') or path.suffix == '.tgz'):
            shutil.copyfile(path,replay/path.name)
    frozen = subprocess.run([args.bun,'install','--frozen-lockfile','--ignore-scripts','--linker','hoisted'],
                            cwd=replay,text=True,capture_output=True,timeout=300)
    report['frozen_log'] = frozen.stdout + frozen.stderr
    frozen.check_returncode()
    assert hashlib.sha256((replay/'bun.lock').read_bytes()).hexdigest() == report['bun_lock_sha256']
    def inventory(directory):
        packages = {}
        for path in (directory/'node_modules').rglob('package.json'):
            # Hoisted runtime packages, including any real nested dependency.
            if path.parent.parent.name != 'node_modules' and not path.parent.parent.name.startswith('@'):
                continue
            value = json.loads(path.read_text(encoding='utf-8'))
            if 'name' in value and 'version' in value:
                packages[path.parent.relative_to(directory/'node_modules').as_posix()] = {
                    'name':value['name'],'version':value['version']}
        return packages
    npm, bun = inventory(reference), inventory(replay)
    report['package_differences'] = {name:{'npm':npm.get(name),'bun':bun.get(name)}
                                   for name in sorted(npm.keys()|bun.keys()) if npm.get(name)!=bun.get(name)}
    report['packages'] = {'npm':len(npm),'bun':len(bun)}
    # Hoisting is allowed to move a package. Compare what each importer resolves,
    # not only the filesystem position (retain that raw difference above).
    def graph(directory, packages):
        edges = []
        for relative, identity in packages.items():
            folder = directory/'node_modules'/relative
            metadata = json.loads((folder/'package.json').read_text(encoding='utf-8'))
            dependencies = {}
            for name in metadata.get('dependencies', {}):
                current = folder
                while current != directory.parent:
                    candidate = current/'node_modules'/name/'package.json'
                    if candidate.is_file():
                        dep = json.loads(candidate.read_text(encoding='utf-8'))
                        dependencies[name] = dep['name']+'@'+dep['version']
                        break
                    current = current.parent
                else:
                    dependencies[name] = 'UNRESOLVED'
            edges.append({'package':identity,'dependencies':dependencies})
        return sorted(edges,key=lambda value:json.dumps(value,sort_keys=True))
    # Bun may retain the musl optional binary on glibc. Keep the inventory diff,
    # allow only this declared inactive package, and verify actual native loading
    # below. No arbitrary extra packages or version drift are accepted.
    extra = '@node-rs/crc32-linux-x64-musl'
    inactive = set()
    if platform.system() == 'Linux' and platform.libc_ver()[0] == 'glibc' and extra in bun and extra not in npm:
        wrapper = json.loads((replay/'node_modules/@node-rs/crc32/package.json').read_text())
        assert wrapper['optionalDependencies'][extra] == bun[extra]['version']
        inactive.add(extra)
    report['reviewed_inactive_optional_packages'] = sorted(inactive)
    compared_bun = {key:value for key,value in bun.items() if key not in inactive}
    report['checks']['resolved_dependency_graph'] = 'passed' if graph(reference,npm)==graph(replay,compared_bun) else 'failed'
    report['layout_differences'] = len(report['package_differences'])
    report['checks']['frozen_install'] = 'passed'
    report['native_files'] = {label:{p.relative_to(directory/'node_modules').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (directory/'node_modules').rglob('*.node')}
                              for label,directory in [('npm',reference),('bun',replay)]}
    compared_native = {key:value for key,value in report['native_files']['bun'].items()
                       if not any(key.startswith(name+'/') for name in inactive)}
    report['checks']['native_files'] = 'passed' if report['native_files']['npm']==compared_native else 'failed'
    script = """
const assert=require('node:assert/strict'), {createRequire}=require('node:module');
const load=createRequire(process.argv[1]+'/package.json');
assert.equal(load('@node-rs/crc32').crc32('123456789'),0xcbf43926);
console.log(JSON.stringify(Object.keys(require.cache).filter(p=>p.endsWith('.node'))));
"""
    loaded = {}
    for label, executable in [('node',shutil.which('node')),('bun',args.bun)]:
        paths = json.loads(subprocess.check_output([executable,'-e',script,str(replay)],text=True,timeout=30))
        assert paths, 'No loaded native addon observed'
        loaded[label] = {Path(path).resolve().relative_to((replay/'node_modules').resolve()).as_posix():hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}
        assert loaded[label] == report['native_files']['npm'], 'Loaded native binary differs from npm reference'
    report['loaded_native_files'] = loaded
    report['checks']['loaded_native_crc'] = 'passed'
    # Persist the generated lock for review; it is not the product's lockfile.
    shutil.copyfile(lock,args.output.with_suffix('.bun.lock'))
finally:
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(args.output),'checks':report['checks']}))
if 'failed' in report['checks'].values():
    raise SystemExit(1)
