"""Invoke Lumi through a bounded JSON subprocess, keeping npm outside uv installs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from filelock import FileLock

SOURCE = Path(__file__).resolve().parent / "lumi"


def data_dir() -> Path:
    configured = os.environ.get("H5P_MCP_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    return (base / "h5p-mcp" / "lumi" / "core-1.28").resolve()


def runtime_dir() -> Path:
    digest = hashlib.sha256((SOURCE / "package-lock.json").read_bytes()).hexdigest()[:16]
    return data_dir() / "runtime" / digest


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js 22.12+ is required by Lumi. Install Node.js, then run h5p-mcp --setup-lumi.")
    return node


def _invoke(action: str, **payload) -> dict:
    runtime = runtime_dir()
    if not (runtime / ".ready").is_file():
        raise RuntimeError("Lumi is not initialized. Run h5p-mcp --setup-lumi once (requires Node.js 22.12+ and npm).")
    env = dict(os.environ, H5P_MCP_LUMI_RUNTIME=str(runtime))
    env.pop("DEBUG", None)  # Keep the child protocol quiet regardless of caller logging.
    request = {"action": action, "data_dir": str(data_dir()), **payload}
    try:
        process = subprocess.run(
            [_node(), str(SOURCE / "bridge.cjs")], input=json.dumps(request, ensure_ascii=False),
            text=True, encoding="utf-8", capture_output=True, env=env, timeout=300,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Lumi {action} exceeded 300 seconds") from error
    try:
        result = json.loads(process.stdout)
    except ValueError as error:
        raise RuntimeError(f"Lumi did not return JSON: {process.stderr[-2000:]}") from error
    if process.returncode:
        raise RuntimeError("Lumi: " + "; ".join(result.get("errors", [process.stderr[-2000:]])))
    return result


def run_lumi(action: str, **payload) -> dict:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    # Separate MCP processes may share the same library cache. Serialize updates
    # and exports so an installation cannot change libraries halfway through a ZIP.
    with FileLock(str(root / "backend.lock"), timeout=300):
        return _invoke(action, **payload)


def setup_lumi(packages: list[str] | None = None) -> dict:
    node = _node()
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if tuple(map(int, version.lstrip("v").split(".")[:2])) < (22, 12):
        raise RuntimeError("Lumi requires Node.js 22.12 or later")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("npm is required for h5p-mcp --setup-lumi")
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root / "backend.lock"), timeout=300):
        runtime = runtime_dir()
        if not (runtime / ".ready").is_file():
            runtime.mkdir(parents=True, exist_ok=True)
            for name in ("package.json", "package-lock.json"):
                shutil.copyfile(SOURCE / name, runtime / name)
            manifest = json.loads((SOURCE / "provenance.json").read_text(encoding="utf-8"))
            archive = SOURCE / manifest["archive"]
            if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["sha256"]:
                raise RuntimeError("Lumi package checksum mismatch")
            shutil.copyfile(archive, runtime / archive.name)
            # Shell-free execution; scripts from downloaded dependencies are disabled.
            subprocess.run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                           cwd=runtime, check=True, timeout=300)
            (runtime / ".ready").touch()
        # Subsequent setup calls reuse installed libraries unless explicit packages
        # were provided. Export itself never contacts npm or H5P Hub.
        if not packages:
            try:
                return _invoke("catalog")
            except RuntimeError:
                pass
        return _invoke("setup", packages=[str(Path(p).resolve()) for p in (packages or [])])
