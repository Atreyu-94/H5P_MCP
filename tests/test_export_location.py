from h5p_mcp.utils.file_utils import resolve_export_dir


def test_default_exports_follow_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("H5P_MCP_EXPORT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_export_dir(None) == tmp_path / "exports"


def test_explicit_directory_and_environment_override(tmp_path, monkeypatch):
    monkeypatch.delenv("H5P_MCP_EXPORT_DIR", raising=False)
    assert resolve_export_dir(str(tmp_path / "explicit")) == tmp_path / "explicit"
    monkeypatch.setenv("H5P_MCP_EXPORT_DIR", str(tmp_path / "override"))
    assert resolve_export_dir(str(tmp_path / "explicit")) == tmp_path / "override"
