"""Versioned JSON authority, also consumable by the future TypeScript adapter."""
from copy import deepcopy
from importlib.resources import files
import json
from itertools import islice

from jsonschema import Draft202012Validator

from h5p_mcp.models.reports import verification

_SCHEMA = json.loads(files(__package__).joinpath('v1.json').read_text('utf-8'))
_CODES = json.loads(files(__package__).joinpath('codes-v1.json').read_text('utf-8'))


def schema(name: str) -> dict:
    """Return a standalone schema: no filesystem or network reference resolution."""
    def expand(value):
        if isinstance(value, list):
            return [expand(item) for item in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            # All references belong to this packaged, acyclic schema authority.
            return expand(_SCHEMA['$defs'][value['$ref'].removeprefix('#/$defs/')])
        return {key: expand(item) for key, item in value.items()}
    result = expand(deepcopy(_SCHEMA['$defs'][name]))
    result['$schema'] = _SCHEMA['$schema']
    return result


def pointer(parts) -> str:
    return ''.join('/' + str(part).replace('~', '~0').replace('/', '~1') for part in parts)


def diagnostic(code: str, location: str = '', *, expected=None, actual=None) -> dict:
    """Never forward exception messages, file paths, values or backend stacks."""
    code = _CODES['aliases'].get(code, code)
    if code not in _CODES['codes']:
        code = 'INTERNAL_ERROR'
    retryable, message, fix = _CODES['codes'][code]
    # Do not truncate a pointer into a different, apparently valid field identity.
    if len(location) > 4096:
        location = ''
    return dict(code=code, pointer=location, message=message,
                expected=expected, actual=actual, retryable=retryable, suggested_fix=fix)


def input_diagnostics(arguments: dict) -> list[dict]:
    errors = Draft202012Validator(schema('prepare_local_input')).iter_errors(arguments)
    # Read one extra error to report truncation; never materialize an unbounded list.
    items = []
    missing_groups = set()
    for error in islice(errors, 101):
        location = list(error.absolute_path)
        if error.validator == 'required':
            group = pointer(location)
            if group in missing_groups:
                continue
            missing_groups.add(group)
            for key in error.validator_value:
                if key not in error.instance:
                    items.append(diagnostic('SCHEMA_VALIDATION_FAILED', pointer([*location, key]),
                                            expected='Required field', actual='Absent'))
                    if len(items) >= 101:
                        return items
            continue
        expected = f'{error.validator}: {json.dumps(error.validator_value, ensure_ascii=True)}'[:256]
        items.append(diagnostic('SCHEMA_VALIDATION_FAILED', pointer(location), expected=expected,
                                actual=f'Value type: {type(error.instance).__name__}'))
        if len(items) >= 101:
            break
    return items


def report(diagnostics=(), *, activity=None, checks=None, operational=False) -> dict:
    items = list(islice(iter(diagnostics), 101))
    result = dict(contract_version='1', ok=not items,
                  kind='operational_error' if operational else 'validation' if items else 'preparation',
                  diagnostics=items[:100], diagnostics_truncated=len(items) > 100,
                  activity=None if items else activity, verification=checks or verification())
    Draft202012Validator(schema('preparation_report')).validate(result)
    return result


def preparation_report(legacy: dict) -> dict:
    return report((diagnostic(item['code'], item.get('pointer', '')) for item in legacy['diagnostics']),
                  activity=legacy['activity'], checks=legacy['verification'])
