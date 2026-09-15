"""Serve the packaged authoring skill using SEP-2640 and FastMCP's public API."""

from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
from typing import Any

import yaml
from fastmcp import FastMCP
from fastmcp.resources.types import TextResource
from fastmcp.server.extensions import MethodBinding, ServerExtension
from mcp.shared.exceptions import MCPError
from mcp_types import PaginatedRequestParams, RequestParams

SKILL_URI = "skill://h5p-authoring/SKILL.md"
EXTENSION_ID = "io.modelcontextprotocol/skills"


class GetSkillParams(RequestParams):
    uri: str


class AuthoringSkillsExtension(ServerExtension):
    """One immutable, process-lifetime snapshot of the packaged skill."""

    identifier = EXTENSION_ID

    def __init__(self) -> None:
        raw = files("h5p_mcp").joinpath("skills/h5p-authoring/SKILL.md").read_bytes()
        self.text = raw.decode("utf-8")
        frontmatter = yaml.safe_load(self.text.split("---", 2)[1])
        self.entry = {
            "uri": SKILL_URI,
            "frontmatter": frontmatter,
            "resources": [{"uri": SKILL_URI, "digest": "sha256:" + sha256(raw).hexdigest(), "size": len(raw)}],
        }

    def methods(self):
        # This extension targets the modern protocol. Legacy clients retain tools
        # and ordinary resource reads without these additional methods.
        versions = frozenset({"2026-07-28"})
        return (
            MethodBinding("skills/list", PaginatedRequestParams, self.list_skills, versions),
            MethodBinding("skills/get", GetSkillParams, self.get_skill, versions),
        )

    @staticmethod
    def _result(**payload: Any) -> dict[str, Any]:
        return {"resultType": "complete", "ttlMs": 300000, "cacheScope": "public", **payload}

    async def list_skills(self, ctx, params: PaginatedRequestParams) -> dict[str, Any]:
        if params.cursor is not None:
            raise MCPError(code=-32602, message="Unknown skills cursor; this catalog has one page")
        return self._result(skills=[deepcopy(self.entry)])

    async def get_skill(self, ctx, params: GetSkillParams) -> dict[str, Any]:
        if params.uri != SKILL_URI:
            raise MCPError(code=-32602, message="Unknown skill URI")
        return self._result(skill=deepcopy(self.entry))


def register_authoring_skill(server: FastMCP) -> None:
    extension = AuthoringSkillsExtension()
    metadata = extension.entry["frontmatter"]
    # Serve the same decoded bytes used for the digest, preserving CRLF on Windows.
    # No user-supplied URI is converted into a filesystem path.
    server.add_resource(TextResource(
        uri=SKILL_URI, name=metadata["name"], description=metadata["description"],
        mime_type="text/markdown", text=extension.text,
    ))
    server.add_extension(extension)
