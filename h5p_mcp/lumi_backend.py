"""Invoke Lumi through a bounded JSON subprocess, keeping npm outside uv installs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from filelock import FileLock, Timeout
from h5p_mcp.limits import limit, check_tree

class BackendError(RuntimeError):
    def __init__(self, message, code="BACKEND_ERROR", details=None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = details


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


def _invoke(action: str, *, deadline: float | None = None, **payload) -> dict:
    deadline = deadline if deadline is not None else time.monotonic() + limit("SECONDS", 300)
    runtime = runtime_dir()
    if not (runtime / ".ready").is_file():
        raise RuntimeError("Lumi is not initialized. Run h5p-mcp --setup-lumi once (requires Node.js 22.12+ and npm).")
    env = dict(os.environ, H5P_MCP_LUMI_RUNTIME=str(runtime))
    env.pop("DEBUG", None)  # Keep the child protocol quiet regardless of caller logging.
    request = {"action": action, "data_dir": str(data_dir()), **payload}
    check_tree(request)
    encoded = json.dumps(request, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > limit("JSON_BYTES", 16777216):
        raise BackendError("JSON byte budget exceeded", "INPUT_TOO_LARGE")
    # Files bound output memory; polling also enforces output and wall-clock budgets.
    with tempfile.TemporaryFile() as incoming, tempfile.TemporaryFile() as outgoing, tempfile.TemporaryFile() as errors:
        incoming.write(encoded.encode("utf-8"))
        incoming.seek(0)
        if time.monotonic() >= deadline:
            raise BackendError('Backend deadline exceeded before launch', 'BACKEND_TIMEOUT')
        process = subprocess.Popen([_node(), str(SOURCE / "bridge.cjs")], stdin=incoming,
                                   stdout=outgoing, stderr=errors, env=env)
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise BackendError(f"Lumi {action} timed out", "BACKEND_TIMEOUT")
                if any(os.fstat(f.fileno()).st_size > limit("OUTPUT_BYTES", 33554432) for f in (outgoing, errors)):
                    raise BackendError("Backend output budget exceeded", "OUTPUT_TOO_LARGE")
                time.sleep(0.05)
        finally:
            # Also executed on KeyboardInterrupt/caller-side exceptions.
            if process.poll() is None:
                process.kill()
            process.wait()
        if any(os.fstat(f.fileno()).st_size > limit("OUTPUT_BYTES", 33554432) for f in (outgoing, errors)):
            raise BackendError("Backend output budget exceeded", "OUTPUT_TOO_LARGE")
        outgoing.seek(0)
        errors.seek(max(0, os.fstat(errors.fileno()).st_size - 2000))
        stderr = errors.read().decode("utf-8", errors="replace")
        try:
            result = json.load(outgoing)
        except ValueError as error:
            raise BackendError(f"Lumi did not return JSON: {stderr}") from error
    if process.returncode:
        raise BackendError("; ".join(result.get("errors", [stderr])), result.get("code", "BACKEND_ERROR"), result.get("details"))
    return result


def run_lumi(action: str, **payload) -> dict:
    deadline = time.monotonic() + limit("SECONDS", 300)
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    # Separate MCP processes may share the same library cache. Serialize updates
    # and exports so an installation cannot change libraries halfway through a ZIP.
    try:
        with FileLock(str(root / "backend.lock"), timeout=max(0, deadline-time.monotonic())):
            return _invoke(action, deadline=deadline, **payload)
    except Timeout as error:
        raise BackendError('Backend deadline exceeded while waiting for lock', 'BACKEND_TIMEOUT') from error


def setup_lumi(packages: list[str] | None = None) -> dict:
    if packages:
        from h5p_mcp.validators.package_validator import prevalidate_archive
        for package in packages:
            prevalidate_archive(Path(package))
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
