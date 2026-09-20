"""Versioned local operation boundaries; remote schemas are descriptive only."""
from collections import OrderedDict
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4

from fastmcp.resources import TextResource
from fastmcp.tools.base import Tool, ToolResult
from fastmcp.exceptions import ToolError
from jsonschema import Draft202012Validator
from mcp.types import ResourceLink
from pydantic import ValidationError

from h5p_mcp.contracts import OPERATIONS, diagnostic, input_diagnostics, pointer, schema
from h5p_mcp.jobs import cancellable, check_cancelled
from h5p_mcp.limits import check_tree, limit
from h5p_mcp.lumi_backend import BackendError
from h5p_mcp.models.reports import verification

_artifacts = OrderedDict()
_lock = Lock()
_handlers = {}
_VALIDATION = {'LIBRARY_NOT_INSTALLED', 'LIBRARY_VERSION_MISMATCH', 'SCHEMA_VALIDATION_FAILED',
               'UNSUPPORTED_SEMANTIC_TYPE', 'STALE_PREPARATION', 'ASSET_NOT_FOUND', 'ASSET_TOO_LARGE',
               'MIME_MISMATCH', 'UNSAFE_ARCHIVE', 'OUTPUT_ALREADY_EXISTS', 'TARGET_INCOMPATIBLE', 'LIMIT_EXCEEDED'}


def failure(error):
    code = getattr(error, 'code', None)
    if isinstance(error, FileExistsError):
        code = 'OUTPUT_ALREADY_EXISTS'
    elif isinstance(error, FileNotFoundError):
        code = 'ASSET_NOT_FOUND'
    elif isinstance(error, (PermissionError, ToolError)):
        code = 'PERMISSION_DENIED'
    elif isinstance(error, ValidationError):
        return [diagnostic('SCHEMA_VALIDATION_FAILED', pointer(item['loc']), expected=item['type'])
                for item in error.errors(include_input=False, include_context=False)[:100]], False
    elif code is None and isinstance(error, (ValueError, RuntimeError)):
        prefix = str(error).partition(':')[0]
        code = prefix if prefix in {'BACKEND_TIMEOUT', 'INPUT_TOO_DEEP', 'INPUT_TOO_LARGE', 'BATCH_TOO_LARGE',
                                   'SCHEMA_TOO_LARGE', 'RESOURCE_TOO_LARGE'} else 'SCHEMA_VALIDATION_FAILED' if isinstance(error, ValueError) else 'BACKEND_UNAVAILABLE'
    if code in {'SCHEMA_TOO_LARGE', 'RESOURCE_TOO_LARGE'}:
        code = 'LIMIT_EXCEEDED'
    item = diagnostic(code or 'INTERNAL_ERROR')
    details = getattr(error, 'details', None)
    items = [item]
    if isinstance(details, list):
        items.extend(diagnostic(d.get('code', 'INTERNAL_ERROR'), d.get('pointer', ''))
                     for d in details[:99] if isinstance(d, dict))
    return items, item['code'] not in _VALIDATION


def operation_report(*, diagnostics=(), operational=False, kind='validation', checks=None, artifact=None):
    items = list(diagnostics)
    result = dict(contract_version='1', ok=not items,
                  kind='operational_error' if operational else kind, diagnostics=items[:100],
                  diagnostics_truncated=len(items) > 100, verification=checks or verification())
    if artifact is not None:
        result['artifact'] = artifact
    return result


def register_artifact(filename, manifest):
    path = Path(filename).resolve()
    digest = sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            check_cancelled()
            size += len(chunk)
            if size > limit('ZIP_ARCHIVE_BYTES', 134217728):
                raise ValueError('RESOURCE_TOO_LARGE: exported package budget exceeded')
            digest.update(chunk)
    identifier = uuid4().hex
    ref = dict(uri=f'h5p-artifact://package/{identifier}', mime_type='application/zip',
               size=size, sha256=digest.hexdigest(), manifest=manifest)
    with _lock:
        _artifacts[identifier] = (path, size, ref['sha256'])
        while len(_artifacts) > limit('ARTIFACTS', 128):
            _artifacts.popitem(last=False)
    return ref


def read_artifact(identifier):
    if not re.fullmatch('[0-9a-f]{32}', identifier):
        raise ValueError('Invalid artifact ID')
    with _lock:
        entry = _artifacts.get(identifier)
    if entry is None:
        raise ValueError('Artifact expired or unknown; export again with a new name')
    path, size, digest = entry
    maximum = limit('RESOURCE_BYTES', 16777216)
    if size > maximum:
        raise ValueError('RESOURCE_TOO_LARGE: increase the local resource limit or reduce the package')
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) != size or sha256(data).hexdigest() != digest:
        raise ValueError('Artifact changed after export')
    return data


class OperationTool(Tool):
    async def run(self, arguments: dict) -> ToolResult:
        input_name, output_name = OPERATIONS['local'][self.name]

        def invoke():
            check_tree(arguments)
            invalid = input_diagnostics(arguments, input_name)
            if invalid:
                return operation_report(diagnostics=invalid, checks=verification(structure='failed'))
            return _handlers[self.name](**arguments)

        try:
            result = await cancellable(invoke)()
            # Enforce the published success/error union before transmission.
            Draft202012Validator(self.output_schema).validate(result)
        except Exception as error:
            diagnostics, operational = failure(error)
            result = operation_report(diagnostics=diagnostics, operational=operational)
        is_error = result.get('kind') == 'operational_error' or any(
            item.get('kind') == 'operational_error' for item in result.get('results', []))
        artifact = result.get('artifact')
        if artifact:
            return ToolResult(content=[ResourceLink(type='resource_link', name='H5P package', uri=artifact['uri'],
                              mime_type=artifact['mime_type'], size=artifact['size'])],
                              structured_content=result, is_error=is_error)
        return ToolResult(structured_content=result, is_error=is_error)


def register_operations(server, functions):
    # Reuse the current public annotations/descriptions, with JSON schemas as authority.
    for name, (input_name, output_name) in OPERATIONS['local'].items():
        function = functions[name]
        _handlers[name] = function
        effect = name in {'refresh_h5p_catalog', 'install_h5p_library', 'install_h5p_library_package', 'export_h5p_activity', 'export_h5p_batch'}
        output = {'type': 'object', 'anyOf': [schema(output_name), schema('error_report')]}
        server.add_tool(OperationTool(name=name, description=function.__doc__ or name,
            parameters=schema(input_name), output_schema=output,
            annotations={'readOnlyHint': not effect, 'destructiveHint': name == 'install_h5p_library_package',
                         'idempotentHint': not effect, 'openWorldHint': name in {'refresh_h5p_catalog', 'install_h5p_library'}}))
    # Resolved snapshots are usable without a custom schema resolver in either runtime.
    profiles = {'contract_version': '1', 'local': {name: {'input': schema(pair[0]), 'output': {'type':'object','anyOf':[schema(pair[1]),schema('error_report')]}}
                for name, pair in OPERATIONS['local'].items()},
                'remote': {**OPERATIONS['remote'], 'inputs': {name: schema(ref) for name, ref in OPERATIONS['remote']['inputs'].items()}}}
    profiles['local']['prepare_h5p_activity'] = {'input': schema('prepare_local_input'), 'output': schema('preparation_report')}
    server.add_resource(TextResource(uri='h5p-contract://v1/profiles', name='h5p-contract-profiles',
                                    mime_type='application/json', text=json.dumps(profiles)))
