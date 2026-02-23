"""Detection helpers for Discord installations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import (
    DEB_DISCORD_NAMES,
    DISCORD_BINARIES,
    DISCORD_CACHE_DIRS,
    DISCORD_CONFIG_DIRS,
    FLATPAK_DISCORD_IDS,
    SNAP_DISCORD_NAMES,
)
from .models import (
    DiscordInstallation,
    DiscordVersion,
    InstallMethod,
    WebCordInstallation,
)

if TYPE_CHECKING:
    from .service import DiscordService

logger = logging.getLogger(__name__)

# Detection-specific timeouts (seconds)
TIMEOUT_PACKAGE_QUERY = 10  # dpkg, snap, flatpak queries
TIMEOUT_PROCESS_CHECK = 5  # pgrep checks


def detect_version(service: DiscordService, version: DiscordVersion) -> DiscordInstallation:
    """Detect a specific Discord version."""
    logger.debug("[DISCORD] Detecting %s...", version.value)
    installation = DiscordInstallation(
        version=version,
        method=InstallMethod.NOT_INSTALLED,
        config_dir=DISCORD_CONFIG_DIRS.get(version.value),
        cache_dir=DISCORD_CACHE_DIRS.get(version.value),
    )
    _check_deb(service, installation, version)
    if installation.method == InstallMethod.NOT_INSTALLED:
        _check_snap(service, installation, version)
    if installation.method == InstallMethod.NOT_INSTALLED:
        _check_flatpak(service, installation, version)
    if installation.method == InstallMethod.NOT_INSTALLED:
        _check_tarball(service, installation, version)
    installation.is_running = is_discord_running(service, version)
    _check_cache(installation)
    return installation


def detect_webcord(service: DiscordService) -> WebCordInstallation:
    """Detect WebCord installation."""
    webcord = WebCordInstallation()
    result = service._shell.run(
        ["flatpak", "info", "io.github.nickvision.webcord"],
        timeout=TIMEOUT_PACKAGE_QUERY,
    )
    if result.success:
        webcord.installed = True
        webcord.method = InstallMethod.FLATPAK
        webcord.path = "flatpak:io.github.nickvision.webcord"
    webcord_paths = [
        Path.home() / "Applications" / "WebCord.AppImage",
        Path.home() / ".local" / "bin" / "webcord",
        Path("/usr/bin/webcord"),
        Path("/usr/local/bin/webcord"),
    ]
    for p in webcord_paths:
        if p.exists():
            webcord.installed = True
            webcord.method = (
                InstallMethod.APPIMAGE if "AppImage" in str(p) else InstallMethod.UNKNOWN
            )
            webcord.path = str(p)
            break
    result = service._shell.run(["pgrep", "-f", "webcord"], timeout=TIMEOUT_PROCESS_CHECK)
    webcord.is_running = result.success and bool(result.stdout.strip())
    return webcord


def is_discord_running(service: DiscordService, version: DiscordVersion) -> bool:
    """Check if Discord version is running."""
    binaries = DISCORD_BINARIES.get(version.value, [])
    for binary in binaries:
        result = service._shell.run(["pgrep", "-f", binary], timeout=TIMEOUT_PROCESS_CHECK)
        if result.success and result.stdout.strip():
            return True
    return False


def find_binary(service: DiscordService, version: DiscordVersion) -> str | None:
    """Find Discord binary in PATH."""
    binaries = DISCORD_BINARIES.get(version.value, [])
    for binary in binaries:
        path = service._shell.get_command_path(binary)
        if path:
            return path
    return None


def get_dir_size_mb(path: Path) -> float:
    """Get directory size in MB."""
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024 * 1024)
    except Exception:
        return 0.0


def _check_deb(service: DiscordService, inst: DiscordInstallation, version: DiscordVersion) -> None:
    """Check for DEB installation."""
    deb_name = DEB_DISCORD_NAMES.get(version.value)
    if deb_name and _is_deb_installed(service, deb_name):
        inst.method = InstallMethod.DEB
        inst.path = f"/usr/share/{deb_name}"
        inst.binary_path = find_binary(service, version)


def _check_snap(
    service: DiscordService, inst: DiscordInstallation, version: DiscordVersion
) -> None:
    """Check for Snap installation."""
    snap_name = SNAP_DISCORD_NAMES.get(version.value)
    if snap_name and _is_snap_installed(service, version):
        inst.method = InstallMethod.SNAP
        inst.path = f"/snap/{snap_name}/current"
        inst.binary_path = f"/snap/bin/{snap_name}"


def _check_flatpak(
    service: DiscordService, inst: DiscordInstallation, version: DiscordVersion
) -> None:
    """Check for Flatpak installation."""
    flatpak_id = FLATPAK_DISCORD_IDS.get(version.value)
    if flatpak_id and _is_flatpak_installed(service, version):
        inst.method = InstallMethod.FLATPAK
        inst.path = f"flatpak:{flatpak_id}"
        inst.binary_path = f"flatpak run {flatpak_id}"


def _check_tarball(
    service: DiscordService, inst: DiscordInstallation, version: DiscordVersion
) -> None:
    """Check for tarball/manual installation."""
    binary = find_binary(service, version)
    if binary:
        inst.method = InstallMethod.TARBALL
        inst.binary_path = binary


def _check_cache(inst: DiscordInstallation) -> None:
    """Check cache presence and size."""
    if inst.cache_dir and inst.cache_dir.exists():
        inst.has_cache = True
        inst.cache_size_mb = get_dir_size_mb(inst.cache_dir)


def _is_deb_installed(service: DiscordService, package_name: str) -> bool:
    """Check if a DEB package is installed."""
    result = service._shell.run(["dpkg", "-s", package_name], timeout=TIMEOUT_PACKAGE_QUERY)
    return result.success and "Status: install ok installed" in result.stdout


def _is_snap_installed(service: DiscordService, version: DiscordVersion) -> bool:
    """Check if Discord is installed via Snap."""
    snap_name = SNAP_DISCORD_NAMES.get(version.value)
    if not snap_name:
        return False
    return service._shell.run(["snap", "list", snap_name], timeout=TIMEOUT_PACKAGE_QUERY).success


def _is_flatpak_installed(service: DiscordService, version: DiscordVersion) -> bool:
    """Check if Discord is installed via Flatpak."""
    flatpak_id = FLATPAK_DISCORD_IDS.get(version.value)
    if not flatpak_id:
        return False
    result = service._shell.run(
        ["flatpak", "info", flatpak_id],
        timeout=TIMEOUT_PACKAGE_QUERY,
    )
    return result.success
