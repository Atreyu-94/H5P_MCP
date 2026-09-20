from __future__ import annotations

import logging
import os
import errno
import ctypes
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from h5p_mcp.models.activity import Activity
from h5p_mcp.utils.file_utils import resolve_export_dir, safe_filename
from h5p_mcp.lumi_backend import run_lumi
from h5p_mcp.jobs import check_cancelled


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    h5p_json: dict[str, Any]
    content_json: dict[str, Any]
    preparation_manifest: dict[str, Any] | None = None


class H5PExporter:
    """
    Export native activities into .h5p (zip) packages.

    The resulting .h5p includes:
    - h5p.json
    - content/content.json and all libraries resolved and packaged by Lumi
    """

    def __init__(self, *, export_dir: str | None = None) -> None:
        self._export_dir = resolve_export_dir(export_dir)

    def export(self, activity: Activity, *, output_name: str) -> ExportResult:
        out_path = self._export_dir / f"{safe_filename(output_name)}.h5p"

        if out_path.exists():
            raise FileExistsError(f"OUTPUT_EXISTS: Export already exists; choose a new output_name: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".lumi-", dir=out_path.parent) as work:
            package = Path(work) / "activity.h5p"
            result = run_lumi("export", activity=activity.model_dump(), path=str(package))
            # Same-filesystem, exclusive publication: no partial output or overwrite,
            # including two concurrent exports with the same output name.
            check_cancelled()
            publish_exclusive(package, out_path)
        return ExportResult(output_path=out_path, h5p_json=result["h5p_json"], content_json=result["content_json"], preparation_manifest=result.get('preparation_manifest'))


def publish_exclusive(source: Path, destination: Path) -> None:
    """Publish a complete staging file; never copy bytes to a visible final path."""
    try:
        os.link(source, destination)
        return
    except OSError as error:
        if error.errno not in (errno.EPERM, errno.ENOTSUP, errno.ENOSYS, errno.EACCES):
            raise
    if os.name == 'nt':
        # Windows rename fails if destination exists (unlike POSIX rename).
        os.rename(source, destination)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith('linux') and hasattr(libc,'renameat2'):
        operation = libc.renameat2
        operation.argtypes = [ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(-100,os.fsencode(source),-100,os.fsencode(destination),1)
    elif sys.platform == 'darwin' and hasattr(libc,'renamex_np'):
        operation = libc.renamex_np
        operation.argtypes = [ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(os.fsencode(source),os.fsencode(destination),4)
    else:
        raise OSError(errno.ENOTSUP,'Atomic no-replace publication unavailable')
    if result:
        code = ctypes.get_errno()
        raise OSError(code,os.strerror(code),str(destination))
