"""
Data models and enums for the systemd service manager.
"""

from dataclasses import dataclass
from enum import Enum


class SystemdUnitType(Enum):
    """Type of systemd unit."""

    SERVICE = "service"
    TIMER = "timer"
    SOCKET = "socket"
    PATH = "path"


class SystemdActiveState(Enum):
    """Active state of a systemd unit."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    RELOADING = "reloading"
    UNKNOWN = "unknown"


class SystemdEnabledState(Enum):
    """Enabled state of a systemd unit."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    STATIC = "static"
    MASKED = "masked"
    INDIRECT = "indirect"
    UNKNOWN = "unknown"


@dataclass
class SystemdUnitStatus:
    """Status information for a systemd unit."""

    name: str
    unit_type: SystemdUnitType
    active_state: SystemdActiveState
    enabled_state: SystemdEnabledState
    description: str = ""
    load_state: str = "not-found"
    sub_state: str = ""
    main_pid: int | None = None
    memory_current: int | None = None  # bytes
    tasks_current: int | None = None
    cpu_usage_nsec: int | None = None
    invocation_id: str | None = None
    active_enter_timestamp: str | None = None
    inactive_enter_timestamp: str | None = None

    @property
    def is_running(self) -> bool:
        """Check if unit is running."""
        return self.active_state == SystemdActiveState.ACTIVE

    @property
    def is_enabled(self) -> bool:
        """Check if unit is enabled."""
        return self.enabled_state == SystemdEnabledState.ENABLED

    @property
    def is_failed(self) -> bool:
        """Check if unit has failed."""
        return self.active_state == SystemdActiveState.FAILED


@dataclass
class JournalEntry:
    """A journal log entry."""

    timestamp: str
    unit: str
    priority: int
    message: str
    pid: int | None = None
    hostname: str | None = None
