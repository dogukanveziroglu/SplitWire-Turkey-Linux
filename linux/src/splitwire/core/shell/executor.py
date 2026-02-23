"""
Shell command executor for SplitWire-Turkey Linux.

Provides safe shell command execution with timeout handling,
output capture, async execution, and privilege elevation.
"""

import asyncio
import logging
import os
import shlex
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from .models import CommandResult, CommandStatus
from .streaming import run_with_output as _stream_run

logger = logging.getLogger(__name__)

_PREVIEW_LEN = 80
_STDERR_LEN = 200


def _cmd_preview(cmd_str: str) -> str:
    """Truncate a command string for log display."""
    if len(cmd_str) > _PREVIEW_LEN:
        return cmd_str[:_PREVIEW_LEN] + "..."
    return cmd_str


def _parse_command(command: str | list[str], shell: bool = False) -> tuple[str, str | list[str]]:
    """
    Parse a command into display string and executable form.

    Returns:
        Tuple of (display_string, executable_command)
    """
    if isinstance(command, str):
        cmd_str = command
        cmd = command if shell else shlex.split(command)
    else:
        cmd_str = " ".join(command)
        cmd = command
    return cmd_str, cmd


def _make_failed_result(
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


def _log_result(returncode: int, stderr: str, duration: float, preview: str) -> None:
    """Log command result at appropriate level."""
    if returncode == 0:
        logger.debug(
            "[SHELL] Success (exit=0, %.2fs): %s",
            duration,
            preview,
        )
    else:
        logger.error(
            "[SHELL] Failed (exit=%d): %s",
            returncode,
            preview,
        )
        if stderr:
            sp = stderr[:_STDERR_LEN] + "..." if len(stderr) > _STDERR_LEN else stderr
            logger.error("[SHELL] stderr: %s", sp)


class ShellExecutor:
    """Executes shell commands with timeout and output capture.

    Supports synchronous, asynchronous, and streaming execution
    modes with configurable environment and working directory.

    Attributes:
        DEFAULT_TIMEOUT: Default command timeout in seconds.
    """

    DEFAULT_TIMEOUT = 60
    TIMEOUT_COMMAND_LOOKUP = 5  # which <command>

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        """Initialize shell executor.

        Args:
            timeout: Default command timeout in seconds.
            env: Additional environment variables to merge.
            cwd: Default working directory for commands.

        Example:
            >>> executor = ShellExecutor(timeout=30)
        """
        self._timeout = timeout
        self._env = self._build_env(env)
        self._cwd = cwd

    @staticmethod
    def _build_env(
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build environment dictionary."""
        env = os.environ.copy()
        paths = [
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/local/sbin",
            "/usr/sbin",
            "/sbin",
        ]
        current_path = env.get("PATH", "")
        for p in paths:
            if p not in current_path:
                current_path = f"{p}:{current_path}"
        env["PATH"] = current_path
        if extra_env:
            env.update(extra_env)
        return env

    def _resolve_env(self, env: dict[str, str] | None) -> dict[str, str]:
        """Merge base env with per-call overrides."""
        run_env = self._env.copy()
        if env:
            run_env.update(env)
        return run_env

    def _resolve_timeout(self, timeout: int | None) -> int:
        """Return explicit timeout or the instance default."""
        return timeout if timeout is not None else self._timeout

    # ----------------------------------------------------------
    # Synchronous execution
    # ----------------------------------------------------------

    def run(
        self,
        command: str | list[str],
        timeout: int | None = None,
        capture_output: bool = True,
        check: bool = False,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        shell: bool = False,
        input_data: str | None = None,
    ) -> CommandResult:
        """Run a command synchronously.

        Args:
            command: Command string or list of arguments.
            timeout: Command timeout (overrides default).
            capture_output: Whether to capture stdout/stderr.
            check: Raise on non-zero return code.
            cwd: Working directory (overrides default).
            env: Additional environment variables.
            shell: Run through system shell.
            input_data: Data to send to stdin.

        Returns:
            CommandResult with execution details.

        Raises:
            subprocess.CalledProcessError: If check=True and
                command returns non-zero exit code.

        Example:
            >>> shell = ShellExecutor()
            >>> result = shell.run("echo hello")
            >>> result.success
            True
        """
        start_time = time.time()
        cmd_str, cmd = _parse_command(command, shell)
        run_env = self._resolve_env(env)
        run_cwd = cwd or self._cwd
        run_timeout = self._resolve_timeout(timeout)
        preview = _cmd_preview(cmd_str)

        logger.debug("[SHELL] Executing: %s", preview)

        try:
            result = self._exec_subprocess(
                cmd,
                run_env,
                run_cwd,
                run_timeout,
                shell,
                input_data,
                capture_output,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "[SHELL] Timeout after %ds: %s",
                run_timeout,
                preview,
            )
            return _make_failed_result(
                CommandStatus.TIMEOUT,
                cmd_str,
                f"Command timed out after {run_timeout} seconds",
                start_time,
            )
        except FileNotFoundError:
            nf = cmd[0] if isinstance(cmd, list) else cmd.split()[0]
            logger.error("[SHELL] Command not found: %s", nf)
            return _make_failed_result(
                CommandStatus.NOT_FOUND,
                cmd_str,
                f"Command not found: {nf}",
                start_time,
            )
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logger.error("[SHELL] Exception during execution: %s", e)
            return _make_failed_result(
                CommandStatus.FAILED,
                cmd_str,
                str(e),
                start_time,
            )

        return self._to_result(
            result,
            cmd_str,
            capture_output,
            check,
            start_time,
            preview,
        )

    @staticmethod
    def _exec_subprocess(
        cmd,
        run_env,
        run_cwd,
        run_timeout,
        shell,
        input_data,
        capture_output,
    ) -> subprocess.CompletedProcess:
        """Execute subprocess.run with the given parameters."""
        if capture_output:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=run_timeout,
                cwd=run_cwd,
                env=run_env,
                shell=shell,
                input=input_data,
                check=False,
            )
        return subprocess.run(
            cmd,
            timeout=run_timeout,
            cwd=run_cwd,
            env=run_env,
            shell=shell,
            input=input_data,
            text=bool(input_data),
            check=False,
        )

    @staticmethod
    def _to_result(
        result: subprocess.CompletedProcess,
        cmd_str: str,
        capture_output: bool,
        check: bool,
        start_time: float,
        preview: str,
    ) -> CommandResult:
        """Convert subprocess result to CommandResult."""
        stdout = (result.stdout or "") if capture_output else ""
        stderr = (result.stderr or "") if capture_output else ""
        duration = time.time() - start_time
        status = CommandStatus.SUCCESS if result.returncode == 0 else CommandStatus.FAILED

        _log_result(result.returncode, stderr, duration, preview)

        cmd_result = CommandResult(
            status=status,
            returncode=result.returncode,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            command=cmd_str,
            duration=duration,
        )

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd_str,
                stdout,
                stderr,
            )

        return cmd_result

    # ----------------------------------------------------------
    # Async execution
    # ----------------------------------------------------------

    async def run_async(
        self,
        command: str | list[str],
        timeout: int | None = None,
        capture_output: bool = True,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a command asynchronously via asyncio.

        Args:
            command: Command string or list of arguments.
            timeout: Command timeout in seconds.
            capture_output: Whether to capture stdout/stderr.
            cwd: Working directory for the command.
            env: Additional environment variables.

        Returns:
            CommandResult with execution details.

        Example:
            >>> import asyncio
            >>> shell = ShellExecutor()
            >>> result = asyncio.run(shell.run_async("echo hi"))
            >>> result.success
            True
        """
        start_time = time.time()
        cmd_str, cmd = _parse_command(command)
        run_env = self._resolve_env(env)
        run_cwd = str(cwd or self._cwd) if (cwd or self._cwd) else None
        run_timeout = self._resolve_timeout(timeout)
        preview = _cmd_preview(cmd_str)

        logger.debug("[SHELL] Async executing: %s", preview)

        try:
            process = await self._create_async_process(
                cmd,
                run_cwd,
                run_env,
                capture_output,
            )
            return await self._await_process(
                process,
                cmd_str,
                run_timeout,
                capture_output,
                start_time,
                preview,
            )
        except FileNotFoundError:
            logger.error("[SHELL] Command not found: %s", cmd[0])
            return _make_failed_result(
                CommandStatus.NOT_FOUND,
                cmd_str,
                f"Command not found: {cmd[0]}",
                start_time,
            )
        except (OSError, ValueError) as e:
            logger.error("[SHELL] Async exception: %s", e)
            return _make_failed_result(
                CommandStatus.FAILED,
                cmd_str,
                str(e),
                start_time,
            )

    @staticmethod
    async def _create_async_process(
        cmd,
        run_cwd,
        run_env,
        capture_output,
    ):
        """Create an asyncio subprocess."""
        if capture_output:
            return await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=run_cwd,
                env=run_env,
            )
        return await asyncio.create_subprocess_exec(
            *cmd,
            cwd=run_cwd,
            env=run_env,
        )

    @staticmethod
    async def _await_process(
        process,
        cmd_str,
        run_timeout,
        capture_output,
        start_time,
        preview,
    ) -> CommandResult:
        """Wait for async process and build result."""
        try:
            stdout, stderr = await _communicate(
                process,
                run_timeout,
                capture_output,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.warning(
                "[SHELL] Async timeout after %ds: %s",
                run_timeout,
                preview,
            )
            return _make_failed_result(
                CommandStatus.TIMEOUT,
                cmd_str,
                f"Command timed out after {run_timeout} seconds",
                start_time,
            )

        duration = time.time() - start_time
        status = CommandStatus.SUCCESS if process.returncode == 0 else CommandStatus.FAILED
        _log_result(
            process.returncode or 0,
            stderr,
            duration,
            preview,
        )

        return CommandResult(
            status=status,
            returncode=process.returncode or 0,
            stdout=stdout.strip() if stdout else "",
            stderr=stderr.strip() if stderr else "",
            command=cmd_str,
            duration=duration,
        )

    # ----------------------------------------------------------
    # Streaming execution (delegates to streaming module)
    # ----------------------------------------------------------

    def run_with_output(
        self,
        command: str | list[str],
        callback: Callable[[str], None],
        timeout: int | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a command with real-time output streaming.

        Each line of stdout is passed to the callback as it arrives.

        Args:
            command: Command string or list of arguments.
            callback: Called with each output line (stripped).
            timeout: Command timeout in seconds.
            cwd: Working directory for the command.
            env: Additional environment variables.

        Returns:
            CommandResult with execution details.

        Example:
            >>> shell = ShellExecutor()
            >>> lines = []
            >>> shell.run_with_output("echo hi", lines.append)
        """
        cmd_str, cmd = _parse_command(command)
        return _stream_run(
            cmd=cmd,
            cmd_str=cmd_str,
            callback=callback,
            run_timeout=self._resolve_timeout(timeout),
            run_cwd=cwd or self._cwd,
            run_env=self._resolve_env(env),
        )

    # ----------------------------------------------------------
    # Utility methods
    # ----------------------------------------------------------

    def command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH.

        Args:
            command: Command name to look up.

        Returns:
            True if the command is found in PATH.
        """
        return self.run(["which", command], timeout=self.TIMEOUT_COMMAND_LOOKUP).success

    def get_command_path(self, command: str) -> str | None:
        """Get the full filesystem path of a command.

        Args:
            command: Command name to look up.

        Returns:
            Absolute path string, or None if not found.
        """
        result = self.run(["which", command], timeout=self.TIMEOUT_COMMAND_LOOKUP)
        return result.stdout if result.success else None


async def _communicate(
    process,
    run_timeout,
    capture_output,
) -> tuple[str, str]:
    """Communicate with async process, handling timeout."""
    if capture_output:
        stdout_b, stderr_b = await asyncio.wait_for(
            process.communicate(),
            timeout=run_timeout,
        )
        return (
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
        )
    await asyncio.wait_for(process.wait(), timeout=run_timeout)
    return "", ""
