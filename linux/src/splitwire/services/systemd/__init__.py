"""
SplitWire systemd service manager package.

Re-exports all public names so that existing imports like
``from splitwire.services.systemd import SystemdManager`` continue to work.
"""

from splitwire.core import get_shell
from splitwire.core.logger import get_logger

from .manager import SystemdManager
from .models import (
    JournalEntry,
    SystemdActiveState,
    SystemdEnabledState,
    SystemdUnitStatus,
    SystemdUnitType,
)

# Singleton instance
_systemd_manager: SystemdManager | None = None


def get_systemd_manager() -> SystemdManager:
    """Get the singleton SystemdManager instance."""
    global _systemd_manager
    if _systemd_manager is None:
        _systemd_manager = SystemdManager()
    return _systemd_manager


__all__ = [
    "JournalEntry",
    "SystemdActiveState",
    "SystemdEnabledState",
    "SystemdManager",
    "SystemdUnitStatus",
    "SystemdUnitType",
    "get_systemd_manager",
]
