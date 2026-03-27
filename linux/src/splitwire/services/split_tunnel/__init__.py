"""
SplitWire split tunnel service package.

Re-exports all public names so that existing imports like
``from splitwire.services.split_tunnel import SplitTunnelService``
continue to work.
"""

from .constants import BROWSER_APPS, CGPROXY_CONFIG_FILE, KNOWN_APPS
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
    "BROWSER_APPS",
    "CGPROXY_CONFIG_FILE",
    "KNOWN_APPS",
    "SplitTunnelConfig",
    "SplitTunnelService",
    "TunneledApp",
    "get_split_tunnel_service",
]
