from __future__ import annotations

import json
import stat
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from h5p_mcp.lumi_backend import run_lumi
from h5p_mcp.limits import limit
from h5p_mcp.models.reports import verification
from h5p_mcp.utils.file_utils import authorized_path
from h5p_mcp.jobs import check_cancelled


@dataclass(frozen=True)
class H5PValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    verification: dict[str, str] = field(default_factory=verification)


def validate_h5p_package(path: str | Path) -> H5PValidationResult:
    """
    Validate JSON roots, then import with Lumi into empty temporary storage.

    Requires a self-contained package. Import validation is not playback testing.
    """
    p = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    if not p.exists():
        return H5PValidationResult(ok=False, errors=[f"File does not exist: {p}"], warnings=[])
    if p.suffix.lower() != ".h5p":
        warnings.append("File does not have .h5p extension (still may be a valid zip).")

    try:
        p = authorized_path(p, 'H5P_MCP_PACKAGE_ROOTS')
        if p.stat().st_size > limit("ZIP_ARCHIVE_BYTES", 134217728):
            raise ValueError("ZIP compressed byte budget exceeded")
        with ZipFile(p, "r") as z:
            _check_archive(z)
            names = set(z.namelist())
            if "h5p.json" not in names:
                errors.append("Missing 'h5p.json' at zip root.")
            if "content/content.json" not in names:
                errors.append("Missing 'content/content.json'.")

            h5p_json = _read_json_from_zip(z, "h5p.json", errors)
            content_json = _read_json_from_zip(z, "content/content.json", errors)

            if isinstance(h5p_json, dict):
                if "mainLibrary" not in h5p_json:
                    errors.append("h5p.json missing 'mainLibrary'.")
                if "preloadedDependencies" not in h5p_json:
                    errors.append("h5p.json missing 'preloadedDependencies'.")
                else:
                    deps = h5p_json.get("preloadedDependencies")
                    if not isinstance(deps, list) or not deps:
                        errors.append("'preloadedDependencies' must be a non-empty list.")

            if not isinstance(h5p_json, dict):
                errors.append("h5p.json must contain a JSON object.")
            if not isinstance(content_json, dict):
                errors.append("content/content.json must contain a JSON object.")

    except Exception as e:  # noqa: BLE001
        errors.append(f"Failed to read zip: {e}")

    stages = verification(structure="failed" if errors else "passed")
    if not errors:
        try:
            report = run_lumi("validate", path=str(p.resolve()))
            errors.extend(report.get("errors", []))
            warnings.extend(report.get("warnings", []))
        except RuntimeError as error:
            errors.append(str(error))
        stages["importation"] = "failed" if errors else "passed"
    return H5PValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings, verification=stages)


def _check_member_path(member, paths):
    # ZipInfo normalizes backslashes on Windows and truncates at NUL. Validate
    # the original header name so those transformations cannot hide ambiguity.
    name = member.orig_filename
    directory = member.is_dir()
    parts = (name[:-1] if directory else name).split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    reserved.update(f'{prefix}{n}' for prefix in ('COM', 'LPT') for n in '123456789¹²³')
    if ('\\' in name or len(parts) > limit('ZIP_PATH_DEPTH', 32) or
            any(not part or part in ('.', '..') or any(c in part for c in '<>:"|?*') or
                part.endswith((' ', '.')) or any(ord(c) < 32 for c in part) or
                part.split('.')[0].upper() in reserved for part in parts)):
        raise ValueError('Unsafe ZIP member path')
    mode = stat.S_IFMT(member.external_attr >> 16)
    if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or (mode == stat.S_IFDIR and not directory):
        raise ValueError('Unsafe ZIP member type (symlink or special file)')
    for index in range(1, len(parts) + 1):
        original = '/'.join(parts[:index])
        key = unicodedata.normalize('NFC', original).casefold()
        kind = directory or index < len(parts)
        previous = paths.get(key)
        if previous is not None and previous != (original, kind):
            raise ValueError('Unsafe ZIP path collision or file/directory conflict')
        paths[key] = (original, kind)


def prevalidate_archive(path: Path) -> None:
    """Same archive boundary for administrative packages, without content roots."""
    path = authorized_path(path, 'H5P_MCP_PACKAGE_ROOTS')
    if path.stat().st_size > limit('ZIP_ARCHIVE_BYTES', 134217728):
        raise ValueError('ZIP compressed byte budget exceeded')
    with ZipFile(path) as archive:
        _check_archive(archive)


def _check_archive(archive: ZipFile) -> None:
    members = archive.infolist()
    if len(members) > limit('ZIP_MEMBERS', 20000):
        raise ValueError('ZIP member budget exceeded')
    if len({m.filename for m in members}) != len(members):
        raise ValueError('Duplicate ZIP member names')
    if sum(m.file_size for m in members) > limit('ZIP_BYTES', 536870912):
        raise ValueError('ZIP expanded byte budget exceeded')
    paths = {}
    expanded = 0
    for member in members:
        check_cancelled()
        _check_member_path(member, paths)
        if member.file_size > limit('ZIP_MEMBER_BYTES', 134217728):
            raise ValueError('ZIP member byte budget exceeded')
        if member.file_size > max(1, member.compress_size)*limit('ZIP_RATIO', 1000):
            raise ValueError('ZIP compression ratio budget exceeded')
        # Drain bounded chunks to check CRC and actual bytes for both callers.
        read = 0
        with archive.open(member) as stream:
            while chunk := stream.read(65536):
                check_cancelled()
                read += len(chunk)
                expanded += len(chunk)
                if read > limit('ZIP_MEMBER_BYTES', 134217728) or expanded > limit('ZIP_BYTES', 536870912):
                    raise ValueError('ZIP streamed byte budget exceeded')
        if read != member.file_size:
            raise ValueError('ZIP member size mismatch')


def _read_json_from_zip(z: ZipFile, name: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        maximum = limit("JSON_BYTES", 16777216)
        if z.getinfo(name).file_size > maximum:
            raise ValueError("JSON byte budget exceeded")
        with z.open(name) as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError("JSON byte budget exceeded")
    except KeyError:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"Invalid JSON in '{name}': {e}")
        return None

