"""Contracts exercised through the MCP client, including operational failures."""
import asyncio
from importlib.resources import files
import json
import subprocess

from fastmcp import Client
from jsonschema import Draft202012Validator
import pytest

from h5p_mcp.contracts import diagnostic, pointer, schema
from h5p_mcp.lumi_backend import BackendError
from h5p_mcp.server import mcp


def call(arguments):
    async def run():
        async with Client(mcp) as client:
            return await client.call_tool('prepare_h5p_activity', arguments, raise_on_error=False)
    return asyncio.run(run())


def payload(result):
    data = result.structured_content
    Draft202012Validator(schema('preparation_report')).validate(data)
    return data


def test_contract_authority_and_resources():
    async def run():
        async with Client(mcp) as client:
            tool = next(t for t in await client.list_tools() if t.name == 'prepare_h5p_activity')
            assert tool.input_schema == schema('prepare_local_input')
            assert tool.output_schema == schema('preparation_report')
            resource = await client.read_resource('h5p-contract://v1/schema')
            assert json.loads(resource[0].text) == json.loads(files('h5p_mcp.contracts').joinpath('v1.json').read_text())
    asyncio.run(run())
    for name in ('diagnostic', 'prepare_local_input', 'preparation_report'):
        Draft202012Validator.check_schema(schema(name))


def test_valid_preparation_preserves_exportable_activity():
    result = call({'title': 'Contract', 'library': 'H5P.TrueFalse 1.8', 'params': {'question': 'True?', 'correct': 'true'}})
    data = payload(result)
    assert not result.is_error and data['ok']
    assert data['activity']['preparation']
    assert data['activity']['params']['correct'] == 'true'
    assert data['verification']['playback'] == 'not_run'
    assert data['verification']['grading'] == 'not_run'


def test_invalid_semantics_is_report_not_execution_error():
    result = call({'title': 'Bad field', 'library': 'H5P.TrueFalse 1.8', 'params': {'question': 'True?', 'correct': 'secret-answer'}})
    data = payload(result)
    assert not result.is_error and not data['ok'] and data['kind'] == 'validation'
    assert data['activity'] is None
    assert any(d['pointer'] == '/params/correct' for d in data['diagnostics'])
    assert 'secret-answer' not in json.dumps(data)


def test_pointer_escaping_from_real_semantic_walker():
    field = 'dot.name[0]/~part'
    result = call({'title': 'Pointer', 'library': 'H5P.TrueFalse 1.8', 'params': {'question': 'True?', 'correct': 'true', field: 'secret'}})
    assert any(d['pointer'] == pointer(['params', field]) for d in payload(result)['diagnostics'])


@pytest.mark.parametrize('arguments, location', [
    ({'title': 'Missing', 'library': 'H5P.TrueFalse 1.8'}, '/params'),
    ({'title': 42, 'library': 'H5P.TrueFalse 1.8', 'params': {}}, '/title'),
    ({'title': 'No coercion', 'library': 'H5P.TrueFalse 1.8', 'params': {}, 'unexpected': True}, ''),
])
def test_input_contract_rejects_before_backend(monkeypatch, arguments, location):
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid input must not reach the backend')
    monkeypatch.setattr('h5p_mcp.server.run_lumi', forbidden)
    result = call(arguments)
    assert not result.is_error
    assert payload(result)['diagnostics'][0]['pointer'] == location


@pytest.mark.parametrize('code,retryable', [('BACKEND_TIMEOUT', True), ('BACKEND_ERROR', False)])
def test_operational_failure_retains_safe_details(monkeypatch, code, retryable):
    def broken(*args, **kwargs):
        raise BackendError('C:/private/password=secret', code, [
            {'code': 'INVALID_PARAMETER', 'pointer': '/params/question', 'message': 'secret'}])
    monkeypatch.setattr('h5p_mcp.server.run_lumi', broken)
    result = call({'title': 'Error', 'library': 'H5P.TrueFalse 1.8', 'params': {}})
    data = payload(result)
    assert result.is_error and data['kind'] == 'operational_error'
    assert data['diagnostics'][0]['retryable'] is retryable
    assert data['diagnostics'][1]['pointer'] == '/params/question'
    assert 'secret' not in json.dumps(data)


def test_diagnostics_bounded_without_returning_material():
    params = {f'unknown{i}': 'secret' * 1000 for i in range(120)}
    result = call({'title': 'Bounded', 'library': 'H5P.TrueFalse 1.8', 'params': params})
    data = payload(result)
    assert len(data['diagnostics']) == 100 and data['diagnostics_truncated']
    assert 'secret' not in json.dumps(data)


def test_code_map_is_closed_and_versioned():
    codes = json.loads(files('h5p_mcp.contracts').joinpath('codes-v1.json').read_text())
    assert codes['version'] == '1'
    assert set(codes['codes']) == set(schema('diagnostic')['properties']['code']['enum'])
    for code in [*codes['codes'], *codes['aliases'], 'unknown']:
        Draft202012Validator(schema('diagnostic')).validate(diagnostic(code))


def test_javascript_and_python_pointer_agree():
    module = str(files('h5p_mcp').joinpath('lumi/diagnostics.cjs'))
    parts = ['params', 'a.b[0]/~', 1, '', '~1']
    result = subprocess.run(['node', '-e', 'const d=require(process.argv[1]);process.stdout.write(d.pointer(JSON.parse(process.argv[2])))', module, json.dumps(parts)],
                            check=True, capture_output=True, text=True)
    assert result.stdout == pointer(parts)
