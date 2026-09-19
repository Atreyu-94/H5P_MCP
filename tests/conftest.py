"""Isolated integration environment by default; offline unit tests need no runtime."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest


@pytest.fixture(scope='session', autouse=True)
def isolated_backend(tmp_path_factory, request):
    if os.environ.get('H5P_MCP_ISOLATED_TESTS', '1') != '1' or all(item.path.name == 'test_hardening.py' for item in request.session.items):
        yield
        return
    from h5p_mcp.lumi_backend import setup_lumi
    old = os.environ.get('H5P_MCP_DATA_DIR')
    root = tmp_path_factory.mktemp('isolated-lumi')
    os.environ['H5P_MCP_DATA_DIR'] = str(root)
    try:
        fixture = Path(__file__).parent / 'fixtures'
        archive = fixture / 'libraries.zip'
        expected = json.loads((fixture / 'libraries.lock.json').read_text())['sha256']
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
        # Trusted, checked-in fixture; the hash is checked before extraction.
        with ZipFile(archive) as package:
            package.extractall(root / 'libraries')
        setup_lumi()
        yield
    finally:
        if old is None:
            os.environ.pop('H5P_MCP_DATA_DIR', None)
        else:
            os.environ['H5P_MCP_DATA_DIR'] = old
