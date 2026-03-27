"""
WireGuard VPN service package for SplitWire Linux.

Re-exports all public API from the original wireguard module
to maintain backward compatibility.
"""

from splitwire.core import get_shell
from splitwire.core.logger import get_logger

from .constants import (
    DEFAULT_EXCLUDED_NETWORKS,
    DISCORD_CLOUDFLARE_IPS,
    EXCLUDED_NETWORKS,
    FULL_TUNNEL_IPS,
    REFRESH_SERVICE_UNIT,
    REFRESH_TIMER_UNIT,
    ROBLOX_IPS,
    SPLIT_TUNNEL_IPS,
    SPLITWIRE_CONFIG_FILE,
    SPLITWIRE_CONFIG_NAME,
    WARP_ENDPOINTS,
    WGCF_ACCOUNT_FILE,
    WGCF_BINARY,
    WGCF_BINARY_NAME,
    WGCF_DIR,
    WGCF_GITHUB_API,
    WGCF_GITHUB_REPO,
    WGCF_PROFILE_FILE,
    WIREGUARD_CONFIG_DIR,
)
from .models import TunnelMode, WGCFAccount, WireGuardInterface
from .service import WireGuardService, get_wireguard_service

__all__ = [
    "DEFAULT_EXCLUDED_NETWORKS",
    "DISCORD_CLOUDFLARE_IPS",
    "EXCLUDED_NETWORKS",
    "FULL_TUNNEL_IPS",
    "REFRESH_SERVICE_UNIT",
    "REFRESH_TIMER_UNIT",
    "ROBLOX_IPS",
    "SPLITWIRE_CONFIG_FILE",
    "SPLITWIRE_CONFIG_NAME",
    "SPLIT_TUNNEL_IPS",
    "WARP_ENDPOINTS",
    "WGCF_ACCOUNT_FILE",
    "WGCF_BINARY",
    "WGCF_BINARY_NAME",
    "WGCF_DIR",
    "WGCF_GITHUB_API",
    "WGCF_GITHUB_REPO",
    "WGCF_PROFILE_FILE",
    "WIREGUARD_CONFIG_DIR",
    "TunnelMode",
    "WGCFAccount",
    "WireGuardInterface",
    "WireGuardService",
    "get_wireguard_service",
]
