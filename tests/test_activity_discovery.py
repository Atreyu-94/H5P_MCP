"""Discovery and native-schema contracts against the configured Lumi runtime."""
import asyncio
import json
import os
import subprocess

import pytest
from fastmcp import Client

from h5p_mcp.server import mcp, list_h5p_activities, get_h5p_activity_schema


@pytest.mark.parametrize('cached,refresh', [(False,False),(True,False),(False,True)])
def test_discovery_network_requires_explicit_refresh(tmp_path, cached, refresh):
    from h5p_mcp.lumi_backend import SOURCE, runtime_dir
    marker = tmp_path / 'network-attempt'
    guard = tmp_path / 'network-guard.cjs'
    guard.write_text("""
const fs = require('node:fs');
function deny() {
  fs.writeFileSync(process.env.NETWORK_MARKER, 'attempted');
  throw new Error('TEST_NETWORK_DENIED');
}
require('node:http').request = deny;
require('node:https').request = deny;
require('node:net').Socket.prototype.connect = deny;
globalThis.fetch = deny;
""", encoding='utf-8')
    if cached:
        (tmp_path / 'cache.json').write_text(json.dumps({'contentTypeCache':[
            {'machineName':'H5P.Cached','title':'Cached','majorVersion':1,
             'minorVersion':0,'patchVersion':0,'h5pMajorVersion':1,'h5pMinorVersion':28}],
            'contentTypeCacheUpdate':1}), encoding='utf-8')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    result = subprocess.run(['node','--require',str(guard),str(SOURCE/'bridge.cjs')],
        input=json.dumps({'action':'discover','data_dir':str(tmp_path),
                          'refresh':refresh,'offset':0,'limit':10}),
        env=dict(os.environ,H5P_MCP_LUMI_RUNTIME=str(runtime_dir()),NETWORK_MARKER=str(marker)),
        capture_output=True,text=True,timeout=30)
    if refresh:
        assert marker.exists(), 'Explicit refresh must attempt the requested network update'
        assert result.returncode != 0
    else:
        assert not marker.exists(), 'Read-only discovery attempted network access'
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report['total'] == int(cached)
        assert report['last_updated'] == (1 if cached else None)
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before
        assert not any(p.is_dir() for p in tmp_path.iterdir()), 'Query created durable storage'


def test_discovery_pagination_and_authoring_status():
    first = list_h5p_activities(limit=1)
    second = list_h5p_activities(offset=1, limit=1)
    assert first["total"] > 4
    assert first["activities"][0]["machine_name"] != second["activities"][0]["machine_name"]
    result = list_h5p_activities(query="H5P.QuestionSet", installed_only=True)
    assert len(result["activities"]) == 1
    assert result["activities"][0]["authoring_supported"] is True
    accordion = list_h5p_activities(query="H5P.Accordion")["activities"]
    assert accordion and accordion[0]["authoring_supported"] is True


def test_schema_exact_version_and_nested_fields():
    result = get_h5p_activity_schema("H5P.QuestionSet", 1, 21)
    assert result["library"] == "H5P.QuestionSet 1.21"
    fields = {field["name"]: field for field in result["semantics"]}
    assert fields["questions"]["type"] == "list"
    assert fields["questions"]["field"]["type"] == "library"
    assert "H5P.MultiChoice 1.16" in fields["questions"]["field"]["options"]
    assert result["metadata"]["coreApi"]["minorVersion"] == 28


def test_missing_version_is_not_silently_substituted():
    with pytest.raises(RuntimeError, match="not installed"):
        get_h5p_activity_schema("H5P.QuestionSet", 99, 99)


@pytest.mark.parametrize("name,major,minor", [("../config", None, None),
    ("H5P.Blanks", 1, None), ("H5P.Blanks", -1, 0)])
def test_invalid_schema_requests(name, major, minor):
    with pytest.raises(ValueError):
        get_h5p_activity_schema(name, major, minor)


@pytest.mark.parametrize("offset,limit", [(-1, 1), (0, 0), (0, 101)])
def test_invalid_pagination(offset, limit):
    with pytest.raises(ValueError):
        list_h5p_activities(offset=offset, limit=limit)


def test_discovery_tools_available_to_mcp_clients():
    async def check():
        async with Client(mcp) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert {"list_h5p_activities", "get_h5p_activity_schema"} <= names
            result = await client.call_tool("get_h5p_activity_schema", {"machine_name": "H5P.TrueFalse"})
            assert result.data["library"] == "H5P.TrueFalse 1.8"
    asyncio.run(check())
