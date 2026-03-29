"""
SplitWire Linux

Privacy-focused network routing tool for Ubuntu/Linux.

This package provides:
- WireGuard VPN with split tunneling (via cgproxy)
- Zapret packet processing (nfqws/tpws)
- ByeDPI/ciadpi proxy
- DNS management with DoH support
"""

__version__ = "1.0.0"
__author__ = "SplitWire-Turkey Contributors"
__license__ = "MIT"

# Version info tuple
VERSION_INFO = (1, 0, 0)


def get_version() -> str:
    """Get the application version string.

    Returns:
        Semantic version string (e.g. "1.0.0").
    """
    return __version__


def get_version_info() -> tuple[int, int, int]:
    """Get the application version as a numeric tuple.

    Returns:
        Tuple of (major, minor, patch) integers.
    """
    return VERSION_INFO
