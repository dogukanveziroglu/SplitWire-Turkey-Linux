"""Installation and build helpers for the Zapret service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .constants import (
    BLACKLIST_FILE,
    LOCAL_CONFIG_DIR,
    NFQWS_BINARY,
    TPWS_BINARY,
    ZAPRET_INSTALL_DIR,
    ZAPRET_REPO,
    ZAPRET_REPO_BRANCH,
)

if TYPE_CHECKING:
    from .service import ZapretService

# Zapret install-specific timeouts (seconds)
TIMEOUT_INSTALL = 300  # dependency install, git clone, make build
TIMEOUT_APT_UPDATE = 120
TIMEOUT_FILE_OPERATION = 30  # mkdir, tee, cp


def install_dependencies(service: ZapretService) -> bool:
    """Install required system dependencies."""
    service._logger.info("Installing Zapret dependencies...")
    cmd = _build_install_cmd(service)
    if cmd is None:
        return False
    result = service._run_privileged(cmd, timeout=TIMEOUT_INSTALL)
    if not result.success:
        service._logger.error("Failed to install packages: %s", result.stderr)
        return False
    return True


def _build_install_cmd(service: ZapretService) -> list[str] | None:
    """Build the package-install command for the current distro."""
    if service._shell.command_exists("apt-get"):
        service._run_privileged(["apt-get", "update"], timeout=TIMEOUT_APT_UPDATE)
        return [
            "apt-get",
            "install",
            "-y",
            "git",
            "make",
            "gcc",
            "libnetfilter-queue-dev",
            "libcap-dev",
            "libnfnetlink-dev",
            "zlib1g-dev",
            "iptables",
        ]
    if service._shell.command_exists("dnf"):
        return [
            "dnf",
            "install",
            "-y",
            "git",
            "make",
            "gcc",
            "libnetfilter_queue-devel",
            "libcap-devel",
            "libnfnetlink-devel",
            "zlib-devel",
            "iptables",
        ]
    if service._shell.command_exists("pacman"):
        return [
            "pacman",
            "-S",
            "--noconfirm",
            "git",
            "make",
            "gcc",
            "libnetfilter_queue",
            "libcap",
            "libnfnetlink",
            "zlib",
            "iptables",
        ]
    service._logger.error("Unsupported package manager")
    return None


def clone_zapret(service: ZapretService) -> bool:
    """Clone or update zapret repository."""
    service._logger.info("Cloning Zapret repository...")
    service._run_privileged(
        ["mkdir", "-p", str(ZAPRET_INSTALL_DIR.parent)],
        timeout=TIMEOUT_FILE_OPERATION,
    )

    if ZAPRET_INSTALL_DIR.exists():
        service._logger.info("Updating existing Zapret installation...")
        result = service._run_privileged(
            ["git", "-C", str(ZAPRET_INSTALL_DIR), "pull"], timeout=TIMEOUT_INSTALL
        )
    else:
        result = service._run_privileged(
            [
                "git",
                "clone",
                "--depth=1",
                "-b",
                ZAPRET_REPO_BRANCH,
                ZAPRET_REPO,
                str(ZAPRET_INSTALL_DIR),
            ],
            timeout=TIMEOUT_INSTALL,
        )

    if not result.success:
        service._logger.error("Git operation failed: %s", result.stderr)
        return False
    return True


def build_zapret(service: ZapretService) -> bool:
    """Build zapret binaries."""
    service._logger.info("Building Zapret binaries...")
    nfq_dir = ZAPRET_INSTALL_DIR / "nfq"
    tpws_dir = ZAPRET_INSTALL_DIR / "tpws"

    if nfq_dir.exists():
        result = service._run_privileged(["make", "-C", str(nfq_dir)], timeout=TIMEOUT_INSTALL)
        if not result.success:
            service._logger.warning("nfqws build warning: %s", result.stderr)

    if tpws_dir.exists():
        result = service._run_privileged(["make", "-C", str(tpws_dir)], timeout=TIMEOUT_INSTALL)
        if not result.success:
            service._logger.warning("tpws build warning: %s", result.stderr)

    if not NFQWS_BINARY.exists() and not TPWS_BINARY.exists():
        service._logger.error("No binaries were built")
        return False

    service._logger.info("Zapret binaries built successfully")
    return True


def setup_config_dirs(service: ZapretService) -> None:
    """Create configuration directories and default blacklist."""
    LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not BLACKLIST_FILE.exists():
        default_domains = [
            "discord.com",
            "discord.gg",
            "discordapp.com",
            "discord.media",
            "discordcdn.com",
            "gateway.discord.gg",
        ]
        service.set_blacklist(default_domains)


def install_systemd_service(service: ZapretService) -> bool:
    """Install systemd service file for Zapret."""
    service_content = (
        "[Unit]\n"
        "Description=SplitWire Zapret Packet Processing\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=forking\n"
        'ExecStart=/usr/bin/python3 -c "'
        "import splitwire.services.zapret as m;"
        'm.get_zapret_service().start()"\n'
        'ExecStop=/usr/bin/python3 -c "'
        "import splitwire.services.zapret as m;"
        'm.get_zapret_service().stop()"\n'
        "RemainAfterExit=yes\n"
        "Restart=on-failure\n"
        "RestartSec=10\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    svc = Path("/etc/systemd/system/splitwire-zapret.service")
    result = service._run_privileged(
        ["tee", str(svc)], input_data=service_content, timeout=TIMEOUT_FILE_OPERATION
    )
    if result.success:
        service._run_privileged(["systemctl", "daemon-reload"])
    return result.success


def remove_systemd_service(service: ZapretService) -> bool:
    """Remove systemd service file for Zapret."""
    svc = Path("/etc/systemd/system/splitwire-zapret.service")
    service._run_privileged(["systemctl", "disable", "splitwire-zapret.service"])
    service._run_privileged(["systemctl", "stop", "splitwire-zapret.service"])
    if svc.exists():
        result = service._run_privileged(["rm", "-f", str(svc)])
        service._run_privileged(["systemctl", "daemon-reload"])
        return result.success
    return True
