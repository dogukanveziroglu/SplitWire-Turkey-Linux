"""
WireGuard service constants.

Path definitions, IP ranges, and configuration constants
for the WireGuard VPN service.
"""

from pathlib import Path

# WireGuard configuration paths
WIREGUARD_CONFIG_DIR = Path("/etc/wireguard")
SPLITWIRE_CONFIG_NAME = "splitwire"
SPLITWIRE_CONFIG_FILE = WIREGUARD_CONFIG_DIR / f"{SPLITWIRE_CONFIG_NAME}.conf"

# WGCF binary and account paths
WGCF_BINARY_NAME = "wgcf"
WGCF_GITHUB_REPO = "ViRb3/wgcf"
WGCF_GITHUB_API = f"https://api.github.com/repos/{WGCF_GITHUB_REPO}/releases/latest"

# Local paths
LOCAL_DATA_DIR = Path.home() / ".local" / "share" / "splitwire"
WGCF_DIR = LOCAL_DATA_DIR / "wgcf"
WGCF_BINARY = WGCF_DIR / WGCF_BINARY_NAME
WGCF_ACCOUNT_FILE = WGCF_DIR / "wgcf-account.toml"
WGCF_PROFILE_FILE = WGCF_DIR / "wgcf-profile.conf"

# Default excluded networks (local/private)
DEFAULT_EXCLUDED_NETWORKS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "224.0.0.0/4",
    "255.255.255.255/32",
]

# Discord and Cloudflare service IP ranges for split tunneling
# These are the IPs that should be routed through VPN
# Note: WARP endpoint IPs (162.159.192-204.x) are NOT included
# to avoid routing loops
DISCORD_CLOUDFLARE_IPS = [
    # Discord service IPs (from DNS lookups)
    "162.159.128.0/24",
    "162.159.129.0/24",
    "162.159.130.0/24",
    "162.159.135.0/24",
    "162.159.136.0/24",
    "162.159.137.0/24",
    "162.159.138.0/24",
    # Cloudflare CDN (Discord assets, images, etc.)
    "104.16.0.0/12",
    "172.64.0.0/13",
    # Additional Cloudflare ranges
    "188.114.96.0/24",
    "188.114.97.0/24",
    # DNS servers - route DNS through VPN for alternative resolution
    # Cloudflare DNS
    "1.1.1.1/32",
    "1.0.0.1/32",
    # Google DNS (backup)
    "8.8.8.8/32",
    "8.8.4.4/32",
    # Quad9 DNS (backup)
    "9.9.9.9/32",
    "149.112.112.112/32",
]

# Roblox IP ranges
ROBLOX_IPS = [
    # Roblox main servers
    "128.116.0.0/16",  # Roblox primary range
    "128.116.13.0/24",  # roblox.com
    # Roblox CDN (Akamai, Fastly)
    "23.0.0.0/8",  # Akamai
    "151.101.0.0/16",  # Fastly
]

# Combined IPs for split tunnel mode
SPLIT_TUNNEL_IPS = DISCORD_CLOUDFLARE_IPS + ROBLOX_IPS

# Full tunnel mode - route everything except local networks
FULL_TUNNEL_IPS = ["0.0.0.0/0"]

# Local/private networks to exclude from VPN (for full tunnel mode)
EXCLUDED_NETWORKS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
]

# WARP endpoint configuration
# Using static IP to avoid DNS resolution dependency during VPN setup
# This prevents internet outage if ISP blocks DNS servers before
# VPN is established.
# engage.cloudflareclient.com resolves to 162.159.192.1
WARP_ENDPOINTS = {
    "standard": "162.159.192.1:500",
    "hostname": "engage.cloudflareclient.com:2408",
}

# Refresh timer systemd unit names
REFRESH_TIMER_UNIT = "splitwire-wg-refresh.timer"
REFRESH_SERVICE_UNIT = "splitwire-wg-refresh.service"
