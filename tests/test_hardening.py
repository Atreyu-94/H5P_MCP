"""Offline regressions: no Lumi installation or personal cache required."""
import subprocess
from zipfile import ZipFile

import pytest

from h5p_mcp.lumi_backend import SOURCE
from h5p_mcp.validators.quiz_validator import validate_h5p_package


def test_semantic_budgets_and_identity():
    script = r'''
const assert = require('node:assert/strict');
const {scalarErrors} = require(process.argv[1]+'/semantics.cjs');
const {prepareActivity} = require(process.argv[1]+'/authoring.cjs');
const {containsLatex} = require(process.argv[1]+'/math.cjs');
assert.equal(scalarErrors({type:'text',regexp:{pattern:'^a+$'}}, 'bbb').length,1);
assert.equal(scalarErrors({type:'text',widget:'html',maxLength:1}, '<p>abc</p>').length,0);
for (const [value, expected] of [[1.2345,1],[1.23,0],[1e-7,1],[1e3,0]])
  assert.equal(scalarErrors({type:'number',decimals:2},value).length,expected);
let deep = 'x'; for(let i=0;i<1000;i++) deep={a:deep};
assert.throws(()=>containsLatex(deep), {code:'INPUT_TOO_DEEP'});
const fields=[{name:'items',type:'list',field:{type:'library',options:['Test.Child 1.0']}}];
const editor={config:{coreApiVersion:{major:1,minor:28}},libraryManager:{
 getLibrary:async()=>({runnable:1}), getSemantics:async(v)=>v.machineName==='Test.Main'?fields:[{name:'text',type:'text'}]}};
(async()=>{
 const make = id=>({library:'Test.Child 1.0',params:{text:'ok'},...(id===undefined?{}:{subContentId:id})});
 const run = items=>prepareActivity(editor,{library:'Test.Main 1.0',params:{items}},{});
 assert.equal((await run([make(42)])).diagnostics[0].code,'INVALID_SUBCONTENT_ID');
 const id='12345678-1234-1234-1234-123456789abc';
 assert.equal((await run([make(id),make(id)])).diagnostics[0].code,'DUPLICATE_SUBCONTENT_ID');
 const first=await run([make()]); assert.equal(first.ok,true);
 const second=await prepareActivity(editor,first.activity,{});
 assert.deepEqual(first.activity,second.activity);
 const bad=await prepareActivity(editor,{library:'Test.Main 1.0',params:deep},{});
 assert.equal(bad.diagnostics[0].code,'INPUT_TOO_DEEP');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node', '-e', script, str(SOURCE)], check=True, timeout=20)


@pytest.mark.parametrize('case', ['duplicate', 'oversize', 'traversal'])
def test_zip_rejected_before_backend(tmp_path, monkeypatch, case):
    monkeypatch.setenv('H5P_MCP_MAX_JSON_BYTES', '20')
    package = tmp_path / 'bad.h5p'
    with ZipFile(package, 'w') as archive:
        archive.writestr('h5p.json', '{}' if case != 'oversize' else ' ' * 21)
        archive.writestr('content/content.json', '{}')
        if case == 'duplicate':
            with pytest.warns(UserWarning):
                archive.writestr('h5p.json', '{}')
        if case == 'traversal':
            archive.writestr('../escape', 'bad')
    report = validate_h5p_package(package)
    assert not report.ok
    assert any(word in ' '.join(report.errors) for word in ['Duplicate', 'budget', 'Unsafe'])


def test_backend_deadline_and_details(tmp_path, monkeypatch):
    from h5p_mcp import lumi_backend as backend
    (tmp_path / '.ready').touch()
    monkeypatch.setattr(backend, 'SOURCE', tmp_path)
    monkeypatch.setattr(backend, 'runtime_dir', lambda: tmp_path)
    monkeypatch.setenv('H5P_MCP_MAX_SECONDS', '1')
    bridge = tmp_path / 'bridge.cjs'
    bridge.write_text('setInterval(()=>{},1000)')
    with pytest.raises(backend.BackendError) as error:
        backend._invoke('test')
    assert error.value.code == 'BACKEND_TIMEOUT'
    bridge.write_text("process.stdout.write(JSON.stringify({code:'TEST_ERROR',errors:['test'],details:{field:'x'}}));process.exitCode=1")
    with pytest.raises(backend.BackendError) as error:
        backend._invoke('test')
    assert error.value.details == {'field':'x'}


def test_batch_budget_precedes_export(monkeypatch):
    from h5p_mcp.server import export_h5p_batch
    monkeypatch.setenv('H5P_MCP_MAX_BATCH', '1')
    with pytest.raises(ValueError, match='BATCH_TOO_LARGE'):
        export_h5p_batch([{}, {}])
