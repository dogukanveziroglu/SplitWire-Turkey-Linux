"""
Polkit elevated execution helpers.

Extracted from polkit.py to keep file sizes under 500 lines.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .polkit import PolkitHelper

from .polkit import ElevationMethod, ElevationResult

logger = logging.getLogger(__name__)


def write_file_as_root(helper: PolkitHelper, content: str, path: str) -> ElevationResult:
    """Write content to a root-owned file using pkexec tee.

    Args:
        helper: PolkitHelper instance for env access.
        content: Text content to write.
        path: Destination file path.

    Returns:
        ElevationResult from the tee command.
    """
    proc = None
    try:
        proc = subprocess.Popen(
            ["pkexec", "tee", path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=helper._get_pkexec_env(),
        )
        stdout, stderr = proc.communicate(
            input=content,
            timeout=helper.TIMEOUT_FILE_WRITE,
        )
        return ElevationResult(
            success=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            cancelled=proc.returncode == 126,
            method=ElevationMethod.PKEXEC,
        )
    except subprocess.TimeoutExpired:
        return _handle_write_timeout(proc)
    except Exception as e:
        return _handle_write_error(proc, e)


def _handle_write_timeout(proc: subprocess.Popen | None) -> ElevationResult:
    """Handle timeout during write_file_as_root."""
    if proc:
        proc.kill()
        proc.communicate()
    return ElevationResult(
        success=False,
        returncode=-1,
        stdout="",
        stderr="Command timed out",
        method=ElevationMethod.PKEXEC,
    )


def _handle_write_error(proc: subprocess.Popen | None, err: Exception) -> ElevationResult:
    """Handle exception during write_file_as_root."""
    if proc and proc.poll() is None:
        proc.kill()
    return ElevationResult(
        success=False,
        returncode=-1,
        stdout="",
        stderr=str(err),
        method=ElevationMethod.PKEXEC,
    )


def run_pkexec(
    helper: PolkitHelper,
    command: list[str],
    _action_id: str | None,
    timeout: int,
    capture_output: bool,
) -> ElevationResult:
    """Run command with pkexec and return an ElevationResult."""
    pkexec_cmd = ["pkexec", *command]
    env = helper._get_pkexec_env()
    try:
        result = subprocess.run(
            pkexec_cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return _pkexec_result(result, capture_output)
    except subprocess.TimeoutExpired:
        return _make_pkexec_error("Command timed out")
    except Exception as e:
        return _make_pkexec_error(str(e))


def _pkexec_result(
    result: subprocess.CompletedProcess,
    capture_output: bool,
) -> ElevationResult:
    """Convert subprocess result to ElevationResult for pkexec."""
    return ElevationResult(
        success=result.returncode == 0,
        returncode=result.returncode,
        stdout=(result.stdout or "") if capture_output else "",
        stderr=(result.stderr or "") if capture_output else "",
        cancelled=result.returncode == 126,
        method=ElevationMethod.PKEXEC,
    )


def _make_pkexec_error(stderr: str) -> ElevationResult:
    """Build a failed ElevationResult for pkexec."""
    return ElevationResult(
        success=False,
        returncode=-1,
        stdout="",
        stderr=stderr,
        method=ElevationMethod.PKEXEC,
    )


def log_elevation_result(
    result: ElevationResult,
    cmd_preview: str,
) -> None:
    """Log the result of an elevation attempt.

    Args:
        result: The elevation result to log.
        cmd_preview: Truncated command string for display.
    """
    if result.success:
        logger.info("[POLKIT] Elevation successful: %s", cmd_preview)
    elif result.cancelled:
        logger.warning("[POLKIT] User cancelled elevation")
    else:
        logger.error(
            "[POLKIT] Elevation failed (exit=%d): %s",
            result.returncode,
            cmd_preview,
        )
        if result.stderr:
            stderr_preview = (
                result.stderr[:200] + "..." if len(result.stderr) > 200 else result.stderr
            )
            logger.error("[POLKIT] stderr: %s", stderr_preview)
