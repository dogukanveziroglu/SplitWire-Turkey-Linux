"""Data models and enums for the Discord service."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DiscordVersion(Enum):
    """Discord version/channel."""

    STABLE = "stable"
    PTB = "ptb"
    CANARY = "canary"


class InstallMethod(Enum):
    """Discord installation method."""

    DEB = "deb"
    SNAP = "snap"
    FLATPAK = "flatpak"
    TARBALL = "tarball"
    APPIMAGE = "appimage"
    NOT_INSTALLED = "not_installed"
    UNKNOWN = "unknown"


@dataclass
class DiscordInstallation:
    """Information about a Discord installation."""

    version: DiscordVersion
    method: InstallMethod
    path: str | None = None
    binary_path: str | None = None
    config_dir: Path | None = None
    cache_dir: Path | None = None
    is_running: bool = False
    has_cache: bool = False
    cache_size_mb: float = 0.0


@dataclass
class WebCordInstallation:
    """Information about WebCord installation."""

    installed: bool = False
    method: InstallMethod = InstallMethod.NOT_INSTALLED
    path: str | None = None
    is_running: bool = False


@dataclass
class DiscordConfig:
    """Discord service configuration."""

    last_repair_date: str | None = None
    auto_clear_cache: bool = False
    preferred_version: str = "stable"


@dataclass
class RepairResult:
    """Result of a repair operation."""

    success: bool
    message: str
    cache_cleared_mb: float = 0.0
    errors: list[str] = field(default_factory=list)
