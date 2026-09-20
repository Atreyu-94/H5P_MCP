"""B0 runtime comparison on one npm tree, with independent library stores."""
import argparse
import base64
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
import wave
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bun', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--installer-report', type=Path,
                        help='Also test a copy of the successful frozen Bun installation')
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
              'known_findings':['Discovery now reads cache storage directly unless refresh is explicitly requested'],
              'not_run':['Other platforms in this individual report', 'Hub/TLS/proxy',
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
        if args.installer_report:
            installation = json.loads(args.installer_report.read_text())
            assert installation['checks']['frozen_install'] == 'passed'
            candidate = Path(installation['artifacts']) / 'frozen-replay'
            source_provenance = json.loads((backend.SOURCE/'provenance.json').read_text())
            assert hashlib.sha256((candidate/source_provenance['archive']).read_bytes()).hexdigest() == source_provenance['sha256']
            runtime = root / 'bun-installed-runtime'
            shutil.copytree(candidate,runtime)
            (runtime/'.ready').touch()
            report['dependency_installer'] = 'bun-frozen'
        else:
            report['dependency_installer'] = 'npm-ci'
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
            # Evidence timestamps describe each observation, not runtime behavior.
            # Validate them, then normalize only this explicitly volatile field.
            if action == 'discover':
                from datetime import datetime
                for value in values:
                    for item in value['activities']:
                        for evidence in item.get('evidence', []):
                            datetime.fromisoformat(evidence['checked_at'].replace('Z', '+00:00'))
                            evidence['checked_at'] = '<observation-time>'
            if values[0] != values[1]:
                (root / f'{action}-difference.json').write_text(json.dumps(
                    {'node':values[0], 'bun':values[1]},indent=2)+'\n',encoding='utf-8')
                raise AssertionError(f'{action} runtime difference; see {root / (action + "-difference.json")}')
            return values[0]
        paired('catalog')
        discovered = paired('discover', installed_only=True, query='', refresh=False, offset=0, limit=100)
        assert discovered['activities'], 'Discovery corpus must include installed activities'
        paired('schema', machine_name='H5P.TrueFalse', major_version=1, minor_version=8)
        report['checks']['catalog_discover_schema'] = 'passed'
        examples = copy.deepcopy(runpy.run_path(str(repo / 'tests/test_native_authoring.py'))['EXAMPLES'])
        examples.append({'library':'H5P.TrueFalse 1.8','params':{
            'question':r'<p>\(1+1=2\)</p>','correct':'true','behaviour':{'enableRetry':True,
            'feedbackOnCorrect':r'Correct: \(1+1=2\)', 'feedbackOnWrong':r'Try again: \(1+1=2\)'}}})
        image = root / 'source.png'
        image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0ioAAAAASUVORK5CYII='))
        examples.append({'library':'H5P.TrueFalse 1.8','assets':{'diagram':str(image)},'params':{
            'question':'<p>Image?</p>','correct':'true','media':{'type':{'library':'H5P.Image 1.1',
            'params':{'file':{'path':'asset:diagram','mime':'image/png'},'alt':'Diagram'}}}}})
        audio = root/'source.wav'
        with wave.open(str(audio),'wb') as stream:
            stream.setparams((1,2,8000,0,'NONE','not compressed'))
            stream.writeframes(b'\0\0'*1600)
        video = root/'source.webm'
        # Synthetic 32x32 blue VP9 video, 0.2 s, generated with FFmpeg 9.0.1.
        shutil.copyfile(repo/'tests/fixtures/video.webm',video)
        examples.append({'library':'H5P.Audio 1.5','assets':{'sound':str(audio)},'params':{
            'files':[{'path':'asset:sound','mime':'audio/wav'}],'autoplay':False}})
        examples.append({'library':'H5P.TrueFalse 1.8','assets':{'clip':str(video),'poster':str(image)},'params':{
            'question':'<p>Video?</p>','correct':'true','media':{'type':{'library':'H5P.Video 1.6',
            'params':{'sources':[{'path':'asset:clip','mime':'video/webm'}],
            'visuals':{'poster':{'path':'asset:poster','mime':'image/png'}}}}}}})
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
            contents = [package_contents(path) for path in paths]
            if 'assets' in example:
                # Only normalize declared fixture media after byte verification.
                filenames = []
                expected_media = {mime:hashlib.sha256(file.read_bytes()).hexdigest() for mime,file in
                                  [('image/png',image),('audio/wav',audio),('video/webm',video)]}
                for package in contents:
                    fields=[]
                    pending=[package['content/content.json']]
                    while pending:
                        value=pending.pop()
                        if isinstance(value,dict):
                            if 'path' in value and 'mime' in value: fields.append(value)
                            pending.extend(value.values())
                        elif isinstance(value,list): pending.extend(value)
                    assert len(fields)==len(example['assets'])
                    for number,field in enumerate(fields):
                        name='content/'+field['path']
                        filenames.append(field['path'])
                        assert field['mime'] in expected_media
                        digest=expected_media[field['mime']]
                        assert package.pop(name)==digest
                        if field['mime']=='image/png': assert field['width']==field['height']==1
                        field['path']=f'b0-fixture-media-{number}'
                        assert 'content/'+field['path'] not in package
                        package['content/'+field['path']]=digest
                report['checks'][f'media_{index}_bytes_and_reference'] = {'status':'passed','original_paths':filenames,
                    'normalization':'Only generated filename of the single media fixture; bytes match input SHA-256'}
            assert contents[0] == contents[1], f'Package difference: {index}'
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
        invalid_ids=copy.deepcopy(examples[1])
        invalid_ids['params']['panels'][0]['content']['subContentId']='invalid'
        assert not paired('prepare',activity=Activity(title='Invalid UUID',**invalid_ids).model_dump())['ok']
        duplicate_ids=copy.deepcopy(examples[1])
        duplicate_ids['params']['panels'].append(copy.deepcopy(duplicate_ids['params']['panels'][0]))
        assert not paired('prepare',activity=Activity(title='Duplicate UUID',**duplicate_ids).model_dump())['ok']
        report['checks']['invalid_and_duplicate_uuid']='passed'
        # Use the same stale manifest and incomplete package with both runtimes.
        stale = copy.deepcopy(activity.model_dump())
        stale['preparation']['libraries'][activity.library]['patch'] = -1
        incomplete = root / 'incomplete.h5p'
        with ZipFile(paths[0]) as source, ZipFile(incomplete,'w') as target:
            for name in ('h5p.json','content/content.json'):
                target.writestr(name,source.read(name))
        for label in ('node','bun'):
            select(label)
            output = root / f'{label}-stale'
            try:
                H5PExporter(export_dir=str(output)).export(Activity.model_validate(stale),output_name='stale')
            except backend.BackendError as error:
                assert error.code == 'STALE_PREPARATION', error
            else:
                raise AssertionError('Stale preparation was accepted')
            assert not list(output.glob('*.h5p'))
            assert not validate_h5p_package(incomplete).ok
            missing = root / f'{label}-missing-math'
            shutil.copytree(stores[label]/'libraries',missing/'libraries',ignore=shutil.ignore_patterns('H5P.MathDisplay-1.0'))
            os.environ['H5P_MCP_DATA_DIR'] = str(missing)
            try:
                math = Activity(title='Missing math',**examples[5])
                result = backend.run_lumi('prepare',activity=math.model_dump())
                assert not result['ok'], result
                assert 'MathDisplay' in ' '.join(result['errors']), result
            finally:
                select(label)
            report['checks'][f'{label}_negative_packages'] = {
                'stale_preparation':'passed','incomplete_package':'passed','missing_math':'passed'}
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
