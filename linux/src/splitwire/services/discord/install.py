"""Installation, reinstallation, and uninstallation helpers for Discord."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import (
    DEB_DISCORD_NAMES,
    DISCORD_DOWNLOAD_URLS,
    FLATPAK_DISCORD_IDS,
    SNAP_DISCORD_NAMES,
)
from .models import DiscordVersion, InstallMethod

if TYPE_CHECKING:
    from .service import DiscordService

logger = logging.getLogger(__name__)


def install_discord(
    service: DiscordService,
    version: DiscordVersion = DiscordVersion.STABLE,
    method: InstallMethod = InstallMethod.DEB,
) -> bool:
    """Install Discord via the specified method."""
    logger.info("Installing Discord %s via %s", version.value, method.value)
    if method == InstallMethod.DEB:
        return _install_deb(service, version)
    if method == InstallMethod.FLATPAK:
        return _install_flatpak(service, version)
    if method == InstallMethod.SNAP:
        return _install_snap(service, version)
    logger.error("Unsupported installation method: %s", method)
    return False


def _install_deb(service: DiscordService, version: DiscordVersion) -> bool:
    """Install Discord via DEB package."""
    url = DISCORD_DOWNLOAD_URLS.get(version.value)
    if not url:
        return False
    try:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            deb_path = Path(tmpdir) / f"discord-{version.value}.deb"
            logger.info("Downloading Discord %s...", version.value)
            result = service._shell.run(["wget", "-q", "-O", str(deb_path), url], timeout=120)
            if not result.success:
                logger.error("Download failed: %s", result.stderr)
                return False
            logger.info("Installing DEB package...")
            result = service._run_privileged(["dpkg", "-i", str(deb_path)], timeout=60)
            if not result.success:
                logger.info("Fixing dependencies...")
                service._run_privileged(["apt-get", "install", "-f", "-y"], timeout=120)
            logger.info("Discord %s installed successfully", version.value)
            return True
    except Exception as e:
        logger.exception("Installation failed: %s", e)
        return False


def _install_flatpak(service: DiscordService, version: DiscordVersion) -> bool:
    """Install Discord via Flatpak."""
    flatpak_id = FLATPAK_DISCORD_IDS.get(version.value)
    if not flatpak_id:
        return False
    if not service._shell.command_exists("flatpak"):
        logger.error("Flatpak is not installed")
        return False
    _ensure_flathub(service)
    result = service._shell.run(["flatpak", "install", "-y", "flathub", flatpak_id], timeout=300)
    if result.success:
        logger.info("Discord %s installed via Flatpak", version.value)
    else:
        logger.error("Flatpak install failed: %s", result.stderr)
    return result.success


def _install_snap(service: DiscordService, version: DiscordVersion) -> bool:
    """Install Discord via Snap."""
    snap_name = SNAP_DISCORD_NAMES.get(version.value)
    if not snap_name:
        return False
    if not service._shell.command_exists("snap"):
        logger.error("Snap is not installed")
        return False
    result = service._run_privileged(["snap", "install", snap_name], timeout=300)
    if result.success:
        logger.info("Discord %s installed via Snap", version.value)
    else:
        logger.error("Snap install failed: %s", result.stderr)
    return result.success


def _ensure_flathub(service: DiscordService) -> None:
    """Add Flathub remote if not present."""
    service._shell.run(
        [
            "flatpak",
            "remote-add",
            "--if-not-exists",
            "flathub",
            "https://flathub.org/repo/flathub.flatpakrepo",
        ],
        timeout=30,
    )


def reinstall_deb(service: DiscordService, version: DiscordVersion) -> bool:
    """Reinstall Discord DEB package."""
    deb_name = DEB_DISCORD_NAMES.get(version.value)
    if not deb_name:
        return False
    service._run_privileged(["dpkg", "-r", deb_name], timeout=30)
    return _install_deb(service, version)


def reinstall_flatpak(service: DiscordService, version: DiscordVersion) -> bool:
    """Reinstall Discord Flatpak."""
    flatpak_id = FLATPAK_DISCORD_IDS.get(version.value)
    if not flatpak_id:
        return False
    service._shell.run(["flatpak", "uninstall", "-y", flatpak_id], timeout=60)
    return _install_flatpak(service, version)


def reinstall_snap(service: DiscordService, version: DiscordVersion) -> bool:
    """Reinstall Discord Snap."""
    snap_name = SNAP_DISCORD_NAMES.get(version.value)
    if not snap_name:
        return False
    service._run_privileged(["snap", "remove", snap_name], timeout=60)
    return _install_snap(service, version)


def uninstall_discord(service: DiscordService, version: DiscordVersion) -> bool:
    """Uninstall a specific Discord version."""
    installation = service._detect_version(version)
    if installation.method == InstallMethod.NOT_INSTALLED:
        logger.info("Discord %s is not installed", version.value)
        return True

    logger.info("Uninstalling Discord %s", version.value)
    if installation.is_running:
        service._kill_discord_version(version)

    if installation.method == InstallMethod.DEB:
        deb_name = DEB_DISCORD_NAMES.get(version.value)
        result = service._run_privileged(["dpkg", "-r", deb_name], timeout=30)
    elif installation.method == InstallMethod.FLATPAK:
        flatpak_id = FLATPAK_DISCORD_IDS.get(version.value)
        result = service._shell.run(["flatpak", "uninstall", "-y", flatpak_id], timeout=60)
    elif installation.method == InstallMethod.SNAP:
        snap_name = SNAP_DISCORD_NAMES.get(version.value)
        result = service._run_privileged(["snap", "remove", snap_name], timeout=60)
    else:
        logger.warning("Cannot uninstall %s installation", installation.method.value)
        return False
    return result.success


def install_webcord(service: DiscordService, method: InstallMethod) -> bool:
    """Install WebCord via specified method."""
    logger.info("Installing WebCord via %s", method.value)
    if method != InstallMethod.FLATPAK:
        logger.error("Unsupported WebCord installation method: %s", method)
        return False
    if not service._shell.command_exists("flatpak"):
        logger.error("Flatpak is not installed")
        return False
    _ensure_flathub(service)
    webcord_ids = [
        "io.github.nickvision.webcord",
        "io.github.nickvision.Webcord",
        "org.nickvision.webcord",
    ]
    for flatpak_id in webcord_ids:
        result = service._shell.run(
            ["flatpak", "install", "-y", "flathub", flatpak_id], timeout=300
        )
        if result.success:
            logger.info("WebCord installed via Flatpak")
            return True
    logger.error("Failed to install WebCord via Flatpak")
    return False


def uninstall_webcord(service: DiscordService) -> bool:
    """Uninstall WebCord."""
    webcord = service._detect_webcord()
    if not webcord.installed:
        return True
    if webcord.method == InstallMethod.FLATPAK:
        result = service._shell.run(
            ["flatpak", "uninstall", "-y", "io.github.nickvision.webcord"], timeout=60
        )
        return result.success
    if webcord.method == InstallMethod.APPIMAGE and webcord.path:
        try:
            Path(webcord.path).unlink()
            return True
        except Exception as e:
            logger.error("Failed to remove WebCord: %s", e)
            return False
    return False


def launch_discord(service: DiscordService, version: DiscordVersion) -> bool:
    """Launch Discord."""
    installation = service._detect_version(version)
    if installation.method == InstallMethod.NOT_INSTALLED:
        logger.error("Discord %s is not installed", version.value)
        return False
    if installation.is_running:
        logger.info("Discord %s is already running", version.value)
        return True
    logger.info("Launching Discord %s", version.value)
    if installation.method == InstallMethod.FLATPAK:
        flatpak_id = FLATPAK_DISCORD_IDS.get(version.value)
        cmd = ["flatpak", "run", flatpak_id]
    elif installation.binary_path:
        cmd = [installation.binary_path]
    else:
        logger.error("Cannot find Discord binary")
        return False
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        logger.error("Failed to launch Discord: %s", e)
        return False


def launch_webcord(service: DiscordService) -> bool:
    """Launch WebCord."""
    webcord = service._detect_webcord()
    if not webcord.installed:
        logger.error("WebCord is not installed")
        return False
    if webcord.is_running:
        logger.info("WebCord is already running")
        return True
    try:
        if webcord.method == InstallMethod.FLATPAK:
            subprocess.Popen(
                ["flatpak", "run", "io.github.nickvision.webcord"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif webcord.path:
            subprocess.Popen(
                [webcord.path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except Exception as e:
        logger.error("Failed to launch WebCord: %s", e)
        return False
