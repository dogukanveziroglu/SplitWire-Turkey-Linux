"""
Shell command execution module for SplitWire-Turkey Linux.

Provides safe shell command execution with:
- Timeout handling
- Output capture
- Async execution
- Privilege elevation integration
"""

from .executor import ShellExecutor
from .models import CommandResult, CommandStatus

__all__ = [
    "CommandResult",
    "CommandStatus",
    "ShellExecutor",
    "command_exists",
    "get_shell",
    "run",
    "run_async",
]

# Global instance
_shell: ShellExecutor | None = None


def get_shell() -> ShellExecutor:
    """Get the global ShellExecutor instance."""
    global _shell
    if _shell is None:
        _shell = ShellExecutor()
    return _shell


def run(command: str | list[str], **kwargs) -> CommandResult:
    """Run a command (convenience function)."""
    return get_shell().run(command, **kwargs)


async def run_async(
    command: str | list[str], **kwargs
) -> CommandResult:
    """Run a command asynchronously (convenience function)."""
    return await get_shell().run_async(command, **kwargs)


def command_exists(command: str) -> bool:
    """Check if a command exists (convenience function)."""
    return get_shell().command_exists(command)
