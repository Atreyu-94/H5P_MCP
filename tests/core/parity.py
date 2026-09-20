"""F3 A/B/C parity and measurements; only documented volatile fields are normalized."""
import argparse
import base64
import copy
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
import wave
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from h5p_mcp import lumi_backend as backend
from h5p_mcp.core_client import CoreClient
from h5p_mcp.models.activity import Activity


def canonical(value):
    value = copy.deepcopy(value)
    if isinstance(value, dict):
        for activity in value.get('activities', []):
            for evidence in activity.get('evidence', []):
                from datetime import datetime
                datetime.fromisoformat(evidence['checked_at'].replace('Z', '+00:00'))
                evidence['checked_at'] = '<observation-time>'
        manifest = value.get('preparation_manifest') or value.get('activity', {}).get('preparation')
        if manifest:
            backend_hashes = manifest['backend']
            for name in list(backend_hashes):
                if name.startswith('core/'):
                    assert len(backend_hashes[name]) == 64
                    del backend_hashes[name]
    return value


def package_contents(filename):
    with ZipFile(filename) as package:
        result = {name: json.loads(package.read(name)) if name in ('h5p.json', 'content/content.json')
                  else hashlib.sha256(package.read(name)).hexdigest() for name in package.namelist()}
    pending = [result['content/content.json']]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if 'path' in item and 'mime' in item and 'content/' + item['path'] in result:
                digest = result.pop('content/' + item['path'])
                item['path'] = 'verified-media-' + digest
                result['content/' + item['path']] = digest
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bun', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--benchmark', action='store_true')
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='h5p-f3-'))
    report = {'platform': platform.platform(), 'artifacts': str(root), 'checks': {},
              'measurements_ms': {}, 'normalization': ['catalog observation timestamp',
              'additional core code hashes verified as SHA-256; legacy backend hashes compared',
              'generated media filenames replaced with verified package-byte digest'],
              'not_measured': ['OS page-cache cold start', 'Moodle', 'HTTP']}
    fixture = REPO / 'tests/fixtures/libraries.zip'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == json.loads(
        fixture.with_name('libraries.lock.json').read_text())['sha256']
    os.environ['H5P_MCP_DATA_DIR'] = str(root / 'data')
    with ZipFile(fixture) as package:
        package.extractall(root / 'data/libraries')
    backend.setup_lumi()
    runtime = backend.runtime_dir()
    report['runtime'] = str(runtime)
    env = dict(os.environ, H5P_MCP_LUMI_RUNTIME=str(REPO))
    report['core_runtime'] = str(REPO)
    report['bun_lock_sha256'] = hashlib.sha256((REPO / 'bun.lock').read_bytes()).hexdigest()
    entry = str(REPO / 'dist/core/adapters/ipc.js')
    examples = [copy.deepcopy(item) for item in runpy.run_path(str(REPO / 'tests/test_native_authoring.py'))['EXAMPLES']]
    examples.append({'library': 'H5P.TrueFalse 1.8', 'params': {'question': r'<p>\(1+1=2\)</p>',
        'correct': 'true', 'behaviour': {'enableRetry': True, 'feedbackOnCorrect': r'Correct: \(1+1=2\)',
                                      'feedbackOnWrong': r'Try again: \(1+1=2\)'}}})
    image = root / 'source.png'
    image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0ioAAAAASUVORK5CYII='))
    examples.append({'library': 'H5P.TrueFalse 1.8', 'assets': {'image': str(image)}, 'params': {
        'question': '<p>Image?</p>', 'correct': 'true', 'media': {'type': {'library': 'H5P.Image 1.1',
        'params': {'file': {'path': 'asset:image', 'mime': 'image/png'}, 'alt': 'Image'}}}}})
    audio = root / 'source.wav'
    with wave.open(str(audio), 'wb') as stream:
        stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0\0' * 1600)
    video = root / 'source.webm'
    shutil.copyfile(REPO / 'tests/fixtures/video.webm', video)
    examples.extend([
        {'library': 'H5P.Audio 1.5', 'assets': {'sound': str(audio)},
         'params': {'files': [{'path': 'asset:sound', 'mime': 'audio/wav'}], 'autoplay': False}},
        {'library': 'H5P.TrueFalse 1.8', 'assets': {'clip': str(video), 'poster': str(image)}, 'params': {
            'question': '<p>Video?</p>', 'correct': 'true', 'media': {'type': {'library': 'H5P.Video 1.6',
            'params': {'sources': [{'path': 'asset:clip', 'mime': 'video/webm'}],
                       'visuals': {'poster': {'path': 'asset:poster', 'mime': 'image/png'}}}}}}}])
    def fixed_ids(value, pointer='root'):
        if isinstance(value, dict):
            if 'library' in value and 'params' in value:
                value['subContentId'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'f3-fixture/' + pointer))
            for key, child in value.items():
                fixed_ids(child, pointer + '/' + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                fixed_ids(child, pointer + '/' + str(index))
    for example in examples:
        fixed_ids(example['params'])
    with ExitStack() as stack:
        clients = {label: stack.enter_context(CoreClient([exe, entry], env=env))
                   for label, exe in [('B', shutil.which('node')), ('C', args.bun)]}
        def invoke(label, action, **payload):
            started = time.perf_counter()
            if label == 'A':
                result = backend.run_lumi(action, **payload)
            else:
                result = clients[label].call({'action': action, 'data_dir': str(root / 'data'), **payload})
            report['measurements_ms'].setdefault('first_' + label + '_' + action,
                                                (time.perf_counter() - started) * 1000)
            return result
        def paired(action, **payload):
            results = [invoke(label, action, **payload) for label in ('A', 'B', 'C')]
            comparable = [canonical(value) for value in results]
            if comparable[0] != comparable[1] or comparable[1] != comparable[2]:
                (root / 'difference.json').write_text(json.dumps(comparable, indent=2), encoding='utf-8')
                raise AssertionError(f'{action} differs; see {root / "difference.json"}')
            return results
        for action, payload in [('catalog', {}), ('discover', {'query': '', 'offset': 0, 'limit': 100}),
                                ('schema', {'machine_name': 'H5P.TrueFalse', 'major_version': 1, 'minor_version': 8})]:
            started = time.perf_counter()
            paired(action, **payload)
            report['measurements_ms']['first_' + action + '_ABC'] = (time.perf_counter() - started) * 1000
        for index, example in enumerate(examples):
            activity = Activity(title=f'F3 fixture {index}', language='es', **example).model_dump()
            prepared = paired('prepare', activity=activity)
            assert all(item['ok'] for item in prepared), prepared
            packages = []
            for label, prepared_value in zip(('A', 'B', 'C'), prepared):
                output = root / f'{label}-{index}.h5p'
                invoke(label, 'export', activity=prepared_value['activity'], path=str(output))
                packages.append(package_contents(output))
                assert invoke(label, 'validate', path=str(output))['ok']
            assert packages[0] == packages[1] == packages[2], f'Package parity {index}'
            report['checks'][example['library'] + ':' + str(index)] = 'prepare/export/empty-import parity'
            print(f'Parity fixture {index + 1}/{len(examples)} passed', flush=True)
        for params in ({}, {'question': 'Q', 'correct': True}, {'question': 'Q', 'unknown': 1}):
            result = paired('prepare', activity=Activity(title='Invalid', library='H5P.TrueFalse 1.8', params=params).model_dump())
            assert not result[0]['ok']
        report['checks']['negative_diagnostics'] = 'passed'
        activity = Activity(title='Benchmark', **examples[0]).model_dump()
        for label in ('B', 'C'):
            prepared = invoke(label, 'prepare', activity=activity)['activity']
            prepared['preparation']['libraries'][prepared['library']]['patch'] = -1
            output = root / f'{label}-stale.h5p'
            try:
                invoke(label, 'export', activity=prepared, path=str(output))
            except backend.BackendError as error:
                assert error.code == 'STALE_PREPARATION'
            else:
                raise AssertionError('Stale preparation accepted')
            assert not output.exists()
            lock = root / 'data/.core-lock'
            lock.mkdir()
            try:
                try:
                    clients[label].call({'action': 'catalog', 'data_dir': str(root / 'data')},
                                        deadline=time.monotonic() + .1)
                except backend.BackendError as error:
                    assert error.code == 'BACKEND_TIMEOUT'
                else:
                    raise AssertionError('Lock deadline ignored')
                assert lock.is_dir()
            finally:
                lock.rmdir()
            assert invoke(label, 'catalog')['libraries']
        report['checks']['stale_cleanup_and_cancel_recovery'] = 'passed'
        if args.benchmark:
            for label in ('A', 'B', 'C'):
                report['measurements_ms'][label] = {}
                for action, payload in [('catalog', {}), ('schema', {'machine_name': 'H5P.TrueFalse'}),
                                         ('prepare', {'activity': activity})]:
                    timings = []
                    for _ in range(20):
                        started = time.perf_counter()
                        invoke(label, action, **payload)
                        timings.append((time.perf_counter() - started) * 1000)
                    report['measurements_ms'][label][action] = {'median': statistics.median(timings),
                        'p95': sorted(timings)[18], 'samples': len(timings)}
                for count in (10, 100):
                    started = time.perf_counter()
                    for index in range(count):
                        invoke(label, 'export', activity=activity, path=str(root / f'{label}-batch-{count}-{index}.h5p'))
                    report['measurements_ms'][label][f'batch_{count}'] = (time.perf_counter() - started) * 1000
                    print(f'Benchmark {label} batch {count} complete', flush=True)
                    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    report['status'] = 'passed'
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'report': str(args.output), 'artifacts': str(root)}))


if __name__ == '__main__':
    main()
