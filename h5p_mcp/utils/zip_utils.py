from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def zip_dir(source_dir: Path, output_zip: Path) -> None:
    """
    Zip a directory preserving relative paths.

    Only files are added — never directory entries — because H5P platforms
    (Lumi, Moodle) reject bare directory records with a "not-in-whitelist"
    error for paths like "content/".
    """
    if not source_dir.is_dir():
        raise ValueError(f"source_dir is not a directory: {source_dir}")
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as z:
        for p in sorted(source_dir.rglob("*")):
            # Skip directories — H5P does not allow directory entries.
            if not p.is_file():
                continue
            # Skip the output zip itself in case it lives inside source_dir.
            if p.resolve() == output_zip.resolve():
                continue
            arcname = p.relative_to(source_dir).as_posix()
            z.write(p, arcname)
