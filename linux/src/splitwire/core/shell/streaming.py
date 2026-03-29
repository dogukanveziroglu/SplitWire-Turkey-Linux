"""
Streaming command execution for SplitWire-Turkey Linux.

Handles real-time output streaming from subprocess execution
with timeout management and thread-based I/O.
"""

import contextlib
import logging
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .models import CommandResult, CommandStatus

logger = logging.getLogger(__name__)

_PREVIEW_LEN = 80
_READER_JOIN_TIMEOUT = 1  # seconds to wait for reader thread after terminate


def _cmd_preview(cmd_str: str) -> str:
    """Truncate a command string for log display."""
    if len(cmd_str) > _PREVIEW_LEN:
        return cmd_str[:_PREVIEW_LEN] + "..."
    return cmd_str


def run_with_output(
    cmd: list[str],
    cmd_str: str,
    callback: Callable[[str], None],
    run_timeout: int,
    run_cwd: Path | None,
    run_env: dict[str, str],
) -> CommandResult:
    """Run a command with real-time output streaming.

    Each stdout line is passed to *callback* as it arrives.

    Args:
        cmd: Parsed command argument list.
        cmd_str: Display string for logging.
        callback: Called with each output line (stripped).
        run_timeout: Timeout in seconds.
        run_cwd: Working directory for the process.
        run_env: Full environment variable mapping.

    Returns:
        CommandResult with execution details.
    """
    start_time = time.time()
    stdout_lines: list[str] = []
    preview = _cmd_preview(cmd_str)
    logger.debug("[SHELL] Streaming execution: %s", preview)

    try:
        process = _create_streaming_process(cmd, run_cwd, run_env)
        return _collect_output(
            process,
            callback,
            stdout_lines,
            cmd_str,
            run_timeout,
            start_time,
            preview,
        )
    except FileNotFoundError:
        return _streaming_not_found(cmd, cmd_str, start_time)
    except (subprocess.SubprocessError, OSError) as e:
        return _streaming_error(e, stdout_lines, cmd_str, start_time)


def _create_streaming_process(
    cmd: list[str],
    run_cwd: Path | None,
    run_env: dict[str, str],
) -> subprocess.Popen[str]:
    """Create a subprocess for streaming output."""
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=run_cwd,
        env=run_env,
        bufsize=1,
    )


def _streaming_not_found(
    cmd: list[str],
    cmd_str: str,
    start_time: float,
) -> CommandResult:
    """Build result for command-not-found during streaming."""
    logger.error("[SHELL] Command not found: %s", cmd[0])
    return CommandResult(
        status=CommandStatus.NOT_FOUND,
        returncode=-1,
        stdout="",
        stderr=f"Command not found: {cmd[0]}",
        command=cmd_str,
        duration=time.time() - start_time,
    )


def _streaming_error(
    exc: Exception,
    stdout_lines: list[str],
    cmd_str: str,
    start_time: float,
) -> CommandResult:
    """Build result for an exception during streaming."""
    logger.error("[SHELL] Streaming exception: %s", exc)
    return CommandResult(
        status=CommandStatus.FAILED,
        returncode=-1,
        stdout="\n".join(stdout_lines),
        stderr=str(exc),
        command=cmd_str,
        duration=time.time() - start_time,
    )


def _collect_output(
    process: subprocess.Popen[str],
    callback: Callable[[str], None],
    stdout_lines: list[str],
    cmd_str: str,
    run_timeout: int,
    start_time: float,
    preview: str,
) -> CommandResult:
    """Collect streaming output and build result."""
    reader = threading.Thread(
        target=_read_lines,
        args=(process, stdout_lines, callback),
    )
    reader.start()
    reader.join(timeout=run_timeout)

    if reader.is_alive():
        return _handle_timeout(
            process,
            reader,
            stdout_lines,
            cmd_str,
            run_timeout,
            start_time,
            preview,
        )

    returncode = process.wait()
    duration = time.time() - start_time
    status = CommandStatus.SUCCESS if returncode == 0 else CommandStatus.FAILED

    if returncode == 0:
        logger.debug(
            "[SHELL] Streaming success (exit=0, %.2fs): %s",
            duration,
            preview,
        )
    else:
        logger.error(
            "[SHELL] Streaming failed (exit=%d): %s",
            returncode,
            preview,
        )

    return CommandResult(
        status=status,
        returncode=returncode,
        stdout="\n".join(stdout_lines),
        stderr="",
        command=cmd_str,
        duration=duration,
    )


def _read_lines(
    process: subprocess.Popen[str],
    stdout_lines: list[str],
    callback: Callable[[str], None],
) -> None:
    """Read lines from process stdout in a thread."""
    if process.stdout is None:
        return
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                stdout_lines.append(line.rstrip())
                callback(line.rstrip())
    except OSError:
        pass  # Pipe closed during read (process killed)
    finally:
        if process.stdout:
            with contextlib.suppress(OSError):
                process.stdout.close()


def _handle_timeout(
    process: subprocess.Popen[str],
    reader: threading.Thread,
    stdout_lines: list[str],
    cmd_str: str,
    run_timeout: int,
    start_time: float,
    preview: str,
) -> CommandResult:
    """Terminate a streaming process that exceeded timeout."""
    process.terminate()
    reader.join(timeout=_READER_JOIN_TIMEOUT)
    if reader.is_alive():
        process.kill()
        reader.join()
    logger.warning(
        "[SHELL] Streaming timeout after %ds: %s",
        run_timeout,
        preview,
    )
    return CommandResult(
        status=CommandStatus.TIMEOUT,
        returncode=-1,
        stdout="\n".join(stdout_lines),
        stderr=f"Command timed out after {run_timeout} seconds",
        command=cmd_str,
        duration=time.time() - start_time,
    )
