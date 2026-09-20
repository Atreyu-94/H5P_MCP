"""F2 end-to-end contracts, evidence, artifacts and local/remote separation."""
import asyncio
import base64
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from fastmcp import Client
from jsonschema import Draft202012Validator
import pytest

from h5p_mcp import server
from h5p_mcp.contracts import OPERATIONS, schema
from h5p_mcp.contracts.operations import read_artifact
from h5p_mcp.lumi_backend import BackendError


def test_all_profiles_are_valid_and_remote_rejects_paths():
    for name in OPERATIONS['$defs']:
        Draft202012Validator.check_schema(schema(name))
    remote = OPERATIONS['remote']
    assert not remote['execution_supported']
    for name in remote['inputs'].values():
        validator = Draft202012Validator(schema(name))
        assert not validator.is_valid({'path': 'C:/private/file.h5p'})
    assert not Draft202012Validator(schema('prepare_remote_input')).is_valid(
        {'title': 'x', 'library': 'H5P.TrueFalse 1.8', 'params': {}, 'assets': {'a': '/private/file'}})
    assert Draft202012Validator(schema('export_remote_input')).is_valid({'preparation_id': 'a' * 32})


def test_full_local_workflow_and_artifact_integrity(tmp_path, monkeypatch):
    monkeypatch.setenv('H5P_MCP_EXPORT_DIR', str(tmp_path))
    async def run():
        async with Client(server.mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            for name in ('export_h5p_activity', 'validate_h5p_package', 'search_h5p_types', 'get_h5p_type_contract'):
                assert tools[name].input_schema == schema(OPERATIONS['local'][name][0])
            catalog = (await client.call_tool('search_h5p_types', {'query': 'H5P.TrueFalse'})).structured_content
            evidence = catalog['activities'][0]['evidence'][0]
            assert evidence['structurally_authorable'] and len(evidence['schema_sha256']) == 64
            assert evidence['checked_at'] and evidence['checks']['playback'] == 'not_run'
            assert catalog['activities'][0]['authoring_supported'] == catalog['activities'][0]['structurally_authorable']
            activity = (await client.call_tool('prepare_h5p_activity', {'title': 'Unit', 'library': 'H5P.TrueFalse 1.8',
                        'params': {'question': '<p>True?</p>', 'correct': 'true'}})).structured_content['activity']
            exported = await client.call_tool('export_h5p_activity', {'activity': activity, 'output_name': 'unit'})
            assert exported.structured_content['ok'] and exported.content[0].type == 'resource_link'
            ref = exported.structured_content['artifact']
            assert ref['manifest']['preparation']
            binary = (await client.read_resource(ref['uri']))[0]
            content = base64.b64decode(binary.blob)
            assert len(content) == ref['size'] and sha256(content).hexdigest() == ref['sha256']
            assert 'blob' not in json.dumps(exported.structured_content)
            good = await client.call_tool('validate_h5p_package', {'path': str(tmp_path / 'unit.h5p')})
            assert good.structured_content['ok'] and good.structured_content['verification']['importation'] == 'passed'
            duplicate = await client.call_tool('export_h5p_activity', {'activity': activity, 'output_name': 'unit'}, raise_on_error=False)
            assert not duplicate.is_error and duplicate.structured_content['diagnostics'][0]['code'] == 'OUTPUT_ALREADY_EXISTS'
            (tmp_path / 'unit.h5p').write_bytes(b'changed')
            with pytest.raises(ValueError, match='changed'):
                read_artifact(ref['uri'].rsplit('/', 1)[1])
    asyncio.run(run())


def test_validation_negative_vs_operational_and_batch(tmp_path, monkeypatch):
    monkeypatch.setenv('H5P_MCP_EXPORT_DIR', str(tmp_path))
    archive = tmp_path / 'unsafe.h5p'
    with ZipFile(archive, 'w') as package:
        package.writestr('../bad', 'data')
    async def run():
        async with Client(server.mcp) as client:
            result = await client.call_tool('validate_h5p_package', {'path': str(archive)}, raise_on_error=False)
            assert not result.is_error and result.structured_content['diagnostics'][0]['code'] == 'UNSAFE_ARCHIVE'
            # A structurally valid ZIP must not turn an unavailable backend into invalid content.
            with ZipFile(archive, 'w') as package:
                package.writestr('h5p.json', json.dumps({'mainLibrary':'H5P.Test','preloadedDependencies':[{}]}))
                package.writestr('content/content.json', '{}')
            def unavailable(*args, **kwargs):
                raise BackendError('secret internal message', 'BACKEND_TIMEOUT')
            monkeypatch.setattr('h5p_mcp.validators.package_validator.run_lumi', unavailable)
            result = await client.call_tool('validate_h5p_package', {'path': str(archive)}, raise_on_error=False)
            assert result.is_error and result.structured_content['diagnostics'][0]['retryable']
            assert 'secret' not in json.dumps(result.structured_content)
            monkeypatch.setattr('h5p_mcp.exporters.h5p_exporter.run_lumi', unavailable)
            batch = await client.call_tool('export_h5p_batch', {'activities':[{'title':'x','library':'H5P.TrueFalse 1.8','params':{}}]}, raise_on_error=False)
            assert batch.is_error and batch.structured_content['results'][0]['diagnostics'][0]['code'] == 'BACKEND_TIMEOUT'
    asyncio.run(run())


def test_resource_limits_and_unknown_ids(tmp_path, monkeypatch):
    from h5p_mcp.contracts.operations import register_artifact
    file = tmp_path / 'small.h5p'
    file.write_bytes(b'12345')
    ref = register_artifact(file, {})
    monkeypatch.setenv('H5P_MCP_MAX_RESOURCE_BYTES', '4')
    with pytest.raises(ValueError, match='RESOURCE_TOO_LARGE'):
        read_artifact(ref['uri'].rsplit('/', 1)[1])
    with pytest.raises(ValueError):
        read_artifact('../private')
    with pytest.raises(ValueError, match='unknown'):
        read_artifact('0' * 32)
