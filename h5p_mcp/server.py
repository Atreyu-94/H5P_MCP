from __future__ import annotations

import argparse
import logging
from typing import Any

from fastmcp import FastMCP
from h5p_mcp.skills_extension import register_authoring_skill

from h5p_mcp.exporters.h5p_exporter import H5PExporter
from h5p_mcp.models.activity import Activity
from h5p_mcp.models.reports import PreparationReport, ExportReport, ValidationReport, BatchReport, verification
from h5p_mcp.lumi_backend import run_lumi
from h5p_mcp.limits import limit
from h5p_mcp.jobs import cancellable, check_cancelled
from h5p_mcp.validators.package_validator import validate_h5p_package


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    # Ensure UTF-8 output on Windows terminals where possible.
    try:
        import sys

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


mcp = FastMCP("h5p-authoring")
register_authoring_skill(mcp)


def local_tool(**options):
    """Keep the Python API synchronous, with cancellable MCP registration."""
    def register(function):
        mcp.tool(**options)(cancellable(function))
        return function
    return register


@local_tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
def list_h5p_activities(query: str = "", installed_only: bool = False,
                        refresh: bool = False, offset: int = 0, limit: int = 20) -> dict[str, Any]:
    """Discover Hub activities and installed versions. Cached/offline by default.

    refresh=True explicitly contacts the H5P Hub and updates the local catalog.
    Paginated results distinguish availability from supported MCP authoring.
    core_compatible refers to the Hub version, not every installed version.
    """
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("offset must be non-negative and limit must be between 1 and 100")
    return run_lumi("discover", query=query, installed_only=installed_only,
                    refresh=refresh, offset=offset, limit=limit)


@local_tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
def get_h5p_activity_schema(machine_name: str, major_version: int | None = None,
                            minor_version: int | None = None,
                            install_if_missing: bool = False) -> dict[str, Any]:
    """Read native semantics.json and library metadata, including dependencies.

    With no version, select the newest installed major/minor. Provide both
    version numbers to read an exact installed version. By default no download
    occurs. install_if_missing=True explicitly downloads the current Hub version
    and dependencies when the requested library is absent. It never upgrades an
    already installed version. Use the returned exact library in create_h5p_activity.
    """
    import re
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", machine_name):
        raise ValueError("Invalid library machine name")
    if (major_version is None) != (minor_version is None):
        raise ValueError("Provide both major_version and minor_version, or neither")
    if major_version is not None and (major_version < 0 or minor_version < 0):
        raise ValueError("Library version numbers must be non-negative")
    return run_lumi("schema", machine_name=machine_name, major_version=major_version,
                    minor_version=minor_version, install_if_missing=install_if_missing)


@local_tool()
def create_h5p_activity(title: str, library: str, params: dict[str, Any],
                        language: str = "en", license: str = "U",
                        assets: dict[str, str] | None = None) -> PreparationReport:
    """Prepare any installed runnable library using its exact native semantics.

    Read get_h5p_activity_schema first, including schemas for nested libraries.
    Returns ok/errors/warnings and normalized activity with schema defaults.
    Media use path="asset:<id>" and assets={<id>: absolute local path}.
    Checks are structural; editor-widget logic and playback still need testing.
    No library download occurs here.
    LaTeX delimiters are detected recursively. The mathematics report identifies
    MathDisplay; missing installation blocks export. Use \\( ... \\) or \\[ ... \\].
    """
    activity = Activity(title=title, library=library, params=params, language=language,
                        license=license, assets=assets or {})
    report = run_lumi("prepare", activity=activity.model_dump())
    excessive = any(d["code"] in {"INPUT_TOO_DEEP", "INPUT_TOO_LARGE"} for d in report["diagnostics"])
    report["verification"] = verification(structure="failed" if excessive else "passed",
                                           semantics="not_run" if excessive else "passed" if report["ok"] else "failed")
    return report


@local_tool()
def export_h5p(activity: Activity, output_name: str) -> ExportReport:
    """Recheck a native activity and export it with libraries and local assets.

    Pass the activity returned by create_h5p_activity after checking ok=true.
    Existing files are never overwritten. Downloads are never implicit.
    """
    result = H5PExporter().export(Activity.model_validate(activity), output_name=output_name)
    return {"output_path": str(result.output_path), "h5p_json": result.h5p_json,
            "content_json": result.content_json, "verification": verification(structure="passed", semantics="passed")}


@local_tool()
def validate_h5p(path: str) -> ValidationReport:
    """Check JSON roots and import a package into empty Lumi storage, not playback."""
    res = validate_h5p_package(path)
    return {"ok": res.ok, "errors": res.errors, "warnings": res.warnings, "verification": res.verification}


@local_tool()
def export_h5p_batch(activities: list[Activity], name_prefix: str = "activity") -> BatchReport:
    """Export native activities independently, returning per-item errors and paths.

    Successful items remain on disk if another item fails; this is not atomic.
    """
    if len(activities) > limit("BATCH", 50):
        raise ValueError("BATCH_TOO_LARGE: maximum batch size exceeded")
    exporter = H5PExporter()
    results = []
    for idx, activity in enumerate(activities):
        check_cancelled()
        name = f"{name_prefix}_{idx+1:03d}"
        try:
            exported = exporter.export(Activity.model_validate(activity), output_name=name)
            results.append({"ok": True, "output_name": name, "output_path": str(exported.output_path)})
        except (ValueError, RuntimeError, OSError) as error:
            results.append({"ok": False, "output_name": name, "error": str(error)})
    return {"count": len(results), "succeeded": sum(r["ok"] for r in results), "results": results}


def main() -> None:
    _configure_logging()

    parser = argparse.ArgumentParser(description="H5P Native Authoring MCP Server")
    parser.add_argument("--setup-lumi", action="store_true", help="Install the Node backend and H5P libraries once")
    parser.add_argument("--lumi-package", action="append", default=[], help="Install libraries from a trusted local .h5p during setup; repeatable")
    args = parser.parse_args()

    if args.lumi_package and not args.setup_lumi:
        parser.error("--lumi-package requires --setup-lumi")
    if args.setup_lumi:
        import json
        from h5p_mcp.lumi_backend import setup_lumi
        print(json.dumps(setup_lumi(args.lumi_package), ensure_ascii=False))
        return

    # MCP stdio server
    mcp.run()


if __name__ == "__main__":
    main()

