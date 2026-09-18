from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from h5p_mcp.models.activity import Activity
from h5p_mcp.utils.file_utils import resolve_export_dir, safe_filename
from h5p_mcp.lumi_backend import run_lumi


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    h5p_json: dict[str, Any]
    content_json: dict[str, Any]


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
            raise FileExistsError(f"Export already exists; choose a new output_name: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".lumi-", dir=out_path.parent) as work:
            package = Path(work) / "activity.h5p"
            result = run_lumi("export", activity=activity.model_dump(), path=str(package))
            # Same-filesystem, exclusive publication: no partial output or overwrite,
            # including two concurrent exports with the same output name.
            os.link(package, out_path)
        return ExportResult(output_path=out_path, h5p_json=result["h5p_json"], content_json=result["content_json"])
