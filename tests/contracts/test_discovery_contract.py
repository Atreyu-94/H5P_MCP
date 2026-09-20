"""Differential coverage against the pinned native semantics corpus."""
import asyncio
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from zipfile import ZipFile

from fastmcp import Client
import pytest

from h5p_mcp.contracts import discovery
from h5p_mcp.server import mcp, get_h5p_type_contract, get_h5p_activity_schema, create_h5p_activity


def test_differential_projection_of_entire_fixture_corpus():
    fixture = Path(__file__).resolve().parents[1] / 'fixtures' / 'libraries.zip'
    checked = 0
    with ZipFile(fixture) as archive:
        for name in archive.namelist():
            if not name.endswith('/semantics.json'):
                continue
            metadata = json.loads(archive.read(name.rsplit('/', 1)[0] + '/library.json'))
            raw = {'library': f"{metadata['machineName']} {metadata['majorVersion']}.{metadata['minorVersion']}",
                   'patch_version': metadata['patchVersion'], 'core': '1.28',
                   'semantics': json.loads(archive.read(name)), 'metadata': metadata}
            original = deepcopy(raw)
            contract = discovery.compact_contract(raw)
            assert raw == original
            assert len(contract['fields']) == len(raw['semantics'])
            stack = list(zip(contract['fields'], raw['semantics']))
            while stack:
                field, native = stack.pop()
                assert field['name'] == native.get('name')
                assert field['type'] == native['type']
                assert field['required'] == (not native.get('optional', False))
                assert ('default' in field) == ('default' in native)
                if 'default' in native:
                    assert field['default'] == native['default']
                for constraint in ('min', 'max', 'decimals', 'regexp', 'maxLength', 'options', 'multiple'):
                    assert (constraint in field.get('constraints', {})) == (constraint in native)
                    if constraint in native:
                        assert field['constraints'][constraint] == native[constraint]
                if native['type'] == 'group':
                    assert len(field['fields']) == len(native['fields'])
                    assert field['value_shape'] == ('single_field' if len(native['fields']) == 1 else 'object')
                    stack.extend(zip(field['fields'], native['fields']))
                if native['type'] == 'list':
                    stack.append((field['field'], native['field']))
                if 'widget' in native:
                    assert field['x-h5p']['widget'] == native['widget']
            checked += 1
    assert checked == 9  # All semantics.json files in the checksum-pinned corpus.


def test_contract_matches_real_preparation_rules():
    contract = get_h5p_type_contract('H5P.TrueFalse', 1, 8)
    assert len(discovery.encode(contract)) < contract['raw_schema']['size']
    correct = next(field for field in contract['fields'] if field['name'] == 'correct')
    allowed = [option['value'] for option in correct['constraints']['options']]
    assert allowed == ['true', 'false']
    for value in [*allowed, True, 'invalid']:
        result = create_h5p_activity('Check', contract['library'], {'question': '<p>Question?</p>', 'correct': value})
        assert result['ok'] == (isinstance(value, str) and value in allowed)
    accordion = get_h5p_type_contract('H5P.Accordion', 1, 0)
    assert 'H5P.AdvancedText 1.1' in accordion['sublibraries']
    panels = next(field for field in accordion['fields'] if field['name'] == 'panels')
    assert panels['constraints']['min'] == 1
    assert not create_h5p_activity('Empty', accordion['library'], {'panels': []})['ok']


def test_published_examples_prepare():
    examples = json.loads(files('h5p_mcp.contracts').joinpath('examples-v1.json').read_text())
    assert examples
    for example in examples:
        name, version = example['library'].split(' ')
        major, minor = map(int, version.split('.'))
        contract = get_h5p_type_contract(name, major, minor)
        assert any(item['params'] == example['params'] for item in contract['examples'])
        result = create_h5p_activity(example['title'], example['library'], example['params'])
        assert result['ok'], result


def test_examples_not_claimed_for_changed_semantics_or_patch():
    raw = get_h5p_activity_schema('H5P.TrueFalse', 1, 8)
    assert discovery.compact_contract(raw)['examples']
    changed = deepcopy(raw)
    changed['patch_version'] += 1
    assert not discovery.compact_contract(changed)['examples']
    raw['semantics'][0]['description'] = 'changed source'
    assert not discovery.compact_contract(raw)['examples']


def test_mcp_resource_integrity_and_no_path_access():
    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool('get_h5p_type_contract', {'machine_name': 'H5P.TrueFalse', 'major_version': 1, 'minor_version': 8})
            ref = result.data['raw_schema']
            content = (await client.read_resource(ref['uri']))[0].text.encode('utf-8')
            assert len(content) == ref['size']
            assert sha256(content).hexdigest() == ref['sha256']
            raw = json.loads(content)
            assert raw['library'] == result.data['library']
            assert raw['semantics']
    asyncio.run(run())
    for invalid in ['../config.json', 'A' * 64, '', 'f' * 63]:
        with pytest.raises(ValueError, match='Invalid schema digest'):
            discovery.read_snapshot(invalid)


def test_snapshots_are_bounded_and_preserve_old_bytes(monkeypatch):
    monkeypatch.setattr(discovery, '_snapshots', discovery.OrderedDict())
    monkeypatch.setenv('H5P_MCP_MAX_SCHEMA_SNAPSHOTS', '2')
    first = discovery.snapshot({'value': 1})
    second = discovery.snapshot({'value': 2})
    assert json.loads(discovery.read_snapshot(first['sha256'])) == {'value': 1}
    discovery.snapshot({'value': 3})
    with pytest.raises(ValueError, match='UNAVAILABLE'):
        discovery.read_snapshot(first['sha256'])
    assert json.loads(discovery.read_snapshot(second['sha256'])) == {'value': 2}
    monkeypatch.setenv('H5P_MCP_MAX_SCHEMA_BYTES', '4')
    with pytest.raises(ValueError, match='SCHEMA_TOO_LARGE'):
        discovery.snapshot({'large': 'value'})
    with pytest.raises(ValueError, match='SCHEMA_TOO_LARGE'):
        discovery.read_snapshot(second['sha256'])
    monkeypatch.setenv('H5P_MCP_MAX_SCHEMA_BYTES', '1000')
    monkeypatch.setenv('H5P_MCP_MAX_SCHEMA_CACHE_BYTES', '4')
    with pytest.raises(ValueError, match='SCHEMA_TOO_LARGE'):
        discovery.snapshot({'value': 4})


def test_new_contract_has_no_implicit_install_option():
    async def run():
        async with Client(mcp) as client:
            tool = next(tool for tool in await client.list_tools() if tool.name == 'get_h5p_type_contract')
            assert set(tool.input_schema['properties']) == {'machine_name', 'major_version', 'minor_version'}
            assert tool.annotations.read_only_hint and not tool.annotations.open_world_hint
            result = await client.call_tool('get_h5p_type_contract', {'machine_name': 'H5P.TrueFalse', 'major_version': 99, 'minor_version': 99}, raise_on_error=False)
            assert result.is_error
    asyncio.run(run())
