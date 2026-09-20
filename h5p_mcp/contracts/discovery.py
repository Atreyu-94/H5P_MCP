"""Compact native semantics, not an approximate JSON Schema validator."""
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json
import re
from threading import Lock

from h5p_mcp.limits import check_tree, limit

_snapshots: OrderedDict[str, bytes] = OrderedDict()
_lock = Lock()
_CONSTRAINTS = ('min', 'max', 'maxLength', 'regexp', 'decimals', 'multiple', 'options')
_KNOWN = {'name', 'type', 'optional', 'default', 'fields', 'field', 'label', 'description',
          'importance', 'common', 'expanded', *_CONSTRAINTS}


def encode(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def snapshot(raw: dict) -> dict:
    content = encode(raw)
    if len(content) > limit('SCHEMA_BYTES', 2097152):
        raise ValueError('SCHEMA_TOO_LARGE: native schema exceeds resource byte budget')
    digest = sha256(content).hexdigest()
    with _lock:
        _snapshots[digest] = content
        _snapshots.move_to_end(digest)
        while len(_snapshots) > limit('SCHEMA_SNAPSHOTS', 16) or sum(map(len, _snapshots.values())) > limit('SCHEMA_CACHE_BYTES', 16777216):
            _snapshots.popitem(last=False)
        if digest not in _snapshots:
            raise ValueError('SCHEMA_TOO_LARGE: native schema exceeds cache byte budget')
    return {'uri': f'h5p-schema://snapshot/{digest}', 'sha256': digest,
            'mime_type': 'application/json', 'size': len(content),
            'lifetime': 'process-local bounded cache; rediscover if evicted or restarted'}


def read_snapshot(digest: str) -> str:
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid schema digest')
    with _lock:
        content = _snapshots.get(digest)
        if content is None:
            raise ValueError('SCHEMA_SNAPSHOT_UNAVAILABLE: query get_h5p_type_contract again')
        if len(content) > limit('SCHEMA_BYTES', 2097152):
            raise ValueError('SCHEMA_TOO_LARGE: resource byte budget exceeded')
        return content.decode('utf-8')


def compact_contract(raw: dict) -> dict:
    check_tree(raw)
    sublibraries = set()

    def project(entry):
        kind = entry['type']
        field = {'name': entry.get('name'), 'type': kind,
                 'required': not entry.get('optional', False)}
        if 'default' in entry:
            field['default'] = deepcopy(entry['default'])
        constraints = {key: deepcopy(entry[key]) for key in _CONSTRAINTS if key in entry}
        if constraints:
            field['constraints'] = constraints
        extension = {key: deepcopy(value) for key, value in entry.items() if key not in _KNOWN}
        if extension:
            field['x-h5p'] = extension
        if kind == 'group':
            children = entry.get('fields', [])
            field['value_shape'] = 'single_field' if len(children) == 1 else 'object'
            field['fields'] = [project(child) for child in children]
        elif kind == 'list':
            field['field'] = project(entry['field'])
        elif kind == 'library':
            sublibraries.update(entry.get('options', []))
        return field

    fields = [project(entry) for entry in raw['semantics']]
    semantics_digest = sha256(encode(raw['semantics'])).hexdigest()
    tested = json.loads(files('h5p_mcp.contracts').joinpath('examples-v1.json').read_text('utf-8'))
    examples = [{'title': item['title'], 'params': item['params'], 'evidence': item['evidence']} for item in tested if item['library'] == raw['library'] and
                item['patch_version'] == raw['patch_version'] and item['semantics_sha256'] == semantics_digest]
    return {'contract_version': '1', 'format': 'h5p-native-compact-v1',
            'library': raw['library'], 'patch_version': raw['patch_version'], 'core': raw['core'],
            'fields': fields, 'sublibraries': sorted(sublibraries), 'examples': examples,
            'raw_schema': snapshot(raw),
            'x-h5p': {
                'required': 'Native flag; defaults can supply missing values.',
                'groups': 'single_field uses the child value without an object wrapper; an optional missing group is omitted.',
                'defaults': 'Preparation fills defaults and missing multi-field groups. Query nested libraries separately.',
                'constraints': 'Native rules, not JSON Schema. Regexp is JavaScript; scalar checks skip maxLength for HTML text.',
                'widgets': 'Widget metadata is retained, not certified. Labels, descriptions and UI grouping flags are omitted; consult raw_schema.',
                'examples': 'Pinned fixture examples, matched by patch and semantics SHA-256; no Moodle evidence.',
                'limits': {'max_depth': limit('DEPTH', 64), 'max_nodes': limit('NODES', 100000),
                           'schema_bytes': limit('SCHEMA_BYTES', 2097152)},
                'verification': 'This is a description of installed semantics, not playback, accessibility or grading evidence.'}}
