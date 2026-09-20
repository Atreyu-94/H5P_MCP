"""Host-configured local policy. This is not remote OAuth authorization."""
from dataclasses import dataclass
import os

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

TOOL_SCOPES = {
    'refresh_h5p_catalog': 'catalog:refresh',
    'install_h5p_library': 'libraries:install',
    'install_h5p_library_package': 'libraries:install',
}


@dataclass(frozen=True)
class AdminPolicy:
    scopes: frozenset[str] = frozenset()
    immutable: bool = False

    @classmethod
    def from_environment(cls):
        scopes = frozenset(os.environ.get('H5P_MCP_ADMIN_SCOPES', '').split())
        if scopes - set(TOOL_SCOPES.values()):
            raise ValueError('Unknown H5P_MCP_ADMIN_SCOPES; use catalog:refresh and/or libraries:install')
        immutable = os.environ.get('H5P_MCP_IMMUTABLE', '0')
        if immutable not in {'0', '1'}:
            raise ValueError('H5P_MCP_IMMUTABLE must be 0 or 1')
        return cls(scopes, immutable == '1')

    def allows(self, scope):
        return not self.immutable and scope in self.scopes

    def require(self, scope):
        if not self.allows(scope):
            raise ToolError(f'ADMIN_FORBIDDEN: requires {scope} and mutable library storage')


# Freeze trusted host configuration at startup; tool arguments cannot grant scopes.
policy = AdminPolicy.from_environment()


def require(scope):
    policy.require(scope)


class AdministrationMiddleware(Middleware):
    # FastMCP's OAuth middleware skips stdio. This local gate must not skip it.
    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        return [tool for tool in tools if tool.name not in TOOL_SCOPES or policy.allows(TOOL_SCOPES[tool.name])]

    async def on_call_tool(self, context, call_next):
        scope = TOOL_SCOPES.get(context.message.name)
        if scope:
            if not policy.allows(scope):
                from fastmcp.tools.base import ToolResult
                from h5p_mcp.contracts import diagnostic
                from h5p_mcp.contracts.operations import operation_report
                return ToolResult(structured_content=operation_report(
                    diagnostics=[diagnostic('PERMISSION_DENIED', expected=scope)], operational=True), is_error=True)
        return await call_next(context)
