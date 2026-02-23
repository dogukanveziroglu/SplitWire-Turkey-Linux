"""
Constants for the systemd service manager.
"""

from pathlib import Path

# System paths
SYSTEM_UNIT_DIR = Path("/etc/systemd/system")
USER_UNIT_DIR = Path.home() / ".config/systemd/user"

# SplitWire service unit names
SPLITWIRE_SERVICES: dict[str, str] = {
    "wireguard": "splitwire-wg.service",
    "wireguard-refresh": "splitwire-wg-refresh.timer",
    "zapret": "splitwire-zapret.service",
    "byedpi": "splitwire-byedpi.service",
    "cgproxy": "splitwire-cgproxy.service",
}
