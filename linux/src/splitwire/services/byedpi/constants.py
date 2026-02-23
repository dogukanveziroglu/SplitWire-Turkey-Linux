"""
ByeDPI service constants.

Path definitions and configuration constants for the ByeDPI proxy service.
"""

from pathlib import Path

# Installation paths
BYEDPI_INSTALL_DIR = Path("/opt/byedpi")
BYEDPI_BINARY = BYEDPI_INSTALL_DIR / "ciadpi"
BYEDPI_CONFIG_DIR = BYEDPI_INSTALL_DIR / "config"

# Local config
LOCAL_CONFIG_DIR = Path.home() / ".config" / "splitwire" / "byedpi"
PRESETS_FILE = LOCAL_CONFIG_DIR / "presets.json"
CONFIG_FILE = LOCAL_CONFIG_DIR / "config.json"

# PID file for process tracking
PID_DIR = Path("/run/splitwire")
BYEDPI_PID_FILE = PID_DIR / "ciadpi.pid"

# GitHub releases
CIADPI_REPO = "hufrea/byedpi"
CIADPI_RELEASE_URL = f"https://api.github.com/repos/{CIADPI_REPO}/releases/latest"

# Default proxy settings
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 1080

# systemd service name
SYSTEMD_SERVICE = "splitwire-byedpi.service"
