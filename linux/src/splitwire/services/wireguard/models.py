"""
WireGuard service data models.

Dataclasses and type definitions for WireGuard VPN service.
"""

from dataclasses import dataclass, field


class TunnelMode:
    """VPN tunnel routing modes."""

    SPLIT = "split"  # Only route specific IPs through VPN (faster, less data)
    FULL = "full"  # Route ALL traffic through VPN (routes all traffic)


@dataclass
class WireGuardInterface:
    """Information about a WireGuard interface."""

    name: str
    public_key: str = ""
    private_key: str = ""
    address: str = ""
    listen_port: int = 0
    endpoint: str = ""
    latest_handshake: str = ""
    transfer_rx: int = 0
    transfer_tx: int = 0
    allowed_ips: list[str] = field(default_factory=list)


@dataclass
class WGCFAccount:
    """WGCF account information."""

    device_id: str = ""
    access_token: str = ""
    private_key: str = ""
    license_key: str = ""
    created: str = ""
