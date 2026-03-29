"""
Service modules for SplitWire Linux.

This package contains service managers for:
- WireGuard VPN with WGCF/WARP integration
- Split tunneling (app-based routing)
- Zapret packet processing
- Blockcheck scanner
- ByeDPI proxy
- Proxy routing
- DNS management with DoH support
- Discord repair and alternative clients
- systemd service management

Uses PEP 562 lazy imports to avoid loading all service modules
at package import time.
"""

from __future__ import annotations

import importlib

# Base types are always needed (lightweight, no external deps)
from .base import (
    BaseService,
    ServiceInfo,
    ServiceStatus,
    ServiceType,
    SystemdService,
)

# Maps attribute name -> (submodule, attribute_in_submodule)
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "BlockcheckResult": (".blockcheck", "BlockcheckResult"),
    "BlockcheckService": (".blockcheck", "BlockcheckService"),
    "BROWSER_APPS": (".split_tunnel", "BROWSER_APPS"),
    "BYEDPI_PRESETS": (".byedpi", "DEFAULT_PRESETS"),
    "ByeDPIConfig": (".byedpi", "ByeDPIConfig"),
    "ByeDPIMode": (".byedpi", "ByeDPIMode"),
    "ByeDPIPreset": (".byedpi", "ByeDPIPreset"),
    "ByeDPIService": (".byedpi", "ByeDPIService"),
    "DEFAULT_PRESETS": (".zapret", "DEFAULT_PRESETS"),
    "DNS_PRESETS": (".dns", "DNS_PRESETS"),
    "DNSBackup": (".dns", "DNSBackup"),
    "DNSConfig": (".dns", "DNSConfig"),
    "DNSManager": (".dns", "DNSManager"),
    "DNSServer": (".dns", "DNSServer"),
    "DNSService": (".dns", "DNSService"),
    "DiscordConfig": (".discord", "DiscordConfig"),
    "DiscordInstallation": (".discord", "DiscordInstallation"),
    "DiscordService": (".discord", "DiscordService"),
    "DiscordVersion": (".discord", "DiscordVersion"),
    "DoHMode": (".dns", "DoHMode"),
    "InstallMethod": (".discord", "InstallMethod"),
    "JournalEntry": (".systemd", "JournalEntry"),
    "KNOWN_APPS": (".split_tunnel", "KNOWN_APPS"),
    "ProxiedApp": (".proxy_route", "ProxiedApp"),
    "ProxyMethod": (".proxy_route", "ProxyMethod"),
    "ProxyRouteConfig": (".proxy_route", "ProxyRouteConfig"),
    "ProxyRouteService": (".proxy_route", "ProxyRouteService"),
    "RepairResult": (".discord", "RepairResult"),
    "SPLITWIRE_CONFIG_FILE": (".wireguard", "SPLITWIRE_CONFIG_FILE"),
    "ScanMode": (".blockcheck", "ScanMode"),
    "ScanProgress": (".blockcheck", "ScanProgress"),
    "ScanStatus": (".blockcheck", "ScanStatus"),
    "SplitTunnelConfig": (".split_tunnel", "SplitTunnelConfig"),
    "SplitTunnelService": (".split_tunnel", "SplitTunnelService"),
    "SystemdActiveState": (".systemd", "SystemdActiveState"),
    "SystemdEnabledState": (".systemd", "SystemdEnabledState"),
    "SystemdManager": (".systemd", "SystemdManager"),
    "SystemdUnitStatus": (".systemd", "SystemdUnitStatus"),
    "SystemdUnitType": (".systemd", "SystemdUnitType"),
    "TunneledApp": (".split_tunnel", "TunneledApp"),
    "WGCFAccount": (".wireguard", "WGCFAccount"),
    "WIREGUARD_CONFIG_DIR": (".wireguard", "WIREGUARD_CONFIG_DIR"),
    "WebCordInstallation": (".discord", "WebCordInstallation"),
    "WireGuardInterface": (".wireguard", "WireGuardInterface"),
    "WireGuardService": (".wireguard", "WireGuardService"),
    "ZapretConfig": (".zapret", "ZapretConfig"),
    "ZapretMode": (".zapret", "ZapretMode"),
    "ZapretPreset": (".zapret", "ZapretPreset"),
    "ZapretService": (".zapret", "ZapretService"),
    "get_blockcheck_service": (".blockcheck", "get_blockcheck_service"),
    "get_byedpi_service": (".byedpi", "get_byedpi_service"),
    "get_discord_service": (".discord", "get_discord_service"),
    "get_dns_service": (".dns", "get_dns_service"),
    "get_proxy_route_service": (".proxy_route", "get_proxy_route_service"),
    "get_split_tunnel_service": (".split_tunnel", "get_split_tunnel_service"),
    "get_systemd_manager": (".systemd", "get_systemd_manager"),
    "get_wireguard_service": (".wireguard", "get_wireguard_service"),
    "get_zapret_service": (".zapret", "get_zapret_service"),
}

__all__ = [
    "BROWSER_APPS",
    "BYEDPI_PRESETS",
    "DEFAULT_PRESETS",
    "DNS_PRESETS",
    "KNOWN_APPS",
    "SPLITWIRE_CONFIG_FILE",
    "WIREGUARD_CONFIG_DIR",
    "BaseService",
    "BlockcheckResult",
    "BlockcheckService",
    "ByeDPIConfig",
    "ByeDPIMode",
    "ByeDPIPreset",
    "ByeDPIService",
    "DNSBackup",
    "DNSConfig",
    "DNSManager",
    "DNSServer",
    "DNSService",
    "DiscordConfig",
    "DiscordInstallation",
    "DiscordService",
    "DiscordVersion",
    "DoHMode",
    "InstallMethod",
    "JournalEntry",
    "ProxiedApp",
    "ProxyMethod",
    "ProxyRouteConfig",
    "ProxyRouteService",
    "RepairResult",
    "ScanMode",
    "ScanProgress",
    "ScanStatus",
    "ServiceInfo",
    "ServiceStatus",
    "ServiceType",
    "SplitTunnelConfig",
    "SplitTunnelService",
    "SystemdActiveState",
    "SystemdEnabledState",
    "SystemdManager",
    "SystemdService",
    "SystemdUnitStatus",
    "SystemdUnitType",
    "TunneledApp",
    "WGCFAccount",
    "WebCordInstallation",
    "WireGuardInterface",
    "WireGuardService",
    "ZapretConfig",
    "ZapretMode",
    "ZapretPreset",
    "ZapretService",
    "get_blockcheck_service",
    "get_byedpi_service",
    "get_discord_service",
    "get_dns_service",
    "get_proxy_route_service",
    "get_split_tunnel_service",
    "get_systemd_manager",
    "get_wireguard_service",
    "get_zapret_service",
]


def __getattr__(name: str) -> object:
    """Lazily import service attributes on first access."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path, __package__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
