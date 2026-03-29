"""
SplitWire split tunnel service package.

Re-exports all public names so that existing imports like
``from splitwire.services.split_tunnel import SplitTunnelService``
continue to work.
"""

from splitwire.core import get_shell
from splitwire.core.logger import get_logger

from .constants import (
    APPS_CONFIG_FILE,
    BROWSER_APPS,
    CGPROXY_CONFIG_DIR,
    CGPROXY_CONFIG_FILE,
    KNOWN_APPS,
    LOCAL_CONFIG_DIR,
)
from .models import SplitTunnelConfig, TunneledApp
from .service import SplitTunnelService

# Singleton instance
_split_tunnel_service: SplitTunnelService | None = None


def get_split_tunnel_service() -> SplitTunnelService:
    """Get the global split tunnel service instance."""
    global _split_tunnel_service
    if _split_tunnel_service is None:
        _split_tunnel_service = SplitTunnelService()
    return _split_tunnel_service


__all__ = [
    "APPS_CONFIG_FILE",
    "BROWSER_APPS",
    "CGPROXY_CONFIG_DIR",
    "CGPROXY_CONFIG_FILE",
    "KNOWN_APPS",
    "LOCAL_CONFIG_DIR",
    "SplitTunnelConfig",
    "SplitTunnelService",
    "TunneledApp",
    "get_split_tunnel_service",
]
