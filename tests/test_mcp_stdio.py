"""Exercise the installed package from outside the checkout, through MCP stdio."""
import asyncio
import json
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_installed_mcp_stdio(tmp_path):
    # Override with ["uvx", "--from", "/absolute/package.whl", "h5p-mcp"]
    # to repeat this exact test against a built wheel in an isolated environment.
    command = json.loads(os.environ.get("H5P_MCP_TEST_COMMAND", "null"))
    command = command or [sys.executable, "-m", "h5p_mcp.server"]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["H5P_MCP_EXPORT_DIR"] = str(tmp_path / "activities")
    params = StdioServerParameters(command=command[0], args=command[1:], env=env, cwd=str(tmp_path))

    async def check():
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert {"create_h5p_activity", "export_h5p", "validate_h5p",
                        "list_h5p_activities", "get_h5p_activity_schema"} <= names
                schema = await session.call_tool("get_h5p_activity_schema", {"machine_name": "H5P.QuestionSet"})
                assert not schema.is_error, schema
                schema_data = schema.structured_content or json.loads(schema.content[0].text)
                assert schema_data["library"] == "H5P.QuestionSet 1.21"
                assert schema_data["semantics"]
                compact = await session.call_tool('get_h5p_type_contract', {'machine_name': 'H5P.TrueFalse', 'major_version': 1, 'minor_version': 8})
                assert not compact.is_error
                contract = compact.structured_content or json.loads(compact.content[0].text)
                native = await session.read_resource(contract['raw_schema']['uri'])
                assert json.loads(native.contents[0].text)['library'] == contract['library']
                assert not {"create_mcq_quiz", "create_true_false_quiz", "create_fill_blanks_quiz", "create_questionset_quiz", "markdown_to_quizzes", "h5p_prompt_helpers"} & names
                examples = [
                    {"library": "H5P.TrueFalse 1.8", "title": "TF", "params": {"question": "True?", "correct": "true"}},
                    {"library": "H5P.Accordion 1.0", "title": "Accordion", "params": {"panels": [{"title": "Panel", "content": {"library": "H5P.AdvancedText 1.1", "params": {"text": "<p>Content</p>"}}}]}},
                ]
                for index, quiz in enumerate(examples):
                    prepared = await session.call_tool('prepare_h5p_activity', quiz)
                    assert not prepared.is_error, prepared
                    preparation = prepared.structured_content or json.loads(prepared.content[0].text)
                    assert preparation['ok'] and preparation['contract_version'] == '1'
                    quiz = preparation['activity']
                    result = await session.call_tool("export_h5p", {"activity": quiz, "output_name": f"activity_{index}"})
                    assert not result.is_error, result
                    data = result.structured_content or json.loads(result.content[0].text)
                    path = Path(data["output_path"])
                    assert path.parent == tmp_path / "activities"
                    assert path.is_file()
                    validated = await session.call_tool("validate_h5p", {"path": str(path)})
                    assert not validated.is_error, validated
                    report = validated.structured_content or json.loads(validated.content[0].text)
                    assert report["ok"], report

    asyncio.run(asyncio.wait_for(check(), timeout=90))


def test_latest_protocol_discovery(tmp_path):
    command = json.loads(os.environ.get("H5P_MCP_TEST_COMMAND", "null"))
    command = command or [sys.executable, "-m", "h5p_mcp.server"]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["H5P_MCP_EXPORT_DIR"] = str(tmp_path / "activities")
    transport = StdioTransport(command=command[0], args=command[1:], env=env, cwd=str(tmp_path))

    async def check():
        async with Client(transport, mode="auto") as client:
            assert str(client.protocol_version) == "2026-07-28"
            assert client.server_info is not None
            names = {tool.name for tool in await client.list_tools()}
            assert {"create_h5p_activity", "export_h5p", "validate_h5p"} <= names

    asyncio.run(asyncio.wait_for(check(), timeout=90))
