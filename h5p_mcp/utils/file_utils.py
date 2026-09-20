from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_filename(name: str, *, default: str = "export") -> str:
    """
    Convert an arbitrary string into a filesystem-safe filename stem.
    """
    cleaned = SAFE_NAME_RE.sub("_", name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or default


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


@contextmanager
def temp_workdir(prefix: str = "h5p_mcp_") -> Iterator[Path]:
    """
    Create a temporary working directory and clean it up.

    Exception-safe: cleans even on export failures.
    """
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        # Best-effort cleanup (Windows file locks can be finicky).
        try:
            shutil.rmtree(d, ignore_errors=False)
        except Exception:  # noqa: BLE001
            shutil.rmtree(d, ignore_errors=True)


def resolve_export_dir(configured: str | None) -> Path:
    """
    Resolve export directory with an environment override.
    """
    env = os.environ.get("H5P_MCP_EXPORT_DIR")
    # Installed tools must not store user activities in site-packages or uv's cache.
    base = Path(env or configured or Path.cwd() / "exports").expanduser().resolve()
    base = authorized_path(base, 'H5P_MCP_EXPORT_ROOTS')
    ensure_dir(base)
    return base


def authorized_path(path: Path, variable: str) -> Path:
    resolved = path.expanduser().resolve()
    raw = os.environ.get(variable)
    if raw is None:
        return resolved
    roots = json.loads(raw)
    if not isinstance(roots, list) or any(not isinstance(root,str) or not Path(root).is_absolute() for root in roots):
        raise ValueError(f'{variable} must be a JSON list of absolute directories')
    if not any(resolved.is_relative_to(Path(root).resolve()) for root in roots):
        raise ValueError(f'Path outside authorized roots: {variable}')
    return resolved

