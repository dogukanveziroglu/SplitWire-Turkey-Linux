"""Path, network, and binary constants for the Zapret service."""

from pathlib import Path

# Zapret installation paths
ZAPRET_INSTALL_DIR = Path("/opt/zapret")
ZAPRET_BIN_DIR = ZAPRET_INSTALL_DIR / "nfq"
ZAPRET_DOCS_DIR = ZAPRET_INSTALL_DIR / "docs"
ZAPRET_FILES_DIR = ZAPRET_INSTALL_DIR / "files"

# Binary paths
NFQWS_BINARY = ZAPRET_BIN_DIR / "nfqws"
TPWS_BINARY = ZAPRET_INSTALL_DIR / "tpws" / "tpws"

# Config directories
LOCAL_CONFIG_DIR = Path.home() / ".config" / "splitwire" / "zapret"
PRESETS_FILE = LOCAL_CONFIG_DIR / "presets.json"
BLACKLIST_FILE = LOCAL_CONFIG_DIR / "blacklist.txt"
CUSTOM_CONFIG_FILE = LOCAL_CONFIG_DIR / "custom.json"

# PID files for process tracking
PID_DIR = Path("/run/splitwire")
NFQWS_PID_FILE = PID_DIR / "nfqws.pid"
TPWS_PID_FILE = PID_DIR / "tpws.pid"

# GitHub repository
ZAPRET_REPO = "https://github.com/bol-van/zapret.git"
ZAPRET_REPO_BRANCH = "master"

# Default ports to filter
DEFAULT_HTTP_PORTS = [80]
DEFAULT_HTTPS_PORTS = [443]
DEFAULT_QUIC_PORTS = [443]

# iptables marks
NFQUEUE_NUM = 200
TPWS_PORT = 988

# Default excluded networks (don't route through zapret)
DEFAULT_EXCLUDED_NETWORKS = [
    "127.0.0.0/8",  # Loopback
    "10.0.0.0/8",  # Private
    "172.16.0.0/12",  # Private
    "192.168.0.0/16",  # Private
]
