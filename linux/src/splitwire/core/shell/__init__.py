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
    """Get the global ShellExecutor singleton.

    Returns:
        The shared ShellExecutor instance.
    """
    global _shell
    if _shell is None:
        _shell = ShellExecutor()
    return _shell


def run(command: str | list[str], **kwargs: object) -> CommandResult:
    """Run a command via the global executor.

    Args:
        command: Command string or argument list.
        **kwargs: Passed to ShellExecutor.run().

    Returns:
        CommandResult with execution details.
    """
    return get_shell().run(command, **kwargs)


async def run_async(command: str | list[str], **kwargs: object) -> CommandResult:
    """Run a command asynchronously via the global executor.

    Args:
        command: Command string or argument list.
        **kwargs: Passed to ShellExecutor.run_async().

    Returns:
        CommandResult with execution details.
    """
    return await get_shell().run_async(command, **kwargs)


def command_exists(command: str) -> bool:
    """Check if a command exists in PATH.

    Args:
        command: Command name to look up.

    Returns:
        True if the command is found.
    """
    return get_shell().command_exists(command)
