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
    base = Path(env or configured or Path(__file__).resolve().parents[1] / "exports")
    ensure_dir(base)
    return base

