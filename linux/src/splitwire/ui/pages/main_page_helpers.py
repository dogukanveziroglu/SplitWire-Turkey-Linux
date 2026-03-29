"""
Helper functions for the WireGuard main page.

Extracts VPN operation logic and async result handling
to keep main_page.py under 500 lines.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from splitwire.core import get_config, get_text, save_config

if TYPE_CHECKING:
    from splitwire.services.dns.service import DNSManager
    from splitwire.services.split_tunnel.service import SplitTunnelService
    from splitwire.services.wireguard import TunnelMode
    from splitwire.services.wireguard.service import WireGuardService

logger = logging.getLogger(__name__)


def do_wireguard_setup(
    wg_service: WireGuardService,
    dns_service: DNSManager,
    tunnel_mode: TunnelMode | None = None,
) -> tuple[bool, str | None]:
    """Run the WireGuard setup sequence (register, config, start, DNS).

    Returns:
        Tuple of (success, error_message_or_None).
    """
    try:
        return _run_wireguard_steps(wg_service, dns_service, tunnel_mode)
    except Exception as e:
        logger.exception("WireGuard setup failed: %s", e)
        return (False, str(e))


def _run_wireguard_steps(
    wg_service: WireGuardService,
    dns_service: DNSManager,
    tunnel_mode: TunnelMode | None,
) -> tuple[bool, str | None]:
    """Execute individual WireGuard setup steps."""
    if not wg_service.register_wgcf():
        return (False, get_text("errors", "wgcf_register_failed"))

    kwargs = {}
    if tunnel_mode is not None:
        kwargs["tunnel_mode"] = tunnel_mode

    if not wg_service.generate_config(**kwargs):
        return (False, get_text("errors", "config_generate_failed"))

    # CRITICAL: Start WireGuard BEFORE changing DNS
    # DNS change before VPN can cause endpoint resolution failure
    if not wg_service.start():
        return (False, get_text("errors", "service_start_failed"))

    time.sleep(1)
    if not wg_service.test_connection():
        logger.warning("[UI:Main] VPN connection test failed, continuing anyway...")

    # NOW safe to change DNS (VPN is active)
    dns_service.install(preset="cloudflare")
    return (True, None)


def do_disconnect(
    wg_service: WireGuardService,
    dns_service: DNSManager,
) -> tuple[bool, str | None]:
    """
    Disconnect VPN and restore DNS.

    Returns:
        Tuple of (success, error_message_or_None)
    """
    try:
        wg_service.stop()
        dns_service.remove()
        return (True, None)
    except Exception as e:
        logger.exception("Disconnect failed: %s", e)
        return (False, str(e))


def do_remove_services(
    wg_service: WireGuardService,
    st_service: SplitTunnelService,
    dns_service: DNSManager,
) -> tuple[bool, str | None]:
    """
    Remove all WireGuard-related services.

    Returns:
        Tuple of (success, error_message_or_None)
    """
    try:
        wg_service.stop()
        wg_service.remove()
        st_service.remove()
        dns_service.remove()
        return (True, None)
    except Exception as e:
        logger.exception("Service removal failed: %s", e)
        return (False, str(e))


def save_page_settings(
    enabled_apps: dict[str, bool],
    custom_apps: list[str],
    switch_browser: object,
    switch_refresh: object,
    switch_full_tunnel: object,
) -> None:
    """Save main page settings to config file."""
    try:
        config = get_config()
        config.wireguard.enabled_known_apps = enabled_apps.copy()
        config.wireguard.custom_apps = custom_apps.copy()
        config.wireguard.include_browsers = switch_browser.get_active()
        config.wireguard.refresh_timer_enabled = switch_refresh.get_active()
        config.wireguard.full_tunnel_mode = switch_full_tunnel.get_active()
        save_config()
        logger.debug("Settings saved")
    except Exception as e:
        logger.error("Failed to save settings: %s", e)


def load_page_settings(
    enabled_apps: dict[str, bool],
    custom_apps_ref: list[str],
    switch_browser: object,
    switch_refresh: object,
    switch_full_tunnel: object,
) -> list[str]:
    """
    Load main page settings from config file.

    Args:
        enabled_apps: Dict to update with loaded app selections
        custom_apps_ref: Mutable list reference for custom apps
        switch_browser: Browser tunneling switch widget
        switch_refresh: Refresh timer switch widget
        switch_full_tunnel: Full tunnel switch widget

    Returns:
        Updated custom apps list (or original if load fails)
    """
    try:
        config = get_config()
        if config.wireguard.enabled_known_apps:
            enabled_apps.update(config.wireguard.enabled_known_apps)
        result_apps = custom_apps_ref
        if config.wireguard.custom_apps:
            result_apps = list(config.wireguard.custom_apps)
        switch_browser.set_active(config.wireguard.include_browsers)
        switch_refresh.set_active(config.wireguard.refresh_timer_enabled)
        switch_full_tunnel.set_active(config.wireguard.full_tunnel_mode)
        logger.debug("Settings loaded")
        return result_apps
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
        return custom_apps_ref
