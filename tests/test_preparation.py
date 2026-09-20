import copy
import subprocess

import pytest

from h5p_mcp.server import create_h5p_activity
from h5p_mcp.models.activity import Activity
from h5p_mcp.exporters.h5p_exporter import H5PExporter
from h5p_mcp.lumi_backend import BackendError, SOURCE


def test_stale_manifest_blocks_publication(tmp_path):
    prepared = create_h5p_activity('Stable', 'H5P.TrueFalse 1.8', {'question':'True?'})
    assert prepared['ok']
    assert prepared['verification']['grading'] == 'not_run'
    activity = copy.deepcopy(prepared['activity'])
    activity['preparation']['libraries']['H5P.TrueFalse 1.8']['patch'] = -1
    with pytest.raises(BackendError, match='STALE_PREPARATION'):
        H5PExporter(export_dir=str(tmp_path)).export(Activity.model_validate(activity), output_name='stale')
    assert not list(tmp_path.glob('*.h5p'))


def test_manifest_compares_without_key_order():
    script = "const {sameManifest}=require(process.argv[1]); if(!sameManifest({a:1,b:{c:2}},{b:{c:2},a:1}))process.exit(1)"
    subprocess.run(['node','-e',script,str(SOURCE/'manifest.cjs')],check=True)


def test_changed_local_asset_blocks_export(tmp_path):
    import base64
    image = tmp_path / 'image.png'
    original = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0ioAAAAASUVORK5CYII=')
    image.write_bytes(original)
    report = create_h5p_activity('Image', 'H5P.TrueFalse 1.8',
        {'question':'Q', 'media':{'type':{'library':'H5P.Image 1.1','params':{'file':{'path':'asset:picture','mime':'image/png'}, 'alt':'test'}}}},
        assets={'picture':str(image)})
    assert report['ok'], report
    image.write_bytes(original + b'changed')
    with pytest.raises(BackendError, match='STALE_PREPARATION'):
        H5PExporter(export_dir=str(tmp_path)).export(Activity.model_validate(report['activity']), output_name='changed')
    assert not (tmp_path/'changed.h5p').exists()


def test_asset_root_and_size_policy(tmp_path, monkeypatch):
    import json
    image = tmp_path / 'image.png'
    image.write_bytes(b'12345')
    args = ('Image', 'H5P.TrueFalse 1.8', {'question':'Q', 'media':{'type':{'library':'H5P.Image 1.1','params':{'file':{'path':'asset:p','mime':'image/png'},'alt':'test'}}}})
    monkeypatch.setenv('H5P_MCP_MAX_ASSET_BYTES', '4')
    report = create_h5p_activity(*args, assets={'p':str(image)})
    assert not report['ok'] and 'budget' in ' '.join(report['errors'])
    monkeypatch.delenv('H5P_MCP_MAX_ASSET_BYTES')
    allowed = tmp_path/'allowed'
    allowed.mkdir()
    monkeypatch.setenv('H5P_MCP_ASSET_ROOTS', json.dumps([str(allowed)]))
    report = create_h5p_activity(*args, assets={'p':str(image)})
    assert not report['ok'] and 'authorized roots' in ' '.join(report['errors'])


@pytest.mark.parametrize('mime,data,error', [
    ('image/png', b'not an image', 'does not match'),
    ('image/svg+xml', b'<svg onload="alert(1)"></svg>', 'unsupported media MIME'),
    ('text/html', b'<script>alert(1)</script>', 'unsupported media MIME'),
])
def test_media_signature_and_active_content(tmp_path, mime, data, error):
    asset = tmp_path/'asset'
    asset.write_bytes(data)
    report = create_h5p_activity('Media', 'H5P.TrueFalse 1.8',
        {'question':'Q', 'media':{'type':{'library':'H5P.Image 1.1',
         'params':{'file':{'path':'asset:p','mime':mime},'alt':'test'}}}}, assets={'p':str(asset)})
    assert not report['ok'] and error in ' '.join(report['errors'])


def test_empty_asset_roots_deny_all(tmp_path, monkeypatch):
    asset = tmp_path/'asset.png'
    asset.write_bytes(b'anything')
    monkeypatch.setenv('H5P_MCP_ASSET_ROOTS', '[]')
    report = create_h5p_activity('Media', 'H5P.TrueFalse 1.8',
        {'question':'Q', 'media':{'type':{'library':'H5P.Image 1.1',
         'params':{'file':{'path':'asset:p','mime':'image/png'},'alt':'test'}}}}, assets={'p':str(asset)})
    assert not report['ok'] and 'authorized roots' in ' '.join(report['errors'])


def test_worker_extraction_enforces_budgets(tmp_path):
    from zipfile import ZipFile
    from h5p_mcp.lumi_backend import runtime_dir
    package = tmp_path/'package.zip'
    with ZipFile(package, 'w') as archive:
        archive.writestr('Library-1.0/library.json', '12345678')
    script = r'''
const assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const load=createRequire(process.argv[1]+'/package.json');
require(process.argv[2]+'/extraction.cjs').installBoundedExtraction(load);
const importer=load('@lumieducation/h5p-server/build/src/PackageImporter').default;
(async()=>{
 process.env.H5P_MCP_MAX_ZIP_MEMBER_BYTES='4';
 await assert.rejects(importer.extractPackage(process.argv[3],process.argv[4],{includeLibraries:true}),/budget/);
 delete process.env.H5P_MCP_MAX_ZIP_MEMBER_BYTES;
 await importer.extractPackage(process.argv[3],process.argv[4],{includeLibraries:true});
 assert.equal(require('node:fs').readFileSync(process.argv[4]+'/Library-1.0/library.json','utf8'),'12345678');
 await assert.rejects(importer.extractPackage(process.argv[3],process.argv[4],{includeLibraries:true}),/EEXIST/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e',script,str(runtime_dir()),str(SOURCE),str(package),str(tmp_path/'extracted')],check=True,timeout=15)
