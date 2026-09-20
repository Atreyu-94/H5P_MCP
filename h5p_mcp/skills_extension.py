"""Serve the packaged authoring skill using SEP-2640 and FastMCP's public API."""

from copy import deepcopy
import json
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
        root = files("h5p_mcp").joinpath("skills/h5p-authoring")
        names = json.loads(root.joinpath("resources.json").read_text("utf-8"))
        self.resources = {"skill://h5p-authoring/" + name: root.joinpath(name).read_bytes() for name in names}
        raw = self.resources[SKILL_URI]
        self.text = raw.decode("utf-8")
        frontmatter = yaml.safe_load(self.text.split("---", 2)[1])
        self.entry = {
            "uri": SKILL_URI,
            "frontmatter": frontmatter,
            "resources": [{"uri": uri, "digest": "sha256:" + sha256(data).hexdigest(), "size": len(data)} for uri, data in self.resources.items()],
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
    for uri, raw in extension.resources.items():
        server.add_resource(TextResource(
            uri=uri, name=metadata["name"] if uri == SKILL_URI else uri.rsplit("/", 1)[-1],
            description=metadata["description"],
            mime_type="application/json" if uri.endswith(".json") else "text/markdown",
            text=raw.decode("utf-8"),
        ))
    server.add_extension(extension)
