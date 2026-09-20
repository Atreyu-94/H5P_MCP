"""Local vNext preparation; persistent IDs and remote stores belong to F5."""
import logging
from importlib.resources import files

from fastmcp.tools.base import Tool, ToolResult
from fastmcp.resources import TextResource

from h5p_mcp.contracts import diagnostic, input_diagnostics, preparation_report, report, schema
from h5p_mcp.jobs import cancellable
from h5p_mcp.limits import check_tree
from h5p_mcp.lumi_backend import BackendError
from h5p_mcp.models.reports import verification


class PrepareTool(Tool):
    async def run(self, arguments: dict) -> ToolResult:
        # Deferred import avoids a second FastMCP instance and keeps the legacy
        # synchronous Python API available to existing callers.
        from h5p_mcp.server import create_h5p_activity

        def prepare():
            try:
                check_tree(arguments)
            except ValueError as error:
                code = str(error).partition(':')[0]
                if code not in {'INPUT_TOO_DEEP', 'INPUT_TOO_LARGE'}:
                    raise
                return report([diagnostic(code)], checks=verification(structure='failed'))
            invalid = input_diagnostics(arguments)
            if invalid:
                return report(invalid, checks=verification(structure='failed'))
            return preparation_report(create_h5p_activity(**arguments))

        try:
            result = await cancellable(prepare)()
        except BackendError as error:
            logging.getLogger(__name__).exception('Preparation backend failed')
            details = error.details if isinstance(error.details, list) else []
            diagnostics = [diagnostic(error.code)]
            diagnostics.extend(diagnostic(item.get('code', 'INTERNAL_ERROR'), item.get('pointer', ''))
                               for item in details[:99] if isinstance(item, dict))
            result = report(diagnostics, operational=True)
        except Exception as error:
            # Cancellation inherits BaseException and must propagate unchanged.
            logging.getLogger(__name__).exception('Preparation operation failed')
            code = 'BACKEND_TIMEOUT' if isinstance(error, RuntimeError) and str(error).startswith('BACKEND_TIMEOUT:') else 'INTERNAL_ERROR'
            result = report([diagnostic(code)], operational=True)
        return ToolResult(structured_content=result, is_error=result['kind'] == 'operational_error')


def register_preparation(server) -> None:
    for name, filename in [('schema', 'v1.json'), ('codes', 'codes-v1.json')]:
        server.add_resource(TextResource(uri=f'h5p-contract://v1/{name}', name=f'h5p-contract-v1-{name}',
                                         mime_type='application/json',
                                         text=files('h5p_mcp.contracts').joinpath(filename).read_text('utf-8')))
    server.add_tool(PrepareTool(
        name='prepare_h5p_activity',
        description='Prepare a local H5P activity using installed native semantics. Returns versioned diagnostics with JSON Pointers. On success pass activity to export_h5p. No persistent preparation ID or remote asset support yet. Does not install libraries or verify playback/grading.',
        parameters=schema('prepare_local_input'), output_schema=schema('preparation_report'),
        annotations={'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': False, 'openWorldHint': False},
    ))
