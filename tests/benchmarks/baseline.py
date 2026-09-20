"""Reproducible baseline A. Run with the repository Python environment."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import threading
from zipfile import ZipFile

import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--installation-only', action='store_true',
                        help='Measure isolated empty/cached npm installs without rerunning activity benchmarks')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo))
    from h5p_mcp.lumi_backend import SOURCE, setup_lumi, run_lumi
    import h5p_mcp.lumi_backend as backend
    from h5p_mcp.server import create_h5p_activity, export_h5p_batch
    from h5p_mcp.models.activity import Activity
    from h5p_mcp.exporters.h5p_exporter import H5PExporter
    from h5p_mcp.validators.package_validator import validate_h5p_package
    def git(*words):
        return subprocess.check_output(['git', '-c', f'safe.directory={repo.as_posix()}', *words], cwd=repo, text=True).strip()
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    tracked = git('ls-files').splitlines()
    provenance = json.loads((SOURCE / 'provenance.json').read_text())
    with tarfile.open(SOURCE / provenance['archive']) as archive:
        names = archive.getnames()
        package = json.load(archive.extractfile('package/package.json'))
        licenses = [n for n in names if 'license' in n.lower() or 'copying' in n.lower()]
    report = {'head': git('rev-parse', 'HEAD'), 'tree': git('status', '--short'),
              'remote': git('remote', 'get-url', 'origin'), 'platform': platform.platform(),
              'python': sys.version, 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
              'checksums': {p: digest(repo / p) for p in tracked if p.startswith('h5p_mcp/lumi/') or p.startswith('tests/fixtures/')},
              'legacy_exports': {p: digest(repo / p) for p in tracked if p.startswith('h5p_mcp/exports/')},
              'lumi_archive': {'license': package.get('license'), 'version': package['version'], 'license_files': licenses,
                               'source_files': sum(n.startswith('package/src/') for n in names)},
              'harness_sha256': digest(Path(__file__)), 'psutil': psutil.__version__,
              'sampling_interval_ms': 10,
              'measurements': {}, 'not_measured': ['OS page-cache cold start', 'persistent Node/Bun (not implemented)']}
    # Test-process instrumentation only; do not change production lock behavior.
    original_lock = backend.FileLock
    waits = []
    class MeasuredLock(original_lock):
        def acquire(self, *args, **kwargs):
            start = time.perf_counter()
            result = super().acquire(*args, **kwargs)
            waits.append((time.perf_counter() - start) * 1000)
            return result
    backend.FileLock = MeasuredLock
    def measure(name, count, function):
        samples = []
        resources = []
        for i in range(count):
            stop = threading.Event()
            peak = {'rss_bytes': 0, 'handles_or_fds': 0}
            process = psutil.Process()
            def sample():
                while not stop.is_set():
                    rss = handles = 0
                    for member in [process, *process.children(recursive=True)]:
                        try:
                            rss += member.memory_info().rss
                            handles += member.num_handles() if os.name == 'nt' else member.num_fds()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    peak['rss_bytes'] = max(peak['rss_bytes'], rss)
                    peak['handles_or_fds'] = max(peak['handles_or_fds'], handles)
                    stop.wait(.01)
            thread = threading.Thread(target=sample, daemon=True)
            wait_offset = len(waits)
            thread.start()
            try:
                start = time.perf_counter()
                function(i)
                samples.append((time.perf_counter() - start) * 1000)
            finally:
                stop.set()
                thread.join()
            peak['lock_acquire_ms'] = sum(waits[wait_offset:])
            resources.append(peak)
        report['measurements'][name] = {'samples_ms': samples, 'median_ms': statistics.median(samples),
            'p95_ms': sorted(samples)[math.ceil(count * .95) - 1], 'resources': resources}
        print(name, round(statistics.median(samples), 2), flush=True)
    with tempfile.TemporaryDirectory(prefix='h5p-baseline-') as temporary:
        root = Path(temporary)
        # A new npm cache gives a controlled cold dependency installation without
        # deleting the user's cache or pretending to flush the OS page cache.
        cache = root / 'npm-cache'
        cache.mkdir()
        assert not list(cache.iterdir())
        os.environ['npm_config_cache'] = str(cache)
        os.environ['npm_config_offline'] = 'false'
        os.environ['H5P_MCP_DATA_DIR'] = str(root / 'data')
        os.environ['H5P_MCP_EXPORT_DIR'] = str(root / 'exports')
        fixture = repo / 'tests/fixtures/libraries.zip'
        assert digest(fixture) == json.loads((fixture.parent / 'libraries.lock.json').read_text())['sha256']
        with ZipFile(fixture) as archive:
            archive.extractall(root / 'data/libraries')
        measure('setup_empty_npm_cache', 1, lambda _: setup_lumi())
        report['installation'] = {'initial_npm_cache': 'empty_unique_directory',
                                  'scripts': 'disabled', 'cached_install_offline': True,
                                  'runtime_directories': 'distinct', 'os_page_cache': 'uncontrolled'}
        cached_data = root / 'data-cached'
        os.environ['H5P_MCP_DATA_DIR'] = str(cached_data)
        os.environ['npm_config_offline'] = 'true'
        with ZipFile(fixture) as archive:
            archive.extractall(cached_data / 'libraries')
        measure('setup_cached_npm_offline_new_runtime', 1, lambda _: setup_lumi())
        measure('setup_ready', 1, lambda _: setup_lumi())
        measure('catalog_first_after_setup', 1, lambda _: run_lumi('catalog'))
        if args.installation_only:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            return
        measure('catalog', 20, lambda _: run_lumi('catalog'))
        measure('schema', 20, lambda _: run_lumi('schema', machine_name='H5P.TrueFalse', major_version=1, minor_version=8))
        def prepare(_):
            value = create_h5p_activity('Baseline', 'H5P.TrueFalse 1.8', {'question': '<p>Two is even.</p>', 'correct': 'true'})
            assert value['ok'], value
            return value
        measure('prepare', 20, prepare)
        activity = Activity.model_validate(prepare(0)['activity'])
        exporter = H5PExporter(export_dir=str(root / 'exports'))
        measure('export', 5, lambda i: exporter.export(activity, output_name=f'baseline-{i}'))
        package_path = root / 'exports/baseline-0.h5p'
        report['export_bytes'] = package_path.stat().st_size
        def validate(_):
            value = validate_h5p_package(package_path)
            assert value.ok, value.errors
        measure('import_fresh', 5, validate)
        def batch(_):
            value = export_h5p_batch([activity] * 10, name_prefix='baseline-batch')
            assert value['succeeded'] == 10, value
        measure('batch_10', 1, batch)
        try:
            export_h5p_batch([activity] * 100)
        except ValueError as error:
            assert 'BATCH_TOO_LARGE' in str(error)
            report['batch_100_default'] = 'rejected'
        else:
            raise AssertionError('Batch limit not enforced')
        os.environ['H5P_MCP_MAX_BATCH'] = '100'
        def large_batch(_):
            value = export_h5p_batch([activity] * 100, name_prefix='baseline-large')
            assert value['succeeded'] == 100, value
        measure('batch_100_override', 1, large_batch)
        report['batch_100_override'] = {'H5P_MCP_MAX_BATCH': 100, 'succeeded': 100}
        # Synchronize with an independent lock owner; timeout rather than hang.
        lock_path = cached_data / 'backend.lock'
        signal = root / 'lock-ready'
        code = ('import sys,time; from pathlib import Path; from filelock import FileLock; '
                'lock=FileLock(sys.argv[1]); lock.acquire(); Path(sys.argv[2]).touch(); '
                'time.sleep(1); lock.release()')
        owner = subprocess.Popen([sys.executable, '-c', code, str(lock_path), str(signal)])
        try:
            deadline = time.monotonic() + 15
            while not signal.exists():
                if owner.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Lock owner failed to become ready')
                time.sleep(.01)
            measure('catalog_contended_lock', 1, lambda _: run_lumi('catalog'))
            owner.wait(timeout=15)
            assert owner.returncode == 0
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
