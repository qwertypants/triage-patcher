from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .contract import Command


@dataclass(frozen=True)
class Execution:
    command_id: str
    exit_code: int | None
    output: str
    timed_out: bool = False
    cancelled: bool = False
    output_limited: bool = False


def disposable_copy(source: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory(prefix="repair-agent-")
    destination = Path(temp.name) / "work"
    shutil.copytree(source, destination, symlinks=True, ignore=shutil.ignore_patterns(".git", ".env", ".aws", ".ssh", "__pycache__", "*.pyc"))
    return temp, destination


def run_command(command: Command, cwd: Path, timeout: int, max_output_bytes: int, cancel: callable | None = None) -> Execution:
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd / ".repair-empty-home"), "LANG": "C.UTF-8"}
    capture = tempfile.TemporaryFile()
    process = subprocess.Popen(command.argv, cwd=cwd, shell=False, stdin=subprocess.DEVNULL, stdout=capture, stderr=subprocess.STDOUT, text=False, env=environment, start_new_session=True)
    started = time.monotonic()
    output = b""
    timed_out = cancelled = output_limited = False
    try:
        while process.poll() is None:
            if cancel and cancel():
                cancelled = True
                break
            if time.monotonic() - started >= timeout:
                timed_out = True
                break
            if os.fstat(capture.fileno()).st_size > max_output_bytes:
                output_limited = True
                break
            time.sleep(0.02)
        if timed_out or cancelled or output_limited:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1)
        output_limited = output_limited or os.fstat(capture.fileno()).st_size > max_output_bytes
        capture.seek(0)
        output = capture.read(max_output_bytes)
    except Exception:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    finally:
        capture.close()
    suffix = "\n[output truncated: output budget exceeded]" if output_limited else ""
    return Execution(command.id, process.returncode, output.decode("utf-8", errors="replace") + suffix, timed_out, cancelled, output_limited)
