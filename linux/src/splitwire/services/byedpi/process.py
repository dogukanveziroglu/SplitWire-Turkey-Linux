"""
ByeDPI process management helpers.

Process lifecycle management for the ciadpi SOCKS5 proxy,
including PID file handling and signal-based termination.
"""

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .constants import BYEDPI_PID_FILE, PID_DIR

# Process management constants
KILL_POLL_ATTEMPTS = 10
KILL_POLL_INTERVAL = 0.1  # seconds
TERMINATE_TIMEOUT = 5  # seconds


def create_pid_dir(run_privileged_fn) -> None:
    """
    Ensure the PID directory exists.

    Args:
        run_privileged_fn: Callable to run privileged commands
    """
    run_privileged_fn(["mkdir", "-p", str(PID_DIR)])


def save_pid(pid: int, run_privileged_fn, logger) -> None:
    """
    Save process PID to file.

    Args:
        pid: Process ID to save
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance
    """
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(str(pid))
            tmp_path = f.name
        run_privileged_fn(["cp", tmp_path, str(BYEDPI_PID_FILE)])
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Failed to save PID: {e}")


def get_pid(logger) -> int | None:
    """
    Read PID from file.

    Args:
        logger: Logger instance

    Returns:
        Process ID or None
    """
    if BYEDPI_PID_FILE.exists():
        try:
            pid = int(BYEDPI_PID_FILE.read_text().strip())
            logger.debug(f"[BYEDPI] Read PID from file: {pid}")
            return pid
        except Exception as e:
            logger.warning(f"[BYEDPI] Failed to read PID file: {e}")
    return None


def remove_pid(run_privileged_fn, logger) -> None:
    """
    Remove PID file.

    Args:
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance
    """
    try:
        logger.debug(f"[BYEDPI] Removing PID file: {BYEDPI_PID_FILE}")
        run_privileged_fn(["rm", "-f", str(BYEDPI_PID_FILE)])
    except Exception as e:
        logger.warning(f"[BYEDPI] Failed to remove PID file: {e}")


def kill_by_pid(run_privileged_fn, logger) -> None:
    """
    Kill the process identified by PID file.

    Args:
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance
    """
    pid = get_pid(logger)
    if not pid:
        return

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(KILL_POLL_ATTEMPTS):
            try:
                os.kill(pid, 0)
                time.sleep(KILL_POLL_INTERVAL)
            except ProcessLookupError:  # noqa: PERF203 -- poll loop needs per-iteration check
                break
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    remove_pid(run_privileged_fn, logger)


def terminate_process(
    process: subprocess.Popen | None,
) -> None:
    """
    Terminate an in-memory tracked process.

    Args:
        process: Popen instance or None
    """
    if process:
        process.terminate()
        try:
            process.wait(timeout=TERMINATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()


def is_process_running(run_privileged_fn, logger) -> bool:
    """
    Check if ciadpi process is running.

    Args:
        run_privileged_fn: Callable to run privileged commands
        logger: Logger instance

    Returns:
        True if process is running
    """
    pid = get_pid(logger)
    if pid:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            remove_pid(run_privileged_fn, logger)
    return False
