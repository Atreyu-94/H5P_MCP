"""Offline regressions: no Lumi installation or personal cache required."""
import subprocess
from zipfile import ZipFile
from zipfile import ZipInfo, ZIP_DEFLATED

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


@pytest.mark.parametrize('names', [
    ['../escape'], ['/absolute'], ['C:/drive'], ['folder/file:stream'],
    ['folder\\file'], ['folder//file'], ['folder/./file'], ['CON.txt'],
    ['folder/LPT1.png'], ['trailing.'], ['space '], ['A/x','a/y'],
    ['caf\u00e9/x','cafe\u0301/y'], ['content','content/file'],
    ['bad?name'], ['/'.join(['deep']*33)],
])
def test_portable_zip_paths_reject_before_import(tmp_path, monkeypatch, names):
    import h5p_mcp.validators.package_validator as validator
    monkeypatch.setattr(validator, 'run_lumi', lambda *a, **k: pytest.fail('Unsafe package reached importer'))
    path = tmp_path/'paths.h5p'
    with ZipFile(path,'w') as archive:
        for name in names:
            archive.writestr(name,'x')
    if names == ['folder\\file']:
        # Windows ZipInfo normalizes separators while writing. Preserve the raw
        # hostile name in both headers without changing lengths or data CRC.
        path.write_bytes(path.read_bytes().replace(b'folder/file',b'folder\\file'))
    result = validator.validate_h5p_package(path)
    assert not result.ok and 'Unsafe ZIP' in ' '.join(result.errors)


def test_zip_symlink_rejected(tmp_path):
    import stat
    path = tmp_path/'symlink.h5p'
    entry = ZipInfo('link')
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(path,'w') as archive:
        archive.writestr(entry,'../outside')
    assert 'symlink' in ' '.join(validate_h5p_package(path).errors)


def test_zip_ratio_and_archive_size_limits(tmp_path, monkeypatch):
    path = tmp_path/'compressed.h5p'
    with ZipFile(path,'w',compression=ZIP_DEFLATED) as archive:
        archive.writestr('large.txt',b'0'*100000)
    monkeypatch.setenv('H5P_MCP_MAX_ZIP_RATIO','10')
    assert 'ratio' in ' '.join(validate_h5p_package(path).errors)
    monkeypatch.setenv('H5P_MCP_MAX_ZIP_ARCHIVE_BYTES',str(path.stat().st_size-1))
    assert 'compressed byte' in ' '.join(validate_h5p_package(path).errors)


def test_zip_explicit_directories_and_size_boundary(tmp_path, monkeypatch):
    import json
    import h5p_mcp.validators.package_validator as validator
    monkeypatch.setattr(validator,'run_lumi',lambda *a,**k:{'errors':[],'warnings':[]})
    path = tmp_path/'valid.h5p'
    with ZipFile(path,'w') as archive:
        archive.writestr('content/','')
        archive.writestr('h5p.json',json.dumps({'mainLibrary':'Test','preloadedDependencies':[{}]}))
        archive.writestr('content/content.json','{}')
    monkeypatch.setenv('H5P_MCP_MAX_ZIP_ARCHIVE_BYTES',str(path.stat().st_size))
    assert validator.validate_h5p_package(path).ok
    monkeypatch.setenv('H5P_MCP_MAX_ZIP_ARCHIVE_BYTES',str(path.stat().st_size+1))
    assert validator.validate_h5p_package(path).ok


def test_zip_corrupt_member_rejected_before_import(tmp_path, monkeypatch):
    import h5p_mcp.validators.package_validator as validator
    monkeypatch.setattr(validator,'run_lumi',lambda *a,**k:pytest.fail('Corrupt data reached importer'))
    path = tmp_path/'corrupt.h5p'
    with ZipFile(path,'w') as archive:
        archive.writestr('asset.bin',b'payload')
    path.write_bytes(path.read_bytes().replace(b'payload',b'payloae'))
    result = validator.validate_h5p_package(path)
    assert not result.ok and 'CRC' in ' '.join(result.errors)


def test_administrative_archive_checked_before_runtime(tmp_path, monkeypatch):
    from h5p_mcp import lumi_backend as backend
    path = tmp_path/'libraries.zip'
    with ZipFile(path, 'w') as archive:
        archive.writestr('../escape', 'bad')
    monkeypatch.setattr(backend, '_node', lambda: pytest.fail('Runtime initialized before preflight'))
    with pytest.raises(ValueError, match='Unsafe ZIP'):
        backend.setup_lumi([str(path)])


def test_access_roots_resolve_and_deny_empty(tmp_path, monkeypatch):
    import json
    from h5p_mcp.utils.file_utils import authorized_path, resolve_export_dir
    allowed = tmp_path/'allowed'
    allowed.mkdir()
    for variable in ['H5P_MCP_PACKAGE_ROOTS', 'H5P_MCP_EXPORT_ROOTS']:
        monkeypatch.setenv(variable, json.dumps([str(allowed)]))
        assert authorized_path(allowed/'new', variable) == allowed/'new'
        with pytest.raises(ValueError):
            authorized_path(allowed/'..'/'outside', variable)
        monkeypatch.setenv(variable, '[]')
        with pytest.raises(ValueError):
            authorized_path(allowed, variable)
        monkeypatch.setenv(variable, '["relative"]')
        with pytest.raises(ValueError):
            authorized_path(allowed, variable)
    monkeypatch.setenv('H5P_MCP_EXPORT_ROOTS', json.dumps([str(allowed)]))
    with pytest.raises(ValueError):
        resolve_export_dir(str(tmp_path/'outside'))
    assert not (tmp_path/'outside').exists()


def test_backend_lock_consumes_deadline(tmp_path, monkeypatch):
    import time
    from filelock import FileLock
    from h5p_mcp import lumi_backend as backend
    monkeypatch.setattr(backend, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(backend, '_invoke', lambda *a, **kw: pytest.fail('Launched after lock deadline'))
    monkeypatch.setenv('H5P_MCP_MAX_SECONDS', '1')
    start = time.monotonic()
    with FileLock(str(tmp_path/'backend.lock')):
        with pytest.raises(backend.BackendError) as error:
            backend.run_lumi('export')
    assert error.value.code == 'BACKEND_TIMEOUT'
    assert time.monotonic()-start < 3


def test_publication_without_hardlinks_is_exclusive(tmp_path, monkeypatch):
    import errno
    from concurrent.futures import ThreadPoolExecutor
    from h5p_mcp.exporters import h5p_exporter as exporter
    def unavailable(*args):
        raise OSError(errno.ENOTSUP, 'No hardlinks')
    monkeypatch.setattr(exporter.os, 'link', unavailable)
    sources = [tmp_path/'a', tmp_path/'b']
    for source in sources:
        source.write_bytes(source.name.encode()*10000)
    target = tmp_path/'final.h5p'
    def publish(source):
        try:
            exporter.publish_exclusive(source, target)
            return source.name
        except FileExistsError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(publish, sources))
    winners = [result for result in results if result]
    assert len(winners) == 1
    assert target.read_bytes() == winners[0].encode()*10000


def test_manifest_dependency_budgets_and_cycles(tmp_path):
    script = r'''
const assert=require('node:assert/strict'), fs=require('node:fs');
const {preparationManifest}=require(process.argv[1]+'/manifest.cjs');
const root=process.argv[2];
for(const name of ['A','B','C']) fs.mkdirSync(root+'/'+name+'-1.0');
const dep=name=>({machineName:name,majorVersion:1,minorVersion:0});
let graph={A:['B'],B:['C'],C:[]};
const editor={libraryManager:{getLibrary:async lib=>({patchVersion:0,preloadedDependencies:graph[lib.machineName].map(dep)})}};
const run=()=>preparationManifest(editor,root,{library:'A 1.0',params:{}},{detected:false});
(async()=>{
  assert.equal(Object.keys((await run()).libraries).length,3);
  graph.C=['A']; await assert.rejects(run(),/Cyclic/); graph.C=[];
  process.env.H5P_MCP_MAX_DEPENDENCY_DEPTH='1'; await assert.rejects(run(),/depth/); delete process.env.H5P_MCP_MAX_DEPENDENCY_DEPTH;
  process.env.H5P_MCP_MAX_LIBRARIES='2'; await assert.rejects(run(),/node/); delete process.env.H5P_MCP_MAX_LIBRARIES;
  process.env.H5P_MCP_MAX_DEPENDENCY_EDGES='1'; await assert.rejects(run(),/edge/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node', '-e', script, str(SOURCE), str(tmp_path)], check=True, timeout=15)


@pytest.mark.parametrize('action', ['prepare', 'validate', 'export'])
def test_cancel_reaps_worker_and_removes_staging(tmp_path, monkeypatch, action):
    import anyio
    import tempfile
    import time
    from h5p_mcp import lumi_backend as backend
    from h5p_mcp.jobs import cancellable
    (tmp_path/'.ready').touch()
    (tmp_path/'bridge.cjs').write_text("require('node:fs').mkdirSync(require('node:path').join(require('node:os').tmpdir(),'child-staging'));setInterval(()=>{},1000)")
    monkeypatch.setattr(backend, 'SOURCE', tmp_path)
    monkeypatch.setattr(backend, 'runtime_dir', lambda: tmp_path)
    monkeypatch.setattr(backend, 'data_dir', lambda: tmp_path)
    children = []
    workspaces = []
    real_popen = backend.subprocess.Popen
    def launch(*args, **kwargs):
        workspaces.append(kwargs['env']['TMPDIR'])
        process = real_popen(*args, **kwargs)
        children.append(process)
        return process
    monkeypatch.setattr(backend.subprocess, 'Popen', launch)
    @cancellable
    def job():
        with tempfile.TemporaryDirectory(dir=tmp_path, prefix='staging-'):
            backend.run_lumi(action)
            pytest.fail('Cancelled worker returned successfully')
    async def exercise():
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(job)
                while not children:
                    await anyio.sleep(0.01)
                group.cancel_scope.cancel()
    start = time.monotonic()
    anyio.run(exercise)
    assert time.monotonic()-start < 5
    assert children and all(child.poll() is not None for child in children)
    assert not list(tmp_path.glob('staging-*'))
    from pathlib import Path
    assert all(not Path(work).exists() for work in workspaces)


def test_cancel_while_waiting_for_lock(tmp_path, monkeypatch):
    import anyio
    from filelock import FileLock
    from h5p_mcp import lumi_backend as backend
    from h5p_mcp.jobs import cancellable
    monkeypatch.setattr(backend, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(backend, '_invoke', lambda *a, **kw: pytest.fail('Cancelled queue launched worker'))
    async def exercise():
        with anyio.fail_after(3):
            async with anyio.create_task_group() as group:
                group.start_soon(cancellable(lambda: backend.run_lumi('export')))
                await anyio.sleep(0.2)
                group.cancel_scope.cancel()
    with FileLock(str(tmp_path/'backend.lock')):
        anyio.run(exercise)


def test_tool_deadline_is_not_reset_between_batch_operations(tmp_path, monkeypatch):
    import anyio
    import time
    from h5p_mcp import lumi_backend as backend
    from h5p_mcp.jobs import cancellable
    monkeypatch.setenv('H5P_MCP_MAX_SECONDS','1')
    monkeypatch.setattr(backend,'data_dir',lambda:tmp_path)
    calls=[]
    def invoke(*args,**kwargs):
        calls.append(1)
        time.sleep(0.15)
        return {}
    monkeypatch.setattr(backend,'_invoke',invoke)
    @cancellable
    def batch():
        for _ in range(50): backend.run_lumi('export')
    start=time.monotonic()
    with pytest.raises(RuntimeError,match='BACKEND_TIMEOUT'):
        anyio.run(batch)
    assert 1 < len(calls) < 12
    assert time.monotonic()-start < 2
