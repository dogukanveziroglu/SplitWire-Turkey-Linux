"""
Service modules for SplitWire Linux.

This package contains service managers for:
- WireGuard VPN with WGCF/WARP integration (Phase 2)
- Split tunneling (app-based routing) (Phase 2)
- Zapret packet processing (Phase 3)
- Blockcheck scanner (Phase 3)
- ByeDPI proxy (Phase 4)
- Proxy routing (Phase 4)
- DNS management with DoH support (Phase 5)
- Discord repair and alternative clients (Phase 6)
- systemd service management (Phase 8)
"""

from .base import (
    BaseService,
    ServiceInfo,
    ServiceStatus,
    ServiceType,
    SystemdService,
)
from .blockcheck import (
    BlockcheckResult,
    BlockcheckService,
    ScanMode,
    ScanProgress,
    ScanStatus,
    get_blockcheck_service,
)
from .byedpi import (
    DEFAULT_PRESETS as BYEDPI_PRESETS,
)
from .byedpi import (
    ByeDPIConfig,
    ByeDPIMode,
    ByeDPIPreset,
    ByeDPIService,
    get_byedpi_service,
)
from .discord import (
    DiscordConfig,
    DiscordInstallation,
    DiscordService,
    DiscordVersion,
    InstallMethod,
    RepairResult,
    WebCordInstallation,
    get_discord_service,
)
from .dns import (
    DNS_PRESETS,
    DNSBackup,
    DNSConfig,
    DNSManager,
    DNSServer,
    DNSService,
    DoHMode,
    get_dns_service,
)
from .proxy_route import (
    ProxiedApp,
    ProxyMethod,
    ProxyRouteConfig,
    ProxyRouteService,
    get_proxy_route_service,
)
from .split_tunnel import (
    BROWSER_APPS,
    KNOWN_APPS,
    SplitTunnelConfig,
    SplitTunnelService,
    TunneledApp,
    get_split_tunnel_service,
)
from .systemd import (
    JournalEntry,
    SystemdActiveState,
    SystemdEnabledState,
    SystemdManager,
    SystemdUnitStatus,
    SystemdUnitType,
    get_systemd_manager,
)
from .wireguard import (
    SPLITWIRE_CONFIG_FILE,
    WIREGUARD_CONFIG_DIR,
    WGCFAccount,
    WireGuardInterface,
    WireGuardService,
    get_wireguard_service,
)
from .zapret import (
    DEFAULT_PRESETS,
    ZapretConfig,
    ZapretMode,
    ZapretPreset,
    ZapretService,
    get_zapret_service,
)

__all__ = [
    # base
    "BaseService",
    "SystemdService",
    "ServiceStatus",
    "ServiceType",
    "ServiceInfo",
    # wireguard
    "WireGuardService",
    "WireGuardInterface",
    "WGCFAccount",
    "get_wireguard_service",
    "WIREGUARD_CONFIG_DIR",
    "SPLITWIRE_CONFIG_FILE",
    # split_tunnel
    "SplitTunnelService",
    "SplitTunnelConfig",
    "TunneledApp",
    "get_split_tunnel_service",
    "KNOWN_APPS",
    "BROWSER_APPS",
    # zapret
    "ZapretService",
    "ZapretConfig",
    "ZapretPreset",
    "ZapretMode",
    "get_zapret_service",
    "DEFAULT_PRESETS",
    # blockcheck
    "BlockcheckService",
    "BlockcheckResult",
    "ScanMode",
    "ScanStatus",
    "ScanProgress",
    "get_blockcheck_service",
    # byedpi
    "ByeDPIService",
    "ByeDPIConfig",
    "ByeDPIPreset",
    "ByeDPIMode",
    "get_byedpi_service",
    "BYEDPI_PRESETS",
    # proxy_route
    "ProxyRouteService",
    "ProxyRouteConfig",
    "ProxiedApp",
    "ProxyMethod",
    "get_proxy_route_service",
    # dns
    "DNSService",
    "DNSConfig",
    "DNSServer",
    "DNSBackup",
    "DNSManager",
    "DoHMode",
    "DNS_PRESETS",
    "get_dns_service",
    # discord
    "DiscordService",
    "DiscordConfig",
    "DiscordInstallation",
    "WebCordInstallation",
    "DiscordVersion",
    "InstallMethod",
    "RepairResult",
    "get_discord_service",
    # systemd
    "SystemdManager",
    "SystemdUnitType",
    "SystemdActiveState",
    "SystemdEnabledState",
    "SystemdUnitStatus",
    "JournalEntry",
    "get_systemd_manager",
]
