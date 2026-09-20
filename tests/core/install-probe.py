"""Measure empty/reused package caches without claiming a cold OS cache."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--bun', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
root = Path(tempfile.mkdtemp(prefix='h5p-f3-installs-'))
report = {'scope': 'A: pinned legacy Lumi runtime; B/C: same frozen production core tree',
          'os_cache': 'not cleared', 'measurements_ms': {}, 'artifacts': str(root)}
for runtime in ('legacy', 'core'):
    cache = root / (runtime + '-cache')
    report['measurements_ms'][runtime] = {}
    for state in ('empty_package_cache', 'reused_package_cache'):
        target = root / (runtime + '-' + state)
        target.mkdir()
        if runtime == 'legacy':
            for name in ('package.json', 'package-lock.json', 'lumieducation-h5p-server-10.0.4-h5pmcp.efcfeebc.tgz'):
                shutil.copyfile(repo / 'h5p_mcp/lumi' / name, target / name)
            command = [shutil.which('npm.cmd' if os.name == 'nt' else 'npm'),
                       'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--cache', str(cache)]
            env = dict(os.environ)
        else:
            for name in ('package.json', 'bun.lock'):
                shutil.copyfile(repo / name, target / name)
            package_dir = target / 'h5p_mcp/lumi'
            package_dir.mkdir(parents=True)
            archive = 'lumieducation-h5p-server-10.0.4-h5pmcp.efcfeebc.tgz'
            shutil.copyfile(repo / 'h5p_mcp/lumi' / archive, package_dir / archive)
            command = [args.bun, 'install', '--production', '--frozen-lockfile', '--ignore-scripts']
            env = dict(os.environ, BUN_INSTALL_CACHE_DIR=str(cache))
        started = time.perf_counter()
        subprocess.run(command, cwd=target, env=env, check=True, timeout=300, stdout=subprocess.DEVNULL)
        report['measurements_ms'][runtime][state] = (time.perf_counter() - started) * 1000
args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
