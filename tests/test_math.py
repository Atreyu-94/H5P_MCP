"""Math addon detection and self-contained package regression checks."""
import json
import subprocess
from zipfile import ZipFile

from h5p_mcp.lumi_backend import SOURCE
from h5p_mcp.server import create_h5p_activity
from h5p_mcp.models.activity import Activity
from h5p_mcp.exporters.h5p_exporter import H5PExporter
from h5p_mcp.validators.quiz_validator import validate_h5p_package


def test_math_detection_and_missing_addon():
    script = r'''
const {containsLatex,inspectMath}=require(process.argv[1]);
const assert=require('node:assert/strict');
(async()=>{
  for(const text of [String.raw`\(x\)`,String.raw`\[x\]`,'$$x$$'])
    assert.equal(containsLatex({nested:[{feedback:text}]}),true);
  for(const text of ['kg/m³','$5','ordinary text']) assert.equal(containsLatex(text),false);
  const manager={getLibrary:async()=>{throw Error('missing')}};
  assert.equal((await inspectMath(manager,{question:'text'})).detected,false);
  const missing=await inspectMath(manager,{question:String.raw`\(x\)`});
  assert.equal(missing.installed,false);
  assert.match(missing.error,/--lumi-package/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node', '-e', script, str(SOURCE / 'math.cjs')], check=True)


def test_nested_latex_exports_addon(tmp_path):
    report = create_h5p_activity('Math', 'H5P.Accordion 1.0', {'panels': [{
        'title': 'Density', 'content': {'library': 'H5P.AdvancedText 1.1',
        'params': {'text': r'<p>\(\rho=\frac{m}{V}\)</p>'}}}]})
    assert report['ok'], report
    assert report['mathematics']['installed']
    exported = H5PExporter(export_dir=str(tmp_path)).export(Activity.model_validate(report['activity']), output_name='math')
    with ZipFile(exported.output_path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        manifest = json.loads(archive.read('h5p.json'))
        assert sum(d['machineName'] == 'H5P.MathDisplay' for d in manifest['preloadedDependencies']) == 1
        assert any(n.startswith('H5P.MathDisplay-1.0/') and n.endswith('.js') for n in archive.namelist())
        assert r'\rho' in json.loads(archive.read('content/content.json'))['panels'][0]['content']['params']['text']
    assert validate_h5p_package(exported.output_path).ok


def test_plain_text_does_not_gain_math_dependency(tmp_path):
    activity = Activity(title='Plain', library='H5P.TrueFalse 1.8', params={'question':'Density uses kg/m³.'})
    result = H5PExporter(export_dir=str(tmp_path)).export(activity, output_name='plain')
    assert all(d['machineName'] != 'H5P.MathDisplay' for d in result.h5p_json['preloadedDependencies'])
    with ZipFile(result.output_path) as archive:
        assert not any(n.startswith('H5P.MathDisplay-') for n in archive.namelist())
