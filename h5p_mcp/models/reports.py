"""Public MCP report schemas; unexecuted checks never imply verification."""
from typing import Any, Literal, NotRequired, TypedDict
from h5p_mcp.models.activity import Activity

Status = Literal['passed', 'failed', 'not_run']


class Verification(TypedDict):
    structure: Status
    semantics: Status
    importation: Status
    playback: Status
    grading: Status


class Diagnostic(TypedDict):
    code: str
    path: str
    message: str
    retryable: bool
    pointer: NotRequired[str]


class PreparationReport(TypedDict):
    ok: bool
    errors: list[str]
    diagnostics: list[Diagnostic]
    warnings: list[str]
    mathematics: dict[str, Any]
    activity: dict[str, Any]
    transformations: list[dict[str, Any]]
    verification: Verification


class ExportReport(TypedDict):
    output_path: str
    h5p_json: dict[str, Any]
    content_json: dict[str, Any]
    verification: Verification


class ValidationReport(TypedDict):
    ok: bool
    errors: list[str]
    warnings: list[str]
    verification: Verification


class BatchItem(TypedDict, total=False):
    ok: bool
    output_name: str
    output_path: str
    error: str


class BatchReport(TypedDict):
    count: int
    succeeded: int
    results: list[BatchItem]


def verification(**stages: Status) -> Verification:
    return {name: stages.get(name, 'not_run') for name in
            ('structure', 'semantics', 'importation', 'playback', 'grading')}
