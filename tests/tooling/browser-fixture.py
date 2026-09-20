"""Create the grading fixture without using a developer's H5P library cache."""
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
root = Path(sys.argv[1]).resolve()
os.environ['H5P_MCP_DATA_DIR'] = str(root / 'data')
fixture = repo / 'tests/fixtures/libraries.zip'
expected = json.loads((fixture.parent / 'libraries.lock.json').read_text())['sha256']
assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected
with ZipFile(fixture) as archive:
    archive.extractall(root / 'data/libraries')
from h5p_mcp.lumi_backend import setup_lumi, runtime_dir
from h5p_mcp.exporters.h5p_exporter import H5PExporter
from h5p_mcp.models.activity import Activity

setup_lumi()
activity = Activity(title='Grading baseline', library='H5P.TrueFalse 1.8', params={
    'question': r'<p>\(1+1=2\)</p>', 'correct':'true',
    'behaviour': {'enableRetry':True,
        'feedbackOnCorrect': r'Correct: \(1+1=2\).',
        'feedbackOnWrong': r'Try again: \(1+1=2\).'},
})
result = H5PExporter(export_dir=str(root / 'packages')).export(activity, output_name='grading')
print(json.dumps({'runtime':str(runtime_dir()), 'packages':str(result.output_path.parent)}))
