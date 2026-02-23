"""
Data models for the shell execution module.

Contains enums and dataclasses for command execution results.
"""

from dataclasses import dataclass
from enum import Enum


class CommandStatus(Enum):
    """Status of command execution."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


@dataclass
class CommandResult:
    """Result of a shell command execution."""

    status: CommandStatus
    returncode: int
    stdout: str
    stderr: str
    command: str
    duration: float = 0.0

    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return (
            self.status == CommandStatus.SUCCESS
            and self.returncode == 0
        )

    @property
    def output(self) -> str:
        """Get combined stdout and stderr."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)
