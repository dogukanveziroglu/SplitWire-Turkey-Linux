"""Discord repair and management service package for SplitWire Linux."""

from .constants import (
    DEB_DISCORD_NAMES,
    DISCORD_CACHE_DIRS,
    DISCORD_CONFIG_DIRS,
    DISCORD_DOWNLOAD_URLS,
    FLATPAK_DISCORD_IDS,
    SNAP_DISCORD_NAMES,
)
from .models import (
    DiscordConfig,
    DiscordInstallation,
    DiscordVersion,
    InstallMethod,
    RepairResult,
    WebCordInstallation,
)
from .service import DiscordService, get_discord_service

__all__ = [
    "DEB_DISCORD_NAMES",
    "DISCORD_CACHE_DIRS",
    "DISCORD_CONFIG_DIRS",
    "DISCORD_DOWNLOAD_URLS",
    "DiscordConfig",
    "DiscordInstallation",
    "DiscordService",
    "DiscordVersion",
    "FLATPAK_DISCORD_IDS",
    "InstallMethod",
    "RepairResult",
    "SNAP_DISCORD_NAMES",
    "WebCordInstallation",
    "get_discord_service",
]
