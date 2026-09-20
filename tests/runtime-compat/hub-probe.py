"""Explicit online B0 probe; never uses the user's active library store."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--runtime-report', type=Path, required=True)
parser.add_argument('--bun', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo))
from h5p_mcp import lumi_backend as backend

reference = json.loads(args.runtime_report.read_text())
backend.runtime_dir = lambda: Path(reference['npm_runtime'])
root = Path(tempfile.mkdtemp(prefix='h5p-b0-hub-'))
report = {'artifacts':str(root), 'checks':{}, 'proxy':'not_run: no proxy support claimed'}
for label, executable in [('node',shutil.which('node')),('bun',args.bun)]:
    os.environ['H5P_MCP_DATA_DIR'] = str(root/label)
    os.environ['H5P_MCP_MAX_SECONDS'] = '90'
    backend._node = lambda executable=executable: executable
    try:
        discovery = backend.run_lumi('discover',query='Audio',installed_only=False,refresh=True,offset=0,limit=20)
        schema = backend.run_lumi('schema',machine_name='H5P.Audio',major_version=None,minor_version=None,install_if_missing=True)
        (root/f'{label}-audio-schema.json').write_text(json.dumps(schema,indent=2),encoding='utf8')
        report['checks'][label] = {'refresh':'passed','install':'passed','library':schema['library'],
                                  'patch':schema['patch_version'],'activities':len(discovery['activities'])}
    except Exception as error:
        report['checks'][label] = {'status':'failed','error':str(error)}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report))
