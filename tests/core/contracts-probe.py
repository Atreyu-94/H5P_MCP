"""Compare the ported compact native projection with the Python authority."""
import json
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
from h5p_mcp.contracts.discovery import compact_contract

libraries = Path(sys.argv[1])
raw = []
for source in sorted(libraries.glob('*/semantics.json')):
    metadata = json.loads(source.with_name('library.json').read_text(encoding='utf-8'))
    raw.append({'library': f"{metadata['machineName']} {metadata['majorVersion']}.{metadata['minorVersion']}",
                'patch_version': metadata['patchVersion'], 'core': '1.28', 'metadata': metadata,
                'semantics': json.loads(source.read_text(encoding='utf-8'))})
assert raw, 'Empty semantic corpus'
code = """
import {projectSemantics} from './dist/core/domain/contracts.js';
let input='';
for await (const chunk of process.stdin) input+=chunk;
console.log(JSON.stringify(JSON.parse(input).map(item=>projectSemantics(item.semantics))));
"""
result = subprocess.check_output(['node', '--input-type=module', '-e', code], cwd=repo,
                                 input=json.dumps(raw).encode(), timeout=30)
for source, projected in zip(raw, json.loads(result), strict=True):
    expected = compact_contract(source)
    assert projected == {key: expected[key] for key in ('fields', 'sublibraries')}, source['library']
print(json.dumps({'native_contracts_compared': len(raw), 'status': 'passed'}))
