"""
System information display helpers.

Extracted from system.py to keep file sizes under 500 lines.
"""

import logging

from .system import SystemInfo

logger = logging.getLogger(__name__)


def print_system_info(info: SystemInfo) -> None:
    """Log system information in a formatted table.

    Args:
        info: SystemInfo to display.
    """
    logger.info("=" * 50)
    logger.info("SplitWire-Turkey System Information")
    logger.info("=" * 50)

    _log_os_info(info)
    _log_network_info(info)
    _log_service_info(info)

    logger.info("=" * 50)
    if info.is_compatible():
        logger.info("System is COMPATIBLE with SplitWire-Turkey")
    else:
        logger.warning("System has COMPATIBILITY ISSUES:")
        for issue in info.get_compatibility_issues():
            logger.warning("  - %s", issue)
    logger.info("=" * 50)


def _log_os_info(info: SystemInfo) -> None:
    """Log OS, kernel, arch, init, and Python info."""
    logger.info("OS: %s", info.ubuntu)
    logger.info("Kernel: %s", info.kernel_version)
    logger.info("Architecture: %s", info.architecture)
    logger.info("Init System: %s", info.init_system.value)
    logger.info("Python: %s", info.python_version)
    logger.info("Running as root: %s", "Yes" if info.is_root else "No")
    logger.info(
        "Can sudo: %s",
        "Yes" if info.can_sudo else "N/A" if info.is_root else "No",
    )


def _log_network_info(info: SystemInfo) -> None:
    """Log firewall, WireGuard, NFQUEUE, DNS, and cgroups info."""
    logger.info("Firewall: %s", info.firewall_backend.value)
    logger.info("  iptables: %s", "Yes" if info.iptables_available else "No")
    logger.info("  nftables: %s", "Yes" if info.nftables_available else "No")

    logger.info("WireGuard:")
    logger.info("  Module loaded: %s", "Yes" if info.wireguard_module_loaded else "No")
    logger.info("  Tools installed: %s", "Yes" if info.wireguard_tools_installed else "No")
    logger.info("  wg-quick: %s", "Yes" if info.wg_quick_available else "No")

    logger.info("NFQUEUE (Zapret):")
    logger.info("  Available: %s", "Yes" if info.nfqueue_available else "No")
    logger.info(
        "  libnetfilter-queue: %s",
        "Yes" if info.libnetfilter_queue_installed else "No",
    )


def _log_service_info(info: SystemInfo) -> None:
    """Log DNS and cgroups service state."""
    logger.info("DNS Manager: %s", info.dns_manager.value)
    logger.info("  resolvectl: %s", "Yes" if info.resolvectl_available else "No")

    logger.info("cgroups:")
    logger.info("  v2: %s", "Yes" if info.cgroups_v2 else "No")
    logger.info("  cgproxy: %s", "Yes" if info.cgproxy_available else "No")
