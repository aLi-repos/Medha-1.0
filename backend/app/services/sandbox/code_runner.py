"""Isolated Python code runner — one controlled local subprocess sandbox.

Isolation properties (Windows, no Docker):
- Real child process (python -I) with a fresh temp working directory
- Environment allowlist only (no MEDHA secrets / DATABASE_URL / JWT)
- Runtime audit hooks block socket connect, os.system, subprocess
- Runtime open() guard blocks paths outside sandbox / Python prefix / SYSTEMROOT
- Timeout terminates the process tree
- Temporary sandbox directory is removed after every run

This is controlled local execution with runtime guards — not a container,
not air-gapped, not a perfect OS-level sandbox.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

MAX_CODE_BYTES = 20_000
MAX_INPUT_JSON_BYTES = 8_000
MAX_OUTPUT_BYTES = 64_000
DEFAULT_TIMEOUT_S = 5.0

# Installed inside the child process before user code runs.
_BOOTSTRAP_SOURCE = r'''
import json
import os
import sys

SANDBOX_ROOT = os.path.abspath(os.environ.get("MEDHA_SANDBOX_ROOT", os.getcwd()))
PYTHON_PREFIX = os.path.abspath(sys.prefix)
SYSTEMROOT = os.path.abspath(os.environ.get("SYSTEMROOT", r"C:\Windows"))
DEVNULLS = {os.devnull, "nul", "NUL", "\\\\.\\NUL", "/dev/null"}

_BLOCKED_EVENTS = frozenset(
    {
        "socket.connect",
        "socket.getaddrinfo",
        "socket.bind",
        "socket.sendto",
        "urllib.Request",
        "os.system",
        "subprocess.Popen",
    }
)


def _to_path(value):
    if value is None or isinstance(value, int):
        return None
    if isinstance(value, bytes):
        try:
            value = os.fsdecode(value)
        except Exception:
            return None
    if hasattr(value, "__fspath__"):
        try:
            value = os.fspath(value)
        except Exception:
            return None
    if not isinstance(value, str):
        return None
    return value


def _path_allowed(path_value: str) -> bool:
    if path_value in DEVNULLS:
        return True
    try:
        ap = os.path.abspath(path_value)
    except Exception:
        return False
    if ap == SANDBOX_ROOT or ap.startswith(SANDBOX_ROOT + os.sep):
        return True
    if ap.startswith(PYTHON_PREFIX + os.sep) or ap == PYTHON_PREFIX:
        return True
    if SYSTEMROOT and (ap.startswith(SYSTEMROOT + os.sep) or ap == SYSTEMROOT):
        return True
    return False


def _audit_hook(event, args):
    if event in _BLOCKED_EVENTS:
        raise PermissionError(f"Sandbox network/process policy blocked: {event}")
    if event == "open":
        path_value = _to_path(args[0] if isinstance(args, (tuple, list)) and args else args)
        if path_value is None:
            return
        if not _path_allowed(path_value):
            raise PermissionError(f"Sandbox filesystem access blocked: {path_value}")


sys.addaudithook(_audit_hook)

_input_raw = os.environ.get("MEDHA_SANDBOX_INPUT", "{}")
try:
    INPUT = json.loads(_input_raw) if _input_raw else {}
except Exception:
    INPUT = {}

_globals = {"__name__": "__main__", "__file__": "<sandbox>", "INPUT": INPUT}
if isinstance(INPUT, dict):
    for _key, _value in INPUT.items():
        if isinstance(_key, str) and _key.isidentifier() and not _key.startswith("_"):
            _globals[_key] = _value

_user_code_path = os.path.join(SANDBOX_ROOT, "user_code.py")
with open(_user_code_path, "r", encoding="utf-8") as _f:
    _src = _f.read()

exec(compile(_src, "<sandbox>", "exec"), _globals, _globals)
'''


class CodeSandboxError(Exception):
    """Invalid code input or sandbox setup failure (before execution)."""


@dataclass
class CodeRunResult:
    status: str  # completed | failed | timeout
    output: str
    error: str
    duration_ms: float
    exit_code: int | None
    timed_out: bool
    output_truncated: bool = False
    network: str = "blocked"
    sandbox: str = "active"


def _validate_code(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        raise CodeSandboxError("code is required for code_executor")
    if "\x00" in code:
        raise CodeSandboxError("code contains null bytes")
    size = len(code.encode("utf-8", errors="replace"))
    if size > MAX_CODE_BYTES:
        raise CodeSandboxError(f"code exceeds {MAX_CODE_BYTES} byte limit")
    return code


def _validate_input(input_data: dict) -> str:
    try:
        payload = json.dumps(input_data, default=str)
    except (TypeError, ValueError) as exc:
        raise CodeSandboxError(f"input_data is not serializable: {exc}") from exc
    if len(payload.encode("utf-8", errors="replace")) > MAX_INPUT_JSON_BYTES:
        raise CodeSandboxError(f"input_data exceeds {MAX_INPUT_JSON_BYTES} byte limit")
    return payload


def _clean_env(sandbox_dir: Path, input_json: str) -> dict[str, str]:
    """Allowlist environment — never copy MEDHA_* secrets or full host env."""
    env: dict[str, str] = {}
    for key in (
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "PATH",
    ):
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["TEMP"] = str(sandbox_dir)
    env["TMP"] = str(sandbox_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["MEDHA_SANDBOX_ROOT"] = str(sandbox_dir)
    env["MEDHA_SANDBOX_INPUT"] = input_json
    return env


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def run_isolated_python(
    code: str,
    *,
    input_data: dict | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
) -> CodeRunResult:
    """Execute Python code in a child process with runtime FS/network guards."""
    code = _validate_code(code)
    input_json = _validate_input(input_data or {})
    if timeout_s <= 0:
        raise CodeSandboxError("timeout must be positive")
    if max_output_bytes <= 0:
        raise CodeSandboxError("max_output_bytes must be positive")

    sandbox_dir = Path(tempfile.mkdtemp(prefix="medha_sbx_"))
    stdout_path = sandbox_dir / "stdout.txt"
    proc: subprocess.Popen | None = None
    start = time.monotonic()
    timed_out = False
    raw_out = b""
    exit_code: int | None = None

    try:
        user_path = sandbox_dir / "user_code.py"
        boot_path = sandbox_dir / "bootstrap.py"
        user_path.write_text(code, encoding="utf-8")
        boot_path.write_text(_BOOTSTRAP_SOURCE, encoding="utf-8")

        env = _clean_env(sandbox_dir, input_json)
        popen_kwargs: dict = {
            "cwd": str(sandbox_dir),
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )

        proc = subprocess.Popen(
            [sys.executable, "-I", "-E", "-B", str(boot_path)],
            **popen_kwargs,
        )
        try:
            raw_out, _ = proc.communicate(timeout=timeout_s)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process_tree(proc)
            exit_code = proc.returncode
            try:
                raw_out, _ = proc.communicate(timeout=2)
            except Exception:
                raw_out = raw_out or b""

        duration_ms = (time.monotonic() - start) * 1000
        text = (raw_out or b"").decode("utf-8", errors="replace")
        output_truncated = False
        if len(text.encode("utf-8", errors="replace")) > max_output_bytes:
            truncated_bytes = text.encode("utf-8", errors="replace")[:max_output_bytes]
            text = truncated_bytes.decode("utf-8", errors="replace") + "\n[output truncated]"
            output_truncated = True

        if timed_out:
            status = "timeout"
            error = f"Execution exceeded {timeout_s}s limit; process terminated"
        elif output_truncated:
            status = "failed"
            error = f"Output exceeded {max_output_bytes} byte limit"
        elif exit_code == 0:
            status = "completed"
            error = ""
        else:
            status = "failed"
            error = text.strip() or f"Process exited with code {exit_code}"
            text = text if text else ""

        # stdout_path reserved for future file-capture; ensure no leftover secret.
        if stdout_path.exists():
            try:
                stdout_path.unlink()
            except OSError:
                pass

        return CodeRunResult(
            status=status,
            output=text if status == "completed" else (text if text else ""),
            error=error,
            duration_ms=duration_ms,
            exit_code=exit_code,
            timed_out=timed_out,
            output_truncated=output_truncated,
            network="blocked",
            sandbox="active",
        )
    except CodeSandboxError:
        raise
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        if proc is not None:
            _terminate_process_tree(proc)
        return CodeRunResult(
            status="failed",
            output="",
            error=str(exc),
            duration_ms=duration_ms,
            exit_code=None,
            timed_out=False,
            network="blocked",
            sandbox="active",
        )
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)
