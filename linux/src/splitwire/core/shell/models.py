"""
Data models for the shell execution module.

Contains enums and dataclasses for command execution results.
"""

from dataclasses import dataclass
from enum import Enum


class CommandStatus(Enum):
    """Status of a completed command execution.

    Attributes:
        SUCCESS: Command exited with code 0.
        FAILED: Command exited with non-zero code.
        TIMEOUT: Command exceeded the time limit.
        CANCELLED: Command was cancelled before completion.
        NOT_FOUND: Command binary was not found in PATH.
    """

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


@dataclass
class CommandResult:
    """Result of a shell command execution.

    Attributes:
        status: Execution outcome category.
        returncode: Process exit code (-1 for internal errors).
        stdout: Captured standard output (stripped).
        stderr: Captured standard error (stripped).
        command: Original command string for logging.
        duration: Wall-clock execution time in seconds.
    """

    status: CommandStatus
    returncode: int
    stdout: str
    stderr: str
    command: str
    duration: float = 0.0

    @property
    def success(self) -> bool:
        """Check if command succeeded (status SUCCESS and code 0).

        Returns:
            True if the command ran successfully.
        """
        return self.status == CommandStatus.SUCCESS and self.returncode == 0

    @property
    def output(self) -> str:
        """Get combined stdout and stderr output.

        Returns:
            Newline-joined stdout and stderr.
        """
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)
