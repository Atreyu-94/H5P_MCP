"""Local administration is opt-in at listing, invocation and legacy flags."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
import pytest

from h5p_mcp import administration as admin
from h5p_mcp import server


@pytest.mark.parametrize('scopes,immutable,expected', [
    ([], False, set()),
    (['catalog:refresh'], False, {'refresh_h5p_catalog'}),
    (['libraries:install'], False, {'install_h5p_library', 'install_h5p_library_package'}),
    (['catalog:refresh', 'libraries:install'], True, set()),
])
def test_catalog_and_direct_mcp_gate(monkeypatch, scopes, immutable, expected):
    monkeypatch.setattr(admin, 'policy', admin.AdminPolicy(frozenset(scopes), immutable))
    def forbidden(*args, **kwargs):
        pytest.fail('Denied operation reached backend')
    monkeypatch.setattr(server, 'run_lumi', forbidden)
    async def run():
        async with Client(server.mcp) as client:
            names = {t.name for t in await client.list_tools()}
            assert names & set(admin.TOOL_SCOPES) == expected
            for name in set(admin.TOOL_SCOPES) - expected:
                arguments = {'machine_name': 'H5P.TrueFalse'} if name == 'install_h5p_library' else {'path': 'missing.h5p'} if name.endswith('_package') else {}
                result = await client.call_tool(name, arguments, raise_on_error=False)
                assert result.is_error
    asyncio.run(run())


def test_legacy_flags_and_python_calls_cannot_bypass(monkeypatch):
    monkeypatch.setattr(admin, 'policy', admin.AdminPolicy())
    calls = [lambda: server.list_h5p_activities(refresh=True),
             lambda: server.get_h5p_activity_schema('H5P.TrueFalse', install_if_missing=True),
             server.refresh_h5p_catalog,
             lambda: server.install_h5p_library('H5P.TrueFalse'),
             lambda: server.install_h5p_library_package('missing.h5p')]
    for call in calls:
        with pytest.raises(ToolError, match='ADMIN_FORBIDDEN'):
            call()


def test_install_existing_exact_library_no_network(monkeypatch):
    monkeypatch.setattr(admin, 'policy', admin.AdminPolicy(frozenset({'libraries:install'})))
    assert server.install_h5p_library('H5P.TrueFalse', 1, 8)['library'] == 'H5P.TrueFalse 1.8'
    async def run():
        async with Client(server.mcp) as client:
            result = await client.call_tool('install_h5p_library', {'machine_name': 'H5P.TrueFalse', 'major_version': 1, 'minor_version': 8})
            assert result.data['library'] == 'H5P.TrueFalse 1.8'
    asyncio.run(run())


def test_refresh_routes_to_explicit_backend_action(monkeypatch):
    monkeypatch.setattr(admin, 'policy', admin.AdminPolicy(frozenset({'catalog:refresh'})))
    calls = []
    monkeypatch.setattr(server, 'run_lumi', lambda action, **kwargs: calls.append((action, kwargs)) or {})
    server.refresh_h5p_catalog()
    assert calls[0][0] == 'discover' and calls[0][1]['refresh'] is True


def test_package_rejected_before_install(monkeypatch, tmp_path):
    monkeypatch.setattr(admin, 'policy', admin.AdminPolicy(frozenset({'libraries:install'})))
    def forbidden(*args, **kwargs):
        pytest.fail('Unsafe archive reached backend')
    monkeypatch.setattr(server, 'run_lumi', forbidden)
    archive = tmp_path / 'unsafe.h5p'
    with ZipFile(archive, 'w') as package:
        package.writestr('../escape', 'unsafe')
    with pytest.raises(ValueError, match='Unsafe ZIP'):
        server.install_h5p_library_package(str(archive))
    monkeypatch.setenv('H5P_MCP_PACKAGE_ROOTS', '[]')
    with pytest.raises(ValueError):
        server.install_h5p_library_package(str(archive))


def test_trusted_package_installs_into_empty_library_store(monkeypatch, tmp_path):
    from h5p_mcp.lumi_backend import runtime_dir
    # Reuse only the initialized runtime; the installation has an empty library store.
    runtime = runtime_dir()
    monkeypatch.setenv('H5P_MCP_DATA_DIR', str(tmp_path / 'installation'))
    monkeypatch.setattr('h5p_mcp.lumi_backend.runtime_dir', lambda: runtime)
    monkeypatch.setattr(admin, 'policy', admin.AdminPolicy(frozenset({'libraries:install'})))
    fixture = Path(__file__).resolve().parents[1] / 'fixtures' / 'libraries.zip'
    result = server.install_h5p_library_package(str(fixture))
    assert result['libraries']['H5P.TrueFalse'] == 'H5P.TrueFalse 1.8'


def snapshot(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) if p.is_file() else None
            for p in root.rglob('*') if p.name != 'backend.lock'}


def test_queries_leave_durable_state_unchanged():
    from h5p_mcp.lumi_backend import data_dir
    root = data_dir()
    # Libraries, configuration and cache, including absence, must stay unchanged.
    before = {name: snapshot(root / name) for name in ['libraries']}
    files_before = {p.name: p.read_bytes() for p in root.glob('*.json')}
    directories_before = {p.name for p in root.iterdir()}
    server.search_h5p_types(installed_only=True)
    server.get_h5p_activity_schema('H5P.TrueFalse', 1, 8)
    assert before == {name: snapshot(root / name) for name in ['libraries']}
    assert files_before == {p.name: p.read_bytes() for p in root.glob('*.json')}
    assert directories_before - {'backend.lock'} == {p.name for p in root.iterdir()} - {'backend.lock'}


@pytest.mark.parametrize('scopes,immutable', [('', '0'), ('libraries:install catalog:refresh', '1')])
def test_real_stdio_does_not_skip_policy(tmp_path, scopes, immutable):
    command = json.loads(os.environ.get('H5P_MCP_TEST_COMMAND', 'null')) or [sys.executable, '-m', 'h5p_mcp.server']
    env = dict(os.environ, H5P_MCP_ADMIN_SCOPES=scopes, H5P_MCP_IMMUTABLE=immutable)
    env.pop('PYTHONPATH', None)
    transport = StdioTransport(command=command[0], args=command[1:], env=env, cwd=str(tmp_path))
    async def run():
        async with Client(transport) as client:
            assert not ({t.name for t in await client.list_tools()} & set(admin.TOOL_SCOPES))
            denied = await client.call_tool('refresh_h5p_catalog', {}, raise_on_error=False)
            assert denied.is_error
            denied_legacy = await client.call_tool('list_h5p_activities', {'refresh': True}, raise_on_error=False)
            assert denied_legacy.is_error
            denied_install = await client.call_tool('get_h5p_activity_schema', {'machine_name': 'H5P.TrueFalse', 'install_if_missing': True}, raise_on_error=False)
            assert denied_install.is_error
            assert not (await client.call_tool('search_h5p_types', {})).is_error
    asyncio.run(run())


def test_immutable_cli_setup_rejected_before_runtime(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'h5p_mcp.server', '--setup-lumi'],
                            env=dict(os.environ, H5P_MCP_IMMUTABLE='1'), cwd=tmp_path,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and 'disabled by H5P_MCP_IMMUTABLE' in result.stderr


def test_policy_fails_closed_on_typo(monkeypatch):
    monkeypatch.setenv('H5P_MCP_ADMIN_SCOPES', 'libraries:instal')
    with pytest.raises(ValueError, match='Unknown'):
        admin.AdminPolicy.from_environment()
