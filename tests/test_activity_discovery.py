"""Discovery and native-schema contracts against the configured Lumi runtime."""
import asyncio

import pytest
from fastmcp import Client

from h5p_mcp.server import mcp, list_h5p_activities, get_h5p_activity_schema


def test_discovery_pagination_and_authoring_status():
    first = list_h5p_activities(limit=1)
    second = list_h5p_activities(offset=1, limit=1)
    assert first["total"] > 4
    assert first["activities"][0]["machine_name"] != second["activities"][0]["machine_name"]
    result = list_h5p_activities(query="H5P.QuestionSet", installed_only=True)
    assert len(result["activities"]) == 1
    assert result["activities"][0]["authoring_supported"] is True
    accordion = list_h5p_activities(query="H5P.Accordion")["activities"]
    assert accordion and accordion[0]["authoring_supported"] is False


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
