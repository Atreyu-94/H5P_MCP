"""B0 runtime comparison on one npm tree, with independent library stores."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile
import uuid
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bun', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo))
    from h5p_mcp import lumi_backend as backend
    from h5p_mcp.models.activity import Activity
    from h5p_mcp.exporters.h5p_exporter import H5PExporter
    from h5p_mcp.validators.package_validator import validate_h5p_package
    node = shutil.which('node')
    version = subprocess.check_output([args.bun, '--version'], text=True).strip()
    assert version == '1.4.2', version
    report = {'bun':version, 'node':subprocess.check_output([node, '--version'],text=True).strip(),
              'os':platform.platform(), 'architecture':platform.machine(), 'cpu':platform.processor(),
              'libc':platform.libc_ver(), 'head':subprocess.check_output(
                  ['git','-c',f'safe.directory={repo.as_posix()}','rev-parse','HEAD'],cwd=repo,text=True).strip(),
              'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'checks':{}, 'decision':'not_certified',
              'known_findings':['Lumi get() contacts Hub on missing cache even with refresh=false; cached corpus is seeded explicitly'],
              'not_run':['Linux/macOS', 'Node 22/24 reference', 'audio/video', 'Hub/TLS/proxy',
                         'signals/backpressure/leak stress', 'TypeScript/lint', 'Bun installer comparison', 'browser']}
    # Keep isolated artifacts for subsequent browser/installer checks and failures.
    root = Path(tempfile.mkdtemp(prefix='h5p-b0-runtime-'))
    report['artifacts'] = str(root)
    fixture = repo / 'tests/fixtures/libraries.zip'
    expected = json.loads((fixture.parent / 'libraries.lock.json').read_text())['sha256']
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected
    os.environ['H5P_MCP_DATA_DIR'] = str(root / 'reference')
    with ZipFile(fixture) as archive:
        archive.extractall(root / 'reference/libraries')
    try:
        backend.setup_lumi()
        runtime = backend.runtime_dir()
        report['npm_runtime'] = str(runtime)
        backend.runtime_dir = lambda: runtime
        stores = {}
        for label in ('node','bun'):
            stores[label] = root / label
            shutil.copytree(root / 'reference/libraries', stores[label] / 'libraries')
            # B0 cached-discovery corpus: both runtimes receive exactly the same
            # explicit cache. A missing cache invokes upstream network I/O.
            (stores[label] / 'cache.json').write_text(json.dumps({
                'contentTypeCache':[], 'contentTypeCacheUpdate':1}),encoding='utf-8')
        def select(label):
            os.environ['H5P_MCP_DATA_DIR'] = str(stores[label])
            backend._node = lambda: node if label == 'node' else args.bun
        crc_script = """
const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const load = createRequire(process.argv[1] + '/package.json');
const {crc32,crc32c} = load('@node-rs/crc32');
assert.equal(crc32('123456789'), 0xcbf43926);
assert.equal(crc32c('123456789'), 0xe3069283);
assert.equal(crc32(''), 0);
const native=Object.keys(require.cache).filter(p=>p.endsWith('.node'));
assert(native.length > 0, 'No native addon observed');
console.log(JSON.stringify({native,crc32:'passed',crc32c:'passed'}));
"""
        for label, executable in [('node',node),('bun',args.bun)]:
            result = subprocess.check_output([executable,'-e',crc_script,str(runtime)],text=True,timeout=30)
            report['checks'][f'{label}_crc'] = json.loads(result)
        def paired(action, **payload):
            values = []
            for label in ('node','bun'):
                select(label)
                values.append(backend.run_lumi(action, **payload))
            if values[0] != values[1]:
                (root / f'{action}-difference.json').write_text(json.dumps(
                    {'node':values[0], 'bun':values[1]},indent=2)+'\n',encoding='utf-8')
                raise AssertionError(f'{action} runtime difference; see {root / (action + "-difference.json")}')
            return values[0]
        paired('catalog')
        paired('discover', installed_only=True, query='', refresh=False)
        paired('schema', machine_name='H5P.TrueFalse', major_version=1, minor_version=8)
        report['checks']['catalog_discover_schema'] = 'passed'
        examples = copy.deepcopy(runpy.run_path(str(repo / 'tests/test_native_authoring.py'))['EXAMPLES'])
        examples.append({'library':'H5P.TrueFalse 1.8','params':{
            'question':r'<p>\(1+1=2\)</p>','correct':'true','behaviour':{'enableRetry':True,
            'feedbackOnCorrect':r'Correct: \(1+1=2\)', 'feedbackOnWrong':r'Try again: \(1+1=2\)'}}})
        def fixed_ids(value, path='root'):
            if isinstance(value,dict):
                if 'library' in value and 'params' in value:
                    value['subContentId'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'b0-fixture/'+path))
                for key, child in value.items():
                    fixed_ids(child,path+'/'+key)
            elif isinstance(value,list):
                for index, child in enumerate(value):
                    fixed_ids(child,path+'/'+str(index))
        def package_contents(path):
            with ZipFile(path) as archive:
                names = archive.namelist()
                assert len(names) == len(set(names))
                return {name:json.loads(archive.read(name)) if name in ('h5p.json','content/content.json')
                        else hashlib.sha256(archive.read(name)).hexdigest() for name in names}
        for index, example in enumerate(examples):
            fixed_ids(example['params'])
            activity = Activity(title=f'B0 fixture {index}', **example)
            prepared = paired('prepare', activity=activity.model_dump())
            assert prepared['ok'], prepared
            activity = Activity.model_validate(prepared['activity'])
            paths = []
            for label in ('node','bun'):
                select(label)
                exporter = H5PExporter(export_dir=str(root / 'exports' / label))
                result = exporter.export(activity,output_name=f'fixture-{index}')
                paths.append(result.output_path)
                try:
                    exporter.export(activity,output_name=f'fixture-{index}')
                except FileExistsError:
                    pass
                else:
                    raise AssertionError('Existing export overwritten')
            assert package_contents(paths[0]) == package_contents(paths[1]), f'Package difference: {index}'
            for label in ('node','bun'):
                select(label)
                for path in paths:
                    validation = validate_h5p_package(path)
                    assert validation.ok, validation.errors
            report['checks'][f'fixture_{index}'] = {'library':example['library'],
                'prepare':'passed','package_files':'passed','cross_import':'passed','no_overwrite':'passed'}
        invalid = Activity(title='Invalid',library='H5P.TrueFalse 1.8',params={'question':'Q','correct':True})
        assert not paired('prepare',activity=invalid.model_dump())['ok']
        report['checks']['invalid_select'] = 'passed'
        report['local_subset'] = 'passed'
    except Exception as error:
        report['local_subset'] = 'failed'
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'report':str(args.output),'result':report.get('local_subset'),'artifacts':str(root)}))


if __name__ == '__main__':
    main()
