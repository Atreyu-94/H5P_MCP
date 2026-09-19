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
    image = tmp_path / 'image.png'
    image.write_bytes(b'original')
    report = create_h5p_activity('Image', 'H5P.TrueFalse 1.8',
        {'question':'Q', 'media':{'type':{'library':'H5P.Image 1.1','params':{'file':{'path':'asset:picture','mime':'image/png'}, 'alt':'test'}}}},
        assets={'picture':str(image)})
    assert report['ok'], report
    image.write_bytes(b'changed')
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
