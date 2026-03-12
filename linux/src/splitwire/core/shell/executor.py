"""
Shell command executor for SplitWire-Turkey Linux.

Provides safe shell command execution with timeout handling,
output capture, async execution, and privilege elevation.
"""

import asyncio
import logging
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from .helpers import (
    cmd_preview,
    handle_exec_error,
    handle_not_found_error,
    handle_timeout_error,
    log_result,
    make_failed_result,
    parse_command,
)
from .models import CommandResult, CommandStatus
from .streaming import run_with_output as _stream_run

logger = logging.getLogger(__name__)


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
        """
        self._timeout = timeout
        self._env = self._build_env(env)
        self._cwd = cwd

    @staticmethod
    def _build_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
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
            command: Command string or argument list.
            timeout: Override default timeout (seconds).
            capture_output: Capture stdout/stderr.
            check: Raise on non-zero exit code.
            cwd: Override working directory.
            env: Extra environment variables.
            shell: Use system shell.
            input_data: Stdin data.

        Returns:
            CommandResult with execution details.
        """
        ctx = self._prepare_run_context(command, timeout, cwd, env, shell)
        return self._execute_and_handle(
            ctx,
            capture_output,
            check,
            input_data,
            shell,
        )

    def _prepare_run_context(
        self,
        command: str | list[str],
        timeout: int | None,
        cwd: Path | None,
        env: dict[str, str] | None,
        shell: bool,
    ) -> dict:
        """Prepare execution context for a synchronous run."""
        cmd_str, cmd = parse_command(command, shell)
        return {
            "start_time": time.time(),
            "cmd_str": cmd_str,
            "cmd": cmd,
            "run_env": self._resolve_env(env),
            "run_cwd": cwd or self._cwd,
            "run_timeout": self._resolve_timeout(timeout),
            "preview": cmd_preview(cmd_str),
        }

    def _execute_and_handle(
        self,
        ctx: dict,
        capture_output: bool,
        check: bool,
        input_data: str | None,
        shell: bool,
    ) -> CommandResult:
        """Execute subprocess and handle errors."""
        logger.debug("[SHELL] Executing: %s", ctx["preview"])
        try:
            result = self._exec_subprocess(
                ctx["cmd"],
                ctx["run_env"],
                ctx["run_cwd"],
                ctx["run_timeout"],
                shell,
                input_data,
                capture_output,
            )
        except subprocess.TimeoutExpired:
            return handle_timeout_error(ctx)
        except FileNotFoundError:
            return handle_not_found_error(ctx)
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            return handle_exec_error(ctx, e)

        return self._to_result(
            result,
            ctx["cmd_str"],
            capture_output,
            check,
            ctx["start_time"],
            ctx["preview"],
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

        log_result(result.returncode, stderr, duration, preview)

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
            command: Command string or argument list.
            timeout: Timeout in seconds.
            capture_output: Capture stdout/stderr.
            cwd: Working directory.
            env: Extra environment variables.

        Returns:
            CommandResult with execution details.
        """
        start_time = time.time()
        cmd_str, cmd = parse_command(command)
        run_env = self._resolve_env(env)
        run_cwd = str(cwd or self._cwd) if (cwd or self._cwd) else None
        run_timeout = self._resolve_timeout(timeout)
        preview = cmd_preview(cmd_str)
        logger.debug("[SHELL] Async executing: %s", preview)

        return await self._try_exec_async(
            cmd,
            run_cwd,
            run_env,
            capture_output,
            cmd_str,
            run_timeout,
            start_time,
            preview,
        )

    async def _try_exec_async(
        self,
        cmd,
        run_cwd,
        run_env,
        capture_output,
        cmd_str,
        run_timeout,
        start_time,
        preview,
    ) -> CommandResult:
        """Attempt async subprocess, handling errors."""
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
            return make_failed_result(
                CommandStatus.NOT_FOUND,
                cmd_str,
                f"Command not found: {cmd[0]}",
                start_time,
            )
        except (OSError, ValueError) as e:
            logger.error("[SHELL] Async exception: %s", e)
            return make_failed_result(
                CommandStatus.FAILED,
                cmd_str,
                str(e),
                start_time,
            )

    @staticmethod
    async def _create_async_process(cmd, run_cwd, run_env, capture_output):
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
            logger.warning("[SHELL] Async timeout after %ds: %s", run_timeout, preview)
            return make_failed_result(
                CommandStatus.TIMEOUT,
                cmd_str,
                f"Command timed out after {run_timeout} seconds",
                start_time,
            )

        duration = time.time() - start_time
        status = CommandStatus.SUCCESS if process.returncode == 0 else CommandStatus.FAILED
        log_result(process.returncode or 0, stderr, duration, preview)

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

        Args:
            command: Command string or argument list.
            callback: Called with each output line.
            timeout: Command timeout in seconds.
            cwd: Working directory.
            env: Extra environment variables.

        Returns:
            CommandResult with execution details.
        """
        cmd_str, cmd = parse_command(command)
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
        """Check if a command exists in PATH."""
        return self.run(["which", command], timeout=self.TIMEOUT_COMMAND_LOOKUP).success

    def get_command_path(self, command: str) -> str | None:
        """Get the full filesystem path of a command."""
        result = self.run(["which", command], timeout=self.TIMEOUT_COMMAND_LOOKUP)
        return result.stdout if result.success else None


async def _communicate(process, run_timeout, capture_output) -> tuple[str, str]:
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
