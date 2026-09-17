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
                assert {"create_true_false_quiz", "export_h5p", "validate_h5p",
                        "list_h5p_activities", "get_h5p_activity_schema"} <= names
                schema = await session.call_tool("get_h5p_activity_schema", {"machine_name": "H5P.QuestionSet"})
                assert not schema.is_error, schema
                schema_data = schema.structured_content or json.loads(schema.content[0].text)
                assert schema_data["library"] == "H5P.QuestionSet 1.21"
                assert schema_data["semantics"]
                examples = [
                    {"type": "mcq", "title": "MCQ", "question": "Two?", "choices": ["2", "3"], "correct_answer": "2"},
                    {"type": "truefalse", "title": "TF", "question": "True?", "correct_answer": True},
                    {"type": "blanks", "title": "Blanks", "text": "Una *palabra*.", "answers": ["palabra"]},
                ]
                examples.append({"type": "questionset", "title": "Mixed", "questions": examples.copy()})
                for index, quiz in enumerate(examples):
                    result = await session.call_tool("export_h5p", {"quiz_data": quiz, "output_name": f"activity_{index}"})
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
            assert {"create_mcq_quiz", "export_h5p", "validate_h5p"} <= names

    asyncio.run(asyncio.wait_for(check(), timeout=90))
