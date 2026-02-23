"""
WireGuard configuration modification helpers.

Pure functions for modifying WireGuard config file content:
AllowedIPs, endpoint, DNS cleanup, and wg show parsing.
"""

import re

from .constants import (
    FULL_TUNNEL_IPS,
    SPLIT_TUNNEL_IPS,
    WARP_ENDPOINTS,
)
from .models import TunnelMode, WireGuardInterface


def modify_allowed_ips(
    config: str,
    tunnel_mode: str = TunnelMode.SPLIT,
    custom_ips: list[str] | None = None,
) -> str:
    """
    Modify AllowedIPs in config based on tunnel mode.

    Args:
        config: Original config content
        tunnel_mode: TunnelMode.SPLIT or TunnelMode.FULL
        custom_ips: Custom IP ranges to route

    Returns:
        Modified config
    """
    if custom_ips:
        ips_to_route = custom_ips
    elif tunnel_mode == TunnelMode.FULL:
        ips_to_route = FULL_TUNNEL_IPS
    else:
        ips_to_route = SPLIT_TUNNEL_IPS

    allowed_ips = ", ".join(ips_to_route)
    return re.sub(
        r"^AllowedIPs\s*=.*$",
        f"AllowedIPs = {allowed_ips}",
        config,
        flags=re.MULTILINE,
    )


def modify_endpoint(config: str, endpoint_type: str = "standard") -> str:
    """
    Modify the endpoint in WireGuard config.

    Args:
        config: Original config content
        endpoint_type: WARP endpoint type

    Returns:
        Modified config with new endpoint
    """
    endpoint = WARP_ENDPOINTS.get(endpoint_type, WARP_ENDPOINTS["standard"])

    config = re.sub(
        r"^Endpoint\s*=.*$",
        f"Endpoint = {endpoint}",
        config,
        flags=re.MULTILINE,
    )

    if "PersistentKeepalive" not in config:
        config = re.sub(
            r"^(Endpoint\s*=.*)$",
            r"\1\nPersistentKeepalive = 25",
            config,
            flags=re.MULTILINE,
        )

    return config


def clean_dns_config(config: str) -> str:
    """
    Remove DNS and IPv6 from WireGuard config.

    Removes DNS line so system keeps its original DNS, and
    strips IPv6 address to prevent routing issues.

    Args:
        config: Original config content

    Returns:
        Modified config without DNS
    """
    config = re.sub(r"^DNS\s*=.*\n?", "", config, flags=re.MULTILINE)
    return re.sub(
        r"^(Address\s*=\s*[0-9./]+),\s*[0-9a-fA-F:]+/\d+",
        r"\1",
        config,
        flags=re.MULTILINE,
    )


def build_config_content(
    raw_config: str,
    endpoint_type: str,
    tunnel_mode: str,
) -> str:
    """
    Apply all config modifications to raw WGCF profile.

    Args:
        raw_config: Raw config file content
        endpoint_type: WARP endpoint type
        tunnel_mode: TunnelMode.SPLIT or TunnelMode.FULL

    Returns:
        Fully modified config content
    """
    config = modify_allowed_ips(raw_config, tunnel_mode=tunnel_mode)
    config = modify_endpoint(config, endpoint_type)
    return clean_dns_config(config)


def parse_wg_show(output: str, interface_name: str) -> WireGuardInterface:
    """
    Parse output of 'wg show' command.

    Args:
        output: Command output
        interface_name: WireGuard interface name

    Returns:
        WireGuardInterface with parsed data
    """
    interface = WireGuardInterface(name=interface_name)

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            _apply_wg_show_field(interface, key.strip().lower(), value.strip())

    return interface


def _apply_wg_show_field(
    interface: WireGuardInterface,
    key: str,
    value: str,
) -> None:
    """
    Apply a parsed field from wg show output to interface.

    Args:
        interface: WireGuardInterface to update
        key: Lowercase field key
        value: Field value
    """
    if key == "public key":
        interface.public_key = value
    elif key == "private key":
        interface.private_key = value
    elif key == "listening port":
        interface.listen_port = int(value) if value.isdigit() else 0
    elif key == "endpoint":
        interface.endpoint = value
    elif key == "allowed ips":
        interface.allowed_ips = [ip.strip() for ip in value.split(",")]
    elif key == "latest handshake":
        interface.latest_handshake = value
    elif key == "transfer":
        _parse_transfer_stats(interface, value)


def _parse_transfer_stats(interface: WireGuardInterface, value: str) -> None:
    """
    Parse transfer stats from wg show output.

    Args:
        interface: WireGuardInterface to update
        value: Transfer stats string
    """
    match = re.search(
        r"([\d.]+)\s*\w+\s*received.*?([\d.]+)\s*\w+\s*sent",
        value,
    )
    if match:
        interface.transfer_rx = int(float(match.group(1)) * 1024 * 1024)
        interface.transfer_tx = int(float(match.group(2)) * 1024 * 1024)
