"""SEP-2640 reference-client checks over a real stdio subprocess.

This exercises transport and an authored activity fixture, not autonomous LLM
selection or a desktop host's approval UI. H5P_MCP_TEST_COMMAND also accepts uvx.
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp.shared.exceptions import MCPError
from mcp_types import Request
from pydantic import TypeAdapter
import pytest
import yaml

URI = "skill://h5p-authoring/SKILL.md"
EXTENSION = "io.modelcontextprotocol/skills"


async def request(client, method, params):
    return await client.session.send_request(
        Request[dict, str](method=method, params=params), TypeAdapter(dict)
    )


def verify_skill(entry, text):
    """Validate the held entry before making this content available for use."""
    assert entry["uri"] == URI
    assert len(entry["resources"]) == 1
    resource = entry["resources"][0]
    assert resource["uri"] == URI
    raw = text.encode("utf-8")
    assert resource["size"] == len(raw)
    assert resource["digest"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert yaml.safe_load(text.split("---", 2)[1]) == entry["frontmatter"]


def test_skills_stdio_authoring(tmp_path):
    command = json.loads(os.environ.get("H5P_MCP_TEST_COMMAND", "null"))
    command = command or [sys.executable, "-m", "h5p_mcp.server"]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["H5P_MCP_EXPORT_DIR"] = str(tmp_path / "activities")
    transport = StdioTransport(command=command[0], args=command[1:], env=env, cwd=str(tmp_path))

    async def check():
        async with Client(transport, mode="auto") as client:
            assert str(client.protocol_version) == "2026-07-28"
            caps = client.server_capabilities
            assert caps.resources is not None
            assert caps.extensions[EXTENSION] == {}
            listed = await request(client, "skills/list", {})
            assert listed["resultType"] == "complete"
            assert listed["cacheScope"] == "public"
            assert listed["ttlMs"] >= 0
            assert "nextCursor" not in listed
            assert len(listed["skills"]) == 1
            entry = listed["skills"][0]
            fetched = await request(client, "skills/get", {"uri": URI})
            assert fetched["skill"] == entry
            assert fetched["resultType"] == "complete"
            assert fetched["cacheScope"] == "public"
            assert fetched["ttlMs"] >= 0
            # Listing does not fetch content. Load only when using this skill.
            content = await client.read_resource(URI)
            assert len(content) == 1
            assert content[0].mime_type == "text/markdown"
            text = content[0].text
            verify_skill(entry, text)
            with pytest.raises(AssertionError):
                verify_skill(entry, text + "tampered")
            altered = json.loads(json.dumps(entry))
            altered["frontmatter"]["description"] = "Changed"
            with pytest.raises(AssertionError):
                verify_skill(altered, text)
            resources = await client.list_resources()
            metadata = next(r for r in resources if str(r.uri) == URI)
            assert metadata.name == entry["frontmatter"]["name"]
            assert metadata.description == entry["frontmatter"]["description"]

            for params in ({"uri": "skill://unknown/SKILL.md"}, {"uri": URI + "/../../server.py"}, {}):
                with pytest.raises(MCPError) as error:
                    await request(client, "skills/get", params)
                assert error.value.code == -32602
            with pytest.raises(MCPError) as error:
                await request(client, "skills/list", {"cursor": "unknown"})
            assert error.value.code == -32602
            with pytest.raises(MCPError):
                await client.read_resource("skill://h5p-authoring/../../server.py")

            # Follow the distributed skill: discover -> schema -> prepare -> export -> import.
            catalog = await client.call_tool("list_h5p_activities", {"query": "H5P.Accordion"})
            assert catalog.data["activities"]
            for name in ("H5P.Accordion", "H5P.AdvancedText"):
                schema = await client.call_tool("get_h5p_activity_schema", {"machine_name": name})
                assert schema.data["semantics"]
            prepared = await client.call_tool("create_h5p_activity", {
                "title": "Cambios de estado", "library": "H5P.Accordion 1.0", "language": "es",
                "params": {"panels": [{"title": "Evaporaci\u00f3n", "content": {
                    "library": "H5P.AdvancedText 1.1", "params": {"text": "<p>L\u00edquido a gas.</p>"}}}]}})
            assert prepared.structured_content["ok"], prepared.structured_content
            exported = await client.call_tool("export_h5p", {"activity": prepared.structured_content["activity"], "output_name": "estados"})
            path = Path(exported.structured_content["output_path"])
            assert path.parent == tmp_path / "activities"
            report = await client.call_tool("validate_h5p", {"path": str(path)})
            assert report.structured_content["ok"], report.structured_content
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read("h5p.json"))
                body = json.loads(archive.read("content/content.json"))
                assert manifest["language"] == "es"
                assert body["panels"][0]["title"] == "Evaporaci\u00f3n"
                assert body["panels"][0]["content"]["library"] == "H5P.AdvancedText 1.1"

    asyncio.run(asyncio.wait_for(check(), timeout=90))
