"""
Constants for the proxy route service.
"""

from pathlib import Path

# Redsocks configuration
REDSOCKS_CONFIG_DIR = Path("/etc/redsocks")
REDSOCKS_CONFIG_FILE = REDSOCKS_CONFIG_DIR / "redsocks.conf"
REDSOCKS_SERVICE = "redsocks.service"

# Local configuration
LOCAL_CONFIG_DIR = Path.home() / ".config" / "splitwire"
PROXY_ROUTE_CONFIG_FILE = LOCAL_CONFIG_DIR / "proxy_route.json"

# iptables chain name
IPTABLES_CHAIN = "SPLITWIRE_PROXY"

# Default proxy settings
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 1080
