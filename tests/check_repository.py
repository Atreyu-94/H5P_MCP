"""Guard the Git index, not ignored developer data or disposable test output."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import subprocess

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git', '-c', f'safe.directory={root.as_posix()}',
                                'ls-files', '-z'], cwd=root).decode().split('\0')
provenance = json.loads((root/'h5p_mcp/lumi/provenance.json').read_text())
allowed = {
    'tests/fixtures/libraries.zip': json.loads((root/'tests/fixtures/libraries.lock.json').read_text())['sha256'],
    'h5p_mcp/lumi/'+provenance['archive']: provenance['sha256'],
}
errors = []
for name in filter(None, files):
    path = PurePosixPath(name)
    if set(path.parts) & {'node_modules', '__pycache__', '.venv', 'dist', 'exports'} or path.suffix in {'.pyc', '.pyo', '.h5p'}:
        errors.append(name)
    if path.suffix in {'.zip', '.tgz', '.gz', '.whl'}:
        if name not in allowed or hashlib.sha256((root/name).read_bytes()).hexdigest() != allowed[name]:
            errors.append(name)
if errors:
    raise SystemExit('Unapproved tracked artifacts: '+', '.join(errors))
print('Tracked artifact guard passed; only checksum-locked library fixtures and Lumi tarball allowed.')
