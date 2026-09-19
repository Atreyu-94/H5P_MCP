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
