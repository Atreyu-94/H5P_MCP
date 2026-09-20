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
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo))
    from h5p_mcp.lumi_backend import SOURCE, setup_lumi, run_lumi
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
              'measurements': {}, 'not_measured': ['OS page-cache cold start', 'process-tree peak RSS', 'handles', 'contended lock wait', 'persistent Node/Bun (not implemented)', 'batch 100 with override']}
    def measure(name, count, function):
        samples = []
        for i in range(count):
            start = time.perf_counter()
            function(i)
            samples.append((time.perf_counter() - start) * 1000)
        report['measurements'][name] = {'samples_ms': samples, 'median_ms': statistics.median(samples),
            'p95_ms': sorted(samples)[math.ceil(count * .95) - 1]}
        print(name, round(statistics.median(samples), 2), flush=True)
    with tempfile.TemporaryDirectory(prefix='h5p-baseline-') as temporary:
        root = Path(temporary)
        os.environ['H5P_MCP_DATA_DIR'] = str(root / 'data')
        os.environ['H5P_MCP_EXPORT_DIR'] = str(root / 'exports')
        fixture = repo / 'tests/fixtures/libraries.zip'
        assert digest(fixture) == json.loads((fixture.parent / 'libraries.lock.json').read_text())['sha256']
        with ZipFile(fixture) as archive:
            archive.extractall(root / 'data/libraries')
        measure('setup_clean_npm_cache_uncontrolled', 1, lambda _: setup_lumi())
        measure('setup_ready', 1, lambda _: setup_lumi())
        measure('catalog_first_after_setup', 1, lambda _: run_lumi('catalog'))
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
