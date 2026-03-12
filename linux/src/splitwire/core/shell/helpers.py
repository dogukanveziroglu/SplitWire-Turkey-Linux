"""
Shell command execution helpers.

Shared utilities for command parsing, result building, and error handling
used by executor.py and streaming.py.
"""

import logging
import shlex
import time

from .models import CommandResult, CommandStatus

logger = logging.getLogger(__name__)

_PREVIEW_LEN = 80
_STDERR_LEN = 200


def cmd_preview(cmd_str: str) -> str:
    """Truncate a command string for log display."""
    if len(cmd_str) > _PREVIEW_LEN:
        return cmd_str[:_PREVIEW_LEN] + "..."
    return cmd_str


def parse_command(command: str | list[str], shell: bool = False) -> tuple[str, str | list[str]]:
    """Parse a command into display string and executable form.

    Returns:
        Tuple of (display_string, executable_command).
    """
    if isinstance(command, str):
        cmd_str = command
        cmd = command if shell else shlex.split(command)
    else:
        cmd_str = " ".join(command)
        cmd = command
    return cmd_str, cmd


def make_failed_result(
    status: CommandStatus,
    cmd_str: str,
    stderr: str,
    start_time: float,
) -> CommandResult:
    """Build a CommandResult for a failed/exceptional execution."""
    return CommandResult(
        status=status,
        returncode=-1,
        stdout="",
        stderr=stderr,
        command=cmd_str,
        duration=time.time() - start_time,
    )


def log_result(returncode: int, stderr: str, duration: float, preview: str) -> None:
    """Log command result at appropriate level."""
    if returncode == 0:
        logger.debug("[SHELL] Success (exit=0, %.2fs): %s", duration, preview)
    else:
        logger.error("[SHELL] Failed (exit=%d): %s", returncode, preview)
        if stderr:
            sp = stderr[:_STDERR_LEN] + "..." if len(stderr) > _STDERR_LEN else stderr
            logger.error("[SHELL] stderr: %s", sp)


def handle_timeout_error(ctx: dict) -> CommandResult:
    """Handle subprocess.TimeoutExpired during run()."""
    logger.warning("[SHELL] Timeout after %ds: %s", ctx["run_timeout"], ctx["preview"])
    return make_failed_result(
        CommandStatus.TIMEOUT,
        ctx["cmd_str"],
        f"Command timed out after {ctx['run_timeout']} seconds",
        ctx["start_time"],
    )


def handle_not_found_error(ctx: dict) -> CommandResult:
    """Handle FileNotFoundError during run()."""
    cmd = ctx["cmd"]
    nf = cmd[0] if isinstance(cmd, list) else cmd.split()[0]
    logger.error("[SHELL] Command not found: %s", nf)
    return make_failed_result(
        CommandStatus.NOT_FOUND,
        ctx["cmd_str"],
        f"Command not found: {nf}",
        ctx["start_time"],
    )


def handle_exec_error(ctx: dict, exc: Exception) -> CommandResult:
    """Handle general execution exceptions during run()."""
    logger.error("[SHELL] Exception during execution: %s", exc)
    return make_failed_result(
        CommandStatus.FAILED,
        ctx["cmd_str"],
        str(exc),
        ctx["start_time"],
    )
